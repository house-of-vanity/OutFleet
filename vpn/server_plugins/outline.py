import logging
from venv import logger
import requests
from django.db import models
from .generic import Server
from urllib3 import PoolManager
from outline_vpn.outline_vpn import OutlineVPN, OutlineServerErrorException
from polymorphic.admin import PolymorphicChildModelAdmin
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.db.models import Count


class OutlineConnectionError(Exception):
    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception

class _FingerprintAdapter(requests.adapters.HTTPAdapter):
	"""
	This adapter injected into the requests session will check that the
	fingerprint for the certificate matches for every request
	"""

	def __init__(self, fingerprint=None, **kwargs):
		self.fingerprint = str(fingerprint)
		super(_FingerprintAdapter, self).__init__(**kwargs)

	def init_poolmanager(self, connections, maxsize, block=False):
		self.poolmanager = PoolManager(
			num_pools=connections,
			maxsize=maxsize,
			block=block,
			assert_fingerprint=self.fingerprint,
		)


class OutlineServer(Server):
    logger = logging.getLogger(__name__)
    admin_url = models.URLField()
    admin_access_cert = models.CharField(max_length=255)
    client_server_name = models.CharField(max_length=255)
    client_hostname = models.CharField(max_length=255)
    client_port = models.CharField(max_length=5)
    
    class Meta:
        verbose_name = 'Outline'
        verbose_name_plural = 'Outline'

    def save(self, *args, **kwargs):
        self.server_type = 'Outline'
        super().save(*args, **kwargs)

    @property
    def status(self):
        return self.get_server_status(raw=True)
    
    @property
    def client(self):
        return OutlineVPN(api_url=self.admin_url, cert_sha256=self.admin_access_cert)


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.client_hostname}:{self.client_port})"
    
    def get_server_status(self, raw=False):
        status = {}
        try:
            info = self.client.get_server_information()
            if raw:
                status = info
            else:
                keys = self.client.get_keys()
                status.update(info)
                status.update({"keys": len(keys)})
        except Exception as e:
            status.update({f"error": e})
        return status
    
    def sync_users(self):
        from vpn.models import User, ACL
        logger.debug(f"[{self.name}] Sync all users")
        keys = self.client.get_keys()
        acls = ACL.objects.filter(server=self)
        acl_users = set(acl.user for acl in acls)

        for user in User.objects.all():
            if user in acl_users:
                self.add_user(user=user)
            else:
                self.delete_user(user=user)

        return True

    
    def sync(self):
        status = {}
        try:
            state = self.client.get_server_information()
            if state["name"] != self.name:
                self.client.set_server_name(self.name)
                status["name"] = f"{state['name']} -> {self.name}"
            elif state["hostnameForAccessKeys"] != self.client_hostname:
                self.client.set_hostname(self.client_hostname)
                status["hostnameForAccessKeys"] = f"{state['hostnameForAccessKeys']} -> {self.client_hostname}"
            elif int(state["portForNewAccessKeys"]) != int(self.client_port):
                self.client.set_port_new_for_access_keys(int(self.client_port))
                status["portForNewAccessKeys"] = f"{state['portForNewAccessKeys']} -> {self.client_port}"
            if len(status) == 0:
                status = {"status": "Nothing to do"}
            return status
        except AttributeError as e:
            raise OutlineConnectionError("Client error. Can't connect.", original_exception=e)

    def _get_key(self, user):
        return self.client.get_key(user.hash)

    def get_user(self, user, raw=False):
        user_info = self._get_key(user)
        if raw:
            return user_info
        else:
            outline_key_dict = user_info.__dict__

            outline_key_dict = {
                key: value 
                for key, value in user_info.__dict__.items() 
                if not key.startswith('_') and key not in [] # fields to mask
            }
            return outline_key_dict
        

    def add_user(self, user):
        try:
            server_user = self._get_key(user)
        except OutlineServerErrorException as e:
            server_user = None
        logger.debug(f"[{self.name}] User {str(server_user)}")

        result = {}
        key = None

        if server_user:
            if server_user.method != "chacha20-ietf-poly1305" or \
            server_user.port != int(self.client_port) or \
            server_user.username != user.username or \
            server_user.password != user.hash or \
            self.client.delete_key(user.hash):

                self.delete_user(user)
                key = self.client.create_key(
                    key_id=user.hash,
                    name=user.username,
                    method=server_user.method,
                    password=user.hash,
                    data_limit=None,
                    port=server_user.port
                )
                logger.debug(f"[{self.name}] User {user.username} updated")
        else:
            try:
                key = self.client.create_key(
                    key_id=user.hash,
                    name=user.username,
                    method="chacha20-ietf-poly1305",
                    password=user.hash,
                    data_limit=None,
                    port=int(self.client_port)
                )
                logger.info(f"[{self.name}] User {user.username} created")
            except OutlineServerErrorException as e:
                error_message = str(e)
                if "code\":\"Conflict" in error_message:
                    logger.warning(f"[{self.name}] Conflict for User {user.username}, trying to force sync. {error_message}")
                    for key in self.client.get_keys():
                        logger.warning(f"[{self.name}] hash: {user.hash}, password: {key.password}")
                        if key.password == user.hash:
                            self.client.delete_key(key.key_id)
                            logger.warning(f"[{self.name}] Removed orphan key{str(key)}")
                    return self.add_user(user)
                else:
                    raise OutlineConnectionError("API Error", original_exception=e)
        try:
            result['key_id'] = key.key_id
            result['name'] = key.name
            result['method'] = key.method
            result['password'] = key.password
            result['data_limit'] = key.data_limit
            result['port'] = key.port
        except Exception as e:
            result = {"error": str(e)}
        return result

    def delete_user(self, user):
        result = None
        try:
            server_user = self._get_key(user)
        except OutlineServerErrorException as e:
            return {"status": "User not found on server. Nothing to do."}

        if server_user:
            self.logger.info(f"[{self.name}] TEST")
            self.client.delete_key(server_user.key_id)
            result = {"status": "User was deleted"}
            self.logger.info(f"[{self.name}] User deleted: {user.username} on server {self.name}")

        return result



class OutlineServerAdmin(PolymorphicChildModelAdmin):
    base_model = OutlineServer
    show_in_index = False  # Не отображать в главном списке админки
    list_display = (
        'name',
        'admin_url',
        'admin_access_cert',
        'client_server_name',
        'client_hostname',
        'client_port',
        'server_status_inline',
        'user_count',
        'registration_date'
    )
    readonly_fields = ('server_status_full', )
    exclude = ('server_type',)

    @admin.display(description='Clients', ordering='user_count')
    def user_count(self, obj):
        return obj.user_count

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(user_count=Count('acl__user'))
        return qs

    def server_status_inline(self, obj):
        status = obj.get_server_status()
        if 'error' in status:
            return mark_safe(f"<span style='color: red;'>Error: {status['error']}</span>")
        # Преобразуем JSON в красивый формат
        import json
        pretty_status = json.dumps(status, indent=4)
        return mark_safe(f"<pre>{pretty_status}</pre>")
    server_status_inline.short_description = "Status"

    def server_status_full(self, obj):
        if obj and obj.pk:
            status = obj.get_server_status()
            if 'error' in status:
                return mark_safe(f"<span style='color: red;'>Error: {status['error']}</span>")
            import json
            pretty_status = json.dumps(status, indent=4)
            return mark_safe(f"<pre>{pretty_status}</pre>")
        return "N/A"

    server_status_full.short_description = "Server Status"

    def get_model_perms(self, request):
        """It disables display for sub-model"""
        return {}
    
admin.site.register(OutlineServer, OutlineServerAdmin)