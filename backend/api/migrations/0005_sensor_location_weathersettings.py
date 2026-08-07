from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('api', '0004_ttn_sensors_use_webhook')]

    operations = [
        migrations.AddField(
            model_name='sensor',
            name='location',
            field=models.CharField(
                choices=[('interior', 'Intérieur'), ('exterior', 'Extérieur')],
                default='interior',
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name='WeatherSettings',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('api_key',    models.CharField(blank=True, max_length=200)),
                ('location',   models.CharField(blank=True, max_length=200)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'weather_settings'},
        ),
    ]
