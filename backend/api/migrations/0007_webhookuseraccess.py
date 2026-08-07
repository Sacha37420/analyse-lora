from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [('api', '0006_mark_jardin_exterior')]

    operations = [
        migrations.CreateModel(
            name='WebhookUserAccess',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('user_email', models.EmailField(max_length=254)),
                ('granted_at', models.DateTimeField(auto_now_add=True)),
                ('webhook',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='user_accesses',
                    to='api.webhook',
                )),
            ],
            options={'db_table': 'webhook_user_accesses', 'ordering': ['user_email']},
        ),
        migrations.AddConstraint(
            model_name='webhookuseraccess',
            constraint=models.UniqueConstraint(fields=['webhook', 'user_email'], name='unique_webhook_user'),
        ),
    ]
