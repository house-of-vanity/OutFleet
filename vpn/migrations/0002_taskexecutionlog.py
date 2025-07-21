# Generated manually to fix migration issue

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vpn', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP TABLE IF EXISTS vpn_taskexecutionlog CASCADE;",
            reverse_sql="-- No reverse operation"
        ),
        migrations.CreateModel(
            name='TaskExecutionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_id', models.CharField(help_text='Celery task ID', max_length=255)),
                ('task_name', models.CharField(help_text='Task name', max_length=100)),
                ('action', models.CharField(help_text='Action performed', max_length=100)),
                ('status', models.CharField(choices=[('STARTED', 'Started'), ('SUCCESS', 'Success'), ('FAILURE', 'Failure'), ('RETRY', 'Retry')], default='STARTED', max_length=20)),
                ('message', models.TextField(help_text='Detailed execution message')),
                ('execution_time', models.FloatField(blank=True, help_text='Execution time in seconds', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('server', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='vpn.server')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='vpn.user')),
            ],
            options={
                'verbose_name': 'Task Execution Log',
                'verbose_name_plural': 'Task Execution Logs',
                'ordering': ['-created_at'],
            },
        ),
        # Create indexes with safe SQL to avoid conflicts
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS vpn_taskexec_task_id_idx ON vpn_taskexecutionlog (task_id);",
            reverse_sql="DROP INDEX IF EXISTS vpn_taskexec_task_id_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS vpn_taskexec_created_idx ON vpn_taskexecutionlog (created_at);",
            reverse_sql="DROP INDEX IF EXISTS vpn_taskexec_created_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS vpn_taskexec_status_idx ON vpn_taskexecutionlog (status);",
            reverse_sql="DROP INDEX IF EXISTS vpn_taskexec_status_idx;"
        ),
    ]
