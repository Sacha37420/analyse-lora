"""Règles métier : normalisation des payloads réseau, routage par device,
évaluation de formule, bornes de période, rattrapage TTN, superposition météo."""
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.utils import timezone

from api import ttn, weather
from api.dashboard import _local_iso, _period_bounds
from api.models import ComputedMeasure, Sensor, SensorReading
from api.views import _extract_external_device_id, _normalize_payload, _safe_eval
from .socle import SocleTestCase

PARIS = ZoneInfo('Europe/Paris')


class NormalisationTests(SocleTestCase):

    def test_ttn(self):
        ts, data = _normalize_payload(
            {'uplink_message': {'received_at': '2026-03-15T08:30:00Z',
                                'decoded_payload': {'temperature': 19.5}}}, 'ttn')
        self.assertEqual(data, {'temperature': 19.5})
        self.assertEqual(ts, datetime(2026, 3, 15, 8, 30, tzinfo=ZoneInfo('UTC')))

    def test_ttn_sans_payload_decode_retombe_sur_frm_payload(self):
        _, data = _normalize_payload({'uplink_message': {'frm_payload': 'AQID'}}, 'ttn')
        self.assertEqual(data, 'AQID')

    def test_chirpstack(self):
        ts, data = _normalize_payload({'deviceInfo': {'devEui': 'x'}, 'time': '2026-03-15T08:30:00Z',
                                       'object': {'h': 60}}, 'chirpstack')
        self.assertEqual(data, {'h': 60})
        self.assertEqual(ts.year, 2026)

    def test_format_standard_et_horodatage_par_defaut(self):
        _, data = _normalize_payload({'timestamp': '2026-03-15T08:30:00Z', 'data': {'v': 1}}, 'http_push')
        self.assertEqual(data, {'v': 1})
        # Sans timestamp : « maintenant ».
        avant = timezone.now()
        ts, data = _normalize_payload({'v': 2}, 'http_push')
        self.assertEqual(data, {'v': 2})
        self.assertGreaterEqual(ts, avant)

    def test_extraction_device_id_par_protocole(self):
        self.assertEqual(_extract_external_device_id({'end_device_ids': {'device_id': 'd1'}}, 'ttn'), 'd1')
        self.assertEqual(_extract_external_device_id({'deviceInfo': {'devEui': 'eui'}}, 'chirpstack'), 'eui')
        self.assertEqual(_extract_external_device_id({'dev_eui': 'h'}, 'helium'), 'h')
        self.assertEqual(_extract_external_device_id({'device_id': 'g'}, 'http_push'), 'g')
        self.assertEqual(_extract_external_device_id({}, 'ttn'), '')


class FormuleTests(SocleTestCase):

    def test_calcul(self):
        self.assertEqual(_safe_eval("row['t'] * 9/5 + 32", {'t': 100}), 212.0)
        self.assertEqual(_safe_eval("sqrt(row['x'])", {'x': 16}), 4.0)
        self.assertEqual(_safe_eval("max(row['a'], row['b'])", {'a': 1, 'b': 5}), 5.0)

    def test_formule_fautive_rend_none_sans_lever(self):
        for f, row in (("row['absent']", {}), ("1/0", {}), ("def x(): pass", {}), ("'texte'", {})):
            self.assertIsNone(_safe_eval(f, row))

    def test_la_formule_n_a_pas_acces_aux_builtins(self):
        # __builtins__ vidé : pas d'import, pas d'open, pas d'eval imbriqué.
        for f in ("__import__('os').getcwd()", "open('/etc/passwd').read()", "eval('1')"):
            self.assertIsNone(_safe_eval(f, {}))


class PeriodeTests(SocleTestCase):

    def test_bornes_de_jour(self):
        now = datetime(2026, 3, 15, 14, 0, tzinfo=PARIS)
        start, end = _period_bounds('day', now)
        self.assertEqual((start.hour, start.minute), (0, 0))
        self.assertEqual(start.date(), now.date())
        self.assertEqual(end.date(), now.date())

    def test_bornes_de_semaine_commencent_un_lundi(self):
        start, end = _period_bounds('week', datetime(2026, 3, 18, 14, 0, tzinfo=PARIS))  # mercredi
        self.assertEqual(start.weekday(), 0)
        self.assertEqual(start.day, 16)
        self.assertEqual((end - start).days, 6)

    def test_bornes_de_mois_passent_decembre_a_janvier(self):
        start, end = _period_bounds('month', datetime(2026, 12, 20, tzinfo=PARIS))
        self.assertEqual((start.month, start.day), (12, 1))
        self.assertEqual(end.year, 2026)
        self.assertEqual(end.month, 12)

    def test_periode_inconnue(self):
        self.assertEqual(_period_bounds('siecle'), (None, None))

    def test_local_iso_sans_decalage(self):
        # Une chaîne naïve, pour que Plotly l'affiche telle quelle.
        dt = datetime(2026, 7, 1, 10, 0, tzinfo=ZoneInfo('UTC'))
        self.assertEqual(_local_iso(dt), '2026-07-01T12:00:00')  # UTC+2 l'été à Paris
        self.assertNotIn('+', _local_iso(dt))


class BackfillTTNTests(SocleTestCase):
    """ttn.backfill : insertion des uplinks manqués, déduplication par timestamp,
    routage par device_id — tout appel réseau simulé par mock du fetch."""

    def setUp(self):
        super().setUp()
        self.wh = self.webhook('app', 'ttn', connection_config={'region': 'eu1', 'app_id': 'a', 'api_key': 'k'})
        self.s = self.sensor('w', protocol='ttn', webhook=self.wh, connection_config={'device_id': 'dev-1'})

    def uplink(self, dev, heure, temp):
        return {'end_device_ids': {'device_id': dev},
                'uplink_message': {'received_at': f'2026-01-01T{heure:02d}:00:00Z',
                                   'decoded_payload': {'temperature': temp}}}

    def test_insere_et_route_puis_deduplique(self):
        ups = [self.uplink('dev-1', 10, 20), self.uplink('dev-1', 11, 21), self.uplink('inconnu', 12, 9)]
        with mock.patch('api.ttn.fetch_stored_uplinks', return_value=ups):
            r1 = ttn.backfill(self.wh.connection_config, [self.s])
        self.assertEqual(r1['inserted'], 2)
        self.assertEqual(r1['unmatched_devices'], ['inconnu'])
        self.assertEqual(SensorReading.objects.filter(sensor=self.s).count(), 2)
        # Relance : les mêmes timestamps ne sont pas réinsérés.
        with mock.patch('api.ttn.fetch_stored_uplinks', return_value=ups):
            r2 = ttn.backfill(self.wh.connection_config, [self.s])
        self.assertEqual(r2['inserted'], 0)
        self.assertEqual(SensorReading.objects.filter(sensor=self.s).count(), 2)

    def test_config_incomplete_leve_ttnerror(self):
        with self.assertRaises(ttn.TTNError):
            ttn.fetch_stored_uplinks({'region': 'eu1', 'app_id': 'a'})  # pas de clé

    def test_reseau_coupe_leve_ttnerror(self):
        # Le socle coupe le réseau sortant : fetch_stored_uplinks doit le traduire proprement.
        with self.assertRaises(ttn.TTNError):
            ttn.fetch_stored_uplinks({'region': 'eu1', 'app_id': 'a', 'api_key': 'k'})


class MeteoTests(SocleTestCase):
    """weather : repli quand le fournisseur est injoignable (réseau coupé par le
    socle), et bornes réelles quand il répond (mock du fetch)."""

    def test_sans_localisation_pas_d_appel(self):
        self.assertIsNone(weather.get_daily_min_max(''))
        self.assertIsNone(weather.get_hourly_temperatures('', None, None))

    def test_fournisseur_injoignable_donne_le_repli(self):
        self.assertEqual(weather.gauge_bounds_for_temperature('Lyon'),
                         (weather.FALLBACK_MIN, weather.FALLBACK_MAX))

    def test_bornes_reelles_quand_le_fournisseur_repond(self):
        with mock.patch('api.weather._geocode_cached', return_value=(45.0, 4.0)), \
             mock.patch('api.weather._compute_daily_min_max', return_value=(3.0, 17.0)):
            self.assertEqual(weather.gauge_bounds_for_temperature('Lyon'), (3.0, 17.0))

    def test_cache_un_seul_calcul_pour_deux_lectures(self):
        with mock.patch('api.weather._compute_daily_min_max', return_value=(1.0, 2.0)) as calc:
            weather.get_daily_min_max('Lyon')
            weather.get_daily_min_max('Lyon')
            self.assertEqual(calc.call_count, 1)


class DashboardChartTests(SocleTestCase):
    """DashboardChartView : bornage à la période et superposition météo réservée
    aux grandeurs thermiques."""

    def setUp(self):
        super().setUp()
        self.s = self.sensor('int', location='interior', weather_location='Lyon')
        now = timezone.now()
        SensorReading.objects.create(sensor=self.s, timestamp=now, data={'temperature': 20})
        SensorReading.objects.create(sensor=self.s, timestamp=now, data={'humidity': 55})

    def test_la_meteo_ne_se_superpose_qu_aux_grandeurs_thermiques(self):
        with mock.patch('api.weather.get_hourly_temperatures', return_value=[(timezone.now(), 18.0)]) as gh:
            temp = self.dev.get(f'/api/dashboard/groups/sensor/{self.s.id}/chart/?field=temperature&period=day').json()
            hum = self.dev.get(f'/api/dashboard/groups/sensor/{self.s.id}/chart/?field=humidity&period=day').json()
        self.assertIsNotNone(temp['weather'])
        self.assertIsNone(hum['weather'])
        gh.assert_called()      # appelée pour la température, pas pour l'humidité
        self.assertEqual(gh.call_count, 1)

    def test_field_obligatoire_et_periode_validee(self):
        base = f'/api/dashboard/groups/sensor/{self.s.id}/chart/'
        self.assertEqual(self.dev.get(base).status_code, 400)
        self.assertEqual(self.dev.get(base + '?field=temperature&period=siecle').status_code, 400)

    def test_un_groupe_sans_acces_est_refuse(self):
        self.assertEqual(self.etranger.get(
            f'/api/dashboard/groups/sensor/{self.s.id}/chart/?field=temperature').status_code, 403)
