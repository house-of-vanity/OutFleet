# Generated migration for UserStatistics model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vpn', '0004_merge_20250721_1223'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserStatistics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('server_name', models.CharField(max_length=256)),
                ('acl_link_id', models.CharField(blank=True, help_text='None for server-level stats', max_length=1024, null=True)),
                ('total_connections', models.IntegerField(default=0)),
                ('recent_connections', models.IntegerField(default=0)),
                ('daily_usage', models.JSONField(default=list, help_text='Daily connection counts for last 30 days')),
                ('max_daily', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Statistics',
                'verbose_name_plural': 'User Statistics',
            },
        ),
        migrations.AddIndex(
            model_name='userstatistics',
            index=models.Index(fields=['user', 'server_name'], name='vpn_usersta_user_id_1c7cd0_idx'),
        ),
        migrations.AddIndex(
            model_name='userstatistics',
            index=models.Index(fields=['updated_at'], name='vpn_usersta_updated_8e6e9b_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='userstatistics',
            unique_together={('user', 'server_name', 'acl_link_id')},
        ),
    ]
