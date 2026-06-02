from rest_framework import serializers
from .models import Sensor, SensorUserAccess, SensorReading, ComputedMeasure


class SensorUserAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SensorUserAccess
        fields = ['id', 'user_email', 'granted_at']
        read_only_fields = ['granted_at']


class SensorSerializer(serializers.ModelSerializer):
    """Serializer complet — utilisé pour le détail et la gestion admin."""

    protocol_display = serializers.CharField(source='get_protocol_display', read_only=True)
    user_accesses    = SensorUserAccessSerializer(many=True, read_only=True)
    reading_count    = serializers.SerializerMethodField()

    class Meta:
        model  = Sensor
        fields = [
            'id', 'name', 'slug', 'description', 'protocol', 'protocol_display',
            'connection_config', 'api_key', 'is_active',
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

    class Meta:
        model  = Sensor
        fields = [
            'id', 'name', 'slug', 'description', 'protocol', 'protocol_display',
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
