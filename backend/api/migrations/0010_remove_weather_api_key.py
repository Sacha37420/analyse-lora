from django.db import migrations


class Migration(migrations.Migration):
    """
    L'intégration météo bascule de Météo-France DPClim (nécessitait un jeton
    portail-api.meteofrance.fr) à Open-Meteo (prévision, gratuite, sans clé)
    — voir api/weather.py. weather_api_key n'a donc plus aucun usage.
    """

    dependencies = [('api', '0009_weather_api_key_textfield')]

    operations = [
        migrations.RemoveField(model_name='webhook', name='weather_api_key'),
        migrations.RemoveField(model_name='sensor', name='weather_api_key'),
    ]
