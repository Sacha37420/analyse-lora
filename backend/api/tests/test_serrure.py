"""Verrou 2 — serrure de l'API (CLAUDE.md, « Sécurité — cloisonnement »).

Jetons RS256 réels via la classe d'authentification de l'app ; seul le
téléchargement du JWKS est remplacé. Trois groupes ouvrent l'app
(`developers,amis,famille`) ; tout le reste est refusé.
"""
import time
import unittest

import jwt
from rest_framework.test import APIClient

from .socle import AUTRE_RSA, CLIENT, KID, SocleTestCase, _RSA, jeton

# Endpoint « authentifié simple » (ni API key, ni IsDeveloper) : la serrure y est nue.
URL = '/api/me/'


class SerrureTests(SocleTestCase):

    def get(self, tok, path=URL):
        c = APIClient()
        if tok is not None:
            c.credentials(HTTP_AUTHORIZATION=f'Bearer {tok}')
        return c.get(path)

    def test_chacun_des_trois_groupes_entre(self):
        for groupe in ('developers', 'amis', 'famille'):
            with self.subTest(groupe=groupe):
                resp = self.get(jeton('x@y.org', [groupe]))
                self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(self.jwks_fetch.call_count, 1)   # la clé vient du JWKS simulé

    def test_sans_jeton_refuse(self):
        self.assertIn(self.get(None).status_code, (401, 403))

    def test_entete_non_bearer_refuse(self):
        for entete in ('Basic abc', jeton(), 'bearer ' + jeton()):
            c = APIClient()
            c.credentials(HTTP_AUTHORIZATION=entete)
            self.assertIn(c.get(URL).status_code, (401, 403))

    def test_client_etranger_refuse(self):
        for azp in ('admin-cli', 'storage', 'account', '', None):
            with self.subTest(azp=azp):
                resp = self.get(jeton(azp=azp))
                self.assertEqual(resp.status_code, 403)
                self.assertIn('autre client', resp.json()['detail'])

    def test_sans_groupe_requis_refuse(self):
        for groups in ([], None, ['autre'], ['Developers'], ['developers-x'], 'amis'):
            with self.subTest(groups=groups):
                resp = self.get(jeton(groups=groups))
                self.assertEqual(resp.status_code, 403)
                self.assertIn('groupe(s)', resp.json()['detail'])

    def test_jeton_expire_refuse(self):
        self.assertEqual(self.get(jeton(exp=-30)).status_code, 403)

    def test_signature_forgee_refusee(self):
        self.assertEqual(self.get(jeton(cle=AUTRE_RSA)).status_code, 403)

    def test_charge_modifiee_apres_signature_refusee(self):
        entete, _, sig = jeton(groups=['autre']).split('.')
        _, charge, _ = jeton(groups=['developers']).split('.')
        self.assertEqual(self.get(f'{entete}.{charge}.{sig}').status_code, 403)

    def test_algorithmes_detournes_refuses(self):
        claims = {'azp': CLIENT, 'email': 'd@e.org', 'groups': ['developers'],
                  'exp': int(time.time()) + 300}
        for nom, tok in (
            ('none', jwt.encode(claims, None, algorithm='none', headers={'kid': KID})),
            ('HS256-jwks', jwt.encode(claims, 'x' * 40, algorithm='HS256', headers={'kid': KID})),
            ('charabia', 'a.b.c'), ('vide', '')):
            with self.subTest(cas=nom):
                self.assertEqual(self.get(tok).status_code, 403)

    def test_sans_email_refuse(self):
        for email in (None, ''):
            resp = self.get(jeton(email=email))
            self.assertEqual(resp.status_code, 403)
            self.assertIn('email', resp.json()['detail'])

    def test_me_rend_les_claims(self):
        body = self.get(jeton('dev@exemple.org', ['developers', 'amis'])).json()
        self.assertEqual(body['email'], 'dev@exemple.org')
        self.assertTrue(body['is_developer'])
        self.assertEqual(self.get(jeton('a@b.org', ['amis'])).json()['is_developer'], False)

    # DÉFAUT (I4) — KeycloakJWTAuthentication n'attrape que InvalidTokenError.
    # Une clé `kid` absente du JWKS fait lever PyJWKClientError (hors de cette
    # hiérarchie) : 500 non géré au lieu d'un 401/403. L'accès reste fermé, mais
    # un jeton forgé provoque des 500 à volonté.
    @unittest.expectedFailure
    def test_kid_inconnu_repond_un_refus_propre(self):
        c = APIClient(raise_request_exception=False)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {jeton(kid='inconnu')}")
        self.assertIn(c.get(URL).status_code, (401, 403))

    def test_kid_inconnu_ne_laisse_pas_entrer(self):
        c = APIClient(raise_request_exception=False)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {jeton(kid='inconnu')}")
        self.assertNotIn(c.get(URL).status_code, range(200, 400))
