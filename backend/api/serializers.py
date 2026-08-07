from rest_framework import serializers
from .models import Sensor, SensorUserAccess, SensorReading, ComputedMeasure, Webhook, WebhookUserAccess


class SensorUserAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SensorUserAccess
        fields = ['id', 'user_email', 'granted_at']
        read_only_fields = ['granted_at']


class WebhookUserAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WebhookUserAccess
        fields = ['id', 'user_email', 'granted_at']
        read_only_fields = ['granted_at']


class WebhookSensorSerializer(serializers.ModelSerializer):
    """Vue allégée d'un capteur, imbriquée dans le détail d'un Webhook."""

    device_id = serializers.SerializerMethodField()

    class Meta:
        model  = Sensor
        fields = ['id', 'name', 'slug', 'device_id']

    def get_device_id(self, obj) -> str:
        return (obj.connection_config or {}).get('device_id', '')


class WebhookSerializer(serializers.ModelSerializer):
    protocol_display = serializers.CharField(source='get_protocol_display', read_only=True)
    sensor_count      = serializers.SerializerMethodField()
    sensors           = WebhookSensorSerializer(many=True, read_only=True)
    user_accesses     = WebhookUserAccessSerializer(many=True, read_only=True)

    class Meta:
        model  = Webhook
        fields = [
            'id', 'name', 'protocol', 'protocol_display', 'connection_config',
            'api_key', 'weather_api_key', 'weather_location', 'is_active',
            'created_at', 'updated_at', 'sensor_count', 'sensors', 'user_accesses',
        ]
        read_only_fields = ['api_key', 'created_at', 'updated_at']

    def get_sensor_count(self, obj) -> int:
        return obj.sensors.count()


class SensorSerializer(serializers.ModelSerializer):
    """Serializer complet — utilisé pour le détail et la gestion admin."""

    protocol_display = serializers.CharField(source='get_protocol_display', read_only=True)
    user_accesses    = SensorUserAccessSerializer(many=True, read_only=True)
    reading_count    = serializers.SerializerMethodField()
    webhook_name     = serializers.CharField(source='webhook.name', read_only=True, default=None)

    class Meta:
        model  = Sensor
        fields = [
            'id', 'name', 'slug', 'description', 'protocol', 'protocol_display',
            'connection_config', 'api_key', 'webhook', 'webhook_name', 'location',
            'weather_api_key', 'weather_location', 'is_active',
            'created_at', 'updated_at', 'user_accesses', 'reading_count',
        ]
        read_only_fields = ['api_key', 'created_at', 'updated_at']

    def get_reading_count(self, obj) -> int:
        return obj.readings.count()


class SensorListSerializer(serializers.ModelSerializer):
    """Serializer allégé pour la liste des capteurs."""

    protocol_display = serializers.CharField(source='get_protocol_display', read_only=True)
    reading_count    = serializers.SerializerMethodField()
    last_reading     = serializers.SerializerMethodField()
    webhook_name     = serializers.CharField(source='webhook.name', read_only=True, default=None)

    class Meta:
        model  = Sensor
        fields = [
            'id', 'name', 'slug', 'description', 'protocol', 'protocol_display',
            'webhook', 'webhook_name', 'location', 'weather_api_key', 'weather_location',
            'is_active', 'created_at', 'reading_count', 'last_reading',
        ]

    def get_reading_count(self, obj) -> int:
        return obj.readings.count()

    def get_last_reading(self, obj):
        reading = obj.readings.first()
        if reading:
            return {'timestamp': reading.timestamp, 'data': reading.data}
        return None


class SensorReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SensorReading
        fields = ['id', 'timestamp', 'data', 'received_at']
        read_only_fields = ['received_at']


class ComputedMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ComputedMeasure
        fields = ['id', 'sensor', 'name', 'description', 'formula', 'unit', 'color', 'created_at']
        read_only_fields = ['created_at']
