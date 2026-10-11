"""Tests backend d'analyse-lora (chantier « tests », contrat v1).

Lancer, comme le lanceur officiel (`scripts/app-test.sh`) :

    python manage.py test

Rien ne sort du conteneur : le JWKS de Keycloak est remplacé par une clé locale
(voir `socle.py`), et tout appel HTTP sortant (Open-Meteo, API Adresse, Storage
Integration TTN) est coupé au niveau du transport, puis simulé explicitement
dans les rares tests qui en ont besoin. Le reste du code de l'app
(authentification, vues, permissions, agrégations) s'exécute réellement.
"""
