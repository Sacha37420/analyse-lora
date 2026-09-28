"""
Rattrapage des uplinks manqués via la Storage Integration de TTN v3.

Le webhook TTN ne rejoue jamais un uplink qu'il n'a pas pu livrer (backend
arrêté, Postgres injoignable…) : ces mesures sont perdues pour nous, mais TTN
les garde un temps dans sa Storage Integration si elle est activée sur
l'application (rétention courte sur la Community Edition — ~2 jours constatés).

Chaque message stocké a exactement le format d'un uplink livré par webhook : on
le passe donc par le même `_normalize_payload`, ce qui donne le même horodatage
(`uplink_message.received_at`) et les mêmes données qu'une livraison normale.
C'est ce qui rend la déduplication sûre : un uplink déjà reçu par webhook a
exactement le même `timestamp` en base (vérifié sur des données réelles), il
n'est jamais inséré deux fois — l'opération peut être relancée à volonté.
"""
import json

import requests

from .models import SensorReading
from .views import _normalize_payload

TIMEOUT_S = 60


class TTNError(Exception):
    pass


def _storage_url(region: str, app_id: str, device_id: str | None) -> str:
    base = f'https://{region}.cloud.thethings.network/api/v3/as/applications/{app_id}'
    if device_id:
        base += f'/devices/{device_id}'
    return base + '/packages/storage/uplink_message'


def fetch_stored_uplinks(config: dict, device_id: str | None = None) -> list[dict]:
    """Tous les uplinks encore conservés par TTN (application entière, ou un seul device)."""
    region  = (config.get('region') or '').strip()
    app_id  = (config.get('app_id') or '').strip()
    api_key = (config.get('api_key') or '').strip()
    if not (region and app_id and api_key):
        raise TTNError("Configuration TTN incomplète : région, Application ID et clé API TTN sont requis.")

    try:
        r = requests.get(
            _storage_url(region, app_id, device_id),
            headers={'Authorization': f'Bearer {api_key}', 'Accept': 'text/event-stream'},
            timeout=TIMEOUT_S,
        )
    except requests.RequestException as e:
        raise TTNError(f"TTN injoignable : {e}") from e

    if r.status_code in (401, 403):
        raise TTNError(
            "TTN refuse la clé API : elle doit avoir le droit « Read application traffic » "
            "(RIGHT_APPLICATION_TRAFFIC_READ)."
        )
    if r.status_code == 404:
        raise TTNError(
            "Aucune donnée stockée côté TTN pour cette application : la Storage Integration "
            "n'est probablement pas activée (Console TTN → Integrations → Storage Integration)."
        )
    if r.status_code != 200:
        raise TTNError(f"TTN a répondu {r.status_code} : {r.text[:200]}")

    # Réponse en flux : un objet JSON {"result": {...}} par message, séparés par des lignes vides.
    uplinks = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if 'error' in obj:
            raise TTNError(f"Erreur TTN : {obj['error'].get('message', obj['error'])}")
        if 'result' in obj:
            uplinks.append(obj['result'])
    return uplinks


def backfill(config: dict, sensors: list, device_id: str | None = None) -> dict:
    """
    Insère les uplinks stockés par TTN absents de la base, routés vers `sensors`
    par `connection_config.device_id` (même règle que l'ingestion par webhook).
    """
    uplinks = fetch_stored_uplinks(config, device_id)
    by_device = {s.connection_config.get('device_id'): s for s in sensors if s.connection_config.get('device_id')}

    received  = {s.id: [] for s in by_device.values()}
    unmatched = set()
    for up in uplinks:
        dev_id = (up.get('end_device_ids') or {}).get('device_id', '')
        sensor = by_device.get(dev_id)
        if sensor is None:
            unmatched.add(dev_id)
            continue
        received[sensor.id].append(_normalize_payload(up, 'ttn'))

    to_insert, per_sensor, oldest = [], [], None
    for sensor in by_device.values():
        readings = received[sensor.id]
        inserted = 0
        if readings:
            first = min(ts for ts, _ in readings)
            oldest = first if oldest is None or first < oldest else oldest
            # Bornée à la fenêtre de rétention TTN : quelques centaines de lignes au plus.
            known = set(sensor.readings.filter(timestamp__gte=first).values_list('timestamp', flat=True))
            for ts, data in readings:
                if ts in known:
                    continue
                known.add(ts)
                to_insert.append(SensorReading(sensor=sensor, timestamp=ts, data=data))
                inserted += 1
        per_sensor.append({'sensor_id': sensor.id, 'name': sensor.name, 'available': len(readings), 'inserted': inserted})

    SensorReading.objects.bulk_create(to_insert)
    return {
        'available_since': oldest.isoformat() if oldest else None,
        'fetched':         len(uplinks),
        'inserted':        len(to_insert),
        'sensors':         per_sensor,
        'unmatched_devices': sorted(d for d in unmatched if d),
    }
