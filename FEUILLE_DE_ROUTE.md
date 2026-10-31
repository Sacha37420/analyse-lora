# Feuille de route — analyse-lora

Ce fichier est lu par une machine : `validate-app.sh` refuse de déployer s'il manque ou s'il ne
contient aucun lot au format ci-dessous, et `app-test.sh` lit la commande de test. Garder les titres
tels quels.

App livrée avant l'obligation de feuille de route : le Lot 1 résume l'existant. Les lots suivants
viennent de l'analyse du 2026-10-31 ; la vue d'ensemble est dans `to_do_global.md`, à la racine du
dépôt du lab. Légende : [C] constaté, [D] déduit.

## Commande de test
python manage.py test

## Lot 1 — Existant : capteurs, ingestion, grandeurs calculées, météo   ·   statut : livré
**Objectif :** tableau de bord de capteurs LoRa (TTN/ChirpStack) : ingestion par webhook ou clé
d'API, grandeurs calculées par formule, météo superposée. Accès : `developers,amis,famille`.
**Tâches :**
- [x] Fonctionnalités en service (`README.md`, `docs/GUIDE-LORA.md`)
- [x] Correctifs du chantier tests (2026-10-12)
**Tests à passer avant de clore le lot :**
- [x] 65 tests backend (`backend/api/tests/`)
- [x] `frontend/e2e/cloisonnement.spec.ts` présent
**Vérifié le :** 2026-10-31 — relevé par lecture (version en service = `9817a50`), tests non rejoués.

## Lot 2 — Évaluateur de formule sûr   ·   statut : livré
**Objectif :** une formule saisie par un utilisateur ne peut plus exécuter de code sur le serveur.
**Constat [C] :** `_safe_eval` fait `eval(formula, {'__builtins__': {}, …})` (`backend/api/views.py:236`).
Ce n'est pas un bac à sable : `().__class__.__base__.__subclasses__()` reste joignable. La formule est
écrite par tout titulaire d'un accès au capteur, membres de `amis` et `famille` compris
(`ComputedMeasureListView.perform_create`, `perform_update`). **P1, urgence U3.**
**Tâches :**
- [x] Évaluateur sur l'AST (`ast.parse(mode='eval')`, `backend/api/formula.py`). Nœuds autorisés : nombres, `BinOp`, `UnaryOp`,
  `Compare`, `IfExp`, `Call` vers les seules fonctions de `math` et `abs`/`round`/`min`/`max`,
  `Subscript` sur `row` avec une clé constante. Aucun attribut, aucune lambda, aucune compréhension.
  Ajouts : `BoolOp` (`and`/`or`), constantes `pi e tau inf nan`, `row['a']['b']` ; retirés de `math` :
  `factorial`, `comb`, `perm` (coût non borné) ; `**` en flottant au-delà de 64 ; opérandes numériques seulement.
- [x] Longueur de formule bornée (500 caractères), et validation à l'enregistrement (400 explicite) en plus de l'évaluation
**Tests à passer avant de clore le lot :**
- [x] `().__class__.__base__.__subclasses__()`, `row.__class__`, `(lambda: 1)()` et `[x for x in ()]` → 400 à l'enregistrement
- [x] Toutes les formules présentes en base donnent le même résultat qu'avant (comparaison sur un échantillon réel)
**Vérifié le :** 2026-10-31 — `bash chantiers/tests/essai.sh analyse-lora` : 83 tests OK **Mis en service le 2026-10-31** (chantier « urgences ») : image construite pendant que l'ancienne tournait, `scripts/app-test.sh` vert sur cette image, puis `up -d --no-build` ; test de cloisonnement par `lab-runner` vert après déploiement.
(`tests/test_formule.py` : 37 formules refusées, à la validation et à l'enregistrement en création et
modification). La base en service ne contient **aucune** grandeur calculée (0 ligne) : comparaison
ancien `eval` / nouvel évaluateur faite sur les 13 819 lectures réelles avec 14 formules (celles du
README, du guide, de l'aide de saisie, plus des variantes) : 193 466 évaluations, 0 écart.

## Lot 3 — Fiche capteur selon le rôle   ·   statut : livré
**Objectif :** un accès en lecture ne permet plus d'injecter des mesures ni de voir les autres titulaires.
**Constat [C] :** `SensorSerializer` rend `api_key`, `connection_config` et `user_accesses`
(`backend/api/serializers.py:61-65`) à quiconque voit la fiche, y compris un accès webhook « en
lecture » depuis `9817a50`. Signalé sans correctif dans `chantiers/tests/rapports/lora-fichiers.md` §(5).
**Tâches :**
- [x] Sérialiseur réduit pour les non-`developers` : sans `api_key`, `connection_config` ni `user_accesses`
  (`SensorReadSerializer`) ; même retrait sur `GET /api/sensors/:id/connection/`, qui rendait aussi la clé
**Tests à passer avant de clore le lot :**
- [x] Un accès webhook et un accès direct ne reçoivent aucun des trois champs ; un membre de `developers` les reçoit
**Vérifié le :** 2026-10-31 — `essai.sh analyse-lora` : 83 tests OK (`tests/test_fiche_capteur.py`). **Mis en service le 2026-10-31** (chantier « urgences ») : image construite pendant que l'ancienne tournait, `scripts/app-test.sh` vert sur cette image, puis `up -d --no-build` ; test de cloisonnement par `lab-runner` vert après déploiement.
Frontend : aucune page hors `developerGuard` ne lit ces champs (déjà optionnels dans `Sensor`) ;
`npx ng build` non concluant en local (`node_modules` incomplet : `plotly.js-basic-dist-min` absent,
erreur préexistante sans rapport) — à confirmer par le build Docker (`npm ci`).

## Lot 4 — Report des correctifs du gabarit   ·   statut : en cours
**Objectif :** même comportement que le gabarit corrigé (chantier T3 de `to_do_global.md`).
**Tâches :**
- [x] Polices en chemin relatif (`frontend/src/styles.scss:3-11`, `url("/assets/…")` → `url("assets/…")`)
- [x] `redirectUri` sur la page courante (`core/redirect-uri.ts`, copie de lab-admin : même origine et sous `/lora/`, sinon `appUrl`)
- [x] `tokenBases()` dans `core/auth.interceptor.ts` (`core/env.ts` : la seule API de l'app ; `core/token-scope.ts`, copie de lab-admin)
- [x] `pkceMethod: 'S256'` (front) — `--pkce` sur le client reste à poser par l'architecte après déploiement
- [x] Ports publiés liés à `${LAB_BIND_ADDR:-127.0.0.1}` (chantier « failles », I1)
- [ ] Couleur par défaut d'une grandeur (`pages/measures/measure-view.ts:34,141`, `'#3b82f6'`) tirée d'un token CSS
**Tests à passer avant de clore le lot :**
- [ ] Un lien direct vers une fiche capteur y revient après la connexion Keycloak
- [ ] Les WOFF2 répondent 200 derrière `/analyse-lora/`
- [ ] `cloisonnement.spec.ts` 3/3
**Vérifié le :** 2026-10-31 — non déployé. Chantier « failles » (secteur E) : image candidate
`analyse-lora-frontend:candidat` construite (`npm ci` + `ng build` OK ; le bundle porte
`pkceMethod:"S256"`, les WOFF2 sont référencés en `./media/…`) ; `docker compose config` rend
`host_ip: 127.0.0.1` pour les deux ports. Les trois tests du lot demandent le déploiement. Reste la
couleur par défaut d'une grandeur (hors chantier).

## Lot 5 — Passage au chemin à portes   ·   statut : à faire
**Objectif :** l'app se déploie par le moteur, tests compris (chantier T1 de `to_do_global.md`).
**Tâches :**
- [ ] Ligne `.owners` `analyse-lora:sacha` (fichier d'architecte)
- [ ] Premier déploiement par lab-admin → « Déployer »
**Tests à passer avant de clore le lot :**
- [ ] `bash scripts/validate-app.sh analyse-lora --quality-only` vert
- [ ] `.lab-state/deployed/analyse-lora.json` porte `backend: ok` et `cloisonnement: ok`
**Vérifié le :**
