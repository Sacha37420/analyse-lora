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

Le résultat est mis en cache (20 min) pour éviter un appel réseau à chaque
rafraîchissement du tableau de bord.
"""
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


def _compute_daily_min_max(location: str) -> tuple[float, float] | None:
    geo = _geocoder(location)
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


def gauge_bounds_for_temperature(location: str) -> tuple[float, float]:
    result = get_daily_min_max(location)
    if result is None:
        return FALLBACK_MIN, FALLBACK_MAX
    return result
