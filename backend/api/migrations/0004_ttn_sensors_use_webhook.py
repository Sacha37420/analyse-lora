import secrets
from django.db import migrations


def migrate_ttn_sensors_to_webhook(apps, schema_editor):
    """
    Reprend les capteurs TTN existants (app_id/region/api_key dupliqués dans
    chaque connection_config) et les rattache à un unique Webhook partagé —
    c'est ainsi que TTN fonctionne réellement (une intégration par application,
    jamais par device). Seul le device_id, propre à chaque capteur, reste en
    connection_config du Sensor.
    """
    Sensor  = apps.get_model('api', 'Sensor')
    Webhook = apps.get_model('api', 'Webhook')

    ttn_sensors = list(Sensor.objects.filter(protocol='ttn', webhook__isnull=True))
    if not ttn_sensors:
        return

    reference = ttn_sensors[0].connection_config or {}
    app_id = reference.get('app_id')
    region = reference.get('region')

    same_app = [
        s for s in ttn_sensors
        if (s.connection_config or {}).get('app_id') == app_id
        and (s.connection_config or {}).get('region') == region
    ]

    webhook = Webhook.objects.create(
        name='sacha-webhook',
        protocol='ttn',
        connection_config={
            'app_id':  app_id,
            'region':  region,
            'api_key': reference.get('api_key', ''),
        },
        api_key=secrets.token_hex(32),
        is_active=True,
    )

    for sensor in same_app:
        device_id = (sensor.connection_config or {}).get('device_id', '')
        sensor.webhook = webhook
        sensor.connection_config = {'device_id': device_id}
        sensor.save(update_fields=['webhook', 'connection_config'])


def revert(apps, schema_editor):
    Webhook = apps.get_model('api', 'Webhook')

    for webhook in Webhook.objects.filter(name='sacha-webhook'):
        for sensor in webhook.sensors.all():
            sensor.connection_config = {
                'app_id':    webhook.connection_config.get('app_id', ''),
                'region':    webhook.connection_config.get('region', ''),
                'api_key':   webhook.connection_config.get('api_key', ''),
                'device_id': (sensor.connection_config or {}).get('device_id', ''),
            }
            sensor.webhook = None
            sensor.save(update_fields=['webhook', 'connection_config'])
        webhook.delete()


class Migration(migrations.Migration):

    dependencies = [('api', '0003_webhook')]

    operations = [
        migrations.RunPython(migrate_ttn_sensors_to_webhook, revert),
    ]
