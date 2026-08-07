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

# Protocoles où un serveur réseau pousse, sous une seule intégration HTTP,
# les uplinks de plusieurs devices — ceux-là seuls peuvent partager un Webhook.
# mqtt (topic dédié par capteur) et http_poll (l'app interroge une URL propre
# au capteur) n'ont pas d'entité « app » à mutualiser : toujours autonomes.
WEBHOOK_PROTOCOL_CHOICES = [
    c for c in PROTOCOL_CHOICES if c[0] in ('http_push', 'ttn', 'chirpstack', 'helium')
]

LOCATION_CHOICES = [
    ('interior', 'Intérieur'),
    ('exterior', 'Extérieur'),
]


class Webhook(models.Model):
    """
    Point d'ingestion HTTP partagé par plusieurs capteurs d'une même « application »
    réseau (application TTN, Application ChirpStack, Flow Helium…). Le réseau LoRa
    n'envoie ces intégrations qu'au niveau de l'app, jamais par device : un capteur
    isolé peut rester en configuration autonome (Sensor.webhook = None).
    """

    name             = models.CharField(max_length=100, unique=True)
    protocol         = models.CharField(max_length=30, choices=WEBHOOK_PROTOCOL_CHOICES)
    connection_config = models.JSONField(default=dict, blank=True)
    api_key          = models.CharField(max_length=64, unique=True, blank=True)
    # Config Météo-France propre à ce webhook — un webhook regroupe des capteurs
    # d'un même lieu physique (même application réseau), donc une seule localisation
    # a du sens ici. Sert à borner les jauges de température (voir api/weather.py).
    weather_api_key  = models.TextField(blank=True)
    weather_location = models.CharField(max_length=200, blank=True)
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'webhooks'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'{self.name} ({self.get_protocol_display()})'


class WebhookUserAccess(models.Model):
    """
    Accès explicite d'un utilisateur à un Webhook — donne accès à tous les
    capteurs qui y sont rattachés, y compris ceux ajoutés plus tard (voir
    _has_sensor_access). Ne donne PAS accès au détail du Webhook lui-même
    (secret d'ingestion, connection_config) : ça reste réservé aux developers.
    """

    webhook    = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='user_accesses')
    user_email = models.EmailField()
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table    = 'webhook_user_accesses'
        constraints = [models.UniqueConstraint(fields=['webhook', 'user_email'], name='unique_webhook_user')]
        ordering    = ['user_email']

    def __str__(self) -> str:
        return f'{self.user_email} → {self.webhook.name}'


class Sensor(models.Model):
    name             = models.CharField(max_length=100)
    slug             = models.SlugField(max_length=50, unique=True)
    description      = models.TextField(blank=True)
    protocol         = models.CharField(max_length=30, choices=PROTOCOL_CHOICES, default='mqtt')
    connection_config = models.JSONField(default=dict, blank=True)
    api_key          = models.CharField(max_length=64, unique=True, blank=True)
    webhook          = models.ForeignKey(Webhook, null=True, blank=True, on_delete=models.SET_NULL, related_name='sensors')
    location         = models.CharField(max_length=10, choices=LOCATION_CHOICES, default='interior')
    # Config Météo-France propre à ce capteur — utilisée seulement quand il n'est
    # rattaché à aucun webhook (sinon c'est la config du webhook qui s'applique,
    # voir Webhook.weather_api_key/weather_location).
    weather_api_key  = models.TextField(blank=True)
    weather_location = models.CharField(max_length=200, blank=True)
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
