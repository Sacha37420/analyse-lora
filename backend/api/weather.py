"""
Bornes de température journalières (min/max) pour les jauges du tableau de
bord, via l'API Météo-France DPClim (données climatologiques,
https://public-api.meteofrance.fr/public/DPClim/v1) — jeton et ville saisis
sur la page Admin > Météo, par webhook ou par capteur autonome (voir
Webhook.weather_api_key / Sensor.weather_api_key).

Authentification (vérifiée en direct le 2026-08-06, cf. incident où la clé de
`restauration` échouait) : la valeur saisie est l'IDENTIFIANT APPLICATIF fourni
par le portail (chaîne Basic « client_id:client_secret »), PAS un jeton
utilisable directement. DPClim n'accepte que le jeton Bearer obtenu en
l'échangeant sur portail-api.meteofrance.fr/token — jamais l'identifiant
directement, jamais en header `apikey`. Le jeton est mis en cache (~55 min).

Portée volontairement réduite par rapport à restauration/backend/api/meteofrance.py
(qui interroge un mois/année arbitraire, avec synchronisation complète du
catalogue France entière et jusqu'à 8 stations de repli) : ici on ne veut que
le min/max D'AUJOURD'HUI, donc on se limite à une géolocalisation ville →
département → 3 stations les plus proches, sans cache de catalogue France
entière. Le résultat est mis en cache (20 min) car la chaîne complète
(commande + attente de production du fichier côté Météo-France) peut prendre
plusieurs dizaines de secondes — inadapté à un appel synchrone à chaque
rafraîchissement du tableau de bord sans cache.
"""
import csv
import hashlib
import io
import math
import time
from datetime import datetime, timezone

import requests
from django.core.cache import cache

BASE      = 'https://public-api.meteofrance.fr/public/DPClim/v1'
GEO_URL   = 'https://api-adresse.data.gouv.fr/search/'
TOKEN_URL = 'https://portail-api.meteofrance.fr/token'

# Pas de marge de sécurité : les vraies bornes du jour, telles quelles (les
# jauges doivent montrer les extrêmes réels, pas des valeurs artificiellement
# élargies). Ce sont aussi les valeurs de repli si l'appel échoue.
FALLBACK_MIN = -5.0
FALLBACK_MAX = 45.0

MAX_STATIONS_ESSAYEES = 3
RESULT_CACHE_TTL   = 20 * 60        # le résultat (min, max) du jour
STATIONS_CACHE_TTL = 24 * 60 * 60   # le catalogue d'un département change rarement
TOKEN_CACHE_TTL     = 55 * 60        # un peu sous l'heure officielle de validité


class MeteoError(Exception):
    pass


def _cred_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def _fetch_token(api_key: str) -> str:
    try:
        r = requests.post(
            TOKEN_URL, data={'grant_type': 'client_credentials'},
            headers={'Authorization': f'Basic {api_key}'}, timeout=15,
        )
    except requests.RequestException as exc:
        raise MeteoError(f'Erreur réseau vers le portail Météo-France : {exc}') from exc
    if r.status_code != 200:
        raise MeteoError(f'Identifiant Météo-France refusé par le portail (HTTP {r.status_code}).')
    try:
        token = r.json().get('access_token')
    except ValueError:
        token = None
    if not token:
        raise MeteoError('Jeton absent de la réponse Météo-France.')
    return token


def _bearer_token(api_key: str, force_refresh: bool = False) -> str:
    cache_key = f'mf_token:{_cred_hash(api_key)}'
    if not force_refresh:
        token = cache.get(cache_key)
        if token:
            return token
    token = _fetch_token(api_key)
    cache.set(cache_key, token, TOKEN_CACHE_TTL)
    return token


def _get(path: str, params: dict, api_key: str, timeout: int = 30, accept: str = 'application/json'):
    url = f'{BASE}/{path}'
    headers = {'Authorization': f'Bearer {_bearer_token(api_key)}', 'Accept': accept}
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    if r.status_code == 401:
        headers['Authorization'] = f'Bearer {_bearer_token(api_key, force_refresh=True)}'
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
    return r


def _geocoder(ville: str):
    """(lat, lon, code_departement) pour une ville, via l'API Adresse — ou None."""
    try:
        r = requests.get(GEO_URL, params={'q': ville, 'type': 'municipality', 'limit': 1}, timeout=15)
        r.raise_for_status()
        feats = r.json().get('features', [])
    except (requests.RequestException, ValueError):
        return None
    if not feats:
        return None
    props = feats[0]['properties']
    lon, lat = feats[0]['geometry']['coordinates']
    departement = props.get('depcode') or (props.get('citycode') or '')[:2]
    if not departement:
        return None
    return lat, lon, departement


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _stations_departement(departement: str, api_key: str) -> list[dict]:
    cache_key = f'mf_stations:{departement}'
    stations = cache.get(cache_key)
    if stations is not None:
        return stations
    try:
        r = _get('liste-stations/horaire', {'id-departement': departement}, api_key, timeout=30)
    except MeteoError:
        return []
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    stations = [s for s in data if s.get('lat') is not None and s.get('lon') is not None
                and s.get('posteOuvert', True)]
    cache.set(cache_key, stations, STATIONS_CACHE_TTL)
    return stations


def _commander(id_station: str, debut_iso: str, fin_iso: str, api_key: str) -> str | None:
    r = _get('commande-station/horaire', {
        'id-station': id_station, 'date-deb-periode': debut_iso, 'date-fin-periode': fin_iso,
    }, api_key, timeout=30)
    if r.status_code not in (200, 202):
        return None
    try:
        return r.json()['elaboreProduitAvecDemandeResponse']['return']
    except (ValueError, KeyError):
        return None


def _telecharger(id_cmde: str, api_key: str, max_essais: int = 6, delai: float = 4.0) -> str | None:
    for _ in range(max_essais):
        r = _get('commande/fichier', {'id-cmde': id_cmde}, api_key, timeout=30, accept='*/*')
        if r.status_code in (200, 201):
            return r.text
        if r.status_code in (202, 204):
            time.sleep(delai)
            continue
        return None
    return None


def _min_max_du_jour(csv_text: str) -> tuple[float, float] | None:
    temperatures = []
    for row in csv.DictReader(io.StringIO(csv_text), delimiter=';'):
        raw = (row.get('T') or '').replace(',', '.').strip()
        if not raw:
            continue
        try:
            temperatures.append(float(raw))
        except ValueError:
            continue
    if not temperatures:
        return None
    return min(temperatures), max(temperatures)


def _compute_daily_min_max(api_key: str, location: str) -> tuple[float, float] | None:
    geo = _geocoder(location)
    if geo is None:
        return None
    lat, lon, departement = geo

    try:
        stations = _stations_departement(departement, api_key)
    except MeteoError:
        return None
    if not stations:
        return None

    classees = sorted(stations, key=lambda s: _haversine(lat, lon, s['lat'], s['lon']))

    now = datetime.now(timezone.utc)
    debut_iso = now.strftime('%Y-%m-%dT00:00:00Z')
    fin_iso   = now.strftime('%Y-%m-%dT%H:00:00Z')

    for station in classees[:MAX_STATIONS_ESSAYEES]:
        try:
            id_cmde = _commander(str(station['id']), debut_iso, fin_iso, api_key)
            if not id_cmde:
                continue
            texte = _telecharger(id_cmde, api_key)
            if not texte:
                continue
        except MeteoError:
            return None
        resultat = _min_max_du_jour(texte)
        if resultat:
            return resultat
    return None


def get_daily_min_max(api_key: str, location: str) -> tuple[float, float] | None:
    if not api_key or not location:
        return None

    cache_key = f'mf_result:{_cred_hash(api_key)}:{location.strip().lower()}'
    cached = cache.get(cache_key)
    if cached is not None:
        return None if cached == 'none' else tuple(cached)

    result = _compute_daily_min_max(api_key, location)
    cache.set(cache_key, list(result) if result else 'none', RESULT_CACHE_TTL)
    return result


def gauge_bounds_for_temperature(api_key: str, location: str) -> tuple[float, float]:
    result = get_daily_min_max(api_key, location)
    if result is None:
        return FALLBACK_MIN, FALLBACK_MAX
    return result
