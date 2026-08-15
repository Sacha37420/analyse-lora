"""
Agrégations pour le tableau de bord : regroupement par webhook (ou par capteur
autonome), grandeurs disponibles, série temporelle bornée à la période exacte
(jour/semaine/mois calendaires, fuseau Europe/Paris), et jauges intérieur/
extérieur.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import weather
from .models import Sensor, Webhook
from .views import _has_sensor_access

PARIS = ZoneInfo('Europe/Paris')


def _period_bounds(period: str, now=None):
    now_paris = (now or timezone.now()).astimezone(PARIS)

    if period == 'day':
        start = now_paris.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = start + timedelta(days=1) - timedelta(microseconds=1)
    elif period == 'week':
        start = (now_paris - timedelta(days=now_paris.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end   = start + timedelta(days=7) - timedelta(microseconds=1)
    elif period == 'month':
        start = now_paris.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        end = next_month - timedelta(microseconds=1)
    else:
        return None, None
    return start, end


def _local_iso(dt) -> str:
    """
    Horodatage en heure locale (Europe/Paris) **sans décalage** : `2026-08-14T10:00:00`.

    Plotly.js n'a aucune gestion de fuseau : il parse une chaîne ISO porteuse
    d'un décalage (`+02:00`) en instant absolu puis étiquette l'axe en UTC — les
    heures s'affichaient donc 1 à 2 h en arrière de l'heure française. Une chaîne
    naïve est reprise telle quelle et s'affiche exactement comme écrite. Les
    séries capteurs et la prévision météo passent toutes deux par ici, condition
    pour qu'elles restent alignées entre elles.
    """
    return dt.astimezone(PARIS).replace(tzinfo=None).isoformat()


def _sensor_brief(s: Sensor) -> dict:
    return {'id': s.id, 'name': s.name, 'location': s.location}


def _is_temperature(field: str) -> bool:
    return 'temp' in field.lower()


def _weather_location(group_type: str, group_id: int, sensors: list[Sensor]) -> str:
    """
    La localisation météo est portée par le webhook (un lieu physique par
    webhook) ou, pour un capteur autonome, par le capteur lui-même.
    """
    if group_type == 'webhook':
        return get_object_or_404(Webhook, pk=group_id).weather_location
    return sensors[0].weather_location if sensors else ''


def _resolve_group(group_type: str, group_id: int, user):
    """Renvoie la liste des Sensor du groupe, restreinte à ceux accessibles à `user`."""
    if group_type == 'webhook':
        webhook = get_object_or_404(Webhook, pk=group_id)
        sensors = list(webhook.sensors.all())
    elif group_type == 'sensor':
        sensors = list(Sensor.objects.filter(pk=group_id, webhook__isnull=True))
    else:
        return None
    return [s for s in sensors if _has_sensor_access(user, s)]


def _latest_value(sensor: Sensor, field: str):
    reading = sensor.readings.filter(data__has_key=field).order_by('-timestamp').first()
    if reading is None:
        return None, None
    return reading.data.get(field), reading.timestamp


class DashboardGroupsView(APIView):
    """GET /api/dashboard/groups/ — un groupe par webhook + un par capteur autonome."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        groups = []

        for webhook in Webhook.objects.all():
            sensors = [s for s in webhook.sensors.all() if _has_sensor_access(user, s)]
            if sensors:
                groups.append({
                    'type': 'webhook', 'id': webhook.id, 'name': webhook.name,
                    'sensors': [_sensor_brief(s) for s in sensors],
                })

        for sensor in Sensor.objects.filter(webhook__isnull=True):
            if _has_sensor_access(user, sensor):
                groups.append({
                    'type': 'sensor', 'id': sensor.id, 'name': sensor.name,
                    'sensors': [_sensor_brief(sensor)],
                })

        return Response(groups)


class DashboardFieldsView(APIView):
    """GET /api/dashboard/groups/:type/:id/fields/ — clés JSON disponibles (20 dernières lectures/capteur)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_type, group_id):
        sensors = _resolve_group(group_type, group_id, request.user)
        if sensors is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not sensors:
            return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        keys = set()
        for s in sensors:
            for reading in s.readings.order_by('-timestamp')[:20]:
                keys.update(reading.data.keys())
        return Response(sorted(keys))


class DashboardChartView(APIView):
    """GET /api/dashboard/groups/:type/:id/chart/?field=X&period=day|week|month"""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_type, group_id):
        sensors = _resolve_group(group_type, group_id, request.user)
        if sensors is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not sensors:
            return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        field  = request.query_params.get('field')
        period = request.query_params.get('period', 'day')
        if not field:
            return Response({'error': 'Paramètre field requis'}, status=status.HTTP_400_BAD_REQUEST)

        start, end = _period_bounds(period)
        if start is None:
            return Response({'error': "period doit être 'day', 'week' ou 'month'"}, status=status.HTTP_400_BAD_REQUEST)

        series = []
        for s in sensors:
            qs = s.readings.filter(timestamp__gte=start, timestamp__lte=end, data__has_key=field).order_by('timestamp')
            points = [{'t': _local_iso(r.timestamp), 'v': r.data.get(field)} for r in qs]
            series.append({'sensor_id': s.id, 'name': s.name, 'location': s.location, 'points': points})

        return Response({
            'period': {'start': start.isoformat(), 'end': end.isoformat()},
            'sensors': series,
            'weather': self._weather_series(group_type, group_id, sensors, field, start, end),
        })

    @staticmethod
    def _weather_series(group_type, group_id, sensors, field, start, end):
        """
        Prévision horaire à superposer aux séries capteurs, ou None.

        Réservée aux grandeurs thermiques : les capteurs et la prévision
        partagent le même axe Y, une courbe en °C sous une série d'humidité ou
        de tension serait illisible et fausse. La plage demandée est la période
        affichée entière — pour « jour », ça inclut donc les heures pas encore
        écoulées, ce qui est bien l'intérêt d'une prévision.
        """
        if not _is_temperature(field):
            return None

        location = _weather_location(group_type, group_id, sensors)
        points = weather.get_hourly_temperatures(location, start, end)
        if not points:
            return None
        return {
            'location': location,
            'points': [{'t': _local_iso(t), 'v': v} for t, v in points],
        }


class DashboardGaugesView(APIView):
    """GET /api/dashboard/groups/:type/:id/gauges/?field=X&period=day|week|month"""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_type, group_id):
        sensors = _resolve_group(group_type, group_id, request.user)
        if sensors is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not sensors:
            return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        field  = request.query_params.get('field')
        period = request.query_params.get('period', 'day')
        if not field:
            return Response({'error': 'Paramètre field requis'}, status=status.HTTP_400_BAD_REQUEST)

        start, end = _period_bounds(period)
        if start is None:
            return Response({'error': "period doit être 'day', 'week' ou 'month'"}, status=status.HTTP_400_BAD_REQUEST)

        interior_sensors = [s for s in sensors if s.location == 'interior']
        exterior_sensor  = next((s for s in sensors if s.location == 'exterior'), None)
        is_temperature   = _is_temperature(field)

        exterior_value, exterior_ts = (_latest_value(exterior_sensor, field) if exterior_sensor else (None, None))

        if is_temperature:
            gauge_min, gauge_max = weather.gauge_bounds_for_temperature(
                _weather_location(group_type, group_id, sensors)
            )
        else:
            # Pas de plage météo pour une grandeur non thermique : la jauge se
            # cadre sur les valeurs réellement observées (tous capteurs du groupe) sur
            # la période affichée, avec une marge pour ne pas coller value/bords.
            values = []
            for s in sensors:
                qs = s.readings.filter(timestamp__gte=start, timestamp__lte=end, data__has_key=field)
                values += [r.data.get(field) for r in qs]
            values = [v for v in values if isinstance(v, (int, float))]
            if values:
                lo, hi = min(values), max(values)
                pad = (hi - lo) * 0.1 or 1.0
                gauge_min, gauge_max = lo - pad, hi + pad
            else:
                gauge_min, gauge_max = 0.0, 1.0

        now_paris  = timezone.now().astimezone(PARIS)
        is_summer  = now_paris.month in (4, 5, 6, 7, 8, 9)

        gauges = []
        for s in interior_sensors:
            value, ts = _latest_value(s, field)

            delta = None
            delta_color = None
            if value is not None and exterior_value is not None:
                delta = value - exterior_value
                if is_temperature:
                    ext_gt_int = exterior_value > value
                    is_red = ext_gt_int if is_summer else not ext_gt_int
                    delta_color = 'red' if is_red else 'green'

            gauges.append({
                'sensor_id': s.id,
                'name': s.name,
                'value': value,
                'timestamp': ts.isoformat() if ts else None,
                'exterior_sensor_name': exterior_sensor.name if exterior_sensor else None,
                'exterior_value': exterior_value,
                'delta': delta,
                'delta_color': delta_color,
                'min': gauge_min,
                'max': gauge_max,
                'is_temperature': is_temperature,
            })

        # Le capteur extérieur a aussi sa propre jauge — juste sa valeur, sans
        # référence ni delta puisqu'il est lui-même la référence des autres.
        if exterior_sensor is not None:
            gauges.append({
                'sensor_id': exterior_sensor.id,
                'name': exterior_sensor.name,
                'value': exterior_value,
                'timestamp': exterior_ts.isoformat() if exterior_ts else None,
                'exterior_sensor_name': None,
                'exterior_value': None,
                'delta': None,
                'delta_color': None,
                'min': gauge_min,
                'max': gauge_max,
                'is_temperature': is_temperature,
            })

        return Response({'gauges': gauges})
