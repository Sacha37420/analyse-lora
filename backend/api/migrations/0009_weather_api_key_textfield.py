from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Les jetons Météo-France réels (portail DPClim) sont des chaînes bien plus
    longues que prévu (observé : > 2000 caractères) — CharField(200) était trop
    court. TextField est illimité côté Postgres.
    """

    dependencies = [('api', '0008_weather_scope_per_webhook_sensor')]

    operations = [
        migrations.AlterField(
            model_name='webhook',
            name='weather_api_key',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='sensor',
            name='weather_api_key',
            field=models.TextField(blank=True),
        ),
    ]
