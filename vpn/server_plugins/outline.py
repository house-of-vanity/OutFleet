import logging
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
    admin_url = models.URLField(help_text="Management URL")
    admin_access_cert = models.CharField(max_length=255, help_text="Fingerprint")
    client_hostname = models.CharField(max_length=255, help_text="Server address for clients")
    client_port = models.CharField(max_length=5, help_text="Server port for clients")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
    
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
                status["all_keys"] = []
                for key in keys:
                    status["all_keys"].append(key.key_id)
        except Exception as e:
            status.update({f"error": e})
        return status
    
    def sync_users(self):
        from vpn.models import User, ACL
        logger = logging.getLogger(__name__)
        logger.debug(f"[{self.name}] Sync all users")
        
        try:
            keys = self.client.get_keys()
        except Exception as e:
            logger.error(f"[{self.name}] Failed to get keys from server: {e}")
            return False
            
        acls = ACL.objects.filter(server=self)
        acl_users = set(acl.user for acl in acls)

        # Log user synchronization details
        user_list = ", ".join([user.username for user in acl_users])
        logger.info(f"[{self.name}] Syncing {len(acl_users)} users: {user_list[:200]}{'...' if len(user_list) > 200 else ''}")

        for user in User.objects.all():
            if user in acl_users:
                try:
                    result = self.add_user(user=user)
                    logger.debug(f"[{self.name}] Added user {user.username}: {result}")
                except Exception as e:
                    logger.error(f"[{self.name}] Failed to add user {user.username}: {e}")
            else:
                try:
                    result = self.delete_user(user=user)
                    if result and 'status' in result and 'deleted' in result['status']:
                        logger.debug(f"[{self.name}] Removed user {user.username}")
                except Exception as e:
                    logger.error(f"[{self.name}] Failed to remove user {user.username}: {e}")

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
        logger = logging.getLogger(__name__)
        logger.debug(f"[{self.name}] Looking for key for user {user.username}")
        try:
            # Try to get key by username first
            result = self.client.get_key(str(user.username))
            logger.debug(f"[{self.name}] Found key for user {user.username} by username")
            return result
        except OutlineServerErrorException:
            # If not found by username, search by password (hash)
            logger.debug(f"[{self.name}] Key not found by username, searching by password")
            try:
                keys = self.client.get_keys()
                for key in keys:
                    if key.password == user.hash:
                        logger.debug(f"[{self.name}] Found key for user {user.username} by password match")
                        return key
                # No key found
                logger.debug(f"[{self.name}] No key found for user {user.username}")
                raise OutlineServerErrorException(f"Key not found for user {user.username}")
            except Exception as e:
                logger.error(f"[{self.name}] Error searching for key for user {user.username}: {e}")
                raise OutlineServerErrorException(f"Error searching for key: {e}")

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
        logger = logging.getLogger(__name__)
        try:
            server_user = self._get_key(user)
        except OutlineServerErrorException as e:
            server_user = None
        
        logger.debug(f"[{self.name}] User {str(server_user)}")

        result = {}
        key = None

        if server_user:
            # Check if user needs update - but don't delete immediately
            needs_update = (
                server_user.method != "chacha20-ietf-poly1305" or 
                server_user.port != int(self.client_port) or 
                server_user.name != user.username or 
                server_user.password != user.hash
            )
            
            if needs_update:
                # Delete old key before creating new one
                try:
                    self.client.delete_key(server_user.key_id)
                    logger.debug(f"[{self.name}] Deleted outdated key for user {user.username}")
                except Exception as e:
                    logger.warning(f"[{self.name}] Failed to delete old key for user {user.username}: {e}")
                
                # Create new key with correct parameters
                try:
                    key = self.client.create_key(
                        key_id=user.username,
                        name=user.username,
                        method="chacha20-ietf-poly1305",
                        password=user.hash,
                        data_limit=None,
                        port=int(self.client_port)
                    )
                    logger.info(f"[{self.name}] User {user.username} updated")
                except OutlineServerErrorException as e:
                    raise OutlineConnectionError(f"Failed to create updated key for user {user.username}", original_exception=e)
            else:
                # User exists and is up to date
                key = server_user
                logger.debug(f"[{self.name}] User {user.username} already up to date")
        else:
            # User doesn't exist, create new key
            try:
                key = self.client.create_key(
                    key_id=user.username,
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
                    logger.warning(f"[{self.name}] Conflict for User {user.username}, trying to resolve. {error_message}")
                    # Find conflicting key by password and remove it
                    try:
                        for existing_key in self.client.get_keys():
                            if existing_key.password == user.hash:
                                logger.warning(f"[{self.name}] Found conflicting key {existing_key.key_id} with same password")
                                self.client.delete_key(existing_key.key_id)
                                break
                        # Try to create again after cleanup
                        return self.add_user(user)
                    except Exception as cleanup_error:
                        logger.error(f"[{self.name}] Failed to resolve conflict for user {user.username}: {cleanup_error}")
                        raise OutlineConnectionError(f"Conflict resolution failed for user {user.username}", original_exception=e)
                else:
                    raise OutlineConnectionError("API Error", original_exception=e)
        
        # Build result from key object
        try:
            if key:
                result = {
                    'key_id': key.key_id,
                    'name': key.name,
                    'method': key.method,
                    'password': key.password,
                    'data_limit': key.data_limit,
                    'port': key.port
                }
            else:
                result = {"error": "No key object returned"}
        except Exception as e:
            logger.error(f"[{self.name}] Error building result for user {user.username}: {e}")
            result = {"error": str(e)}
        
        return result

    def delete_user(self, user):
        result = None
        try:
            server_user = self._get_key(user)
        except OutlineServerErrorException as e:
            return {"status": "User not found on server. Nothing to do."}

        if server_user:
            self.logger.info(f"Deleting key with key_id: {server_user.key_id}")
            self.client.delete_key(server_user.key_id)
            result = {"status": "User was deleted"}
            self.logger.info(f"[{self.name}] User deleted: {user.username} on server {self.name}")

        return result



class OutlineServerAdmin(PolymorphicChildModelAdmin):
    base_model = OutlineServer
    show_in_index = False
    list_display = (
        'name',
        'admin_url',
        'admin_access_cert',
        'client_hostname',
        'client_port',
        'user_count',
        'server_status_inline',
    )
    readonly_fields = ('server_status_full', 'registration_date',)
    list_editable = ('admin_url', 'admin_access_cert', 'client_hostname', 'client_port',)
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
