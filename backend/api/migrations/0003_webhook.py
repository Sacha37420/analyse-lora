from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [('api', '0002_example_data')]

    operations = [
        migrations.CreateModel(
            name='Webhook',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name',             models.CharField(max_length=100, unique=True)),
                ('protocol',         models.CharField(
                    choices=[
                        ('http_push',  'HTTP Push (Webhook)'),
                        ('ttn',        'The Things Network (TTN v3)'),
                        ('chirpstack', 'ChirpStack'),
                        ('helium',     'Helium Network'),
                    ],
                    max_length=30,
                )),
                ('connection_config', models.JSONField(blank=True, default=dict)),
                ('api_key',          models.CharField(blank=True, max_length=64, unique=True)),
                ('is_active',        models.BooleanField(default=True)),
                ('created_at',       models.DateTimeField(auto_now_add=True)),
                ('updated_at',       models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'webhooks', 'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='sensor',
            name='webhook',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sensors',
                to='api.webhook',
            ),
        ),
    ]
