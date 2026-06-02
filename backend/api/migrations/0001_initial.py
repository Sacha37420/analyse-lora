from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Sensor',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name',             models.CharField(max_length=100)),
                ('slug',             models.SlugField(unique=True)),
                ('description',      models.TextField(blank=True)),
                ('protocol',         models.CharField(
                    choices=[
                        ('mqtt',       'MQTT'),
                        ('http_push',  'HTTP Push (Webhook)'),
                        ('http_poll',  'HTTP Pull (Polling)'),
                        ('ttn',        'The Things Network (TTN v3)'),
                        ('chirpstack', 'ChirpStack'),
                        ('helium',     'Helium Network'),
                    ],
                    default='mqtt',
                    max_length=30,
                )),
                ('connection_config', models.JSONField(blank=True, default=dict)),
                ('api_key',          models.CharField(blank=True, max_length=64, unique=True)),
                ('is_active',        models.BooleanField(default=True)),
                ('created_at',       models.DateTimeField(auto_now_add=True)),
                ('updated_at',       models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'sensors', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='SensorUserAccess',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('user_email', models.EmailField()),
                ('granted_at', models.DateTimeField(auto_now_add=True)),
                ('sensor',     models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='user_accesses',
                    to='api.sensor',
                )),
            ],
            options={'db_table': 'sensor_user_accesses', 'ordering': ['user_email']},
        ),
        migrations.AddConstraint(
            model_name='sensoruseraccess',
            constraint=models.UniqueConstraint(fields=['sensor', 'user_email'], name='unique_sensor_user'),
        ),
        migrations.CreateModel(
            name='SensorReading',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('timestamp',   models.DateTimeField()),
                ('data',        models.JSONField()),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('sensor',      models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='readings',
                    to='api.sensor',
                )),
            ],
            options={'db_table': 'sensor_readings', 'ordering': ['-timestamp']},
        ),
        migrations.AddIndex(
            model_name='sensorreading',
            index=models.Index(fields=['sensor', 'timestamp'], name='sensor_ts_idx'),
        ),
        migrations.CreateModel(
            name='ComputedMeasure',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name',        models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('formula',     models.TextField()),
                ('unit',        models.CharField(blank=True, max_length=20)),
                ('color',       models.CharField(default='#3b82f6', max_length=7)),
                ('created_at',  models.DateTimeField(auto_now_add=True)),
                ('sensor',      models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='measures',
                    to='api.sensor',
                )),
            ],
            options={'db_table': 'computed_measures', 'ordering': ['name']},
        ),
        migrations.AddConstraint(
            model_name='computedmeasure',
            constraint=models.UniqueConstraint(fields=['sensor', 'name'], name='unique_measure_name'),
        ),
    ]
