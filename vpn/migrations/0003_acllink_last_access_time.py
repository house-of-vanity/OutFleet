# Generated migration for adding last_access_time field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vpn', '0002_taskexecutionlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='acllink',
            name='last_access_time',
            field=models.DateTimeField(blank=True, help_text='Last time this link was accessed', null=True),
        ),
    ]
