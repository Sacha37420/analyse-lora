"""Validité métier (relecture « metier-ux » du 2026-11-17) : bornes de dates,
ingestion mal formée, jauges sur des valeurs non numériques, messages d'erreur
TTN, cohérence protocole capteur / webhook, changement d'heure."""
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import requests
from django.utils import timezone
from rest_framework.test import APIClient

from api import ttn
from api.dashboard import _period_bounds
from api.models import ComputedMeasure, SensorReading
from .socle import SocleTestCase

PARIS = ZoneInfo('Europe/Paris')
UTC = ZoneInfo('UTC')


class BornesDeDatesTests(SocleTestCase):
    """`start` / `end` de GET …/data/ et …/compute/ : bornes incluses, date
    illisible refusée (400) au lieu d'une erreur 500."""

    def setUp(self):
        super().setUp()
        self.s = self.sensor('a')
        for h in (8, 10, 12):
            SensorReading.objects.create(sensor=self.s, timestamp=f'2026-01-01T{h:02d}:00:00Z', data={'t': h})
        self.m = ComputedMeasure.objects.create(sensor=self.s, name='F', formula="row['t'] * 2")

    def test_bornes_incluses_sur_les_lectures(self):
        corps = self.dev.get(f'/api/sensors/{self.s.id}/data/',
                             {'start': '2026-01-01T08:00:00Z', 'end': '2026-01-01T10:00:00Z'}).json()
        self.assertEqual(corps['count'], 2)

    def test_compute_rend_les_points_de_la_plage_dans_l_ordre_chronologique(self):
        corps = self.dev.get(f'/api/measures/{self.m.id}/compute/',
                             {'start': '2026-01-01T09:00:00Z', 'end': '2026-01-01T12:00:00Z'}).json()
        self.assertEqual([p['v'] for p in corps['points']], [20, 24])

    def test_date_illisible_refusee_sur_les_lectures(self):
        for params in ({'start': 'hier'}, {'end': '2026-13-45T00:00:00Z'}):
            resp = self.dev.get(f'/api/sensors/{self.s.id}/data/', params)
            self.assertEqual(resp.status_code, 400, params)
            self.assertIn(next(iter(params)), resp.json())

    def test_date_illisible_refusee_sur_le_calcul(self):
        resp = self.dev.get(f'/api/measures/{self.m.id}/compute/', {'start': 'pas-une-date'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('start', resp.json())


class IngestionMalFormeeTests(SocleTestCase):
    """Un uplink mal formé est refusé (400) sans rien créer, au lieu d'une erreur 500."""

    def setUp(self):
        super().setUp()
        self.s = self.sensor('a')
        self.wh = self.webhook('app1', 'ttn')
        self.sw = self.sensor('w', protocol='ttn', webhook=self.wh, connection_config={'device_id': 'd1'})

    def post(self, path, body, cle):
        return APIClient().post(path, body, format='json', HTTP_X_API_KEY=cle)

    def test_horodatage_illisible_refuse(self):
        for ts in ('hier', '2026-02-30T10:00:00Z', 12):
            resp = self.post(f'/api/sensors/{self.s.id}/data/', {'timestamp': ts, 'data': {'t': 1}}, self.s.api_key)
            self.assertEqual(resp.status_code, 400, ts)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_corps_qui_n_est_pas_un_objet_refuse(self):
        resp = self.post(f'/api/sensors/{self.s.id}/data/', [1, 2], self.s.api_key)
        self.assertEqual(resp.status_code, 400)
        resp = self.post(f'/api/webhooks/{self.wh.id}/data/', [1, 2], self.wh.api_key)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_webhook_horodatage_illisible_refuse(self):
        corps = {'end_device_ids': {'device_id': 'd1'},
                 'uplink_message': {'received_at': 'jamais', 'decoded_payload': {'t': 1}}}
        resp = self.post(f'/api/webhooks/{self.wh.id}/data/', corps, self.wh.api_key)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_une_cle_fausse_reste_un_403_meme_avec_un_corps_invalide(self):
        resp = self.post(f'/api/sensors/{self.s.id}/data/', [1], 'mauvaise')
        self.assertEqual(resp.status_code, 403)


class JaugesTests(SocleTestCase):
    """Jauges intérieur/extérieur : écart = intérieur − extérieur, et aucun
    écart (ni erreur 500) quand une valeur n'est pas un nombre."""

    def setUp(self):
        super().setUp()
        self.wh = self.webhook('maison', 'ttn')
        self.int = self.sensor('int', protocol='ttn', webhook=self.wh, location='interior')
        self.ext = self.sensor('ext', protocol='ttn', webhook=self.wh, location='exterior')
        now = timezone.now()
        SensorReading.objects.create(sensor=self.int, timestamp=now, data={'temperature': 21.5, 'etat': 'ok'})
        SensorReading.objects.create(sensor=self.ext, timestamp=now, data={'temperature': 9.5, 'etat': 'ko'})

    def jauges(self, field):
        resp = self.dev.get(f'/api/dashboard/groups/webhook/{self.wh.id}/gauges/', {'field': field})
        self.assertEqual(resp.status_code, 200)
        return {g['sensor_id']: g for g in resp.json()['gauges']}

    def test_ecart_interieur_moins_exterieur(self):
        g = self.jauges('temperature')
        self.assertEqual(g[self.int.id]['delta'], 12.0)
        self.assertIn(g[self.int.id]['delta_color'], ('red', 'green'))
        self.assertIsNone(g[self.ext.id]['delta'])     # la référence n'a pas d'écart

    def test_valeur_non_numerique_sans_ecart(self):
        g = self.jauges('etat')
        self.assertEqual(g[self.int.id]['value'], 'ok')
        self.assertIsNone(g[self.int.id]['delta'])


class MessagesTTNTests(SocleTestCase):
    """Le message d'erreur TTN est rendu à l'écran : il ne doit porter ni l'URL
    demandée (texte d'une exception `requests`), ni le corps brut de la réponse."""

    CONFIG = {'region': 'eu1', 'app_id': 'appli-privee', 'api_key': 'k'}

    def test_erreur_reseau_sans_l_url(self):
        exc = requests.ConnectionError('Max retries exceeded with url: /api/v3/as/applications/appli-privee/…')
        with mock.patch('api.ttn.requests.get', side_effect=exc):
            with self.assertRaises(ttn.TTNError) as ctx:
                ttn.fetch_stored_uplinks(self.CONFIG)
        self.assertNotIn('appli-privee', str(ctx.exception))

    def test_reponse_d_erreur_sans_le_corps_brut(self):
        rep = mock.Mock(status_code=500, text='<html>trace interne</html>')
        with mock.patch('api.ttn.requests.get', return_value=rep):
            with self.assertRaises(ttn.TTNError) as ctx:
                ttn.fetch_stored_uplinks(self.CONFIG)
        self.assertNotIn('trace interne', str(ctx.exception))

    def test_reponse_illisible_donne_une_ttnerror(self):
        rep = mock.Mock(status_code=200, text='pas du json\n')
        with mock.patch('api.ttn.requests.get', return_value=rep):
            with self.assertRaises(ttn.TTNError):
                ttn.fetch_stored_uplinks(self.CONFIG)

    def test_backfill_ignore_un_horodatage_illisible(self):
        wh = self.webhook('app', 'ttn', connection_config=self.CONFIG)
        s = self.sensor('w', protocol='ttn', webhook=wh, connection_config={'device_id': 'd1'})
        ups = [{'end_device_ids': {'device_id': 'd1'},
                'uplink_message': {'received_at': f'2026-01-01T{h}:00:00Z', 'decoded_payload': {'t': 1}}}
               for h in ('10', '99')]
        with mock.patch('api.ttn.fetch_stored_uplinks', return_value=ups):
            r = ttn.backfill(wh.connection_config, [s])
        self.assertEqual(r['inserted'], 1)
        self.assertEqual(SensorReading.objects.filter(sensor=s).count(), 1)


class ProtocoleEtWebhookTests(SocleTestCase):
    """Un capteur rattaché à un webhook a le protocole de ce webhook, par la
    fiche capteur comme par la page Connexion."""

    def setUp(self):
        super().setUp()
        self.wh = self.webhook('app1', 'ttn')
        self.sw = self.sensor('w', protocol='ttn', webhook=self.wh)
        self.autonome = self.sensor('m', protocol='mqtt')

    def test_changer_le_protocole_d_un_capteur_rattache_refuse(self):
        resp = self.dev.patch(f'/api/sensors/{self.sw.id}/', {'protocol': 'mqtt'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('protocol', resp.json())
        self.sw.refresh_from_db()
        self.assertEqual(self.sw.protocol, 'ttn')

    def test_rattacher_par_la_fiche_a_un_webhook_d_un_autre_protocole_refuse(self):
        resp = self.dev.patch(f'/api/sensors/{self.autonome.id}/', {'webhook': self.wh.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.autonome.refresh_from_db()
        self.assertIsNone(self.autonome.webhook_id)

    def test_fiche_complete_coherente_acceptee(self):
        corps = {'name': 'w2', 'slug': 'w', 'protocol': 'ttn', 'location': 'exterior'}
        self.assertEqual(self.dev.put(f'/api/sensors/{self.sw.id}/', corps, format='json').status_code, 200)

    def test_patch_de_la_seule_meteo_accepte(self):
        resp = self.dev.patch(f'/api/sensors/{self.autonome.id}/', {'weather_location': 'Lyon'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_connexion_changer_le_protocole_en_gardant_le_webhook_refuse(self):
        resp = self.dev.put(f'/api/sensors/{self.sw.id}/connection/', {'protocol': 'chirpstack'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.sw.refresh_from_db()
        self.assertEqual(self.sw.protocol, 'ttn')

    def test_connexion_protocole_inconnu_refuse(self):
        resp = self.dev.put(f'/api/sensors/{self.autonome.id}/connection/', {'protocol': 'pigeon'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.autonome.refresh_from_db()
        self.assertEqual(self.autonome.protocol, 'mqtt')

    def test_connexion_detacher_et_changer_de_protocole_accepte(self):
        resp = self.dev.put(f'/api/sensors/{self.sw.id}/connection/',
                            {'protocol': 'mqtt', 'webhook': None, 'connection_config': {}}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.sw.refresh_from_db()
        self.assertEqual((self.sw.protocol, self.sw.webhook_id), ('mqtt', None))


class ChangementDHeureTests(SocleTestCase):
    """Bornes de période en heure de Paris : le jour du passage à l'heure
    d'hiver dure 25 h, la semaine qui le contient 7 j + 1 h."""

    def test_jour_de_25_heures(self):
        start, end = _period_bounds('day', datetime(2026, 10, 25, 12, 0, tzinfo=PARIS))
        self.assertEqual(start.utcoffset(), timedelta(hours=2))
        self.assertEqual(end.utcoffset(), timedelta(hours=1))
        self.assertEqual(end.astimezone(UTC) - start.astimezone(UTC), timedelta(hours=25, microseconds=-1))

    def test_semaine_contenant_le_changement(self):
        start, end = _period_bounds('week', datetime(2026, 10, 22, 12, 0, tzinfo=PARIS))
        self.assertEqual((start.day, start.hour), (19, 0))
        self.assertEqual((end.day, end.hour, end.minute), (25, 23, 59))
        self.assertEqual(end.astimezone(UTC) - start.astimezone(UTC), timedelta(days=7, hours=1, microseconds=-1))
