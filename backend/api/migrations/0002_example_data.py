import datetime
import secrets
from django.db import migrations
from django.utils import timezone


def add_example_sensors(apps, schema_editor):
    Sensor        = apps.get_model('api', 'Sensor')
    SensorReading = apps.get_model('api', 'SensorReading')

    s1 = Sensor.objects.create(
        name='Capteur Température Serre',
        slug='temp-serre-01',
        description='Capteur HTU21D dans la serre principale — température et humidité',
        protocol='mqtt',
        connection_config={
            'broker_host': 'mqtt.local',
            'broker_port': '1883',
            'topic':       'sensors/temp-serre-01/up',
        },
        api_key=secrets.token_hex(32),
        is_active=True,
    )

    s2 = Sensor.objects.create(
        name='Pluviomètre Jardin',
        slug='pluv-jardin-01',
        description='Pluviomètre LoRa via TTN — cumul pluie + tension batterie',
        protocol='ttn',
        connection_config={
            'app_id':    'garden-monitor',
            'device_id': 'pluv-01',
            'region':    'eu1',
        },
        api_key=secrets.token_hex(32),
        is_active=True,
    )

    now = timezone.now()

    # 24 h de données simulées pour le capteur de température
    for i in range(48):
        ts = now - datetime.timedelta(minutes=i * 30)
        SensorReading.objects.create(
            sensor=s1,
            timestamp=ts,
            data={
                'temperature': round(16 + (i % 12) * 0.8 + (i % 3) * 0.2, 1),
                'humidity':    round(60 + (i % 7) * 2.5 - (i % 5), 1),
            },
        )

    # 7 jours de données pour le pluviomètre
    for i in range(28):
        ts = now - datetime.timedelta(hours=i * 6)
        SensorReading.objects.create(
            sensor=s2,
            timestamp=ts,
            data={
                'rain_mm':   round((i % 5) * 1.8, 1),
                'battery_v': round(3.7 - i * 0.01, 2),
            },
        )


class Migration(migrations.Migration):

    dependencies = [('api', '0001_initial')]

    operations = [
        migrations.RunPython(add_example_sensors, migrations.RunPython.noop),
    ]
