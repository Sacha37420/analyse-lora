"""Lot 3 — fiche capteur selon le rôle.

Hors `developers`, la fiche ne rend ni `api_key` (elle permet d'injecter des
mesures), ni `connection_config`, ni `user_accesses` (les autres titulaires).
Même règle pour /api/sensors/:id/connection/, qui rendait aussi la clé.
"""
from .socle import SocleTestCase

CHAMPS_RESERVES = ('api_key', 'connection_config', 'user_accesses')


class FicheCapteurTests(SocleTestCase):

    def setUp(self):
        super().setUp()
        self.wh = self.webhook('app1', 'ttn')
        self.par_webhook = self.sensor('w1', protocol='ttn', webhook=self.wh,
                                       connection_config={'device_id': 'dev-1'})
        self.direct = self.sensor('d1', connection_config={'device_id': 'dev-2'})
        self.donne_acces_webhook(self.wh, 'ami@exemple.org')
        self.donne_acces(self.direct, 'ami@exemple.org')
        self.donne_acces(self.direct, 'autre@exemple.org')

    def fiche(self, client, sensor):
        resp = client.get(f'/api/sensors/{sensor.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def test_acces_webhook_ne_recoit_aucun_champ_reserve(self):
        body = self.fiche(self.ami, self.par_webhook)
        for champ in CHAMPS_RESERVES:
            self.assertNotIn(champ, body)
        # La fiche reste utilisable par les pages de lecture.
        for champ in ('id', 'name', 'protocol_display', 'reading_count'):
            self.assertIn(champ, body)

    def test_acces_direct_ne_recoit_aucun_champ_reserve(self):
        body = self.fiche(self.ami, self.direct)
        for champ in CHAMPS_RESERVES:
            self.assertNotIn(champ, body)
        self.assertNotIn('autre@exemple.org', str(body))
        self.assertNotIn(self.direct.api_key, str(body))

    def test_un_developer_recoit_les_trois_champs(self):
        body = self.fiche(self.dev, self.direct)
        self.assertEqual(body['api_key'], self.direct.api_key)
        self.assertEqual(body['connection_config'], {'device_id': 'dev-2'})
        self.assertEqual(sorted(a['user_email'] for a in body['user_accesses']),
                         ['ami@exemple.org', 'autre@exemple.org'])

    def test_liste_des_capteurs_sans_champ_reserve(self):
        resp = self.ami.get('/api/sensors/')
        self.assertEqual(resp.status_code, 200)
        for s in resp.json():
            for champ in CHAMPS_RESERVES:
                self.assertNotIn(champ, s)

    def test_connexion_sans_cle_hors_developers(self):
        for sensor in (self.par_webhook, self.direct):
            with self.subTest(capteur=sensor.slug):
                resp = self.ami.get(f'/api/sensors/{sensor.id}/connection/')
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertNotIn('api_key', body)
                self.assertNotIn('connection_config', body)
                self.assertNotIn(sensor.api_key, str(body))

    def test_connexion_complete_pour_un_developer(self):
        body = self.dev.get(f'/api/sensors/{self.direct.id}/connection/').json()
        self.assertEqual(body['api_key'], self.direct.api_key)
        self.assertEqual(body['connection_config'], {'device_id': 'dev-2'})

    def test_cle_lue_hors_developers_n_existe_plus(self):
        # Cas négatif de bout en bout : sans la clé, un accès en lecture ne peut
        # plus injecter de mesure (il ne la reçoit d'aucune route).
        textes = [str(self.ami.get(u).json()) for u in (
            f'/api/sensors/{self.direct.id}/', f'/api/sensors/{self.direct.id}/connection/',
            '/api/sensors/')]
        for t in textes:
            self.assertNotIn(self.direct.api_key, t)
            self.assertNotIn(self.par_webhook.api_key, t)
