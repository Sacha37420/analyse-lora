"""Qui voit et gère quoi : developer vs accès nominatif (capteur ou webhook),
clés d'API d'ingestion, réservations aux developers."""
import unittest

from api.models import ComputedMeasure, Sensor, SensorReading, SensorUserAccess
from .socle import SocleTestCase, jeton


class VisibiliteCapteursTests(SocleTestCase):

    def setUp(self):
        super().setUp()
        self.a = self.sensor('a')
        self.b = self.sensor('b')
        self.donne_acces(self.a, 'ami@exemple.org')

    def ids(self, resp):
        self.assertEqual(resp.status_code, 200)
        return sorted(s['id'] for s in resp.json())

    def test_developer_voit_tous_les_capteurs(self):
        self.assertEqual(self.ids(self.dev.get('/api/sensors/')), sorted([self.a.id, self.b.id]))

    def test_un_membre_ne_voit_que_les_capteurs_qui_lui_sont_ouverts(self):
        self.assertEqual(self.ids(self.ami.get('/api/sensors/')), [self.a.id])
        self.assertEqual(self.ids(self.etranger.get('/api/sensors/')), [])

    def test_detail_d_un_capteur_sans_acces_refuse(self):
        self.assertEqual(self.ami.get(f'/api/sensors/{self.a.id}/').status_code, 200)
        self.assertEqual(self.ami.get(f'/api/sensors/{self.b.id}/').status_code, 403)
        self.assertEqual(self.etranger.get(f'/api/sensors/{self.a.id}/').status_code, 403)

    def test_acces_webhook_couvre_les_donnees_de_ses_capteurs(self):
        # Chemin HONORÉ : les vues qui passent par _has_sensor_access (données,
        # tableau de bord, connexion, grandeurs) propagent l'accès du webhook à
        # ses capteurs, présents et futurs (cf. docstring de WebhookUserAccess).
        wh = self.webhook('app1', 'ttn')
        s1 = self.sensor('w1', protocol='ttn', webhook=wh)
        from api.models import SensorReading
        SensorReading.objects.create(sensor=s1, timestamp='2026-01-01T00:00:00Z', data={'t': 1})
        self.donne_acces_webhook(wh, 'ami@exemple.org')
        self.assertEqual(self.ami.get(f'/api/sensors/{s1.id}/data/').status_code, 200)
        # Capteur rattaché APRÈS l'octroi : couvert sans nouvel accès.
        s2 = self.sensor('w2', protocol='ttn', webhook=wh)
        SensorReading.objects.create(sensor=s2, timestamp='2026-01-01T00:00:00Z', data={'t': 2})
        self.assertEqual(self.ami.get(f'/api/sensors/{s2.id}/data/').status_code, 200)

    # DÉFAUT (I4) — incohérence de cloisonnement. L'accès au niveau du webhook
    # est honoré par les vues passant par _has_sensor_access (données, tableau
    # de bord…), mais la LISTE et le DÉTAIL d'un capteur ne regardent que les
    # SensorUserAccess directs (SensorListView.get_queryset et la permission
    # HasSensorAccess, api/permissions.py — elle ignore sensor.webhook). Un
    # utilisateur à qui on a ouvert un webhook peut lire les mesures de ses
    # capteurs mais pas leur fiche, et ne les voit pas dans sa liste : les deux
    # vues devraient réutiliser _has_sensor_access comme les autres.
    @unittest.expectedFailure
    def test_acces_webhook_couvre_aussi_le_detail_du_capteur(self):
        wh = self.webhook('app1', 'ttn')
        s1 = self.sensor('w1', protocol='ttn', webhook=wh)
        self.donne_acces_webhook(wh, 'ami@exemple.org')
        self.assertEqual(self.ami.get(f'/api/sensors/{s1.id}/').status_code, 200)
        self.assertIn(s1.id, self.ids(self.ami.get('/api/sensors/')))


class ReserveAuxDevelopersTests(SocleTestCase):
    """Création/modification de capteurs et webhooks, gestion des accès,
    détail d'un webhook (secret d'ingestion) : developers seulement."""

    def setUp(self):
        super().setUp()
        self.s = self.sensor('a')
        self.donne_acces(self.s, 'ami@exemple.org')
        self.wh = self.webhook('app1', 'ttn')

    def refuse_aux_non_dev(self, methode, path, **kw):
        for client, attendu in ((self.ami, 403), (self.etranger, 403)):
            resp = getattr(client, methode)(path, kw.get('data', {}), format='json')
            self.assertEqual(resp.status_code, attendu, f'{methode} {path}')

    def test_creer_un_capteur_reserve_aux_developers(self):
        self.refuse_aux_non_dev('post', '/api/sensors/', data={'name': 'x', 'slug': 'x', 'protocol': 'mqtt'})
        self.assertEqual(Sensor.objects.count(), 1)
        resp = self.dev.post('/api/sensors/', {'name': 'x', 'slug': 'x', 'protocol': 'mqtt'}, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_modifier_supprimer_un_capteur_reserve_aux_developers(self):
        # Un membre avec accès LECTURE ne peut ni modifier ni supprimer.
        self.assertEqual(self.ami.put(f'/api/sensors/{self.s.id}/',
                                      {'name': 'z', 'slug': 'a', 'protocol': 'mqtt'}, format='json').status_code, 403)
        self.assertEqual(self.ami.delete(f'/api/sensors/{self.s.id}/').status_code, 403)
        self.assertEqual(self.dev.delete(f'/api/sensors/{self.s.id}/').status_code, 204)

    def test_liste_et_detail_webhook_reserves_aux_developers(self):
        # Le détail d'un webhook porte api_key + connection_config (secrets).
        self.refuse_aux_non_dev('get', '/api/webhooks/')
        self.assertEqual(self.ami.get(f'/api/webhooks/{self.wh.id}/').status_code, 403)
        body = self.dev.get(f'/api/webhooks/{self.wh.id}/').json()
        self.assertIn('api_key', body)
        self.assertTrue(body['api_key'])

    def test_gestion_des_acces_reservee_aux_developers(self):
        self.refuse_aux_non_dev('get', f'/api/sensors/{self.s.id}/users/')
        self.refuse_aux_non_dev('post', f'/api/sensors/{self.s.id}/users/',
                                data={'user_email': 'tiers@exemple.org'})
        self.assertEqual(SensorUserAccess.objects.filter(user_email='tiers@exemple.org').count(), 0)
        resp = self.dev.post(f'/api/sensors/{self.s.id}/users/', {'user_email': 'Tiers@Exemple.org'}, format='json')
        self.assertEqual(resp.status_code, 201)
        # Normalisé en minuscules — comparé tel quel à l'email du jeton.
        self.assertTrue(SensorUserAccess.objects.filter(sensor=self.s, user_email='tiers@exemple.org').exists())

    def test_backfill_ttn_reserve_aux_developers(self):
        # Utilise la clé API TTN du webhook, visible des seuls developers.
        path = f'/api/dashboard/groups/webhook/{self.wh.id}/ttn-backfill/'
        self.refuse_aux_non_dev('post', path)

    def test_connexion_secret_modifiable_par_les_seuls_developers(self):
        # GET /connection/ accessible avec accès capteur ; PUT réservé aux developers.
        self.assertEqual(self.ami.get(f'/api/sensors/{self.s.id}/connection/').status_code, 200)
        self.assertEqual(self.ami.put(f'/api/sensors/{self.s.id}/connection/',
                                      {'protocol': 'mqtt'}, format='json').status_code, 403)


class IngestionParCleTests(SocleTestCase):
    """SensorDataView / WebhookDataView : auth gérée à la main (clé d'API en plus
    du JWT). Chemin `AllowAny` délibéré — à cadrer précisément."""

    def setUp(self):
        super().setUp()
        self.s = self.sensor('a', protocol='ttn')
        self.wh = self.webhook('app1', 'ttn')
        self.sw = self.sensor('w', protocol='ttn', webhook=self.wh,
                              connection_config={'device_id': 'dev-123'})

    def payload_ttn(self, dev='dev-123', temp=21):
        return {'end_device_ids': {'device_id': dev},
                'uplink_message': {'received_at': '2026-01-01T10:00:00Z', 'decoded_payload': {'temperature': temp}}}

    def post(self, path, body, **headers):
        from rest_framework.test import APIClient
        return APIClient().post(path, body, format='json', **headers)

    def test_la_bonne_cle_ingere_sans_jeton(self):
        resp = self.post(f'/api/sensors/{self.s.id}/data/', {'data': {'t': 1}},
                         HTTP_X_API_KEY=self.s.api_key)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(SensorReading.objects.filter(sensor=self.s).count(), 1)

    def test_la_cle_passe_aussi_en_bearer(self):
        resp = self.post(f'/api/sensors/{self.s.id}/data/', {'data': {'t': 1}},
                         HTTP_AUTHORIZATION=f'Bearer {self.s.api_key}')
        self.assertEqual(resp.status_code, 201)

    def test_une_cle_fausse_ou_absente_est_refusee(self):
        for h in ({}, {'HTTP_X_API_KEY': 'mauvaise'}, {'HTTP_X_API_KEY': self.wh.api_key},
                  {'HTTP_AUTHORIZATION': 'Bearer mauvaise'}):
            resp = self.post(f'/api/sensors/{self.s.id}/data/', {'data': {}}, **h)
            self.assertEqual(resp.status_code, 403, h)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_la_cle_d_un_capteur_n_ouvre_pas_un_autre(self):
        autre = self.sensor('b')
        resp = self.post(f'/api/sensors/{autre.id}/data/', {'data': {}}, HTTP_X_API_KEY=self.s.api_key)
        self.assertEqual(resp.status_code, 403)

    def test_lecture_des_donnees_par_jeton_avec_acces(self):
        SensorReading.objects.create(sensor=self.s, timestamp='2026-01-01T10:00:00Z', data={'t': 1})
        self.assertEqual(self.dev.get(f'/api/sensors/{self.s.id}/data/').json()['count'], 1)
        self.assertEqual(self.etranger.get(f'/api/sensors/{self.s.id}/data/').status_code, 403)
        self.donne_acces(self.s, 'ami@exemple.org')
        self.assertEqual(self.ami.get(f'/api/sensors/{self.s.id}/data/').json()['count'], 1)

    def test_webhook_ingestion_route_vers_le_bon_capteur(self):
        resp = self.post(f'/api/webhooks/{self.wh.id}/data/', self.payload_ttn('dev-123'),
                         HTTP_X_API_KEY=self.wh.api_key)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(SensorReading.objects.filter(sensor=self.sw).count(), 1)

    def test_webhook_device_inconnu_ne_cree_rien(self):
        resp = self.post(f'/api/webhooks/{self.wh.id}/data/', self.payload_ttn('fantome'),
                         HTTP_X_API_KEY=self.wh.api_key)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_webhook_cle_du_capteur_n_ouvre_pas_le_webhook(self):
        resp = self.post(f'/api/webhooks/{self.wh.id}/data/', self.payload_ttn(),
                         HTTP_X_API_KEY=self.sw.api_key)
        self.assertEqual(resp.status_code, 403)


class GrandeursCalculeesTests(SocleTestCase):
    """ComputedMeasure : liste/détail/compute. Mesure le cloisonnement réel
    (plusieurs vues n'imposent aucun accès au capteur sous-jacent)."""

    def setUp(self):
        super().setUp()
        self.s = self.sensor('a')
        self.m = ComputedMeasure.objects.create(sensor=self.s, name='F', formula="row['t']*9/5+32")

    def test_compute_exige_l_acces_au_capteur(self):
        SensorReading.objects.create(sensor=self.s, timestamp='2026-01-01T00:00:00Z', data={'t': 100})
        self.assertEqual(self.etranger.get(f'/api/measures/{self.m.id}/compute/').status_code, 403)
        body = self.dev.get(f'/api/measures/{self.m.id}/compute/').json()
        self.assertEqual(body['points'][0]['v'], 212.0)

    def test_liste_des_grandeurs_rendue_a_qui_a_l_acces(self):
        self.assertEqual(self.dev.get(f'/api/sensors/{self.s.id}/measures/').json()[0]['id'], self.m.id)

    # Corrigé : get_queryset avalait la PermissionDenied (200 + liste vide).
    def test_liste_des_grandeurs_refusee_sans_acces(self):
        self.assertEqual(self.etranger.get(f'/api/sensors/{self.s.id}/measures/').status_code, 403)

    # Corrigé : ComputedMeasureDetailView ne portait que IsAuthenticated.
    def test_detail_d_une_grandeur_exige_l_acces_au_capteur(self):
        self.assertEqual(self.etranger.get(f'/api/measures/{self.m.id}/').status_code, 403)

    def test_modification_et_suppression_d_une_grandeur_exigent_l_acces_au_capteur(self):
        url = f'/api/measures/{self.m.id}/'
        self.assertEqual(self.etranger.patch(url, {'formula': '0'}, format='json').status_code, 403)
        self.assertEqual(self.etranger.put(url, {'sensor': self.s.id, 'name': 'F', 'formula': '0'},
                                           format='json').status_code, 403)
        self.assertEqual(self.etranger.delete(url).status_code, 403)
        self.m.refresh_from_db()
        self.assertEqual(self.m.formula, "row['t']*9/5+32")

    def test_qui_a_l_acces_au_capteur_gere_sa_grandeur(self):
        url = f'/api/measures/{self.m.id}/'
        self.donne_acces(self.s, 'ami@exemple.org')
        self.assertEqual(self.ami.get(url).status_code, 200)
        self.assertEqual(self.ami.patch(url, {'unit': '°F'}, format='json').status_code, 200)
        # … mais ne la déplace pas vers un capteur qui ne lui est pas ouvert.
        autre = self.sensor('b')
        self.assertEqual(self.ami.patch(url, {'sensor': autre.id}, format='json').status_code, 403)
        self.m.refresh_from_db()
        self.assertEqual(self.m.sensor_id, self.s.id)
        self.assertEqual(self.ami.delete(url).status_code, 204)
        self.assertEqual(self.dev.get(url).status_code, 404)

    # DÉFAUT (I4) — ComputedMeasureListView.perform_create ne revérifie pas
    # l'accès au capteur (get_queryset le fait, mais CreateModelMixin ne passe
    # pas par get_queryset). Un membre sans accès crée une grandeur sur
    # n'importe quel capteur.
    @unittest.expectedFailure
    def test_creation_d_une_grandeur_exige_l_acces_au_capteur(self):
        resp = self.etranger.post(f'/api/sensors/{self.s.id}/measures/',
                                  {'name': 'G', 'formula': "row['t']"}, format='json')
        self.assertIn(resp.status_code, (403, 404))
        self.assertEqual(ComputedMeasure.objects.filter(name='G').count(), 0)
