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

```bash
bash setup2.sh analyse-lora --yes
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
| `GET` `PUT` `DELETE` | `/api/sensors/<id>/` | Détail d'un capteur |
| **`POST`** | **`/api/sensors/<id>/data/`** | **Ingestion d'une mesure** |
| `GET` | `/api/sensors/<id>/data/` | Lectures paginées (`start`, `end`, `page`, `page_size` ≤ 1000) |
| `GET` `PUT` | `/api/sensors/<id>/connection/` | Config de connexion + guide + `api_key` |
| `GET` | `/api/connection-methods/` | Tous les guides de connexion |
| `GET` `POST` | `/api/sensors/<id>/users/` | Accès utilisateurs (developers) |
| `GET` `POST` | `/api/sensors/<id>/measures/` | Grandeurs calculées |
| `GET` | `/api/measures/<id>/compute/` | Évaluer la formule sur une plage |

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

L'évaluation est sandboxée (`__builtins__` vidé, seules les fonctions du module `math` sont
exposées) et renvoie `None` en cas d'erreur — une formule fausse produit une courbe vide, pas une
exception. **Les noms de champs dépendent de votre décodeur** : regardez le premier uplink reçu
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
