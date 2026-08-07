from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('api', '0007_webhookuseraccess')]

    operations = [
        migrations.AddField(
            model_name='webhook',
            name='weather_api_key',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='webhook',
            name='weather_location',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='sensor',
            name='weather_api_key',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='sensor',
            name='weather_location',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.DeleteModel(name='WeatherSettings'),
    ]
