import logging
import json
import requests
from django.db import models
from django.shortcuts import render, redirect
from django.conf import settings
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
    readonly_fields = ('server_status_full', 'registration_date', 'export_configuration_display', 'server_statistics_display', 'recent_activity_display', 'json_import_field')
    list_editable = ('admin_url', 'admin_access_cert', 'client_hostname', 'client_port',)
    exclude = ('server_type',)
    
    def get_fieldsets(self, request, obj=None):
        """Customize fieldsets based on whether object exists"""
        if obj is None:  # Adding new server
            return (
                ('JSON Import', {
                    'fields': ('json_import_field',),
                    'description': 'Quick import from Outline server JSON configuration'
                }),
                ('Server Configuration', {
                    'fields': ('name', 'comment', 'admin_url', 'admin_access_cert', 'client_hostname', 'client_port')
                }),
            )
        else:  # Editing existing server
            return (
                ('Server Configuration', {
                    'fields': ('name', 'comment', 'admin_url', 'admin_access_cert', 'client_hostname', 'client_port', 'registration_date')
                }),
                ('Server Status', {
                    'fields': ('server_status_full',)
                }),
                ('Export Configuration', {
                    'fields': ('export_configuration_display',)
                }),
                ('Statistics & Users', {
                    'fields': ('server_statistics_display',),
                    'classes': ('collapse',)
                }),
                ('Recent Activity', {
                    'fields': ('recent_activity_display',),
                    'classes': ('collapse',)
                }),
            )
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/sync/', self.admin_site.admin_view(self.sync_server_view), name='outlineserver_sync'),
        ]
        return custom_urls + urls

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

    def sync_server_view(self, request, object_id):
        """AJAX view to sync server settings"""
        from django.http import JsonResponse
        
        if request.method == 'POST':
            try:
                server = OutlineServer.objects.get(pk=object_id)
                result = server.sync()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Server "{server.name}" synchronized successfully',
                    'details': result
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Use the default Django admin add view"""
        return super().add_view(request, form_url, extra_context)
    
    @admin.display(description='Import JSON Configuration')
    def json_import_field(self, obj):
        """Display JSON import field for new servers only"""
        if obj and obj.pk:
            # Hide for existing servers
            return ''
            
        html = '''
        <div style="width: 100%;">
            <textarea id="import-json-config" class="vLargeTextField" rows="8" 
                      placeholder='{
  "apiUrl": "https://your-server:port/path",
  "certSha256": "your-certificate-hash",
  "serverName": "My Outline Server",
  "clientHostname": "your-server.com",
  "clientPort": 1257,
  "comment": "Server description"
}' style="font-family: 'Courier New', monospace; font-size: 0.875rem; width: 100%;"></textarea>
            <div class="help" style="margin-top: 0.5rem;">
                Paste JSON configuration from your Outline server setup to automatically fill the fields below.
            </div>
            <div style="margin-top: 1rem;">
                <button type="button" id="import-json-btn" class="btn btn-primary" onclick="importJsonConfig()">Import Configuration</button>
            </div>
            <script>
            function importJsonConfig() {
                const textarea = document.getElementById('import-json-config');
                try {
                    const jsonText = textarea.value.trim();
                    if (!jsonText) {
                        alert('Please enter JSON configuration');
                        return;
                    }
                    
                    const config = JSON.parse(jsonText);
                    
                    // Validate required fields
                    if (!config.apiUrl || !config.certSha256) {
                        alert('Invalid JSON format. Required fields: apiUrl, certSha256');
                        return;
                    }
                    
                    // Parse apiUrl to extract components
                    const url = new URL(config.apiUrl);
                    
                    // Fill form fields
                    const adminUrlField = document.getElementById('id_admin_url');
                    const adminCertField = document.getElementById('id_admin_access_cert');
                    const clientHostnameField = document.getElementById('id_client_hostname');
                    const clientPortField = document.getElementById('id_client_port');
                    const nameField = document.getElementById('id_name');
                    const commentField = document.getElementById('id_comment');
                    
                    if (adminUrlField) adminUrlField.value = config.apiUrl;
                    if (adminCertField) adminCertField.value = config.certSha256;
                    
                    // Use provided hostname or extract from URL
                    const hostname = config.clientHostname || config.hostnameForAccessKeys || url.hostname;
                    if (clientHostnameField) clientHostnameField.value = hostname;
                    
                    // Use provided port or extract from various sources
                    const clientPort = config.clientPort || config.portForNewAccessKeys || url.port || '1257';
                    if (clientPortField) clientPortField.value = clientPort;
                    
                    // Generate server name if not provided and field is empty
                    if (nameField && !nameField.value) {
                        const serverName = config.serverName || config.name || 'Outline-' + hostname;
                        nameField.value = serverName;
                    }
                    
                    // Fill comment if provided and field exists
                    if (commentField && config.comment) {
                        commentField.value = config.comment;
                    }
                    
                    // Clear the JSON input
                    textarea.value = '';
                    
                    alert('Configuration imported successfully! Review the fields below and save.');
                    
                    // Click on Server Configuration tab if using Jazzmin
                    const serverTab = document.querySelector('a[href="#server-configuration-tab"]');
                    if (serverTab) {
                        serverTab.click();
                    }
                    
                } catch (error) {
                    alert('Invalid JSON format: ' + error.message);
                }
            }
            
            // Add paste event listener
            document.addEventListener('DOMContentLoaded', function() {
                const textarea = document.getElementById('import-json-config');
                if (textarea) {
                    textarea.addEventListener('paste', function(e) {
                        setTimeout(importJsonConfig, 100);
                    });
                }
            });
            </script>
        </div>
        '''
        
        return mark_safe(html)
    
    @admin.display(description='Server Statistics & Users')
    def server_statistics_display(self, obj):
        """Display server statistics and user management"""
        if not obj or not obj.pk:
            return mark_safe('<div style="color: #6c757d; font-style: italic;">Statistics will be available after saving</div>')
        
        try:
            from vpn.models import ACL, AccessLog, UserStatistics
            from django.utils import timezone
            from datetime import timedelta
            
            # Get user statistics
            user_count = ACL.objects.filter(server=obj).count()
            total_links = 0
            server_keys_count = 0
            
            try:
                from vpn.models import ACLLink
                total_links = ACLLink.objects.filter(acl__server=obj).count()
                
                # Try to get actual keys count from server
                server_status = obj.get_server_status()
                if 'keys' in server_status:
                    server_keys_count = server_status['keys']
            except Exception:
                pass
            
            # Get active users count (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            active_users_count = UserStatistics.objects.filter(
                server_name=obj.name,
                recent_connections__gt=0
            ).values('user').distinct().count()
            
            html = '<div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 0.375rem; padding: 1rem;">'
            
            # Overall Statistics
            html += '<div style="background: #e7f3ff; border-left: 4px solid #007cba; padding: 12px; margin-bottom: 16px; border-radius: 4px;">'
            html += '<div style="display: flex; gap: 20px; margin-bottom: 8px; flex-wrap: wrap;">'
            html += f'<div><strong>Total Users:</strong> {user_count}</div>'
            html += f'<div><strong>Active Users (30d):</strong> {active_users_count}</div>'
            html += f'<div><strong>Total Links:</strong> {total_links}</div>'
            html += f'<div><strong>Server Keys:</strong> {server_keys_count}</div>'
            html += '</div>'
            html += '</div>'
            
            # Get users data with ACL information
            acls = ACL.objects.filter(server=obj).select_related('user').prefetch_related('links')
            
            if acls:
                html += '<h5 style="color: #495057; margin: 16px 0 8px 0;">👥 Users with Access</h5>'
                
                for acl in acls:
                    user = acl.user
                    links = list(acl.links.all())
                    
                    # Get last access time from any link
                    last_access = None
                    for link in links:
                        if link.last_access_time:
                            if last_access is None or link.last_access_time > last_access:
                                last_access = link.last_access_time
                    
                    # Check if user has key on server
                    server_key = False
                    try:
                        obj.get_user(user)
                        server_key = True
                    except Exception:
                        pass
                    
                    html += '<div style="background: #ffffff; border: 1px solid #e9ecef; border-radius: 0.25rem; padding: 0.75rem; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;">'
                    
                    # User info
                    html += '<div style="flex: 1;">'
                    html += f'<div style="font-weight: 500; font-size: 14px; color: #495057;">{user.username}'
                    if user.comment:
                        html += f' <span style="color: #6c757d; font-size: 12px; font-weight: normal;">- {user.comment}</span>'
                    html += '</div>'
                    html += f'<div style="font-size: 12px; color: #6c757d;">{len(links)} link(s)'
                    if last_access:
                        from django.utils.timezone import localtime
                        local_time = localtime(last_access)
                        html += f' | Last access: {local_time.strftime("%Y-%m-%d %H:%M")}'
                    else:
                        html += ' | Never accessed'
                    html += '</div>'
                    html += '</div>'
                    
                    # Status and actions
                    html += '<div style="display: flex; gap: 8px; align-items: center;">'
                    if server_key:
                        html += '<span style="background: #d4edda; color: #155724; padding: 2px 6px; border-radius: 3px; font-size: 10px;">✅ On Server</span>'
                    else:
                        html += '<span style="background: #f8d7da; color: #721c24; padding: 2px 6px; border-radius: 3px; font-size: 10px;">❌ Missing</span>'
                    
                    html += f'<a href="/admin/vpn/user/{user.id}/change/" class="btn btn-sm btn-outline-primary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; border-radius: 0.2rem; margin: 0 0.1rem;">👤 Edit</a>'
                    html += '</div>'
                    html += '</div>'
            else:
                html += '<div style="color: #6c757d; font-style: italic; text-align: center; padding: 20px; background: #f9fafb; border-radius: 6px;">'
                html += 'No users assigned to this server'
                html += '</div>'
            
            html += '</div>'
            return mark_safe(html)
            
        except Exception as e:
            return mark_safe(f'<div style="color: #dc3545;">Error loading statistics: {e}</div>')
    
    @admin.display(description='Export Configuration')
    def export_configuration_display(self, obj):
        """Display JSON export configuration"""
        if not obj or not obj.pk:
            return mark_safe('<div style="color: #6c757d; font-style: italic;">Export will be available after saving</div>')
        
        try:
            # Build export data
            export_data = {
                'apiUrl': obj.admin_url,
                'certSha256': obj.admin_access_cert,
                'serverName': obj.name,
                'clientHostname': obj.client_hostname,
                'clientPort': int(obj.client_port),
                'comment': obj.comment,
                'serverType': 'outline',
                'dateCreated': obj.registration_date.isoformat() if obj.registration_date else None,
                'id': obj.id
            }
            
            # Try to get server status
            try:
                server_status = obj.get_server_status()
                if 'error' not in server_status:
                    export_data['serverInfo'] = server_status
            except Exception:
                pass
            
            json_str = json.dumps(export_data, indent=2)
            # Escape the JSON for HTML
            from django.utils.html import escape
            escaped_json = escape(json_str)
            
            html = '''
            <div>
                <textarea id="export-json-config" class="vLargeTextField" rows="10" readonly 
                          style="font-family: 'Courier New', monospace; font-size: 0.875rem; background-color: #f8f9fa; width: 100%;">''' + escaped_json + '''</textarea>
                <div class="help" style="margin-top: 0.5rem;">
                    <strong>Includes:</strong> Server settings, connection details, live server info (if accessible), creation date, and comment.
                </div>
                <div style="padding-top: 1rem;">
                    <button type="button" id="copy-export-btn" class="btn btn-sm btn-secondary" 
                            onclick="var btn=this; document.getElementById('export-json-config').select(); document.execCommand('copy'); btn.innerHTML='✅ Copied!'; setTimeout(function(){btn.innerHTML='📋 Copy JSON';}, 2000);" 
                            style="margin-right: 10px;">📋 Copy JSON</button>
                    <button type="button" id="sync-server-btn" data-server-id="''' + str(obj.id) + '''" class="btn btn-sm btn-primary">🔄 Sync Server Settings</button>
                    <span style="margin-left: 0.5rem; font-size: 0.875rem; color: #6c757d;">
                        Synchronize server name, hostname, and port settings
                    </span>
                </div>
            </div>
            '''
            
            return mark_safe(html)
            
        except Exception as e:
            return mark_safe(f'<div style="color: #dc3545;">Error generating export: {e}</div>')
    
    @admin.display(description='Recent Activity')
    def recent_activity_display(self, obj):
        """Display recent activity in admin-friendly format"""
        if not obj or not obj.pk:
            return mark_safe('<div style="color: #6c757d; font-style: italic;">Activity will be available after saving</div>')
        
        try:
            from vpn.models import AccessLog
            from django.utils.timezone import localtime
            from datetime import timedelta
            from django.utils import timezone
            
            # Get recent access logs for this server (last 7 days)
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_logs = AccessLog.objects.filter(
                server=obj.name,
                timestamp__gte=seven_days_ago
            ).order_by('-timestamp')[:20]
            
            if not recent_logs:
                return mark_safe('<div style="color: #6c757d; font-style: italic; padding: 12px; background: #f8f9fa; border-radius: 4px;">No recent activity (last 7 days)</div>')
            
            html = '<div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 0; max-height: 300px; overflow-y: auto;">'
            
            # Header
            html += '<div style="background: #e9ecef; padding: 8px 12px; border-bottom: 1px solid #dee2e6; font-weight: 600; font-size: 12px; color: #495057;">'
            html += f'📊 Access Log ({recent_logs.count()} entries, last 7 days)'
            html += '</div>'
            
            # Activity entries
            for i, log in enumerate(recent_logs):
                bg_color = '#ffffff' if i % 2 == 0 else '#f8f9fa'
                local_time = localtime(log.timestamp)
                
                # Status icon and color
                if log.action == 'Success':
                    icon = '✅'
                    status_color = '#28a745'
                elif log.action == 'Failed':
                    icon = '❌'
                    status_color = '#dc3545'
                else:
                    icon = 'ℹ️'
                    status_color = '#6c757d'
                
                html += f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; border-bottom: 1px solid #f1f3f4; background: {bg_color};">'
                
                # Left side - user and link info
                html += '<div style="display: flex; gap: 8px; align-items: center; flex: 1; min-width: 0;">'
                html += f'<span style="color: {status_color}; font-size: 14px;">{icon}</span>'
                html += '<div style="overflow: hidden;">'
                html += f'<div style="font-weight: 500; font-size: 12px; color: #495057; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{log.user}</div>'
                
                if log.acl_link_id:
                    link_short = log.acl_link_id[:12] + '...' if len(log.acl_link_id) > 12 else log.acl_link_id
                    html += f'<div style="font-family: monospace; font-size: 10px; color: #6c757d;">{link_short}</div>'
                
                html += '</div></div>'
                
                # Right side - timestamp and status
                html += '<div style="text-align: right; flex-shrink: 0;">'
                html += f'<div style="font-size: 10px; color: #6c757d;">{local_time.strftime("%m-%d %H:%M")}</div>'
                html += f'<div style="font-size: 9px; color: {status_color}; font-weight: 500;">{log.action}</div>'
                html += '</div>'
                
                html += '</div>'
            
            # Footer with summary if there are more entries
            total_recent = AccessLog.objects.filter(
                server=obj.name,
                timestamp__gte=seven_days_ago
            ).count()
            
            if total_recent > 20:
                html += f'<div style="background: #e9ecef; padding: 6px 12px; font-size: 11px; color: #6c757d; text-align: center;">'
                html += f'Showing 20 of {total_recent} entries from last 7 days'
                html += '</div>'
            
            html += '</div>'
            return mark_safe(html)
            
        except Exception as e:
            return mark_safe(f'<div style="color: #dc3545; font-size: 12px;">Error loading activity: {e}</div>')
    
    def get_model_perms(self, request):
        """It disables display for sub-model"""
        return {}
    
    class Media:
        js = ('admin/js/generate_link.js',)
        css = {'all': ('admin/css/vpn_admin.css',)}
    
admin.site.register(OutlineServer, OutlineServerAdmin)
