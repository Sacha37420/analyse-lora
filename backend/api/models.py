import secrets
from django.db import models

PROTOCOL_CHOICES = [
    ('mqtt',        'MQTT'),
    ('http_push',   'HTTP Push (Webhook)'),
    ('http_poll',   'HTTP Pull (Polling)'),
    ('ttn',         'The Things Network (TTN v3)'),
    ('chirpstack',  'ChirpStack'),
    ('helium',      'Helium Network'),
]


class Sensor(models.Model):
    name             = models.CharField(max_length=100)
    slug             = models.SlugField(max_length=50, unique=True)
    description      = models.TextField(blank=True)
    protocol         = models.CharField(max_length=30, choices=PROTOCOL_CHOICES, default='mqtt')
    connection_config = models.JSONField(default=dict, blank=True)
    api_key          = models.CharField(max_length=64, unique=True, blank=True)
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sensors'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'{self.name} ({self.get_protocol_display()})'


class SensorUserAccess(models.Model):
    """Accès explicite d'un utilisateur à un capteur (complète la logique groupe developers)."""

    sensor     = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='user_accesses')
    user_email = models.EmailField()
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'sensor_user_accesses'
        constraints     = [models.UniqueConstraint(fields=['sensor', 'user_email'], name='unique_sensor_user')]
        ordering        = ['user_email']

    def __str__(self) -> str:
        return f'{self.user_email} → {self.sensor.name}'


class SensorReading(models.Model):
    """Mesure brute reçue d'un capteur, stockée en JSON."""

    sensor      = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='readings')
    timestamp   = models.DateTimeField()
    data        = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sensor_readings'
        ordering = ['-timestamp']
        indexes  = [models.Index(fields=['sensor', 'timestamp'], name='sensor_ts_idx')]

    def __str__(self) -> str:
        return f'{self.sensor.name} @ {self.timestamp}'


class ComputedMeasure(models.Model):
    """
    Grandeur dérivée calculée à partir des données brutes d'un capteur.
    La formule est une expression Python : row['temperature'] * 9/5 + 32
    """

    sensor      = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='measures')
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    formula     = models.TextField()
    unit        = models.CharField(max_length=20, blank=True)
    color       = models.CharField(max_length=7, default='#3b82f6')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table    = 'computed_measures'
        constraints = [models.UniqueConstraint(fields=['sensor', 'name'], name='unique_measure_name')]
        ordering    = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.sensor.name})'
