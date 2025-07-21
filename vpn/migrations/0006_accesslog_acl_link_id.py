# Generated migration for AccessLog acl_link_id field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vpn', '0005_userstatistics'),
    ]

    operations = [
        migrations.AddField(
            model_name='accesslog',
            name='acl_link_id',
            field=models.CharField(blank=True, editable=False, help_text='ID of the ACL link used', max_length=1024, null=True),
        ),
        migrations.AddIndex(
            model_name='accesslog',
            index=models.Index(fields=['acl_link_id'], name='vpn_accessl_acl_lin_b23c6e_idx'),
        ),
    ]
