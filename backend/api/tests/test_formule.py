"""Lot 2 — évaluateur de formule sans eval (api/formula.py).

Une formule est saisie par tout titulaire d'un accès au capteur : elle ne doit
pouvoir ni exécuter de code, ni bloquer le serveur, et une formule refusée l'est
dès l'enregistrement (400), pas seulement au calcul.
"""
import math

from api.formula import MAX_FORMULA_LENGTH, FormulaError, compile_formula, safe_eval
from api.models import ComputedMeasure, SensorReading
from .socle import SocleTestCase

# Lectures réelles (relevées le 2026-10-31 dans la base en service, capteurs 3 et 5).
LECTURE_SHT = {'Ext': 1, 'Hum_SHT': 66.5, 'TempC_DS': 327.67, 'TempC_SHT': 16.42,
               'Systimestamp': 1793445450}
LECTURE_PILE = {'BatV': 3.128, 'Hum_SHT': 83.9, 'TempC_DS': 327.67, 'TempC_SHT': 9.39,
                'Bat_status': 3, 'Ext_sensor': 'Temperature Sensor'}

# Formules documentées (README, docs/GUIDE-LORA.md, aide de saisie du frontend,
# tests existants) et résultat attendu, calculé ici en Python ordinaire.
FORMULES_DOCUMENTEES = [
    ("row['TempC_SHT'] * 9 / 5 + 32", LECTURE_SHT, 16.42 * 9 / 5 + 32),
    ("row['TempC_SHT'] - (100 - row['Hum_SHT']) / 5", LECTURE_SHT, 16.42 - (100 - 66.5) / 5),
    ("(row['BatV'] - 2.5) / (3.6 - 2.5) * 100", LECTURE_PILE, (3.128 - 2.5) / (3.6 - 2.5) * 100),
    ("row['temperature'] * 9/5 + 32", {'temperature': 20}, 68.0),
    ("row['humidity'] / 100", {'humidity': 55}, 0.55),
    ("row['voltage'] * 3.3", {'voltage': 0.5}, 0.5 * 3.3),
    ("sqrt(row['x']**2 + row['y']**2)", {'x': 3, 'y': 4}, 5.0),
    ("row['t'] * 9/5 + 32", {'t': 100}, 212.0),
    ("row['t']*9/5+32", {'t': 100}, 212.0),
    ("sqrt(row['x'])", {'x': 16}, 4.0),
    ("max(row['a'], row['b'])", {'a': 1, 'b': 5}, 5.0),
    # Combinaisons admises par la nouvelle grammaire.
    ("round(log10(row['v']), 2)", {'v': 1234}, round(math.log10(1234), 2)),
    ("abs(min(row['a'], -2))", {'a': 1}, 2.0),
    ("row['t'] if row['t'] < 100 else 100", {'t': 327.67}, 100.0),
    ("1 if row['a'] > 0 and not row['b'] else 0", {'a': 1, 'b': 0}, 1.0),
    ("pi * row['r'] ** 2", {'r': 2}, math.pi * 4),
    ("row['o']['v'] + row['l'][1]", {'o': {'v': 1}, 'l': [10, 20]}, 21.0),
    ("2 ** 10", {}, 1024.0),
    ("-row['t'] % 7 // 2", {'t': 3}, float((-3 % 7) // 2)),
    ("0 < row['t'] <= 20", {'t': 16.42}, 1.0),
]

# Ce qui doit être refusé, à l'enregistrement comme au calcul.
FORMULES_REFUSEES = [
    "().__class__.__base__.__subclasses__()",
    "row.__class__",
    "(lambda: 1)()",
    "[x for x in ()]",
    "__import__('os').getcwd()",
    "open('/etc/passwd').read()",
    "eval('1')",
    "getattr(row, 'keys')",
    "row.get('t')",
    "row",
    "row[row]",
    "row['a'][row['b']]",
    "x",
    "'texte'",
    "'a' * 10",
    "[1, 2]",
    "{'a': 1}",
    "{1}",
    "(1, 2)",
    "sqrt(x=4)",
    "max(*row['l'])",
    "factorial(10)",
    "math.sqrt(4)",
    "(y := 3)",
    "f'{1}'",
    "1 if 1 in row else 0",
    "row['a'] is None",
    "1 << 3",
    "1 & 3",
    "~1",
    "def x(): pass",
    "import os",
    "1; 2",
    "",
    "   ",
    "1 +",
    "1" + "+1" * (MAX_FORMULA_LENGTH // 2),
]


class EvaluateurTests(SocleTestCase):

    def test_formules_documentees_meme_resultat(self):
        for f, row, attendu in FORMULES_DOCUMENTEES:
            with self.subTest(formule=f):
                self.assertAlmostEqual(safe_eval(f, row), attendu, places=9)

    def test_formules_refusees_par_la_validation(self):
        for f in FORMULES_REFUSEES:
            with self.subTest(formule=f):
                with self.assertRaises(FormulaError):
                    compile_formula(f)
                self.assertIsNone(safe_eval(f, {'a': 1, 'b': 2, 'l': [1, 2], 't': 1}))

    def test_erreurs_a_l_evaluation_rendent_none(self):
        for f, row in (("row['absent']", {}), ("1/0", {}), ("sqrt(-1)", {}),
                       ("row['s'] * 1000", {'s': 'texte'}), ("-row['s']", {'s': 'x'}),
                       ("row['l'][5]", {'l': [1]}), ("10 ** 400", {}), ("log(0)", {})):
            with self.subTest(formule=f):
                self.assertIsNone(safe_eval(f, row))

    def test_puissance_geante_ne_bloque_pas(self):
        # Avec eval, 9**9**9 calculait un entier de 370 millions de chiffres.
        self.assertIsNone(safe_eval("9 ** 9 ** 9", {}))
        self.assertIsNone(safe_eval("row['a'] ** row['b']", {'a': 10, 'b': 10 ** 6}))

    def test_champ_texte_converti_comme_avant(self):
        # Le résultat final reste passé à float(), comme avec l'ancien évaluateur.
        self.assertEqual(safe_eval("row['v']", {'v': '3.5'}), 3.5)
        self.assertEqual(safe_eval("row['ok']", {'ok': True}), 1.0)


class FormuleALEnregistrementTests(SocleTestCase):

    def setUp(self):
        super().setUp()
        self.s = self.sensor('a')
        self.donne_acces(self.s, 'ami@exemple.org')
        self.url = f'/api/sensors/{self.s.id}/measures/'

    def creer(self, client, formula):
        return client.post(self.url, {'sensor': self.s.id, 'name': 'G', 'formula': formula},
                           format='json')

    def test_formules_malveillantes_400_a_la_creation(self):
        for f in ("().__class__.__base__.__subclasses__()", "row.__class__",
                  "(lambda: 1)()", "[x for x in ()]"):
            for client in (self.ami, self.dev):
                with self.subTest(formule=f):
                    resp = self.creer(client, f)
                    self.assertEqual(resp.status_code, 400, resp.content)
                    self.assertIn('formula', resp.json())
        self.assertFalse(ComputedMeasure.objects.exists())

    def test_formule_trop_longue_400(self):
        resp = self.creer(self.ami, "1" + "+1" * MAX_FORMULA_LENGTH)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('formula', resp.json())

    def test_formule_valide_acceptee(self):
        resp = self.creer(self.ami, "row['TempC_SHT'] * 9 / 5 + 32")
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_modification_vers_une_formule_refusee_400(self):
        m = ComputedMeasure.objects.create(sensor=self.s, name='F', formula="row['t']")
        url = f'/api/measures/{m.id}/'
        for f in ("().__class__.__base__.__subclasses__()", "row.__class__"):
            with self.subTest(formule=f):
                self.assertEqual(self.ami.patch(url, {'formula': f}, format='json').status_code, 400)
                self.assertEqual(self.ami.put(url, {'sensor': self.s.id, 'name': 'F', 'formula': f},
                                              format='json').status_code, 400)
        m.refresh_from_db()
        self.assertEqual(m.formula, "row['t']")

    def test_formule_refusee_deja_en_base_ne_donne_aucun_point(self):
        # Une formule écrite avant la validation (ou directement en base) :
        # le calcul rend une courbe vide, sans erreur ni exécution.
        m = ComputedMeasure.objects.create(sensor=self.s, name='F',
                                           formula="().__class__.__base__.__subclasses__()")
        SensorReading.objects.create(sensor=self.s, timestamp='2026-01-01T00:00:00Z', data={'t': 1})
        resp = self.ami.get(f'/api/measures/{m.id}/compute/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['points'], [])

    def test_compute_saute_les_lectures_en_erreur(self):
        m = ComputedMeasure.objects.create(sensor=self.s, name='F', formula="row['t'] * 2")
        SensorReading.objects.create(sensor=self.s, timestamp='2026-01-01T00:00:00Z', data={'t': 1})
        SensorReading.objects.create(sensor=self.s, timestamp='2026-01-02T00:00:00Z', data={'u': 1})
        SensorReading.objects.create(sensor=self.s, timestamp='2026-01-03T00:00:00Z', data={'t': 4})
        points = self.ami.get(f'/api/measures/{m.id}/compute/').json()['points']
        self.assertEqual([p['v'] for p in points], [2.0, 8.0])
