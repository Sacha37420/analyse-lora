# analyse-lora

Collecte, stockage et exploitation de mesures de capteurs LoRaWAN (et de toute source poussant du JSON).
Django REST + Angular, authentification Keycloak (realm `ssolab`).

Ports : **8086** (backend) / **4204** (frontend).

> 📖 **Vous débutez avec LoRa ?** Le guide complet — comprendre la techno, choisir et acheter un
> capteur, l'enregistrer sur The Things Network, le brancher ici — est dans
> **[docs/GUIDE-LORA.md](docs/GUIDE-LORA.md)**.

---

## Ce que fait l'application

1. On déclare un **capteur** (`Sensor`) : un nom, un slug, un protocole, et une `api_key` générée
   automatiquement.
2. Le réseau LoRa (TTN, ChirpStack, Helium…) **pousse ses uplinks** sur l'endpoint d'ingestion,
   authentifié par cette `api_key`.
3. Chaque uplink est stocké tel quel en JSON (`SensorReading.data`) — aucun schéma imposé.
4. On définit des **grandeurs calculées** (`ComputedMeasure`) : une formule Python évaluée sur chaque
   mesure, pour tracer des courbes dérivées (conversion d'unité, point de rosée, moyenne glissante…).

La chaîne complète, du capteur à l'écran :

```
Capteur LoRaWAN  ──radio 868 MHz──►  Passerelle  ──IP──►  Serveur réseau (TTN / ChirpStack)
                                                                      │
                                                            webhook HTTP POST
                                                                      ▼
                                          analyse-lora  ──►  PostgreSQL  ──►  Angular
```

---

## Démarrage

Depuis la racine du lab :

```bash
bash scripts/setup2.sh analyse-lora --yes
```

Le script enchaîne le nettoyage des containers, la propagation des URLs, le démarrage de sso-lab,
la création/mise à jour du client Keycloak, puis le build. **Ne pas appeler `recompose_docker.sh`
directement.**

---

## API

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/me/` | Utilisateur courant (email, groupes) |
| `GET` `POST` | `/api/sensors/` | Lister / créer un capteur |
| `GET` `PUT` `PATCH` `DELETE` | `/api/sensors/<id>/` | Détail d'un capteur |
| **`POST`** | **`/api/sensors/<id>/data/`** | **Ingestion d'une mesure** |
| `GET` | `/api/sensors/<id>/data/` | Lectures paginées (`start`, `end`, `page`, `page_size` ≤ 1000) |
| `GET` `PUT` | `/api/sensors/<id>/connection/` | Config de connexion + guide + `api_key` |
| `GET` | `/api/connection-methods/` | Tous les guides de connexion |
| `GET` `POST` | `/api/sensors/<id>/users/` | Accès utilisateurs (developers) |
| `DELETE` | `/api/sensors/<id>/users/<email>/` | Retirer un accès (developers) |
| `GET` `POST` | `/api/webhooks/` | Webhooks : points d'ingestion partagés par plusieurs capteurs (developers) |
| `GET` `PUT` `PATCH` `DELETE` | `/api/webhooks/<id>/` | Détail d'un webhook (developers) |
| **`POST`** | **`/api/webhooks/<id>/data/`** | **Ingestion partagée** : l'uplink est routé vers le capteur d'après l'identifiant de device |
| `GET` `POST` | `/api/webhooks/<id>/users/` | Accès utilisateurs au webhook (developers) |
| `DELETE` | `/api/webhooks/<id>/users/<email>/` | Retirer un accès (developers) |
| `GET` `POST` | `/api/sensors/<id>/measures/` | Grandeurs calculées |
| `GET` `PUT` `PATCH` `DELETE` | `/api/measures/<id>/` | Détail d'une grandeur calculée |
| `GET` | `/api/measures/<id>/compute/` | Évaluer la formule sur une plage |
| `GET` | `/api/dashboard/groups/` | Groupes du tableau de bord (webhook ou capteur autonome) |
| `GET` | `/api/dashboard/groups/<type>/<id>/fields/`, `…/chart/`, `…/gauges/` | Champs, courbes et jauges d'un groupe |
| `POST` | `/api/dashboard/groups/<type>/<id>/ttn-backfill/` | Combler les trous depuis TTN (developers) |

Derrière Caddy (avec un domaine), l'API est servie sous `/lora-api` : une route `/api/…` du
tableau se joint à `https://<domaine>/lora-api/api/…`, et l'app elle-même à `https://<domaine>/lora/`.

### Combler les trous depuis TTN

Le webhook TTN ne rejoue jamais un uplink qu'il n'a pas pu livrer (backend arrêté, base
injoignable…). Le bouton **« Combler les trous depuis TTN »** du tableau de bord (developers,
groupes en protocole TTN) relit les uplinks conservés par la **Storage Integration** de TTN et
insère ceux absents de la base — déduplication par horodatage exact, relançable sans risque.

Prérequis côté TTN : Storage Integration activée sur l'application (Console → Integrations →
Storage Integration), et clé API TTN renseignée sur le webhook avec le droit *Read application
traffic*. Rétention courte sur la Community Edition (~2 jours constatés) : un trou plus ancien
n'est pas récupérable. Code : `backend/api/ttn.py`.

---

## Ingestion — le point important

**L'endpoint est `POST /api/sensors/<id>/data/`**, où `<id>` est l'identifiant numérique du capteur.
L'URL exacte, prête à copier, est affichée dans l'app (page *Connexion* du capteur) et renvoyée par
`GET /api/sensors/<id>/connection/` dans le champ `api_ingest_url`.

L'authentification se fait par la clé du capteur, **au choix** :

```
Authorization: Bearer <api_key>
X-API-Key: <api_key>
```

Un JWT Keycloak valide fonctionne également (pratique pour tester depuis le frontend).

Test en ligne de commande :

```bash
curl -X POST http://localhost:8086/api/sensors/1/data/ \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"timestamp": "2026-07-14T10:00:00Z", "data": {"temperature": 21.5, "humidity": 48}}'
```

### Formats acceptés

`_normalize_payload()` reconnaît trois formes et en extrait `(timestamp, data)` :

| Détection | Timestamp lu dans | Données lues dans |
|---|---|---|
| clé `uplink_message` → **TTN v3** | `uplink_message.received_at` | `uplink_message.decoded_payload` |
| clé `deviceInfo` → **ChirpStack v4** | `time` | `object` |
| sinon → **format standard** | `timestamp` | `data` (ou le corps entier) |

Un webhook TTN ou ChirpStack se branche donc **sans aucune transformation intermédiaire**. À une
condition : que le **payload formatter** soit configuré côté réseau, sinon `decoded_payload` est
absent et la mesure arrive vide.

---

## Grandeurs calculées

Une `ComputedMeasure` porte une `formula` : une expression Python évaluée sur chaque lecture, où
`row` est le dictionnaire `SensorReading.data`.

```python
row['temperature'] * 9 / 5 + 32          # °C → °F
row['TempC_SHT'] - (100 - row['Hum_SHT']) / 5   # point de rosée (approximation)
sqrt(row['x']**2 + row['y']**2)
```

La formule n'est **jamais passée à `eval`** : elle est analysée puis parcourue nœud par nœud
(`backend/api/formula.py`). Sont admis : nombres, `row['champ']` (clé écrite en clair, imbrication
`row['a']['b']` comprise), `+ - * / // % **`, comparaisons, `and`/`or`/`not`, `a if c else b`, les
fonctions de `math` (sauf `factorial`, `comb`, `perm`) et `abs`, `round`, `min`, `max`, les
constantes `pi`, `e`, `tau`, `inf`, `nan`. Tout le reste (attributs, lambdas, compréhensions,
chaînes hors clé, arguments nommés…) est refusé **dès l'enregistrement** (400, champ `formula`),
comme une formule de plus de 500 caractères. À l'évaluation, une erreur rend `None` — une formule
fausse produit une courbe vide, pas une exception.

**Les noms de champs dépendent de votre décodeur** : regardez le premier uplink reçu
avant d'écrire une formule.

---

## Accès et sécurité

- Toute l'API (hors ingestion par `api_key`) exige un JWT Keycloak valide.
- Le backend vérifie le claim `azp` **et** le claim `groups` — voir le `CLAUDE.md` du dépôt parent.
- Le groupe **`developers`** voit et administre tous les capteurs.
- Les autres utilisateurs ne voient que les capteurs auxquels un developer leur a donné accès
  explicitement (`SensorUserAccess`, par adresse e-mail).
- L'`api_key` d'un capteur donne un accès **direct en lecture et en écriture** à ses mesures, sans
  passer par Keycloak. Elle est faite pour être collée dans un webhook — traitez-la comme un secret.
  Seuls les `developers` la reçoivent : hors de ce groupe, la fiche capteur et
  `/api/sensors/:id/connection/` ne rendent ni `api_key`, ni `connection_config`, ni la liste des
  autres titulaires (`user_accesses`).
