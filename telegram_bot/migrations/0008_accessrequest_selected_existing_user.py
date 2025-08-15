# Generated migration for adding selected_existing_user field

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('telegram_bot', '0007_remove_botsettings_help_message_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='accessrequest',
            name='selected_existing_user',
            field=models.ForeignKey(
                blank=True,
                help_text='Existing user selected to link with this Telegram account',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='selected_for_requests',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]