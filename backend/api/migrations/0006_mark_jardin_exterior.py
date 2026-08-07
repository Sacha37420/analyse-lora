from django.db import migrations


def mark_exterior_sensors(apps, schema_editor):
    """
    Best-effort : reprend les capteurs existants dont le nom/device_id trahit
    un usage extérieur (ex. « Jardin », device_id 'temp-exterieur') et les
    bascule en location='exterior'. Réglable ensuite à la main depuis la page
    Admin > Capteurs — ce n'est qu'une reprise de données initiale.
    """
    Sensor = apps.get_model('api', 'Sensor')
    hints = ('exterieur', 'extérieur', 'exterior', 'jardin', 'outdoor', 'dehors')

    for sensor in Sensor.objects.all():
        name     = (sensor.name or '').lower()
        device_id = (sensor.connection_config or {}).get('device_id', '').lower()
        if any(h in name for h in hints) or any(h in device_id for h in hints):
            sensor.location = 'exterior'
            sensor.save(update_fields=['location'])


def revert(apps, schema_editor):
    Sensor = apps.get_model('api', 'Sensor')
    Sensor.objects.filter(location='exterior').update(location='interior')


class Migration(migrations.Migration):

    dependencies = [('api', '0005_sensor_location_weathersettings')]

    operations = [
        migrations.RunPython(mark_exterior_sensors, revert),
    ]
