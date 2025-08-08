# Generated manually to properly remove old Xray models

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('vpn', '0014_alter_xraycoreserver_client_hostname_and_more'),
    ]

    operations = [
        # Remove unique_together first to avoid field reference issues
        migrations.AlterUniqueTogether(
            name='xrayinbound',
            unique_together=None,
        ),
        
        # Remove old models completely
        migrations.DeleteModel(
            name='XrayClient',
        ),
        migrations.DeleteModel(
            name='XrayInbound',
        ),
        migrations.DeleteModel(
            name='XrayInboundServer',
        ),
        migrations.DeleteModel(
            name='XrayCoreServer',
        ),
    ]