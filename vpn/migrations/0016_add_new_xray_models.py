# Generated manually to add new Xray models

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vpn', '0015_remove_old_xray_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='XrayConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grpc_address', models.CharField(default='127.0.0.1:10085', help_text='Xray gRPC API address (host:port)', max_length=255)),
                ('default_client_hostname', models.CharField(help_text='Default hostname for client connections', max_length=255)),
                ('stats_enabled', models.BooleanField(default=True, help_text='Enable traffic statistics')),
                ('cert_renewal_days', models.IntegerField(default=60, help_text='Renew certificates X days before expiration')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Xray Configuration',
                'verbose_name_plural': 'Xray Configuration',
            },
        ),
        migrations.CreateModel(
            name='Credentials',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Descriptive name for these credentials', max_length=100, unique=True)),
                ('cred_type', models.CharField(choices=[('cloudflare', 'Cloudflare API'), ('dns_provider', 'DNS Provider'), ('email', 'Email SMTP'), ('other', 'Other')], help_text='Type of credentials', max_length=20)),
                ('credentials', models.JSONField(help_text="Credentials data (e.g., {'api_token': '...', 'email': '...'})")),
                ('description', models.TextField(blank=True, help_text='Description of what these credentials are used for')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Credentials',
                'verbose_name_plural': 'Credentials',
                'ordering': ['cred_type', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Certificate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(help_text='Domain name for this certificate', max_length=255, unique=True)),
                ('certificate_pem', models.TextField(help_text='Certificate in PEM format')),
                ('private_key_pem', models.TextField(help_text='Private key in PEM format')),
                ('cert_type', models.CharField(choices=[('self_signed', 'Self-Signed'), ('letsencrypt', "Let's Encrypt"), ('custom', 'Custom')], help_text='Type of certificate', max_length=20)),
                ('expires_at', models.DateTimeField(help_text='Certificate expiration date')),
                ('auto_renew', models.BooleanField(default=True, help_text='Automatically renew certificate before expiration')),
                ('last_renewed', models.DateTimeField(blank=True, help_text='Last renewal timestamp', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('credentials', models.ForeignKey(blank=True, help_text="Credentials for Let's Encrypt (Cloudflare API)", null=True, on_delete=django.db.models.deletion.SET_NULL, to='vpn.credentials')),
            ],
            options={
                'verbose_name': 'Certificate',
                'verbose_name_plural': 'Certificates',
                'ordering': ['domain'],
            },
        ),
        migrations.CreateModel(
            name='Inbound',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Unique identifier for this inbound', max_length=100, unique=True)),
                ('protocol', models.CharField(choices=[('vless', 'VLESS'), ('vmess', 'VMess'), ('trojan', 'Trojan'), ('shadowsocks', 'Shadowsocks')], help_text='Protocol type', max_length=20)),
                ('port', models.IntegerField(help_text='Port to listen on')),
                ('network', models.CharField(choices=[('tcp', 'TCP'), ('ws', 'WebSocket'), ('grpc', 'gRPC'), ('http', 'HTTP/2'), ('quic', 'QUIC')], default='tcp', help_text='Transport protocol', max_length=20)),
                ('security', models.CharField(choices=[('none', 'None'), ('tls', 'TLS'), ('reality', 'REALITY')], default='none', help_text='Security type', max_length=20)),
                ('domain', models.CharField(blank=True, help_text='Client connection domain', max_length=255)),
                ('full_config', models.JSONField(default=dict, help_text='Complete configuration for creating inbound on server')),
                ('listen_address', models.CharField(default='0.0.0.0', help_text='IP address to listen on', max_length=45)),
                ('enable_sniffing', models.BooleanField(default=True, help_text='Enable protocol sniffing')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('certificate', models.ForeignKey(blank=True, help_text='Certificate for TLS', null=True, on_delete=django.db.models.deletion.SET_NULL, to='vpn.certificate')),
            ],
            options={
                'verbose_name': 'Inbound',
                'verbose_name_plural': 'Inbounds',
                'ordering': ['protocol', 'port'],
                'unique_together': {('port', 'listen_address')},
            },
        ),
        migrations.CreateModel(
            name='SubscriptionGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="Group name (e.g., 'VLESS Premium', 'VMess Basic')", max_length=100, unique=True)),
                ('description', models.TextField(blank=True, help_text='Description of this subscription group')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this group is active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('inbounds', models.ManyToManyField(blank=True, help_text='Inbounds included in this group', to='vpn.inbound')),
            ],
            options={
                'verbose_name': 'Subscription Group',
                'verbose_name_plural': 'Subscription Groups',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='UserSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=True, help_text='Whether this subscription is active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vpn.subscriptiongroup')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='xray_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Subscription',
                'verbose_name_plural': 'User Subscriptions',
                'ordering': ['user__username', 'subscription_group__name'],
                'unique_together': {('user', 'subscription_group')},
            },
        ),
    ]