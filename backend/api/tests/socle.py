"""Socle commun : vrais jetons RS256, JWKS local, réseau sortant coupé.

* ``PyJWKClient.fetch_data`` → clé publique locale : signature, expiration,
  ``azp``, groupes et email sont vérifiés pour de vrai par
  ``KeycloakJWTAuthentication``.
* ``HTTPAdapter.send`` → ``ConnectionError`` : aucun appel réseau ne part du
  conteneur de test (Open-Meteo, API Adresse, TTN). C'est aussi le comportement
  « fournisseur météo injoignable » de l'app ; les tests qui veulent des données
  météo/TTN patchent la fonction du module concerné.
"""
from __future__ import annotations

import json
import time
from unittest import mock

import jwt
import requests
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.authentication import KeycloakJWTAuthentication
from api.models import Sensor, SensorUserAccess, Webhook, WebhookUserAccess

CLIENT = 'analyse-lora'
REQUIS = 'developers,amis,famille'
KID = 'cle-locale-de-test'

_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
AUTRE_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_ABSENT = object()


def _jwks() -> dict:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_RSA.public_key())
    jwk = json.loads(jwk) if isinstance(jwk, str) else dict(jwk)
    jwk.update({'kid': KID, 'use': 'sig', 'alg': 'RS256'})
    return {'keys': [jwk]}


def jeton(email=_ABSENT, groups=_ABSENT, *, azp=CLIENT, exp=300, cle=None, kid=KID, **claims) -> str:
    payload = {'azp': azp, 'exp': int(time.time()) + exp, 'iat': int(time.time()) - 1}
    if email is _ABSENT:
        email = 'dev@exemple.org'
    if email is not None:
        payload['email'] = email
        payload['preferred_username'] = email.split('@')[0]
    if groups is _ABSENT:
        groups = ['developers']
    if groups is not None:
        payload['groups'] = groups
    payload.update(claims)
    return jwt.encode(payload, cle or _RSA, algorithm='RS256', headers={'kid': kid})


def client_de(email: str, groups) -> APIClient:
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {jeton(email, groups)}')
    return c


@override_settings(
    KEYCLOAK_CLIENT_ID=CLIENT,
    KEYCLOAK_REQUIRED_GROUPS=REQUIS,
    KEYCLOAK_ISSUER_URI='http://keycloak.test/realms/ssolab',
)
class SocleTestCase(TestCase):

    def setUp(self) -> None:
        super().setUp()
        KeycloakJWTAuthentication._jwks_client = None
        self.addCleanup(setattr, KeycloakJWTAuthentication, '_jwks_client', None)
        p = mock.patch('jwt.PyJWKClient.fetch_data', autospec=True, side_effect=lambda _s: _jwks())
        self.jwks_fetch = p.start()
        self.addCleanup(p.stop)
        # Aucun appel réseau sortant ne doit partir du conteneur de test.
        p = mock.patch('requests.adapters.HTTPAdapter.send', autospec=True,
                       side_effect=requests.ConnectionError('réseau coupé (test)'))
        p.start()
        self.addCleanup(p.stop)
        cache.clear()
        self.addCleanup(cache.clear)
        # Table rase : la migration 0002_example_data insère des capteurs et des
        # mesures d'exemple, committés dans la base de test. On repart d'un socle
        # vide pour que les comptes soient déterministes (le DELETE est annulé
        # avec la transaction du test).
        Sensor.objects.all().delete()        # cascade : lectures, accès, grandeurs
        Webhook.objects.all().delete()

        # developer (voit tout), membre sans accès, non-membre du realm.
        self.dev = client_de('dev@exemple.org', ['developers'])
        self.ami = client_de('ami@exemple.org', ['amis'])
        self.etranger = client_de('etr@exemple.org', ['famille'])

    # ── fabriques ORM ─────────────────────────────────────────────────────────
    def sensor(self, slug='s1', **kw) -> Sensor:
        return Sensor.objects.create(name=kw.pop('name', slug), slug=slug, **kw)

    def webhook(self, name='wh', protocol='ttn', **kw) -> Webhook:
        return Webhook.objects.create(name=name, protocol=protocol, **kw)

    def donne_acces(self, sensor, email='ami@exemple.org'):
        return SensorUserAccess.objects.create(sensor=sensor, user_email=email)

    def donne_acces_webhook(self, webhook, email='ami@exemple.org'):
        return WebhookUserAccess.objects.create(webhook=webhook, user_email=email)
