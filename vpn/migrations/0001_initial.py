# Initial migration

from django.conf import settings
from django.db import migrations, models
import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
import shortuuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('comment', models.TextField(blank=True, default='', help_text='Free form user comment')),
                ('registration_date', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('last_access', models.DateTimeField(blank=True, null=True)),
                ('hash', models.CharField(help_text='Random user hash. It\'s using for client config generation.', max_length=64, unique=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='AccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.CharField(blank=True, editable=False, max_length=256, null=True)),
                ('server', models.CharField(blank=True, editable=False, max_length=256, null=True)),
                ('action', models.CharField(editable=False, max_length=100)),
                ('data', models.TextField(blank=True, default='', editable=False)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Server',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Server name', max_length=100)),
                ('comment', models.TextField(blank=True, default='')),
                ('registration_date', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('server_type', models.CharField(choices=[('Outline', 'Outline'), ('Wireguard', 'Wireguard')], editable=False, max_length=50)),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_%(app_label)s.%(class)s_set+', to='contenttypes.contenttype')),
            ],
            options={
                'verbose_name': 'Server',
                'verbose_name_plural': 'Servers',
                'permissions': [('access_server', 'Can view public status')],
                'base_manager_name': 'objects',
            },
        ),
        migrations.CreateModel(
            name='OutlineServer',
            fields=[
                ('server_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='vpn.server')),
                ('admin_url', models.URLField(help_text='Management URL')),
                ('admin_access_cert', models.CharField(help_text='Fingerprint', max_length=255)),
                ('client_hostname', models.CharField(help_text='Server address for clients', max_length=255)),
                ('client_port', models.CharField(help_text='Server port for clients', max_length=5)),
            ],
            options={
                'verbose_name': 'Outline',
                'verbose_name_plural': 'Outline',
                'base_manager_name': 'objects',
            },
            bases=('vpn.server',),
        ),
        migrations.CreateModel(
            name='WireguardServer',
            fields=[
                ('server_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='vpn.server')),
                ('address', models.CharField(max_length=100)),
                ('port', models.IntegerField()),
                ('client_private_key', models.CharField(max_length=255)),
                ('server_publick_key', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name': 'Wireguard',
                'verbose_name_plural': 'Wireguard',
                'base_manager_name': 'objects',
            },
            bases=('vpn.server',),
        ),
        migrations.CreateModel(
            name='ACL',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vpn.server')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ACLLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField(blank=True, default='', help_text='ACL link comment, device name, etc...')),
                ('link', models.CharField(blank=True, default='', help_text='Access link to get dynamic configuration', max_length=1024, null=True, unique=True, verbose_name='Access link')),
                ('acl', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='links', to='vpn.acl')),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='servers',
            field=models.ManyToManyField(blank=True, help_text='Servers user has access to', through='vpn.ACL', to='vpn.server'),
        ),
        migrations.AddConstraint(
            model_name='acl',
            constraint=models.UniqueConstraint(fields=('user', 'server'), name='unique_user_server'),
        ),
    ]
