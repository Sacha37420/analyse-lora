# Guide LoRa — de l'achat du capteur à la courbe à l'écran

Guide complet pour débuter : comprendre la technologie, choisir et acheter le bon matériel,
enregistrer le capteur sur un réseau, et le brancher sur **analyse-lora**.

Aucun prérequis en radio. Comptez **un week-end** pour aller du carton à la première courbe.

---

## Sommaire

1. [Comprendre ce qu'est vraiment un capteur LoRa](#1-comprendre-ce-quest-vraiment-un-capteur-lora)
2. [Qui peut lire mes données ?](#2-qui-peut-lire-mes-données-)
3. [Choisir son matériel](#3-choisir-son-matériel)
4. [Checklist d'achat](#4-checklist-dachat)
5. [Installation : connecter sa passerelle à TTN](#5-installation--connecter-sa-passerelle-à-ttn)
6. [Installation : enregistrer le capteur sur TTN](#6-installation--enregistrer-le-capteur-sur-ttn)
7. [Le payload formatter — l'étape qu'on oublie](#7-le-payload-formatter--létape-quon-oublie)
8. [Brancher le capteur sur analyse-lora](#8-brancher-le-capteur-sur-analyse-lora)
9. [Créer des grandeurs calculées](#9-créer-des-grandeurs-calculées)
10. [Changer les clés (commandes AT)](#10-changer-les-clés-commandes-at)
11. [Dépannage](#11-dépannage)
12. [Aller plus loin : ChirpStack auto-hébergé](#12-aller-plus-loin--chirpstack-auto-hébergé)
13. [Sources](#13-sources)

---

## 1. Comprendre ce qu'est vraiment un capteur LoRa

### LoRa ≠ LoRaWAN

Deux mots qu'on confond en permanence, et toute la suite en dépend :

- **LoRa** est une *modulation radio* (propriété de Semtech) qui travaille dans les bandes libres
  sub-GHz — **868 MHz en Europe**. Sa particularité : elle sait décoder un signal noyé sous le bruit
  ambiant, d'où une portée énorme pour une puissance ridicule.
- **LoRaWAN** est le *protocole réseau* posé au-dessus : identités, chiffrement, gestion des
  passerelles, adaptation du débit.

**Le chiffrement est dans LoRaWAN, pas dans LoRa.** Retenez-le : c'est la source du malentendu de
sécurité le plus fréquent (voir §2).

### Ce qu'il y a dans le boîtier

Quatre choses : un microcontrôleur basse consommation, une puce radio (typiquement un **SX1262**),
le capteur proprement dit, et une pile. C'est tout.

### Des caractéristiques extrêmes, dans les deux sens

| | Réalité |
|---|---|
| Portée | 2–5 km en ville, 10–15 km en terrain dégagé |
| Autonomie | 2 à 10 ans sur pile |
| Débit | quelques dizaines d'octets par message, quelques messages par heure |

Ce dernier point est le plus mal compris. **LoRa n'est pas un Wi-Fi lent, c'est un autre métier.**
On n'envoie pas un fichier, on envoie 10 octets toutes les quinze minutes.

Deux limites vous encadrent, et elles ne sont pas négociables :

- **Duty cycle légal de 1 %** sur la bande 868 MHz : votre capteur n'a le droit d'émettre qu'environ
  **36 secondes par heure**.
- **Fair Use Policy de TTN** : ~30 secondes de temps d'antenne par jour en montant, et **10 downlinks
  par jour** maximum.

Conséquence pratique : n'émettez pas « toutes les 10 secondes pour tester ». Vous vous feriez taire.

### La chaîne complète

```
Capteur  ──radio 868 MHz──►  Passerelle  ──IP──►  Serveur réseau  ──webhook──►  analyse-lora
(pile)                       (gateway)             (TTN/ChirpStack)              (votre app)
```

Notez qu'il existe aussi le **LoRa point-à-point** (deux modules qui se parlent directement, sans
aucune infrastructure) et **Meshtastic** (un réseau maillé, façon talkie-walkie). Autres usages,
sans serveur réseau — et **sans chiffrement par défaut**.

### Quand LoRa est le *mauvais* choix

Si votre besoin est à 20 mètres avec une prise de courant à côté, **prenez du Zigbee, du BLE ou du
Wi-Fi**. LoRa ne brille que quand il n'y a ni réseau ni électricité : le fond du jardin, la cave,
une cabane, une ruche, un compteur d'eau, un champ.

---

## 2. Qui peut lire mes données ?

### Oui, n'importe qui peut *capter* les trames

Le 868 MHz est une bande libre, en clair dans l'air. Toute personne équipée d'un récepteur LoRa (une
carte à 20 €) et située à portée capte vos paquets. Il n'y a rien à « pirater » : c'est une diffusion
radio publique.

C'est d'ailleurs le principe *assumé* de The Things Network — ce sont les passerelles d'inconnus qui
relaient vos capteurs.

### Mais le contenu est chiffré de bout en bout

LoRaWAN chiffre la charge utile en **AES-128** avec une clé (`AppSKey`) que seuls le capteur et le
serveur applicatif possèdent. Ni la passerelle ni le serveur réseau ne peuvent la lire. Un attaquant
ne peut ni lire, ni injecter une fausse mesure, ni rejouer un ancien message (les compteurs de
trames l'interdisent).

### Ce qui fuite quand même : les métadonnées

L'adresse du capteur (`DevAddr`, stable, donc **traçable**), l'horodatage et la fréquence des
émissions, la taille des messages, et la puissance reçue — donc une **localisation approximative**
par triangulation.

Personne ne saura que votre cave est à 14 °C. Mais quelqu'un pourra savoir qu'un appareil donné a
émis, à tel moment, depuis à peu près tel endroit. Pour un tracker GPS, ce n'est pas anodin.

### Les trois cas où il n'y a réellement *aucune* protection

Ce sont précisément les configurations d'un débutant :

1. **Le LoRa point-à-point maison.** Si vous flashez un Heltec avec RadioLib et envoyez `"temp=21.5"`
   en brut, sans LoRaWAN : **c'est en clair, lisible par tout le monde, à 10 km.**
2. **Meshtastic sur le canal par défaut.** La clé du canal public est publique et documentée. Créez
   un canal privé.
3. **L'ABP avec compteurs remis à zéro.** La faille historique de LoRaWAN : rejeu et réutilisation du
   flux de chiffrement. **Utilisez toujours OTAA, jamais ABP.**

### Le point à connaître sur TTN

Sur **TTN Community, c'est TTN qui détient votre `AppSKey`** — donc TTN peut lire vos données en
clair. Ce n'est pas une faille, c'est le contrat du service gratuit. Si ça vous dérange, la réponse
est ChirpStack auto-hébergé (§12).

### Et le brouillage

**Rien ne protège du brouillage.** La bande ISM est libre, un brouilleur fait taire vos capteurs, et
LoRaWAN n'a aucune parade. Si votre usage est une alarme, ne comptez **jamais** sur l'absence de
message comme preuve que tout va bien : surveillez l'absence de *heartbeat* et traitez-la comme une
alerte.

---

## 3. Choisir son matériel

### Le capteur : LHT52 ou LHT65N ?

Les deux sont des Dragino, la marque de référence pour débuter. Ils ne jouent pas dans la même
catégorie.

| | **Dragino LHT52** | **Dragino LHT65N** |
|---|---|---|
| Taille | 58 × 58 × 20 mm | 135 × 70 × 30 mm, 105 g |
| Pile | 2 × AAA alcalines (remplaçables partout) | Li-SOCl₂ 2400 mAh, jusqu'à 10 ans |
| Étanchéité | IP52 — **intérieur uniquement** | robuste, prévu pour l'extérieur |
| Sonde externe | une sonde temp. en option (port USB-C) | **écosystème complet** (voir ci-dessous) |
| Datalog | oui | oui (3200 mesures) |
| Prix indicatif | ~25–35 € | ~40–50 € |

**La pile est le vrai sujet technique.** Le Li-SOCl₂ du LHT65N tient une tension parfaitement plate
jusqu'à épuisement et fonctionne jusqu'à −40 °C. Une pile alcaline AAA s'effondre au froid et encaisse
mal les pics de courant d'une émission LoRa. C'est *pour cela* que le LHT52 est un capteur
d'intérieur, pas seulement parce que son boîtier est IP52.

> ⚠️ Les « 10 ans » sont annoncés à intervalle d'émission très long. Il existe un fil entier sur le
> forum TTN intitulé *« LHT65 — disappointing battery life »*. Émettez toutes les 5 minutes en SF12
> et vous tiendrez des mois, pas des années.

**Le port externe du LHT65N est sa vraie raison d'être.** Ce n'est pas un thermomètre, c'est une
*plateforme* :

| Sonde | Usage |
|---|---|
| E1 / E3 | sonde DS18B20 déportée (1 m / 2 m plate) |
| **E2** | câble 5 fils : **interruption, ADC, comptage d'impulsions** |
| E5 | capteur de luminosité BH1750 |

C'est le **E2** qui fait la différence : contact reed, compteur d'eau à impulsions, sonde analogique.

#### Verdict

Posez-vous une seule question : **mesurer une température, ou disposer d'une plateforme pour
bricoler ?**

- **LHT52** — mesurer l'ambiance d'une pièce, voir des données arriver, apprendre. Moins cher,
  discret, piles trouvables en supermarché. **C'est le bon premier achat.**
- **LHT65N** — si vous savez déjà que vous voudrez mesurer dehors, au froid, déporter une sonde, ou
  compter des impulsions sur le port E2.

Et si l'envie de bricoler vient ensuite, un **Heltec V3 à 20 €** vous donnera bien plus de liberté
qu'un LHT65N, pour moins cher.

### La passerelle : en avez-vous seulement besoin ?

**Vérifiez d'abord la couverture** sur la carte TTN ou sur [ttnmapper.org](https://ttnmapper.org).
Si vous êtes couvert, vous n'avez **rien** à acheter.

Sinon, une passerelle intérieure suffit — et une seule chez vous peut couvrir tout un quartier :

| Modèle | Prix indicatif |
|---|---|
| **SenseCAP M2** (Seeed) | ~119 € — WiFi + Ethernet + PoE, TTN/ChirpStack pris en charge nativement |
| Dragino LPS8v2 | ~100–130 € |
| RAK7268 | ~130–150 € |
| Mikrotik wAP LR8 | ~120 € |
| Concentrateur RAK2287 sur Raspberry Pi | ~80 € + le Pi |

> ⛔ **Fuyez les « single channel gateways » à 15 €.** Elles ne sont pas conformes à LoRaWAN et vous
> passerez vos soirées à débugger des fantômes.

### Le DIY

| Carte | Pour quoi |
|---|---|
| **Heltec WiFi LoRa 32 V3** (~20 €) | ESP32-S3 + SX1262 + écran OLED. Parfait pour apprendre. |
| **LilyGO T3S3** | équivalent, autres formats |
| **RAK4631** (WisBlock) | nRF52840 + SX1262, **modulaire, vraiment basse conso** |
| **LoRa-E5** | STM32WL — radio intégrée au microcontrôleur |

**Le piège :** un ESP32 (Heltec, LilyGO) consomme trop pour tenir des années sur pile. Excellent pour
apprendre, inadapté à un capteur autonome. Pour du déploiement réel : RAK4631 ou LoRa-E5.

Côté logiciel, **RadioLib** est aujourd'hui la bibliothèque de référence et gère LoRaWAN proprement.

### Budget de départ

| Scénario | Coût |
|---|---|
| Couvert par TTN, juste un capteur | **~30 €** |
| Non couvert : capteur + passerelle | **~150–180 €** |
| Ajout DIY (Heltec + adaptateur AT) | **+ ~35 €** |

*Prix indicatifs — à revérifier, ils bougent.*

---

## 4. Checklist d'achat

- [ ] **Fréquence : EU868.** Un module 915 MHz (version américaine, souvent moins chère) est
      **illégal en France** et ne joindra jamais aucune passerelle. C'est l'erreur n°1.
- [ ] **Ne jamais alimenter un module LoRa sans antenne connectée** — vous grillez l'étage de
      puissance en quelques secondes.
- [ ] Pas de « single channel gateway ».
- [ ] Vérifier la couverture TTN **avant** d'acheter une passerelle.
- [ ] Garder précieusement l'**autocollant dans la boîte** : il porte vos clés (§6).

---

## 5. Installation : connecter sa passerelle à TTN

*(Si la couverture TTN suffisait déjà chez vous — §3 —, vous n'avez rien acheté ni à connecter :
passez directement à la section suivante.)*

### Le principe : la passerelle ne détient aucun secret

Contrairement au capteur (§6), **la passerelle ne contient aucune clé cryptographique**. Elle n'a
qu'un seul identifiant public, le **Gateway EUI** (imprimé sur son étiquette, comme le DevEUI d'un
capteur) — rien d'équivalent à l'AppKey. Son rôle se limite à faire transiter les trames radio
868 MHz vers TTN en IP, sans jamais rien déchiffrer ni signer. C'est précisément ce qui permet de
relayer sans risque les capteurs d'inconnus sur une passerelle TTN publique (§2) : elle ne peut
techniquement rien lire de ce qu'elle transporte.

### Deux protocoles de liaison passerelle → TTN, un seul à retenir

| Protocole | Port | Sécurité | À utiliser ? |
|---|---|---|---|
| **Packet Forwarder** (Semtech UDP, historique) | 1700/UDP | Aucune — ni chiffrement ni authentification | Non, sauf compatibilité forcée avec un vieux matériel |
| **Basic Station** (LNS, WebSocket) | 8887/TCP (TLS) | Authentifié par clé API, chiffré TLS | **Oui, toujours** |

En Packet Forwarder, n'importe qui connaissant l'adresse IP de votre passerelle peut usurper son
identité auprès de TTN. Vos mesures resteraient illisibles (chiffrement AppKey, toujours en place,
§2), mais un tiers pourrait injecter du faux trafic sous le nom de votre passerelle. Basic Station
est le mode recommandé par TTN depuis plusieurs années ; toute passerelle récente le propose,
dont la SenseCAP M2.

### Procédure (exemple SenseCAP M2 — transposable à toute passerelle Basic Station)

> ⚠️ **À vérifier à réception du matériel.** L'IP `192.168.168.1`, le chemin de menu
> `LoRa → LoRa Network` et le nom exact des champs (étapes 3-4) viennent de guides tiers
> (ThinkRobotics, wikis communautaires) recoupés entre eux — pas du PDF constructeur lui-même
> (illisible à l'extraction automatique, lien en §13). Le principe et les valeurs de connexion TTN
> (LNS Server URI, port 8887, certificat) sont fiables : c'est le standard Basic Station documenté
> par TTN, indépendant du fabricant. Seuls l'IP et les intitulés de menu pourraient différer selon
> la version de firmware livrée — si c'est le cas, suivez l'appli **SenseCAP Mate** (QR code de
> l'étiquette) qui vous guidera avec l'interface réelle de votre unité, ou le PDF officiel en §13.

1. **Enregistrez d'abord la passerelle côté TTN**, avant même de la configurer physiquement :
   console *The Things Stack Community* → **Gateways → Register gateway**.
   - **Gateway EUI** : recopiez celui imprimé sur l'étiquette du boîtier.
   - **Gateway ID** : un identifiant à vous (minuscules, chiffres, tirets).
   - **Frequency plan** : `Europe 863-870 MHz (SF9 for RX2 — recommended)` — le même plan que celui
     du capteur (§6).
2. **Générez une clé API dédiée** : sur la page de la gateway tout juste créée →
   **API keys → Add API key** → cochez uniquement le droit **« Link as Gateway »**, rien de plus.
   Copiez la clé immédiatement, elle ne sera plus jamais réaffichée en clair.
3. **Accédez à la console locale de la passerelle** : la SenseCAP M2 démarre en point d'accès WiFi —
   connectez-vous à son réseau puis ouvrez `192.168.168.1` dans un navigateur (ou utilisez l'appli
   mobile **SenseCAP Mate**, qui fait la même chose via le QR code de l'étiquette). Configurez
   d'abord sa sortie réseau : WiFi vers votre box, ou câble Ethernet.
4. **Dans la console locale : `LoRa → LoRa Network`**, réglez :

   | Champ | Valeur |
   |---|---|
   | Mode | **Basic Station** |
   | LNS Server URI | `wss://eu1.cloud.thethings.network:8887` |
   | TLS server authentication | activé |
   | Certificat | **Let's Encrypt ISRG Root X1** (proposé par défaut dans la liste) |
   | Authorization / API Key | la clé générée à l'étape 2 |

   > 💡 `eu1` est le nom du **cluster Europe** de TTN Community — c'est celui qu'il faut en France.
   > Ce n'est pas un plan de fréquences, juste l'adresse du serveur ; ne le confondez pas avec
   > `Europe 863-870 MHz` de l'étape 1, qui est un réglage différent.

5. **Vérifiez** : dans la console TTN, la page de la gateway doit passer à **« connected »** en
   quelques secondes (onglet *Live Data* **de la gateway**, pas celui du capteur — les deux sont
   distincts). Si rien ne se passe, voir §11.

> ⚠️ **Gateway EUI ≠ DevEUI**, et **clé API de la passerelle ≠ AppKey du capteur** (§6). Ce sont
> deux paires d'identifiants pour deux usages différents — authentifier une connexion réseau contre
> chiffrer une charge utile. Les confondre enregistre le mauvais identifiant au mauvais endroit,
> sans message d'erreur explicite.

---

## 6. Installation : enregistrer le capteur sur TTN

### Le principe : vous ne créez pas les clés, vous les recopiez

Contre-intuitif, mais c'est le cœur du sujet : **un capteur LoRaWAN commercial arrive déjà
provisionné en usine.** Ses identifiants sont imprimés sur un autocollant, dans la boîte. Le travail
consiste à **copier les clés du capteur vers le serveur réseau** — jamais l'inverse. Vous ne touchez
pas au capteur : vous lui mettez les piles, point.

Trois identifiants figurent sur l'étiquette :

| Identifiant | Rôle | Secret ? |
|---|---|---|
| **DevEUI** | 64 bits — l'identité unique du capteur (une sorte d'adresse MAC) | non |
| **JoinEUI** (ex-AppEUI) | 64 bits — désigne l'application / serveur de join | non |
| **AppKey** | 128 bits — **la** clé racine | **oui, absolument** |

### Ce qui se passe au premier allumage (OTAA)

Le capteur diffuse une *JoinRequest* contenant son DevEUI, son JoinEUI et un aléa, signée avec
l'AppKey. Le serveur réseau reconnaît le DevEUI, retrouve l'AppKey que vous y avez saisie, vérifie la
signature, et répond une *JoinAccept*.

À partir de là, **les deux côtés dérivent tout seuls les clés de session** (`NwkSKey` et `AppSKey`,
celles qui chiffrent réellement vos mesures) ainsi qu'une adresse `DevAddr`. Personne ne les saisit
jamais, et elles sont régénérées à chaque nouveau join.

C'est exactement pour ça qu'OTAA est sûr et qu'ABP ne l'est pas : en ABP, on écrit les clés de session
en dur, à la main, une fois pour toutes.

### La procédure

1. Créez un compte sur **[The Things Stack Community](https://console.cloud.thethings.network)**
   (gratuit) et choisissez le cluster **Europe 1**.
2. **Create an application** (ex. `lab-capteurs`).
3. **Register end device** → choisissez **« From the LoRaWAN Device Repository »** → marque
   **Dragino**, modèle **LHT52** (ou LHT65N), version matérielle/firmware, profil **EU_863_870**.

   > ⚠️ **Ne sautez pas cette étape au profit d'une saisie manuelle.** Le Device Repository configure
   > le profil radio **et installe automatiquement le décodeur de payload** (§7). C'est deux heures
   > de gagnées.

4. **Frequency plan** : `Europe 863-870 MHz (SF9 for RX2 — recommended)`.
5. Recopiez **JoinEUI, DevEUI et AppKey** depuis l'autocollant — ou **scannez le QR code** de la
   boîte, qui remplit tout.
6. **Mettez les piles.** La *JoinRequest* apparaît dans l'onglet **Live Data** en quelques secondes,
   suivie du premier uplink.

> 💡 Les clés se saisissent en **MSB** — c'est l'ordre dans lequel Dragino les imprime et celui que
> TTN attend par défaut. Ne les inversez pas.

---

## 7. Le payload formatter — l'étape qu'on oublie

Un capteur LoRaWAN n'envoie pas du JSON. Il envoie **une poignée d'octets binaires**, compressés à
l'extrême (le duty cycle, souvenez-vous).

Sans décodeur, TTN vous montre du base64 illisible, `decoded_payload` est absent, et **analyse-lora
enregistre une mesure vide**. C'est le symptôme n°1 des débuts.

Le **payload formatter** est un petit script JavaScript, côté TTN, qui transforme :

```
0B 45 01 E4 03 12 ...      →      { "TempC_SHT": 21.5, "Hum_SHT": 48.2, "BatV": 3.6 }
```

**Vous n'avez pas à l'écrire** : si vous avez enregistré le device via le *Device Repository* (§6,
étape 3), il est déjà installé. Sinon, récupérez-le sur le wiki Dragino et collez-le dans
*Payload formatters → Uplink → Custom JavaScript formatter*.

> ⚠️ **Les noms de champs produits dépendent du décodeur et du modèle.** Ne les devinez pas :
> regardez le premier uplink dans *Live Data*, et utilisez les noms que vous y lisez. Ce sont eux
> qui arriveront dans `SensorReading.data`, et donc eux que vous emploierez dans vos formules (§9).

---

## 8. Brancher le capteur sur analyse-lora

### 7.1 — Créer le capteur dans l'app

Connectez-vous à analyse-lora avec un compte du groupe **`developers`**, puis créez un capteur :

- **Nom** : `Cave` (par exemple)
- **Protocole** : `The Things Network (TTN v3)`

L'app génère une **`api_key`** et affiche l'**URL d'ingestion**. Vous les retrouvez à tout moment sur
la page *Connexion* du capteur (ou via `GET /api/sensors/<id>/connection/`).

L'URL a cette forme — `<id>` est l'identifiant numérique du capteur :

```
POST https://<votre-domaine>/api/sensors/<id>/data/
```

### 7.2 — Créer le webhook côté TTN

Dans la console TTN : **Integrations → Webhooks → Add webhook → Custom webhook**.

| Champ | Valeur |
|---|---|
| Webhook ID | `analyse-lora` |
| Webhook format | **JSON** |
| Base URL | `https://<votre-domaine>/api/sensors/<id>/data/` |
| Additional headers | `Authorization` : `Bearer <api_key>` |
| Enabled messages | **Uplink message** uniquement |

Laissez le champ *path* de l'uplink **vide** : TTN posterait sinon sur un sous-chemin inexistant.

### 7.3 — Pourquoi ça marche sans transformation

Le backend normalise nativement le format TTN : il détecte la clé `uplink_message`, lit l'horodatage
dans `uplink_message.received_at` et les données dans `uplink_message.decoded_payload`. Le format
ChirpStack v4 (`deviceInfo` + `object`) est reconnu de la même façon.

**Vous n'avez donc aucun code à écrire, aucun middleware à intercaler.**

### 7.4 — Vérifier

Attendez un uplink (ou provoquez-le : chez Dragino, un appui sur le bouton force une émission).

- Côté TTN : *Live Data* doit montrer l'uplink **et** la ligne du webhook en succès (`200`/`201`).
- Côté app : la mesure apparaît dans les données du capteur.
- En ligne de commande, pour simuler un uplink sans attendre :

```bash
curl -X POST https://<votre-domaine>/api/sensors/1/data/ \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2026-07-14T10:00:00Z","data":{"TempC_SHT":21.5,"Hum_SHT":48.2}}'
```

Une réponse `201` avec la mesure sérialisée = la chaîne est bonne.

---

## 9. Créer des grandeurs calculées

Une **grandeur calculée** est une formule Python évaluée sur chaque mesure. `row` est le dictionnaire
des données reçues.

```python
row['TempC_SHT'] * 9 / 5 + 32                      # °C → °F
row['TempC_SHT'] - (100 - row['Hum_SHT']) / 5      # point de rosée (approximation)
(row['BatV'] - 2.5) / (3.6 - 2.5) * 100            # niveau de pile en %
```

L'évaluation est sandboxée et renvoie `None` en cas d'erreur : une formule fausse donne une courbe
vide, jamais une exception. **Utilisez les noms de champs réellement reçus** (§7) — pas ceux de cet
exemple, qui dépendent de votre décodeur.

---

## 10. Changer les clés (commandes AT)

**Vous n'en avez très probablement pas besoin.** Les clés d'usine sont uniques par appareil et
parfaitement sûres. Vous ne les changerez que le jour où vous auto-hébergerez ChirpStack et voudrez
maîtriser vous-même la gestion des clés.

Si vous y tenez, sur le **LHT52** :

| | |
|---|---|
| Matériel | adaptateur **AS-02** (convertisseur USB Type-C) + un adaptateur USB-TTL |
| Débit | **115200** bauds, 8N1 |
| Mot de passe AT | **`123456`** par défaut — les commandes AT sont désactivées sans lui |
| Expiration | 5 minutes, puis il faut ressaisir le mot de passe |

Commandes utiles : `AT+DEUI`, `AT+APPEUI`, `AT+APPKEY`.

> ⚠️ Une AppKey mal recopiée donne un capteur qui **ne joint plus jamais rien, sans le moindre message
> d'erreur**. Avec l'achat d'un module 915 MHz, c'est le grand classique du débutant.

---

## 11. Dépannage

| Symptôme | Cause la plus probable |
|---|---|
| Aucune JoinRequest dans TTN | **Pas de couverture passerelle.** Cherchez ici en premier, pas dans les clés — le capteur réémet en boucle sans se plaindre. |
| Aucune JoinRequest, et vous êtes couvert | Module **915 MHz** au lieu de 868. Ou plan de fréquences erroné. |
| JoinRequest visible, mais jamais de JoinAccept | **AppKey ou DevEUI mal recopiés** (souvent un problème d'ordre MSB/LSB). |
| La gateway n'apparaît jamais **« connected »** dans TTN | Clé API invalide/expirée, certificat TLS non accepté, ou port **8887 sortant** bloqué par la box/le pare-feu. |
| Gateway **« connected »**, mais aucune JoinRequest de vos capteurs | Ce n'est pas un problème de connexion passerelle→TTN : diagnostiquez côté capteur (lignes ci-dessous — portée, plan de fréquences). |
| Uplinks reçus, mais payload en base64 illisible | **Payload formatter absent** (§7). |
| Mesures qui arrivent **vides** dans analyse-lora | Même cause : pas de `decoded_payload`, donc rien à extraire. |
| TTN affiche le webhook en erreur `403` | `api_key` fausse, ou header `Authorization` mal formé (il faut `Bearer <clé>`). |
| TTN affiche le webhook en erreur `404` | URL d'ingestion fausse. Reprenez-la sur la page *Connexion* du capteur. |
| Le capteur émet, puis se tait | **Duty cycle / Fair Use Policy.** Vous émettez trop souvent. |
| Courbe d'une grandeur calculée vide | Noms de champs faux dans la formule (§9). Vérifiez le contenu réel d'une mesure. |
| Pile vide en quelques mois | Intervalle d'émission trop court, ou SF12 forcé. Laissez faire l'**ADR**. |

---

## 12. Aller plus loin : ChirpStack auto-hébergé

TTN Community est parfait pour démarrer, mais **TTN détient vos clés de session** et peut donc lire
vos données (§2). ChirpStack, lui, s'auto-héberge — et vous avez déjà toute l'infrastructure Docker
qu'il faut dans ce lab.

Ce que ça change :

- **Vous redevenez le seul détenteur des clés.** Le chiffrement AES-128 devient réellement de bout
  en bout, du capteur jusqu'à analyse-lora.
- Plus de Fair Use Policy (le duty cycle légal de 1 %, lui, reste).
- Il faut une passerelle à vous, pointée vers votre serveur — la configuration Basic Station vue en
  §5 se réutilise à l'identique, seule la **LNS Server URI** change : elle pointe vers votre
  `chirpstack-gateway-bridge` (`wss://votre-domaine:8887`) au lieu du cluster TTN.

Côté app, **rien à changer** : le protocole `chirpstack` est déjà géré, et le backend normalise
nativement le format v4 (`deviceInfo` + `object`). Le webhook se configure dans
*Application → Integrations → HTTP*, avec le même header `Authorization: Bearer <api_key>`.

Si les données sont réellement sensibles, ajoutez une couche de chiffrement **applicative** au-dessus
du payload LoRaWAN : le serveur réseau ne voit alors plus rien, même auto-hébergé. Et choisissez un
capteur à élément sécurisé (type ATECC608, présent sur les RAK) — sinon un accès physique de trente
secondes au boîtier suffit à extraire les clés.

---

## 13. Sources

- [Dragino — Get Devices Keys](https://wiki.dragino.com/xwiki/bin/view/Main/Get%20Devices%20Keys/)
- [Manuel LHT52 (PDF)](https://files.seeedstudio.com/products/SenseCAP/101990983_LHT52/LHT52_Temperature_Humidity_Sensor_UserManual_v1.0.pdf)
- [Manuel LHT65N (wiki Dragino)](https://wiki.dragino.com/xwiki/bin/view/Main/User%20Manual%20for%20LoRaWAN%20End%20Nodes/LHT65N%20LoRaWAN%20Temperature%20&%20Humidity%20Sensor%20Manual/)
- [The Things Stack — Dragino LHT52](https://www.thethingsindustries.com/docs/hardware/devices/models/dragino-lht52/)
- [Fiche produit LHT52](https://www.dragino.com/products/temperature-humidity-sensor/item/199-lht52.html) · [Fiche produit LHT65N](https://www.dragino.com/products/temperature-humidity-sensor/item/224-lht65n.html)
- [TTN Mapper — couverture](https://ttnmapper.org)
- [SenseCAP M2 — Connect to The Things Network (PDF)](https://files.seeedstudio.com/products/SenseCAP/M2_Multi-Platform_Gateway/Connect%20M2%20Multi%20Platform%20Gateway%20to%20The%20Things%20Network.pdf)
- [Fiche produit SenseCAP M2 — Gotronic](https://www.gotronic.fr/art-passerelle-lorawan-m2-114992981-38391.htm)
- [Forum TTN — « LHT65: disappointing battery life »](https://www.thethingsnetwork.org/forum/t/lht65-disappointing-battery-life/52153)
