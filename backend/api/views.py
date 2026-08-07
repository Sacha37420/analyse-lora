import math
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ComputedMeasure, Sensor, SensorReading, SensorUserAccess, Webhook, WebhookUserAccess
from .permissions import HasSensorAccess, IsDeveloper, _is_developer
from .serializers import (
    ComputedMeasureSerializer,
    SensorListSerializer,
    SensorReadingSerializer,
    SensorSerializer,
    SensorUserAccessSerializer,
    WebhookSerializer,
    WebhookUserAccessSerializer,
)

# ── Guides de connexion (statiques) ──────────────────────────────────────────

CONNECTION_GUIDES = {
    'mqtt': {
        'protocol': 'mqtt',
        'label': 'MQTT',
        'icon': 'wifi',
        'description': 'Connexion directe à un broker MQTT. Le capteur ou la gateway publie des messages sur un topic.',
        'supports_webhook': False,
        'fields': [
            {'key': 'broker_host', 'label': 'Hôte du broker',   'placeholder': 'mqtt.example.com', 'required': True},
            {'key': 'broker_port', 'label': 'Port',             'placeholder': '1883',              'required': True},
            {'key': 'topic',       'label': 'Topic de données', 'placeholder': 'sensors/mon-capteur/up', 'required': True},
            {'key': 'username',    'label': 'Utilisateur',      'placeholder': '(optionnel)',        'required': False},
            {'key': 'password',    'label': 'Mot de passe',     'placeholder': '(optionnel)',        'required': False},
        ],
        'guide_steps': [
            'Configurez votre gateway ou réseau LoRa pour publier sur le broker MQTT renseigné.',
            'Format JSON attendu : {"timestamp": "2024-01-01T00:00:00Z", "data": {"field": value}}',
            'Un agent worker (ex. paho-mqtt) souscrit au topic et pousse vers l\'endpoint d\'ingestion.',
            'Endpoint d\'ingestion : POST {api_ingest_url} (header : Authorization: Bearer {api_key})',
            'Exemple CLI : mosquitto_sub -h {broker_host} -p {broker_port} -t {topic} \\',
            '  | while read msg; do curl -s -X POST {api_ingest_url} \\',
            '      -H "Authorization: Bearer {api_key}" -H "Content-Type: application/json" \\',
            '      -d "$msg"; done',
        ],
    },
    'http_push': {
        'protocol': 'http_push',
        'label': 'HTTP Push (Webhook)',
        'icon': 'send',
        'description': 'Le serveur réseau LoRa pousse les données vers votre endpoint via HTTP POST.',
        'supports_webhook': True,
        'fields': [],
        'guide_steps': [
            'Configurez le webhook dans votre réseau LoRa (TTN, ChirpStack…) :',
            '  URL : {api_ingest_url}',
            '  Méthode : POST',
            '  Header : Authorization: Bearer {api_key}',
            'Format standard attendu : {"timestamp": "...", "data": {...}}',
            'Les formats TTN et ChirpStack natifs sont aussi acceptés automatiquement.',
        ],
    },
    'ttn': {
        'protocol': 'ttn',
        'label': 'The Things Network (TTN v3)',
        'icon': 'cloud',
        'description': 'Intégration native TTN via webhook HTTP ou MQTT.',
        'supports_webhook': True,
        'fields': [
            {'key': 'app_id',    'label': 'Application ID', 'placeholder': 'my-app@ttn',          'required': True},
            {'key': 'device_id', 'label': 'Device ID',      'placeholder': 'mon-capteur',          'required': True},
            {'key': 'region',    'label': 'Région TTN',     'placeholder': 'eu1',                  'required': True},
            {'key': 'api_key',   'label': 'Clé API TTN',    'placeholder': 'NNSXS.xxxxxxx',        'required': False},
        ],
        'guide_steps': [
            '1. Connectez-vous à TTN Console : https://console.cloud.thethings.network',
            '2. Créez une Application et enregistrez votre device LoRaWAN (OTAA recommandé).',
            '3. Dans Integrations → Webhooks → Add Webhook :',
            '   - Base URL : {api_ingest_url}',
            '   - Authorization : Bearer {api_key}',
            '   - Messages activés : Uplink message',
            '4. Ajoutez un Payload Formatter (JavaScript) pour décoder vos données en objet JSON.',
            'Le payload TTN (uplink_message.decoded_payload) est automatiquement normalisé.',
        ],
    },
    'chirpstack': {
        'protocol': 'chirpstack',
        'label': 'ChirpStack',
        'icon': 'server',
        'description': 'Intégration via ChirpStack Application Server (v3 ou v4).',
        'supports_webhook': True,
        'fields': [
            {'key': 'server',         'label': 'Serveur ChirpStack', 'placeholder': 'https://chirpstack.example.com', 'required': True},
            {'key': 'application_id', 'label': 'Application ID',     'placeholder': '1',                             'required': True},
            {'key': 'api_token',      'label': 'API Token',          'placeholder': 'xxxxxxxx',                      'required': False},
        ],
        'guide_steps': [
            '1. Accédez à votre ChirpStack Application Server.',
            '2. Sélectionnez votre Application → Integrations.',
            '3. Ajoutez une intégration HTTP :',
            '   - Uplink data URL : {api_ingest_url}',
            '   - Headers : Authorization: Bearer {api_key}',
            '4. Configurez le codec de l\'appareil pour décoder le payload LoRa.',
            'Le format ChirpStack (deviceInfo + object) est normalisé automatiquement.',
        ],
    },
    'helium': {
        'protocol': 'helium',
        'label': 'Helium Network',
        'icon': 'radio',
        'description': 'Intégration via Helium Console.',
        'supports_webhook': True,
        'fields': [
            {'key': 'device_eui', 'label': 'Device EUI', 'placeholder': '0000000000000000', 'required': True},
            {'key': 'app_eui',    'label': 'App EUI',    'placeholder': '0000000000000000', 'required': False},
        ],
        'guide_steps': [
            '1. Créez un device dans Helium Console : https://console.helium.com',
            '2. Créez une intégration HTTP :',
            '   - Endpoint : {api_ingest_url}',
            '   - Method : POST',
            '   - Headers : Authorization: Bearer {api_key}',
            '3. Dans Flows, reliez votre device à l\'intégration.',
            '4. Ajoutez un Function pour décoder le payload si nécessaire.',
        ],
    },
    'http_poll': {
        'protocol': 'http_poll',
        'label': 'HTTP Pull (Polling périodique)',
        'icon': 'refresh',
        'description': 'Votre serveur interroge périodiquement l\'API source du capteur.',
        'supports_webhook': False,
        'fields': [
            {'key': 'source_url',     'label': 'URL source',              'placeholder': 'https://api.sensor.io/readings', 'required': True},
            {'key': 'poll_interval_s','label': 'Intervalle (secondes)',   'placeholder': '60',                             'required': True},
            {'key': 'auth_header',    'label': 'Auth source (optionnel)', 'placeholder': 'Bearer xxx',                    'required': False},
        ],
        'guide_steps': [
            '1. Renseignez l\'URL de l\'API source du capteur ou du réseau LoRa.',
            '2. Configurez un job cron ou Celery pour sonder l\'URL à l\'intervalle indiqué.',
            '3. Transformez la réponse au format standard et poussez vers :',
            '   POST {api_ingest_url}',
            '   Authorization: Bearer {api_key}',
            'Exemple cron (chaque minute) :',
            '*/1 * * * * curl -s "{source_url}" | python3 transform.py \\',
            '  | curl -s -X POST {api_ingest_url} \\',
            '      -H "Authorization: Bearer {api_key}" -H "Content-Type: application/json" -d @-',
        ],
    },
}

# ── Guides de connexion Webhook (partagés par plusieurs capteurs) ───────────
#
# TTN/ChirpStack/Helium livrent leurs intégrations HTTP au niveau de
# l'application réseau, jamais par device : `fields` décrit cette config
# partagée (à saisir une fois, sur le Webhook). `sensor_field` décrit le seul
# champ qui reste propre à chaque capteur — l'identifiant qui permet de
# retrouver, dans le flux mélangé reçu par le Webhook, à quel capteur
# appartient chaque uplink.

WEBHOOK_GUIDES = {
    'ttn': {
        'fields': [
            {'key': 'app_id',  'label': 'Application ID', 'placeholder': 'my-app@ttn',   'required': True},
            {'key': 'region',  'label': 'Région TTN',      'placeholder': 'eu1',           'required': True},
            {'key': 'api_key', 'label': 'Clé API TTN',     'placeholder': 'NNSXS.xxxxxxx', 'required': False},
        ],
        'sensor_field': {'key': 'device_id', 'label': 'Device ID', 'placeholder': 'mon-capteur'},
        'guide_steps': [
            '1. Connectez-vous à TTN Console : https://console.cloud.thethings.network',
            '2. Dans votre Application (tous vos devices doivent y être enregistrés) → Integrations → Webhooks → Add Webhook :',
            '   - Base URL : {api_ingest_url}',
            '   - Authorization : Bearer {api_key}',
            '   - Messages activés : Uplink message',
            '3. Un seul webhook suffit pour toute l\'application : chaque device y publie ses uplinks.',
            '4. Sur chaque capteur rattaché à ce webhook, renseignez son Device ID TTN — c\'est ce qui permet de router chaque uplink vers le bon capteur ici.',
            'Le payload TTN (uplink_message.decoded_payload) est automatiquement normalisé.',
        ],
    },
    'chirpstack': {
        'fields': [
            {'key': 'server',         'label': 'Serveur ChirpStack', 'placeholder': 'https://chirpstack.example.com', 'required': True},
            {'key': 'application_id', 'label': 'Application ID',     'placeholder': '1',                             'required': True},
            {'key': 'api_token',      'label': 'API Token',          'placeholder': 'xxxxxxxx',                      'required': False},
        ],
        'sensor_field': {'key': 'device_id', 'label': 'Device EUI', 'placeholder': '0000000000000000'},
        'guide_steps': [
            '1. Accédez à votre ChirpStack Application Server → votre Application → Integrations.',
            '2. Ajoutez une intégration HTTP unique pour toute l\'Application :',
            '   - Uplink data URL : {api_ingest_url}',
            '   - Headers : Authorization: Bearer {api_key}',
            '3. Sur chaque capteur rattaché à ce webhook, renseignez son Device EUI — c\'est ce qui permet de router chaque uplink vers le bon capteur ici.',
            'Le format ChirpStack (deviceInfo + object) est normalisé automatiquement.',
        ],
    },
    'helium': {
        'fields': [
            {'key': 'app_eui', 'label': 'App EUI (optionnel)', 'placeholder': '0000000000000000', 'required': False},
        ],
        'sensor_field': {'key': 'device_id', 'label': 'Device EUI', 'placeholder': '0000000000000000'},
        'guide_steps': [
            '1. Dans Helium Console, créez une intégration HTTP unique :',
            '   - Endpoint : {api_ingest_url}',
            '   - Method : POST',
            '   - Headers : Authorization: Bearer {api_key}',
            '2. Dans Flows, reliez tous vos devices concernés à cette même intégration.',
            '3. Sur chaque capteur rattaché à ce webhook, renseignez son Device EUI — c\'est ce qui permet de router chaque uplink vers le bon capteur ici.',
        ],
    },
    'http_push': {
        'fields': [],
        'sensor_field': {'key': 'device_id', 'label': 'Identifiant device', 'placeholder': 'mon-capteur'},
        'guide_steps': [
            'Configurez un unique webhook côté réseau LoRa, partagé par tous les capteurs concernés :',
            '  URL : {api_ingest_url}',
            '  Méthode : POST',
            '  Header : Authorization: Bearer {api_key}',
            'Chaque payload JSON doit inclure un champ "device_id" identifiant le capteur émetteur :',
            '  {"device_id": "...", "timestamp": "...", "data": {...}}',
            'Sur chaque capteur rattaché à ce webhook, renseignez ce même identifiant.',
        ],
    },
}

# ── Évaluation sécurisée de formule ──────────────────────────────────────────

_MATH_BUILTINS = {k: getattr(math, k) for k in dir(math) if not k.startswith('_')}
_MATH_BUILTINS.update({'abs': abs, 'round': round, 'min': min, 'max': max})


def _safe_eval(formula: str, row: dict):
    try:
        result = eval(formula, {'__builtins__': {}, 'row': row, **_MATH_BUILTINS})  # noqa: S307
        return float(result)
    except Exception:
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_sensor_access(user, sensor) -> bool:
    if _is_developer(user):
        return True
    email = getattr(user, 'email', '')
    if sensor.user_accesses.filter(user_email=email).exists():
        return True
    # Partagé au niveau du Webhook : donne accès à tous ses capteurs, y compris
    # ceux qui y seraient rattachés plus tard (pas de copie figée d'accès).
    return bool(sensor.webhook_id) and sensor.webhook.user_accesses.filter(user_email=email).exists()


def _normalize_payload(payload: dict, protocol: str):
    """Normalise les formats TTN / ChirpStack / standard vers (timestamp, data)."""
    now = timezone.now()

    # TTN v3
    if 'uplink_message' in payload:
        um     = payload['uplink_message']
        ts_str = um.get('received_at') or payload.get('received_at')
        ts     = parse_datetime(ts_str) if ts_str else now
        data   = um.get('decoded_payload') or um.get('frm_payload') or {}
        return ts, data

    # ChirpStack v4
    if 'deviceInfo' in payload:
        ts_str = payload.get('time')
        ts     = parse_datetime(ts_str) if ts_str else now
        data   = payload.get('object') or {}
        return ts, data

    # Format standard
    ts_str = payload.get('timestamp')
    ts     = parse_datetime(ts_str) if ts_str else now
    data   = payload.get('data', payload)
    return ts, data


def _extract_external_device_id(payload: dict, protocol: str) -> str:
    """
    Identifiant du device émetteur tel que porté par le payload réseau — utilisé
    pour router un uplink reçu sur un Webhook partagé vers le bon Sensor
    (Sensor.connection_config['device_id']).
    """
    if protocol == 'ttn':
        return (payload.get('end_device_ids') or {}).get('device_id', '')
    if protocol == 'chirpstack':
        info = payload.get('deviceInfo') or {}
        return info.get('devEui') or info.get('deviceName') or ''
    if protocol == 'helium':
        return payload.get('dev_eui') or payload.get('device_eui') or ''
    # http_push générique : champ "device_id" attendu à la racine du payload
    return payload.get('device_id', '')


# ── Vues ──────────────────────────────────────────────────────────────────────

class MeView(APIView):
    """GET /api/me/ — informations de l'utilisateur connecté."""

    def get(self, request):
        user = request.user
        return Response({
            'email':    user.email,
            'username': user.username,
            'groups':   user.claims.get('groups', []),
            'is_developer': _is_developer(user),
        })


class SensorListView(ListCreateAPIView):
    """
    GET  /api/sensors/ — liste des capteurs (tous si developer, accessibles sinon)
    POST /api/sensors/ — créer un capteur (developers uniquement)
    """

    def get_serializer_class(self):
        return SensorSerializer if self.request.method == 'POST' else SensorListSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsDeveloper()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if _is_developer(user):
            return Sensor.objects.all()
        email = user.email
        ids = SensorUserAccess.objects.filter(user_email=email).values_list('sensor_id', flat=True)
        return Sensor.objects.filter(id__in=ids)


class SensorDetailView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/sensors/:id/ — détail (accès requis)
    PUT    /api/sensors/:id/ — modifier (developers)
    DELETE /api/sensors/:id/ — supprimer (developers)
    """

    queryset             = Sensor.objects.all()
    serializer_class     = SensorSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsAuthenticated(), IsDeveloper()]
        return [IsAuthenticated(), HasSensorAccess()]

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj


class SensorUserAccessListView(APIView):
    """
    GET  /api/sensors/:pk/users/ — liste des accès (developers)
    POST /api/sensors/:pk/users/ — ajouter un accès   (developers)
    """

    permission_classes = [IsAuthenticated, IsDeveloper]

    def get(self, request, pk):
        sensor   = get_object_or_404(Sensor, pk=pk)
        accesses = sensor.user_accesses.all()
        return Response(SensorUserAccessSerializer(accesses, many=True).data)

    def post(self, request, pk):
        sensor = get_object_or_404(Sensor, pk=pk)
        email  = request.data.get('user_email', '').strip().lower()
        if not email:
            return Response({'error': 'user_email requis'}, status=status.HTTP_400_BAD_REQUEST)
        access, created = SensorUserAccess.objects.get_or_create(
            sensor=sensor, user_email=email,
        )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(SensorUserAccessSerializer(access).data, status=code)


class SensorUserAccessDeleteView(APIView):
    """DELETE /api/sensors/:pk/users/:email/ — révoquer un accès (developers)."""

    permission_classes = [IsAuthenticated, IsDeveloper]

    def delete(self, request, pk, email):
        sensor  = get_object_or_404(Sensor, pk=pk)
        deleted, _ = SensorUserAccess.objects.filter(sensor=sensor, user_email=email).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookUserAccessListView(APIView):
    """
    GET  /api/webhooks/:pk/users/ — liste des accès (developers)
    POST /api/webhooks/:pk/users/ — ajouter un accès — donne accès à tous les
    capteurs rattachés à ce webhook, présents et futurs (developers)
    """

    permission_classes = [IsAuthenticated, IsDeveloper]

    def get(self, request, pk):
        webhook  = get_object_or_404(Webhook, pk=pk)
        accesses = webhook.user_accesses.all()
        return Response(WebhookUserAccessSerializer(accesses, many=True).data)

    def post(self, request, pk):
        webhook = get_object_or_404(Webhook, pk=pk)
        email   = request.data.get('user_email', '').strip().lower()
        if not email:
            return Response({'error': 'user_email requis'}, status=status.HTTP_400_BAD_REQUEST)
        access, created = WebhookUserAccess.objects.get_or_create(
            webhook=webhook, user_email=email,
        )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(WebhookUserAccessSerializer(access).data, status=code)


class WebhookUserAccessDeleteView(APIView):
    """DELETE /api/webhooks/:pk/users/:email/ — révoquer un accès (developers)."""

    permission_classes = [IsAuthenticated, IsDeveloper]

    def delete(self, request, pk, email):
        webhook = get_object_or_404(Webhook, pk=pk)
        deleted, _ = WebhookUserAccess.objects.filter(webhook=webhook, user_email=email).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SensorDataView(APIView):
    """
    GET  /api/sensors/:pk/data/ — lectures paginées (JWT ou API key)
    POST /api/sensors/:pk/data/ — ingérer une mesure  (JWT ou API key)
    """

    authentication_classes = []  # on gère l'auth manuellement (API key en plus de JWT)
    permission_classes     = []

    def _resolve_user(self, request):
        """Retourne (user, is_api_key) depuis le header Authorization."""
        from .authentication import KeycloakJWTAuthentication
        auth_header    = request.headers.get('Authorization', '')
        api_key_header = request.headers.get('X-API-Key', '')
        return auth_header, api_key_header

    def _check_access(self, request, sensor) -> bool:
        auth_header    = request.headers.get('Authorization', '')
        api_key_header = request.headers.get('X-API-Key', '')

        # API key directe
        raw_key = api_key_header or (auth_header[7:] if auth_header.startswith('Bearer ') else '')
        if raw_key == sensor.api_key:
            return True

        # JWT Keycloak
        from .authentication import KeycloakJWTAuthentication
        auth = KeycloakJWTAuthentication()
        result = auth.authenticate(request)
        if result is None:
            return False
        user, _ = result
        return _has_sensor_access(user, sensor)

    def _get_jwt_user(self, request):
        from .authentication import KeycloakJWTAuthentication
        auth   = KeycloakJWTAuthentication()
        result = auth.authenticate(request)
        return result[0] if result else None

    def get(self, request, pk):
        sensor = get_object_or_404(Sensor, pk=pk)
        if not self._check_access(request, sensor):
            return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        qs = sensor.readings.all()

        start = request.query_params.get('start')
        end   = request.query_params.get('end')
        if start:
            qs = qs.filter(timestamp__gte=parse_datetime(start))
        if end:
            qs = qs.filter(timestamp__lte=parse_datetime(end))

        try:
            page_size = min(int(request.query_params.get('page_size', 100)), 1000)
            page      = max(int(request.query_params.get('page', 1)), 1)
        except ValueError:
            page_size, page = 100, 1

        total    = qs.count()
        readings = qs[(page - 1) * page_size: page * page_size]

        return Response({
            'count':     total,
            'page':      page,
            'page_size': page_size,
            'results':   SensorReadingSerializer(readings, many=True).data,
        })

    def post(self, request, pk):
        sensor = get_object_or_404(Sensor, pk=pk)
        if not self._check_access(request, sensor):
            return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        payload             = request.data
        timestamp, data     = _normalize_payload(payload, sensor.protocol)

        reading = SensorReading.objects.create(
            sensor=sensor,
            timestamp=timestamp,
            data=data,
        )
        return Response(SensorReadingSerializer(reading).data, status=status.HTTP_201_CREATED)


class SensorConnectionView(APIView):
    """
    GET /api/sensors/:pk/connection/ — config + guide (accès requis)
    PUT /api/sensors/:pk/connection/ — modifier la config (developers)
    """

    def _get_user(self, request):
        from .authentication import KeycloakJWTAuthentication
        result = KeycloakJWTAuthentication().authenticate(request)
        return result[0] if result else None

    def get(self, request, pk):
        sensor = get_object_or_404(Sensor, pk=pk)
        user   = self._get_user(request)
        if not user or not _has_sensor_access(user, sensor):
            return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        guide   = dict(CONNECTION_GUIDES.get(sensor.protocol, {}))
        webhook = sensor.webhook
        return Response({
            'sensor_id':        sensor.id,
            'slug':             sensor.slug,
            'protocol':         sensor.protocol,
            'connection_config': sensor.connection_config,
            'api_key':          sensor.api_key,
            'api_ingest_url':   f'/api/sensors/{sensor.pk}/data/',
            'guide':            guide,
            'webhook_guide':    WEBHOOK_GUIDES.get(sensor.protocol),
            # Pas de secret ici (api_key/connection_config du Webhook) : ce champ
            # est visible par tout utilisateur ayant accès à CE capteur, alors que
            # le Webhook peut en regrouper d'autres auxquels il n'a pas accès.
            # Le détail complet (secret inclus) vit sur /api/webhooks/:id/, réservé
            # aux developers.
            'webhook': (
                {'id': webhook.id, 'name': webhook.name, 'protocol': webhook.protocol}
                if webhook else None
            ),
        })

    def put(self, request, pk):
        sensor = get_object_or_404(Sensor, pk=pk)
        user   = self._get_user(request)
        if not user or not _is_developer(user):
            return Response({'error': 'Réservé aux developers'}, status=status.HTTP_403_FORBIDDEN)

        if 'protocol' in request.data:
            sensor.protocol = request.data['protocol']
        if 'connection_config' in request.data:
            sensor.connection_config = request.data['connection_config']
        if 'webhook' in request.data:
            webhook_id = request.data['webhook']
            if webhook_id in (None, ''):
                sensor.webhook = None
            else:
                webhook = get_object_or_404(Webhook, pk=webhook_id)
                if webhook.protocol != sensor.protocol:
                    return Response(
                        {'error': f"Ce webhook est en protocole {webhook.protocol}, incompatible avec le protocole {sensor.protocol} du capteur."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                sensor.webhook = webhook
        sensor.save()
        return Response({
            'protocol':         sensor.protocol,
            'connection_config': sensor.connection_config,
            'webhook':          sensor.webhook_id,
        })


class ConnectionMethodsView(APIView):
    """GET /api/connection-methods/ — liste tous les guides disponibles."""

    def get(self, request):
        methods = []
        for protocol, guide in CONNECTION_GUIDES.items():
            entry = dict(guide)
            entry['webhook_guide'] = WEBHOOK_GUIDES.get(protocol)
            methods.append(entry)
        return Response(methods)


class WebhookListView(ListCreateAPIView):
    """
    GET  /api/webhooks/ — liste des webhooks (developers)
    POST /api/webhooks/ — créer un webhook (developers)
    """

    queryset            = Webhook.objects.all()
    serializer_class    = WebhookSerializer
    permission_classes  = [IsAuthenticated, IsDeveloper]


class WebhookDetailView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/webhooks/:id/ — détail, secret + capteurs rattachés (developers)
    PUT    /api/webhooks/:id/ — modifier (developers)
    DELETE /api/webhooks/:id/ — supprimer — détache les capteurs rattachés (developers)
    """

    queryset            = Webhook.objects.all()
    serializer_class    = WebhookSerializer
    permission_classes  = [IsAuthenticated, IsDeveloper]


class WebhookDataView(APIView):
    """
    POST /api/webhooks/:pk/data/ — point d'ingestion partagé par tous les capteurs
    rattachés à ce webhook. Route chaque uplink vers le bon Sensor via l'identifiant
    de device porté par le payload réseau (voir _extract_external_device_id).
    """

    authentication_classes = []
    permission_classes     = []

    def _check_access(self, request, webhook) -> bool:
        auth_header    = request.headers.get('Authorization', '')
        api_key_header = request.headers.get('X-API-Key', '')
        raw_key = api_key_header or (auth_header[7:] if auth_header.startswith('Bearer ') else '')
        if raw_key == webhook.api_key:
            return True

        from .authentication import KeycloakJWTAuthentication
        auth = KeycloakJWTAuthentication()
        result = auth.authenticate(request)
        if result is None:
            return False
        user, _ = result
        return _is_developer(user)

    def post(self, request, pk):
        webhook = get_object_or_404(Webhook, pk=pk)
        if not self._check_access(request, webhook):
            return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        payload     = request.data
        external_id = _extract_external_device_id(payload, webhook.protocol)
        if not external_id:
            return Response(
                {'error': "Identifiant de device introuvable dans le payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sensor = webhook.sensors.filter(connection_config__device_id=external_id).first()
        if sensor is None:
            return Response(
                {'error': f"Aucun capteur rattaché à ce webhook avec device_id={external_id!r}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        timestamp, data = _normalize_payload(payload, webhook.protocol)
        reading = SensorReading.objects.create(sensor=sensor, timestamp=timestamp, data=data)
        return Response(SensorReadingSerializer(reading).data, status=status.HTTP_201_CREATED)


class ComputedMeasureListView(ListCreateAPIView):
    """
    GET  /api/sensors/:pk/measures/ — liste des grandeurs
    POST /api/sensors/:pk/measures/ — créer une grandeur
    """

    serializer_class   = ComputedMeasureSerializer
    permission_classes = [IsAuthenticated]

    def _get_sensor(self):
        sensor = get_object_or_404(Sensor, pk=self.kwargs['pk'])
        if not _has_sensor_access(self.request.user, sensor):
            self.permission_denied(self.request)
        return sensor

    def get_queryset(self):
        try:
            return self._get_sensor().measures.all()
        except Exception:
            return ComputedMeasure.objects.none()

    def perform_create(self, serializer):
        sensor = get_object_or_404(Sensor, pk=self.kwargs['pk'])
        serializer.save(sensor=sensor)


class ComputedMeasureDetailView(RetrieveUpdateDestroyAPIView):
    """GET / PUT / DELETE /api/measures/:pk/"""

    queryset           = ComputedMeasure.objects.all()
    serializer_class   = ComputedMeasureSerializer
    permission_classes = [IsAuthenticated]


class MeasureComputeView(APIView):
    """
    GET /api/measures/:pk/compute/?start=...&end=...
    Évalue la formule de la grandeur sur l'ensemble des lectures dans la plage.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        measure = get_object_or_404(ComputedMeasure, pk=pk)
        sensor  = measure.sensor

        if not _has_sensor_access(request.user, sensor):
            return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        qs = sensor.readings.all()
        start = request.query_params.get('start')
        end   = request.query_params.get('end')
        if start:
            qs = qs.filter(timestamp__gte=parse_datetime(start))
        if end:
            qs = qs.filter(timestamp__lte=parse_datetime(end))
        qs = qs.order_by('timestamp')[:2000]

        points = []
        for reading in qs:
            value = _safe_eval(measure.formula, reading.data)
            if value is not None:
                points.append({'t': reading.timestamp.isoformat(), 'v': value})

        return Response({
            'measure': ComputedMeasureSerializer(measure).data,
            'points':  points,
        })
