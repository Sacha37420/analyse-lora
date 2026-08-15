"""
Bornes de température journalières (min/max) pour les jauges du tableau de
bord, via l'API de prévision Open-Meteo (https://open-meteo.com/) — gratuite,
sans clé — pour la ville saisie sur la page Admin > Météo, par webhook ou par
capteur autonome (voir Webhook.weather_location / Sensor.weather_location).

Ce sont les bornes PRÉVUES pour la journée en cours (min/max prévisionnels sur
les 24h du jour), pas les extrêmes déjà observés à l'instant de l'appel — une
jauge affiche donc la plage attendue pour toute la journée, y compris ses
heures pas encore passées. `timezone=auto` fait déterminer par Open-Meteo le
fuseau local du point demandé, donc le "jour" correspond au jour calendaire
local de la ville — pas de piège de bord UTC à minuit comme avec l'ancienne
intégration Météo-France DPClim (qui, elle, ne donnait que le min/max déjà
observé depuis 00:00 UTC).

La même API sert aussi la prévision *heure par heure* tracée en fond du
graphique du tableau de bord (`get_hourly_temperatures`) — même endpoint, même
localisation, même cache : ce que la jauge montre condensé en deux bornes, la
courbe le montre déroulé sur la période affichée.

Le résultat est mis en cache (20 min) pour éviter un appel réseau à chaque
rafraîchissement du tableau de bord.
"""
from datetime import datetime, timedelta

import requests
from django.core.cache import cache

GEO_URL      = 'https://api-adresse.data.gouv.fr/search/'
FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'

# Pas de marge de sécurité : les vraies bornes prévues du jour, telles quelles
# (les jauges doivent montrer les extrêmes réels, pas des valeurs
# artificiellement élargies). Ce sont aussi les valeurs de repli si l'appel échoue.
FALLBACK_MIN = -5.0
FALLBACK_MAX = 45.0

RESULT_CACHE_TTL = 20 * 60  # le résultat (min, max) du jour
HOURLY_CACHE_TTL = 20 * 60  # la série horaire d'une plage de dates donnée
GEO_CACHE_TTL    = 24 * 60 * 60  # les coordonnées d'une ville ne bougent pas

# Fenêtre acceptée par /forecast pour start_date/end_date : environ
# [aujourd'hui − 93 j, aujourd'hui + 15 j]. **Hors fenêtre, l'API répond 400 sans
# aucune donnée partielle** (vérifié en réel) — une période « mois » déborde donc
# forcément côté futur : il faut rogner la demande, pas la passer telle quelle.
# Une marge d'un jour de chaque côté absorbe l'écart de « aujourd'hui » entre
# notre fuseau et celui du serveur Open-Meteo.
FORECAST_PAST_DAYS   = 92
FORECAST_FUTURE_DAYS = 14


def _geocoder(ville: str):
    """(lat, lon) pour une ville, via l'API Adresse — ou None."""
    try:
        r = requests.get(GEO_URL, params={'q': ville, 'type': 'municipality', 'limit': 1}, timeout=15)
        r.raise_for_status()
        feats = r.json().get('features', [])
    except (requests.RequestException, ValueError):
        return None
    if not feats:
        return None
    lon, lat = feats[0]['geometry']['coordinates']
    return lat, lon


def _geocode_cached(ville: str):
    """`_geocoder` avec cache 24 h — deux appelants (jauges + courbe horaire)."""
    cache_key = f'weather_geo:{ville.strip().lower()}'
    cached = cache.get(cache_key)
    if cached is not None:
        return None if cached == 'none' else tuple(cached)

    geo = _geocoder(ville)
    cache.set(cache_key, list(geo) if geo else 'none', GEO_CACHE_TTL)
    return geo


def _compute_daily_min_max(location: str) -> tuple[float, float] | None:
    geo = _geocode_cached(location)
    if geo is None:
        return None
    lat, lon = geo

    try:
        r = requests.get(FORECAST_URL, params={
            'latitude': lat, 'longitude': lon,
            'daily': 'temperature_2m_min,temperature_2m_max',
            'timezone': 'auto', 'forecast_days': 1,
        }, timeout=15)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        daily = r.json()['daily']
        tmin = daily['temperature_2m_min'][0]
        tmax = daily['temperature_2m_max'][0]
    except (ValueError, KeyError, IndexError):
        return None
    if tmin is None or tmax is None:
        return None
    return float(tmin), float(tmax)


def get_daily_min_max(location: str) -> tuple[float, float] | None:
    if not location:
        return None

    cache_key = f'weather_result:{location.strip().lower()}'
    cached = cache.get(cache_key)
    if cached is not None:
        return None if cached == 'none' else tuple(cached)

    result = _compute_daily_min_max(location)
    cache.set(cache_key, list(result) if result else 'none', RESULT_CACHE_TTL)
    return result


def _fetch_hourly(lat: float, lon: float, start_date, end_date) -> list | None:
    """Liste `[[epoch_utc, °C], …]` — sérialisable telle quelle en cache."""
    try:
        r = requests.get(FORECAST_URL, params={
            'latitude': lat, 'longitude': lon,
            'hourly': 'temperature_2m',
            # `timeformat=unixtime` renvoie un instant absolu (epoch UTC) : la
            # conversion vers l'heure locale se fait ici, sans jamais dépendre
            # d'un décalage fixe — un mois à cheval sur un changement d'heure
            # serait faux avec `utc_offset_seconds` appliqué uniformément.
            # `timezone=auto` reste utile : il fixe les bornes de *jour* de
            # start_date/end_date sur le fuseau du point demandé.
            'timezone': 'auto', 'timeformat': 'unixtime',
            'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(),
        }, timeout=15)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        hourly = r.json()['hourly']
        pairs = list(zip(hourly['time'], hourly['temperature_2m']))
    except (ValueError, KeyError, TypeError):
        return None
    return [[t, float(v)] for t, v in pairs if t is not None and v is not None]


def get_hourly_temperatures(location: str, start, end) -> list[tuple[datetime, float]] | None:
    """
    Prévision de température heure par heure entre `start` et `end` (datetimes
    *aware*), pour `location`. Renvoie `[(datetime aware, °C), …]` — dans le
    fuseau de `start` — ou None (pas de localisation, géocodage ou appel en
    échec, plage hors fenêtre de prévision).
    """
    if not location:
        return None

    tz = start.tzinfo
    today = datetime.now(tz).date()
    start_date = max(start.date(), today - timedelta(days=FORECAST_PAST_DAYS))
    end_date   = min(end.date(),   today + timedelta(days=FORECAST_FUTURE_DAYS))
    if start_date > end_date:
        return None

    cache_key = f'weather_hourly:{location.strip().lower()}:{start_date}:{end_date}'
    cached = cache.get(cache_key)
    if cached is None:
        geo = _geocode_cached(location)
        result = _fetch_hourly(geo[0], geo[1], start_date, end_date) if geo else None
        cached = result if result else 'none'
        cache.set(cache_key, cached, HOURLY_CACHE_TTL)
    if cached == 'none':
        return None

    points = [(datetime.fromtimestamp(t, tz), v) for t, v in cached]
    return [(t, v) for t, v in points if start <= t <= end]


def gauge_bounds_for_temperature(location: str) -> tuple[float, float]:
    result = get_daily_min_max(location)
    if result is None:
        return FALLBACK_MIN, FALLBACK_MAX
    return result
