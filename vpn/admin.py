import json
import shortuuid
from polymorphic.admin import (
    PolymorphicParentModelAdmin,
)
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.db.models import Count
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import path, reverse
from django.http import HttpResponseRedirect

from django.contrib.auth.admin import UserAdmin
from .models import User, AccessLog, TaskExecutionLog, UserStatistics
from django.utils.timezone import localtime
from vpn.models import User, ACL, ACLLink
from vpn.forms import UserForm
from mysite.settings import EXTERNAL_ADDRESS
from django.db.models import Max, Subquery, OuterRef, Q
from .server_plugins import (
    Server,
    WireguardServer,
    WireguardServerAdmin,
    OutlineServer,
    OutlineServerAdmin,
    XrayServerV2,
    XrayServerV2Admin)

# Import new Xray admin configuration
from .admin_xray import add_subscription_management_to_user

# This will be registered at the end of the file


@admin.register(TaskExecutionLog)
class TaskExecutionLogAdmin(admin.ModelAdmin):
    list_display = ('task_name_display', 'action', 'status_display', 'server', 'user', 'execution_time_display', 'created_at')
    list_filter = ('task_name', 'status', 'server', 'created_at')
    search_fields = ('task_id', 'task_name', 'action', 'user__username', 'server__name', 'message')
    readonly_fields = ('task_id', 'task_name', 'server', 'user', 'action', 'status', 'message_formatted', 'execution_time', 'created_at')
    ordering = ('-created_at',)
    list_per_page = 100
    date_hierarchy = 'created_at'
    actions = ['trigger_full_sync', 'trigger_statistics_update']
    
    fieldsets = (
        ('Task Information', {
            'fields': ('task_id', 'task_name', 'action', 'status')
        }),
        ('Related Objects', {
            'fields': ('server', 'user')
        }),
        ('Execution Details', {
            'fields': ('message_formatted', 'execution_time', 'created_at')
        }),
    )
    
    def trigger_full_sync(self, request, queryset):
        """Trigger manual full synchronization of all servers"""
        # This action doesn't require selected items
        try:
            from vpn.tasks import sync_all_users
            
            # Start the sync task
            task = sync_all_users.delay()
            
            self.message_user(
                request,
                f'Full synchronization started successfully. Task ID: {task.id}. Check logs below for progress.',
                level=messages.SUCCESS
            )
            
        except Exception as e:
            self.message_user(
                request,
                f'Failed to start full synchronization: {e}',
                level=messages.ERROR
            )
    
    trigger_full_sync.short_description = "🔄 Trigger full sync of all servers"
    
    def trigger_statistics_update(self, request, queryset):
        """Trigger manual update of user statistics cache"""
        # This action doesn't require selected items
        try:
            from vpn.tasks import update_user_statistics
            
            # Start the statistics update task
            task = update_user_statistics.delay()
            
            self.message_user(
                request,
                f'User statistics update started successfully. Task ID: {task.id}. Check logs below for progress.',
                level=messages.SUCCESS
            )
            
        except Exception as e:
            self.message_user(
                request,
                f'Failed to start statistics update: {e}',
                level=messages.ERROR
            )
    
    trigger_statistics_update.short_description = "📊 Update user statistics cache"
    
    def get_actions(self, request):
        """Remove default delete action for logs"""
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    
    @admin.display(description='Task', ordering='task_name')
    def task_name_display(self, obj):
        task_names = {
            'sync_all_servers': '🔄 Sync All',
            'sync_all_users_on_server': '👥 Server Sync',
            'sync_server_info': '⚙️ Server Info',
            'sync_user_on_server': '👤 User Sync',
            'cleanup_task_logs': '🧹 Cleanup',
            'update_user_statistics': '📊 Statistics',
        }
        return task_names.get(obj.task_name, obj.task_name)
    
    @admin.display(description='Status', ordering='status')
    def status_display(self, obj):
        status_icons = {
            'STARTED': '🟡 Started',
            'SUCCESS': '✅ Success',
            'FAILURE': '❌ Failed',
            'RETRY': '🔄 Retry',
        }
        return status_icons.get(obj.status, obj.status)
    
    @admin.display(description='Time', ordering='execution_time')
    def execution_time_display(self, obj):
        if obj.execution_time:
            if obj.execution_time < 1:
                return f"{obj.execution_time*1000:.0f}ms"
            else:
                return f"{obj.execution_time:.2f}s"
        return '-'
    
    @admin.display(description='Message')
    def message_formatted(self, obj):
        if obj.message:
            return mark_safe(f"<pre style='white-space: pre-wrap; max-width: 800px;'>{obj.message}</pre>")
        return '-'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Override to handle actions that don't require item selection"""
        # Handle actions that don't require selection
        if 'action' in request.POST:
            action = request.POST['action']
            if action == 'trigger_full_sync':
                # Call the action directly without queryset requirement
                self.trigger_full_sync(request, None)
                # Return redirect to prevent AttributeError
                return redirect(request.get_full_path())
            elif action == 'trigger_statistics_update':
                # Call the statistics update action
                self.trigger_statistics_update(request, None)
                # Return redirect to prevent AttributeError
                return redirect(request.get_full_path())
        
        return super().changelist_view(request, extra_context)


admin.site.site_title = "VPN Manager"
admin.site.site_header = "VPN Manager"
admin.site.index_title = "OutFleet"

def format_object(data):
    try:  
        if isinstance(data, dict):
            formatted_data = json.dumps(data, indent=2)
            return mark_safe(f"<pre>{formatted_data}</pre>")
        elif isinstance(data, str):
            return mark_safe(f"<pre>{data}</pre>")
        else:
            return mark_safe(f"<pre>{str(data)}</pre>")
    except Exception as e:
        return mark_safe(f"<span style='color: red;'>Error: {e}</span>")

class UserNameFilter(admin.SimpleListFilter):
    title = 'User'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        users = set(User.objects.values_list('username', flat=True))
        return [(user, user) for user in users]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__username=self.value())
        return queryset

class ServerNameFilter(admin.SimpleListFilter):
    title = 'Server Name'
    parameter_name = 'acl__server__name'

    def lookups(self, request, model_admin):
        servers = set(ACL.objects.values_list('server__name', flat=True))
        return [(server, server) for server in servers]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(acl__server__name=self.value())
        return queryset


class LastAccessFilter(admin.SimpleListFilter):
    title = 'Last Access'
    parameter_name = 'last_access_status'

    def lookups(self, request, model_admin):
        return [
            ('never', 'Never accessed'),
            ('week', 'Last week'),
            ('month', 'Last month'),
            ('old', 'Older than 3 months'),
        ]

    def queryset(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        if self.value() == 'never':
            # Links that have never been accessed
            return queryset.filter(last_access_time__isnull=True)
        elif self.value() == 'week':
            # Links accessed in the last week
            week_ago = timezone.now() - timedelta(days=7)
            return queryset.filter(last_access_time__gte=week_ago)
        elif self.value() == 'month':
            # Links accessed in the last month
            month_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(last_access_time__gte=month_ago)
        elif self.value() == 'old':
            # Links not accessed for more than 3 months
            three_months_ago = timezone.now() - timedelta(days=90)
            return queryset.filter(last_access_time__lt=three_months_ago)
        return queryset

@admin.register(Server)
class ServerAdmin(PolymorphicParentModelAdmin):
    base_model = Server
    child_models = (OutlineServer, WireguardServer, XrayServerV2)
    list_display = ('name_with_icon', 'server_type', 'comment_short', 'user_stats', 'server_status_compact', 'registration_date')
    search_fields = ('name', 'comment')
    list_filter = ('server_type', )
    actions = ['move_clients_action', 'purge_all_keys_action', 'sync_all_selected_servers', 'sync_xray_inbounds', 'check_status']
    
    class Media:
        css = {
            'all': ('admin/css/vpn_admin.css',)
        }
        js = ('admin/js/server_status_check.js',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('move-clients/', self.admin_site.admin_view(self.move_clients_view), name='server_move_clients'),
            path('<int:server_id>/check-status/', self.admin_site.admin_view(self.check_server_status_view), name='server_check_status'),
            path('<int:object_id>/sync/', self.admin_site.admin_view(self.sync_server_view), name='server_sync'),
        ]
        return custom_urls + urls

    def move_clients_action(self, request, queryset):
        """Кастомное действие для перехода к странице переноса клиентов"""
        if queryset.count() == 0:
            self.message_user(request, "Выберите хотя бы один сервер.", level=messages.ERROR)
            return
        
        # Перенаправляем на страницу переноса клиентов
        selected_ids = ','.join(str(server.id) for server in queryset)
        return HttpResponseRedirect(f"{reverse('admin:server_move_clients')}?servers={selected_ids}")

    move_clients_action.short_description = "Move client links between servers"

    def move_clients_view(self, request):
        """View for moving clients between servers"""
        if request.method == 'GET':
            # Get selected servers from URL parameters
            server_ids = request.GET.get('servers', '').split(',')
            if not server_ids or server_ids == ['']:
                messages.error(request, "No servers selected.")
                return redirect('admin:vpn_server_changelist')
            
            try:
                # Only work with database objects, don't check server connectivity
                servers = Server.objects.filter(id__in=server_ids)
                all_servers = Server.objects.all()
                
                # Get ACL links for selected servers with related data
                # This is purely database operation, no server connectivity required
                links_by_server = {}
                for server in servers:
                    try:
                        # Get all ACL links for this server with user and ACL data
                        links = ACLLink.objects.filter(
                            acl__server=server
                        ).select_related('acl__user', 'acl__server').order_by('acl__user__username', 'comment')
                        links_by_server[server] = links
                    except Exception as e:
                        # Log the error but continue with other servers
                        messages.warning(request, f"Warning: Could not load links for server {server.name}: {e}")
                        links_by_server[server] = []
                
                context = {
                    'title': 'Move Client Links Between Servers',
                    'servers': servers,
                    'all_servers': all_servers,
                    'links_by_server': links_by_server,
                }
                
                return render(request, 'admin/move_clients.html', context)
                
            except Exception as e:
                messages.error(request, f"Database error while loading data: {e}")
                return redirect('admin:vpn_server_changelist')
        
        elif request.method == 'POST':
            # Process the transfer of ACL links - purely database operations
            try:
                source_server_id = request.POST.get('source_server')
                target_server_id = request.POST.get('target_server')
                selected_link_ids = request.POST.getlist('selected_links')
                comment_regex = request.POST.get('comment_regex', '').strip()
                
                if not source_server_id or not target_server_id:
                    messages.error(request, "Please select both source and target servers.")
                    return redirect(request.get_full_path())
                
                if source_server_id == target_server_id:
                    messages.error(request, "Source and target servers cannot be the same.")
                    return redirect(request.get_full_path())
                
                if not selected_link_ids:
                    messages.error(request, "Please select at least one link to move.")
                    return redirect(request.get_full_path())
                
                # Parse and validate regex pattern if provided
                regex_pattern = None
                regex_replacement = None
                regex_parts = None
                if comment_regex:
                    try:
                        import re
                        regex_parts = comment_regex.split(' -> ')
                        if len(regex_parts) != 2:
                            messages.error(request, "Invalid regex format. Use: pattern -> replacement")
                            return redirect(request.get_full_path())
                        
                        pattern_str = regex_parts[0]
                        replacement_str = regex_parts[1]
                        
                        # Convert JavaScript-style $1, $2, $3 to Python-style \1, \2, \3
                        python_replacement = replacement_str
                        import re as regex_module
                        # Replace $1, $2, etc. with \1, \2, etc. for Python regex
                        python_replacement = regex_module.sub(r'\$(\d+)', r'\\\1', replacement_str)
                        
                        # Test compile the regex pattern
                        regex_pattern = re.compile(pattern_str)
                        regex_replacement = python_replacement
                        
                        # Test the replacement on a sample string to validate syntax
                        test_result = regex_pattern.sub(regex_replacement, "test sample")
                        
                    except re.error as e:
                        messages.error(request, f"Invalid regular expression pattern '{regex_parts[0] if regex_parts else comment_regex}': {e}")
                        return redirect(request.get_full_path())
                    except Exception as e:
                        messages.error(request, f"Error in regex replacement '{replacement_str if 'replacement_str' in locals() else 'unknown'}': {e}")
                        return redirect(request.get_full_path())
                
                # Get server objects from database only
                try:
                    source_server = Server.objects.get(id=source_server_id)
                    target_server = Server.objects.get(id=target_server_id)
                except Server.DoesNotExist:
                    messages.error(request, "One of the selected servers was not found in database.")
                    return redirect('admin:vpn_server_changelist')
                
                moved_count = 0
                errors = []
                users_processed = set()
                comments_transformed = 0
                
                # Process each selected link - database operations only
                for link_id in selected_link_ids:
                    try:
                        # Get the ACL link with related ACL and user data
                        acl_link = ACLLink.objects.select_related('acl__user', 'acl__server').get(
                            id=link_id, 
                            acl__server=source_server
                        )
                        user = acl_link.acl.user
                        
                        # Apply regex transformation to comment if provided
                        original_comment = acl_link.comment
                        if regex_pattern and regex_replacement is not None:
                            try:
                                # Use Python's re.sub for replacement, which properly handles $1, $2 groups
                                new_comment = regex_pattern.sub(regex_replacement, original_comment)
                                if new_comment != original_comment:
                                    acl_link.comment = new_comment
                                    comments_transformed += 1
                                    # Debug logging - shows both original and converted patterns
                                    print(f"DEBUG: Transformed '{original_comment}' -> '{new_comment}'")
                                    print(f"  Original pattern: '{regex_parts[0]}' -> '{regex_parts[1]}'")
                                    print(f"  Python pattern: '{regex_parts[0]}' -> '{regex_replacement}'")
                            except Exception as e:
                                errors.append(f"Error applying regex to link {link_id} ('{original_comment}'): {e}")
                                # Continue with original comment
                        
                        # Check if user already has ACL on target server
                        target_acl = ACL.objects.filter(user=user, server=target_server).first()
                        
                        if target_acl:
                            created = False
                        else:
                            # Create new ACL without auto-creating default link
                            target_acl = ACL(user=user, server=target_server)
                            target_acl.save(auto_create_link=False)
                            created = True
                        
                        # Move the link to target ACL - pure database operation
                        acl_link.acl = target_acl
                        acl_link.save()
                        
                        moved_count += 1
                        users_processed.add(user.username)
                        
                        if created:
                            messages.info(request, f"Created new ACL for user {user.username} on server {target_server.name}")
                        
                    except ACLLink.DoesNotExist:
                        errors.append(f"Link with ID {link_id} not found on source server")
                    except Exception as e:
                        errors.append(f"Database error moving link {link_id}: {e}")
                
                # Clean up empty ACLs on source server - database operation only
                try:
                    empty_acls = ACL.objects.filter(
                        server=source_server,
                        links__isnull=True
                    )
                    deleted_acls_count = empty_acls.count()
                    empty_acls.delete()
                except Exception as e:
                    messages.warning(request, f"Warning: Could not clean up empty ACLs: {e}")
                    deleted_acls_count = 0
                
                if moved_count > 0:
                    success_msg = (
                        f"Successfully moved {moved_count} link(s) for {len(users_processed)} user(s) "
                        f"from '{source_server.name}' to '{target_server.name}'. "
                        f"Cleaned up {deleted_acls_count} empty ACL(s)."
                    )
                    if comments_transformed > 0:
                        success_msg += f" Transformed {comments_transformed} comment(s) using regex."
                    
                    messages.success(request, success_msg)
                
                if errors:
                    for error in errors:
                        messages.error(request, error)
                
                return redirect('admin:vpn_server_changelist')
                
            except Exception as e:
                messages.error(request, f"Database error during link transfer: {e}")
                return redirect('admin:vpn_server_changelist')
    
    def check_server_status_view(self, request, server_id):
        """AJAX view to check server status"""
        from django.http import JsonResponse
        import logging
        
        logger = logging.getLogger(__name__)
        
        if request.method == 'POST':
            try:
                logger.info(f"Checking status for server ID: {server_id}")
                server = Server.objects.get(pk=server_id)
                real_server = server.get_real_instance()
                logger.info(f"Server found: {server.name}, type: {type(real_server).__name__}")
                
                # Check server status based on type
                from vpn.server_plugins.outline import OutlineServer
                # Old xray_core module removed - skip this server type
                
                if isinstance(real_server, OutlineServer):
                    try:
                        logger.info(f"Checking Outline server: {server.name}")
                        # Try to get server info to check if it's online
                        info = real_server.client.get_server_information()
                        if info:
                            logger.info(f"Server {server.name} is online with {info.get('accessKeyCount', info.get('access_key_count', 'unknown'))} keys")
                            return JsonResponse({
                                'success': True,
                                'status': 'online',
                                'message': f'Server is online. Keys: {info.get("accessKeyCount", info.get("access_key_count", "unknown"))}'
                            })
                        else:
                            logger.warning(f"Server {server.name} returned no info")
                            return JsonResponse({
                                'success': True,
                                'status': 'offline',
                                'message': 'Server not responding'
                            })
                    except Exception as e:
                        logger.error(f"Error checking Outline server {server.name}: {e}")
                        return JsonResponse({
                            'success': True,
                            'status': 'error',
                            'message': f'Connection error: {str(e)[:100]}'
                        })
                
                elif isinstance(real_server, XrayServerV2):
                    try:
                        logger.info(f"Checking Xray v2 server: {server.name}")
                        # Get server status from new Xray implementation
                        status = real_server.get_server_status()
                        if status and isinstance(status, dict):
                            if status.get('accessible', False):
                                message = f'✅ Server is {status.get("status", "accessible")}. '
                                message += f'Host: {status.get("client_hostname", "N/A")}, '
                                message += f'API: {status.get("api_address", "N/A")}'
                                
                                if status.get('api_connected'):
                                    message += ' (Connected)'
                                    # Add stats if available
                                    api_stats = status.get('api_stats', {})
                                    if api_stats and isinstance(api_stats, dict):
                                        if 'connection' in api_stats:
                                            message += f', Stats: {api_stats.get("connection", "ok")}'
                                        if api_stats.get('library') == 'not_available':
                                            message += ' [Basic check only]'
                                elif status.get('api_error'):
                                    message += f' ({status.get("api_error")})'
                                
                                message += f', Inbounds: {status.get("total_inbounds", 0)}'
                                
                                logger.info(f"Xray v2 server {server.name} status: {message}")
                                return JsonResponse({
                                    'success': True,
                                    'status': 'online',
                                    'message': message
                                })
                            else:
                                error_msg = status.get('error') or status.get('api_error', 'Unknown error')
                                logger.warning(f"Xray v2 server {server.name} not accessible: {error_msg}")
                                return JsonResponse({
                                    'success': True,
                                    'status': 'offline',
                                    'message': f'❌ Server not accessible: {error_msg}'
                                })
                        else:
                            logger.warning(f"Xray v2 server {server.name} returned invalid status")
                            return JsonResponse({
                                'success': True,
                                'status': 'offline',
                                'message': 'Invalid server response'
                            })
                    except Exception as e:
                        logger.error(f"Error checking Xray v2 server {server.name}: {e}")
                        return JsonResponse({
                            'success': True,
                            'status': 'error',
                            'message': f'Connection error: {str(e)[:100]}'
                        })
                
                else:
                    # For other server types, just return basic info
                    logger.info(f"Server {server.name}, type: {server.server_type}")
                    return JsonResponse({
                        'success': True,
                        'status': 'unknown',
                        'message': f'Status check not implemented for {server.server_type} servers'
                    })
                    
            except Server.DoesNotExist:
                logger.error(f"Server with ID {server_id} not found")
                return JsonResponse({
                    'success': False,
                    'error': 'Server not found'
                }, status=404)
            except Exception as e:
                logger.error(f"Unexpected error checking server {server_id}: {e}")
                return JsonResponse({
                    'success': False,
                    'error': f'Unexpected error: {str(e)}'
                }, status=500)
        
        logger.warning(f"Invalid request method {request.method} for server status check")
        return JsonResponse({
            'success': False,
            'error': 'Invalid request method'
        }, status=405)

    def purge_all_keys_action(self, request, queryset):
        """Purge all keys from selected servers without changing database"""
        if queryset.count() == 0:
            self.message_user(request, "Please select at least one server.", level=messages.ERROR)
            return
        
        success_count = 0
        error_count = 0
        total_keys_removed = 0
        
        for server in queryset:
            try:
                # Get the real polymorphic instance
                real_server = server.get_real_instance()
                server_type = type(real_server).__name__
                
                # Check if this is an Outline server
                from vpn.server_plugins.outline import OutlineServer
                
                if isinstance(real_server, OutlineServer) and hasattr(real_server, 'client'):
                    # For Outline servers, get all keys and delete them
                    try:
                        keys = real_server.client.get_keys()
                        keys_count = len(keys)
                        
                        for key in keys:
                            try:
                                real_server.client.delete_key(key.key_id)
                            except Exception as e:
                                self.message_user(
                                    request, 
                                    f"Failed to delete key {key.key_id} from {server.name}: {e}",
                                    level=messages.WARNING
                                )
                        
                        total_keys_removed += keys_count
                        success_count += 1
                        self.message_user(
                            request,
                            f"Successfully purged {keys_count} keys from server '{server.name}'.",
                            level=messages.SUCCESS
                        )
                        
                    except Exception as e:
                        error_count += 1
                        self.message_user(
                            request,
                            f"Failed to connect to server '{server.name}': {e}",
                            level=messages.ERROR
                        )
                else:
                    self.message_user(
                        request,
                        f"Key purging only supported for Outline servers. Skipping '{server.name}' (type: {server_type}).",
                        level=messages.INFO
                    )
                    
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Unexpected error with server '{server.name}': {e}",
                    level=messages.ERROR
                )
        
        # Summary message
        if success_count > 0:
            self.message_user(
                request,
                f"Purge completed! {success_count} server(s) processed, {total_keys_removed} total keys removed. "
                f"Database unchanged - run sync to restore proper keys.",
                level=messages.SUCCESS
            )
        
        if error_count > 0:
            self.message_user(
                request,
                f"{error_count} server(s) had errors during purge.",
                level=messages.WARNING
            )
    
    purge_all_keys_action.short_description = "🗑️ Purge all keys from server (database unchanged)"
    
    def sync_all_selected_servers(self, request, queryset):
        """Trigger sync for all users on selected servers"""
        if queryset.count() == 0:
            self.message_user(request, "Please select at least one server.", level=messages.ERROR)
            return
        
        try:
            from vpn.tasks import sync_all_users_on_server
            
            tasks_started = 0
            errors = []
            
            for server in queryset:
                try:
                    task = sync_all_users_on_server.delay(server.id)
                    tasks_started += 1
                    self.message_user(
                        request,
                        f"🔄 Sync task started for '{server.name}' (Task ID: {task.id})",
                        level=messages.SUCCESS
                    )
                except Exception as e:
                    errors.append(f"'{server.name}': {e}")
            
            if tasks_started > 0:
                self.message_user(
                    request,
                    f"✅ Started sync tasks for {tasks_started} server(s). Check Task Execution Logs for progress.",
                    level=messages.SUCCESS
                )
            
            if errors:
                for error in errors:
                    self.message_user(
                        request,
                        f"❌ Failed to sync {error}",
                        level=messages.ERROR
                    )
                    
        except Exception as e:
            self.message_user(
                request,
                f"❌ Failed to start sync tasks: {e}",
                level=messages.ERROR
            )
    
    sync_all_selected_servers.short_description = "🔄 Sync all users on selected servers"
    
    def check_status(self, request, queryset):
        """Check status for selected servers"""
        for server in queryset:
            try:
                status = server.get_server_status()
                msg = f"{server.name}: {status.get('accessible', 'Unknown')} - {status.get('status', 'N/A')}"
                self.message_user(request, msg, level=messages.INFO)
            except Exception as e:
                self.message_user(request, f"Error checking {server.name}: {e}", level=messages.ERROR)
    check_status.short_description = "📊 Check server status"
    
    def sync_xray_inbounds(self, request, queryset):
        """Sync inbounds for selected servers (Xray v2 only)"""
        from .server_plugins.xray_v2 import XrayServerV2
        synced_count = 0
        
        for server in queryset:
            try:
                real_server = server.get_real_instance()
                if isinstance(real_server, XrayServerV2):
                    real_server.sync_inbounds()
                    synced_count += 1
                    self.message_user(request, f"Scheduled inbound sync for {server.name}", level=messages.SUCCESS)
                else:
                    self.message_user(request, f"{server.name} is not an Xray v2 server", level=messages.WARNING)
            except Exception as e:
                self.message_user(request, f"Error syncing inbounds for {server.name}: {e}", level=messages.ERROR)
        
        if synced_count > 0:
            self.message_user(request, f"Scheduled inbound sync for {synced_count} server(s)", level=messages.SUCCESS)
    sync_xray_inbounds.short_description = "🔧 Sync Xray inbounds"

    @admin.display(description='Server', ordering='name')
    def name_with_icon(self, obj):
        """Display server name with type icon"""
        icons = {
            'outline': '🔵',
            'wireguard': '🟢',
            'xray_core': '🟣',
            'xray_v2': '🟡',
        }
        icon = icons.get(obj.server_type, '')
        name_part = f"{icon} {obj.name}" if icon else obj.name
        return name_part
    
    @admin.display(description='Comment')
    def comment_short(self, obj):
        """Display shortened comment"""
        if obj.comment:
            short_comment = obj.comment[:40] + '...' if len(obj.comment) > 40 else obj.comment
            return mark_safe(f'<span title="{obj.comment}" style="font-size: 12px;">{short_comment}</span>')
        return '-'
    
    @admin.display(description='Users & Links')
    def user_stats(self, obj):
        """Display user count and active links statistics (optimized)"""
        try:
            from django.utils import timezone
            from datetime import timedelta
            
            user_count = obj.user_count if hasattr(obj, 'user_count') else 0
            
            # Use prefetched data if available
            if hasattr(obj, 'acl_set'):
                all_links = []
                for acl in obj.acl_set.all():
                    if hasattr(acl, 'links') and hasattr(acl.links, 'all'):
                        all_links.extend(acl.links.all())
                
                total_links = len(all_links)
                
                # Count active links from prefetched data
                thirty_days_ago = timezone.now() - timedelta(days=30)
                active_links = sum(1 for link in all_links 
                                 if link.last_access_time and link.last_access_time >= thirty_days_ago)
            else:
                # Fallback to direct queries (less efficient)
                total_links = ACLLink.objects.filter(acl__server=obj).count()
                thirty_days_ago = timezone.now() - timedelta(days=30)
                active_links = ACLLink.objects.filter(
                    acl__server=obj,
                    last_access_time__isnull=False,
                    last_access_time__gte=thirty_days_ago
                ).count()
            
            # Color coding based on activity
            if user_count == 0:
                color = '#9ca3af'  # gray - no users
            elif total_links == 0:
                color = '#dc2626'  # red - no links
            elif total_links > 0 and active_links > total_links * 0.7:  # High activity
                color = '#16a34a'  # green
            elif total_links > 0 and active_links > total_links * 0.3:  # Medium activity
                color = '#eab308'  # yellow
            else:
                color = '#f97316'  # orange - low activity
            
            return mark_safe(
                f'<div style="font-size: 12px;">' +
                f'<div style="color: {color}; font-weight: bold;">👥 {user_count} users</div>' +
                f'<div style="color: #6b7280;">🔗 {active_links}/{total_links} active</div>' +
                f'</div>'
            )
        except Exception as e:
            return mark_safe(f'<span style="color: #dc2626; font-size: 11px;">Stats error: {e}</span>')
    
    @admin.display(description='Activity')
    def activity_summary(self, obj):
        """Display recent activity summary (optimized)"""
        try:
            # Simplified version - avoid heavy DB queries on list page
            # This could be computed once per page load if needed
            return mark_safe(
                f'<div style="font-size: 11px; color: #6b7280;">' +
                f'<div>📊 Activity data</div>' +
                f'<div><small>Click to view details</small></div>' +
                f'</div>'
            )
        except Exception as e:
            return mark_safe(f'<span style="color: #dc2626; font-size: 11px;">Activity unavailable</span>')
    
    @admin.display(description='Status')
    def server_status_compact(self, obj):
        """Display server status in compact format (optimized)"""
        try:
            # Avoid expensive server connectivity checks on list page
            # Show basic info and let users click to check status
            server_type_icons = {
                'outline': '🔵',
                'wireguard': '🟢',
                'xray_core': '🟣',
            }
            icon = server_type_icons.get(obj.server_type, '⚪')
            
            return mark_safe(
                f'<div style="color: #6b7280; font-size: 11px;">' +
                f'{icon} {obj.server_type.title()}<br>' +
                f'<button type="button" class="check-status-btn btn btn-xs" '
                f'data-server-id="{obj.id}" data-server-name="{obj.name}" '
                f'data-server-type="{obj.server_type}" '
                f'style="background: #007cba; color: white; border: none; padding: 2px 6px; '
                f'border-radius: 3px; font-size: 10px; cursor: pointer;">'
                f'⚪ Check Status'
                f'</button>' +
                f'</div>'
            )
        except Exception as e:
            return mark_safe(
                f'<div style="color: #f97316; font-size: 11px; font-weight: bold;">' +
                f'⚠️ Error<br>' +
                f'<span style="font-weight: normal;" title="{str(e)}">' +
                f'{str(e)[:25]}...</span>' +
                f'</div>'
            )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(user_count=Count('acl'))
        qs = qs.prefetch_related(
            'acl_set__links',
            'acl_set__user'
        )
        return qs
    
    def sync_server_view(self, request, object_id):
        """Dispatch sync to appropriate server type."""
        from django.shortcuts import redirect, get_object_or_404
        from django.contrib import messages
        # XrayCoreServer removed - using XrayServerV2 now
        
        try:
            server = get_object_or_404(Server, pk=object_id)
            real_server = server.get_real_instance()
            
            # Handle XrayServerV2
            if isinstance(real_server, XrayServerV2):
                return redirect(f'/admin/vpn/xrayserverv2/{real_server.pk}/sync/')
            
            # Fallback for other server types
            else:
                messages.info(request, f"Sync not implemented for server type: {real_server.server_type}")
                return redirect('admin:vpn_server_changelist')
            
        except Exception as e:
            messages.error(request, f"Error during sync: {e}")
            return redirect('admin:vpn_server_changelist')

#admin.site.register(User, UserAdmin)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserForm
    list_display = ('username', 'comment', 'registration_date', 'hash_link', 'server_count')
    search_fields = ('username', 'hash')
    readonly_fields = ('hash_link', 'user_statistics_summary')
    
    class Media:
        css = {
            'all': ('admin/css/vpn_admin.css',)
        }
    
    fieldsets = (
        ('User Information', {
            'fields': ('username', 'first_name', 'last_name', 'email', 'comment')
        }),
        ('Access Information', {
            'fields': ('hash_link', 'is_active')
        }),
        ('Statistics & Server Management', {
            'fields': ('user_statistics_summary',),
            'classes': ('wide',)
        }),
    )

    @admin.display(description='User Portal', ordering='hash')
    def hash_link(self, obj):
        portal_url = f"{EXTERNAL_ADDRESS}/u/{obj.hash}"
        json_url = f"{EXTERNAL_ADDRESS}/stat/{obj.hash}"
        return format_html(
            '<div style="display: flex; gap: 10px; flex-wrap: wrap;">' + 
            '<a href="{}" target="_blank" style="background: #4ade80; color: #000; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold;">🌐 Portal</a>' +
            '<a href="{}" target="_blank" style="background: #3b82f6; color: #fff; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold;">📄 JSON</a>' +
            '</div>',
            portal_url, json_url
        )
    
    @admin.display(description='User Statistics Summary')
    def user_statistics_summary(self, obj):
        """Display user statistics with integrated server management"""
        try:
            from .models import UserStatistics
            from django.db import models
            
            # Get statistics for this user
            user_stats = UserStatistics.objects.filter(user=obj).aggregate(
                total_connections=models.Sum('total_connections'),
                recent_connections=models.Sum('recent_connections'),
                total_links=models.Count('id'),
                max_daily_peak=models.Max('max_daily')
            )
            
            # Get server breakdown
            server_breakdown = UserStatistics.objects.filter(user=obj).values('server_name').annotate(
                connections=models.Sum('total_connections'),
                links=models.Count('id')
            ).order_by('-connections')
            
            # Get all ACLs and links for this user
            user_acls = ACL.objects.filter(user=obj).select_related('server').prefetch_related('links')
            
            # Get available servers not yet assigned
            all_servers = Server.objects.all()
            assigned_server_ids = [acl.server.id for acl in user_acls]
            unassigned_servers = all_servers.exclude(id__in=assigned_server_ids)
            
            html = '<div class="user-management-section">'
            
            # Overall Statistics
            html += '<div style="background: #e7f3ff; border-left: 4px solid #007cba; padding: 12px; margin-bottom: 16px; border-radius: 4px;">'
            html += f'<div style="display: flex; gap: 20px; margin-bottom: 8px; flex-wrap: wrap;">'
            html += f'<div><strong>Total Uses:</strong> {user_stats["total_connections"] or 0}</div>'
            html += f'<div><strong>Recent (30d):</strong> {user_stats["recent_connections"] or 0}</div>'
            html += f'<div><strong>Total Links:</strong> {user_stats["total_links"] or 0}</div>'
            if user_stats["max_daily_peak"]:
                html += f'<div><strong>Daily Peak:</strong> {user_stats["max_daily_peak"]}</div>'
            html += f'</div>'
            html += '</div>'
            
            # Server Management
            if user_acls:
                html += '<h4 style="color: #007cba; margin: 16px 0 8px 0;">🔗 Server Access & Links</h4>'
                
                for acl in user_acls:
                    server = acl.server
                    links = list(acl.links.all())
                    
                    # Server header (no slow server status checks)
                    type_icon = '🔵' if server.server_type == 'outline' else '🟢' if server.server_type == 'wireguard' else '🟣' if server.server_type == 'xray_core' else ''
                    html += f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
                    html += f'<h5 style="margin: 0; color: #333; font-size: 14px; font-weight: 600;">{type_icon} {server.name}</h5>'
                    
                    # Server stats
                    server_stat = next((s for s in server_breakdown if s['server_name'] == server.name), None)
                    if server_stat:
                        html += f'<span style="background: #f8f9fa; padding: 4px 8px; border-radius: 4px; font-size: 12px; color: #6c757d;">'
                        html += f'📊 {server_stat["connections"]} uses ({server_stat["links"]} links)'
                        html += f'</span>'
                    html += f'</div>'
                    
                    html += '<div class="server-section">'
                    
                    # Links display
                    if links:
                        for link in links:
                            # Get link stats
                            link_stats = UserStatistics.objects.filter(
                                user=obj, server_name=server.name, acl_link_id=link.link
                            ).first()
                            
                            html += '<div class="link-item">'
                            html += f'<div style="flex: 1;">'
                            html += f'<div style="font-family: monospace; font-size: 13px; color: #007cba; font-weight: 500;">'
                            html += f'{link.link[:16]}...' if len(link.link) > 16 else link.link
                            html += f'</div>'
                            if link.comment:
                                html += f'<div style="font-size: 11px; color: #6c757d;">{link.comment}</div>'
                            html += f'</div>'
                            
                            # Link stats and actions
                            html += f'<div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">'
                            if link_stats:
                                html += f'<span style="background: #d4edda; color: #155724; padding: 2px 6px; border-radius: 3px; font-size: 10px;">'
                                html += f'✨ {link_stats.total_connections}'
                                html += f'</span>'
                            
                            # Test link button
                            html += f'<a href="{EXTERNAL_ADDRESS}/ss/{link.link}#{server.name}" target="_blank" '
                            html += f'class="btn btn-sm btn-primary btn-sm-custom">🔗</a>'
                            
                            # Delete button
                            html += f'<button type="button" class="btn btn-sm btn-danger btn-sm-custom delete-link-btn" '
                            html += f'data-link-id="{link.id}" data-link-name="{link.link[:12]}">🗑️</button>'
                            
                            # Last access
                            if link.last_access_time:
                                local_time = localtime(link.last_access_time)
                                html += f'<span style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 10px; color: #6c757d;">'
                                html += f'{local_time.strftime("%m-%d %H:%M")}'
                                html += f'</span>'
                            else:
                                html += f'<span style="background: #f8d7da; color: #721c24; padding: 2px 6px; border-radius: 3px; font-size: 10px;">'
                                html += f'Never'
                                html += f'</span>'
                            
                            html += f'</div></div>'
                    
                    # Add link button
                    html += f'<div style="text-align: center; margin-top: 12px;">'
                    html += f'<button type="button" class="btn btn-sm btn-success add-link-btn" '
                    html += f'data-server-id="{server.id}" data-server-name="{server.name}">'
                    html += f'➕ Add Link'
                    html += f'</button>'
                    html += f'</div>'
                    
                    html += '</div>'  # End server-section
            
            # Add server access section
            if unassigned_servers:
                html += '<div style="background: #d1ecf1; border-left: 4px solid #bee5eb; padding: 12px; margin-top: 16px; border-radius: 4px;">'
                html += '<h5 style="margin: 0 0 8px 0; color: #0c5460; font-size: 13px;">➕ Available Servers</h5>'
                html += '<div style="display: flex; gap: 8px; flex-wrap: wrap;">'
                for server in unassigned_servers:
                    type_icon = '🔵' if server.server_type == 'outline' else '🟢' if server.server_type == 'wireguard' else '🟣' if server.server_type == 'xray_core' else ''
                    html += f'<button type="button" class="btn btn-sm btn-outline-info btn-sm-custom add-server-btn" '
                    html += f'data-server-id="{server.id}" data-server-name="{server.name}">'
                    html += f'{type_icon} {server.name}'
                    html += f'</button>'
                html += '</div></div>'
            
            html += '</div>'  # End user-management-section
            return mark_safe(html)
            
        except Exception as e:
            return mark_safe(f'<span style="color: #dc3545;">Error loading management interface: {e}</span>')
    
    @admin.display(description='Recent Activity')
    def recent_activity_display(self, obj):
        """Display recent activity in compact admin-friendly format"""
        try:
            from datetime import timedelta
            from django.utils import timezone
            
            # Get recent access logs for this user (last 7 days, limited)
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_logs = AccessLog.objects.filter(
                user=obj.username,
                timestamp__gte=seven_days_ago
            ).order_by('-timestamp')[:15]  # Limit to 15 most recent
            
            if not recent_logs:
                return mark_safe('<div style="color: #6c757d; font-style: italic; padding: 12px; background: #f8f9fa; border-radius: 4px;">No recent activity (last 7 days)</div>')
            
            html = '<div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 0; max-height: 300px; overflow-y: auto;">'
            
            # Header
            html += '<div style="background: #e9ecef; padding: 8px 12px; border-bottom: 1px solid #dee2e6; font-weight: 600; font-size: 12px; color: #495057;">'
            html += f'📊 Recent Activity ({recent_logs.count()} entries, last 7 days)'
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
                
                # Left side - server and link info
                html += f'<div style="display: flex; gap: 8px; align-items: center; flex: 1; min-width: 0;">'
                html += f'<span style="color: {status_color}; font-size: 14px;">{icon}</span>'
                html += f'<div style="overflow: hidden;">'
                html += f'<div style="font-weight: 500; font-size: 12px; color: #495057; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{log.server}</div>'
                
                if log.acl_link_id:
                    link_short = log.acl_link_id[:12] + '...' if len(log.acl_link_id) > 12 else log.acl_link_id
                    html += f'<div style="font-family: monospace; font-size: 10px; color: #6c757d;">{link_short}</div>'
                
                html += f'</div></div>'
                
                # Right side - timestamp and status
                html += f'<div style="text-align: right; flex-shrink: 0;">'
                html += f'<div style="font-size: 10px; color: #6c757d;">{local_time.strftime("%m-%d %H:%M")}</div>'
                html += f'<div style="font-size: 9px; color: {status_color}; font-weight: 500;">{log.action}</div>'
                html += f'</div>'
                
                html += f'</div>'
            
            # Footer with summary if there are more entries
            total_recent = AccessLog.objects.filter(
                user=obj.username,
                timestamp__gte=seven_days_ago
            ).count()
            
            if total_recent > 15:
                html += f'<div style="background: #e9ecef; padding: 6px 12px; font-size: 11px; color: #6c757d; text-align: center;">'
                html += f'Showing 15 of {total_recent} entries from last 7 days'
                html += f'</div>'
            
            html += '</div>'
            return mark_safe(html)
            
        except Exception as e:
            return mark_safe(f'<span style="color: #dc3545; font-size: 12px;">Error loading activity: {e}</span>')

    @admin.display(description='Allowed servers', ordering='server_count')
    def server_count(self, obj):
        return obj.server_count
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(server_count=Count('acl'))
        return qs
    
    def get_urls(self):
        """Add custom URLs for link management"""
        urls = super().get_urls()
        custom_urls = [
            path('<int:user_id>/add-link/', self.admin_site.admin_view(self.add_link_view), name='user_add_link'),
            path('<int:user_id>/delete-link/<int:link_id>/', self.admin_site.admin_view(self.delete_link_view), name='user_delete_link'),
            path('<int:user_id>/add-server-access/', self.admin_site.admin_view(self.add_server_access_view), name='user_add_server_access'),
        ]
        return custom_urls + urls
    
    def add_link_view(self, request, user_id):
        """AJAX view to add a new link for user on specific server"""
        from django.http import JsonResponse
        
        if request.method == 'POST':
            try:
                user = User.objects.get(pk=user_id)
                server_id = request.POST.get('server_id')
                comment = request.POST.get('comment', '')
                
                if not server_id:
                    return JsonResponse({'error': 'Server ID is required'}, status=400)
                
                server = Server.objects.get(pk=server_id)
                acl = ACL.objects.get(user=user, server=server)
                
                # Create new link
                new_link = ACLLink.objects.create(
                    acl=acl,
                    comment=comment,
                    link=shortuuid.ShortUUID().random(length=16)
                )
                
                return JsonResponse({
                    'success': True,
                    'link_id': new_link.id,
                    'link': new_link.link,
                    'comment': new_link.comment,
                    'url': f"{EXTERNAL_ADDRESS}/ss/{new_link.link}#{server.name}"
                })
                
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    def delete_link_view(self, request, user_id, link_id):
        """AJAX view to delete a specific link"""
        from django.http import JsonResponse
        
        if request.method == 'POST':
            try:
                user = User.objects.get(pk=user_id)
                link = ACLLink.objects.get(pk=link_id, acl__user=user)
                link.delete()
                
                return JsonResponse({'success': True})
                
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    def add_server_access_view(self, request, user_id):
        """AJAX view to add server access for user"""
        from django.http import JsonResponse
        
        if request.method == 'POST':
            try:
                user = User.objects.get(pk=user_id)
                server_id = request.POST.get('server_id')
                
                if not server_id:
                    return JsonResponse({'error': 'Server ID is required'}, status=400)
                
                server = Server.objects.get(pk=server_id)
                
                # Check if ACL already exists
                if ACL.objects.filter(user=user, server=server).exists():
                    return JsonResponse({'error': 'User already has access to this server'}, status=400)
                
                # Create new ACL (with default link)
                acl = ACL.objects.create(user=user, server=server)
                
                return JsonResponse({
                    'success': True,
                    'server_name': server.name,
                    'server_type': server.server_type,
                    'acl_id': acl.id
                })
                
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add user management data and fix layout"""
        extra_context = extra_context or {}
        
        if object_id:
            try:
                user = User.objects.get(pk=object_id)
                extra_context.update({
                    'user_object': user,
                    'external_address': EXTERNAL_ADDRESS,
                })
                
            except User.DoesNotExist:
                pass
        
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        import logging
        logger = logging.getLogger(__name__)
        
        super().save_model(request, obj, form, change)
        selected_servers = form.cleaned_data.get('servers', [])

        # Remove ACLs that are no longer selected
        removed_acls = ACL.objects.filter(user=obj).exclude(server__in=selected_servers)
        for acl in removed_acls:
            logger.info(f"Removing ACL for user {obj.username} from server {acl.server.name}")
        removed_acls.delete()

        # Create new ACLs for newly selected servers (with default links)
        for server in selected_servers:
            acl, created = ACL.objects.get_or_create(user=obj, server=server)
            if created:
                logger.info(f"Created new ACL for user {obj.username} on server {server.name}")
            # Note: get_or_create will use the default save() method which creates default links

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'server', 'acl_link_display', 'action', 'formatted_timestamp')
    list_filter = ('user', 'server', 'action', 'timestamp')
    search_fields = ('user', 'server', 'acl_link_id', 'action', 'timestamp', 'data')
    readonly_fields = ('server', 'user', 'acl_link_id', 'formatted_timestamp', 'action', 'formated_data')

    @admin.display(description='Link', ordering='acl_link_id')
    def acl_link_display(self, obj):
        if obj.acl_link_id:
            return format_html(
                '<span style="font-family: monospace; color: #2563eb;">{}</span>',
                obj.acl_link_id[:12] + '...' if len(obj.acl_link_id) > 12 else obj.acl_link_id
            )
        return '-'

    @admin.display(description='Timestamp')
    def formatted_timestamp(self, obj):
        local_time = localtime(obj.timestamp)
        return local_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    
    @admin.display(description='Details')
    def formated_data(self, obj):
        return format_object(obj.data)


class ACLLinkInline(admin.TabularInline):
    model = ACLLink
    extra = 1
    help_text = 'Add or change ACL links'
    verbose_name = 'Dynamic link'
    verbose_name_plural = 'Dynamic links'
    fields = ('link', 'generate_link_button', 'comment')
    readonly_fields = ('generate_link_button',)

    @admin.display(description="Generate")
    def generate_link_button(self, obj=None):
        return format_html(
            '<button type="button" class="generate-link" onclick="generateLink(this)">🔄</button>'
        )

    class Media:
        js = ('admin/js/generate_link.js',)

@admin.register(ACL)
class ACLAdmin(admin.ModelAdmin):

    list_display = ('user', 'server', 'server_type', 'display_links', 'created_at')
    list_filter = (UserNameFilter, 'server__server_type', ServerNameFilter)
    # Fixed search_fields - removed problematic polymorphic server fields
    search_fields = ('user__username', 'user__comment', 'links__link')
    readonly_fields = ('user_info',)
    inlines = [ACLLinkInline]

    @admin.display(description='Server Type', ordering='server__server_type')
    def server_type(self, obj):
        return obj.server.get_server_type_display()

    @admin.display(description='Client info')
    def user_info(self, obj):
        server = obj.server
        user = obj.user
        try:
            # Use cached statistics instead of direct server requests
            from .models import UserStatistics
            user_stats = UserStatistics.objects.filter(
                user=user,
                server_name=server.name
            ).first()
            
            if user_stats:
                # Format cached data nicely
                data = {
                    'user': user.username,
                    'server': server.name,
                    'total_connections': user_stats.total_connections,
                    'recent_connections': user_stats.recent_connections,
                    'max_daily': user_stats.max_daily,
                    'last_updated': user_stats.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'from_cache'
                }
                return format_object(data)
            else:
                # Fallback to minimal server check (avoid slow API calls on admin pages)
                return mark_safe(
                    '<div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 8px; border-radius: 4px;">' +
                    '<strong>ℹ️ User Statistics:</strong><br>' +
                    'No cached statistics available.<br>' +
                    '<small>Run "Update user statistics cache" action to populate data.</small>' +
                    '</div>'
                )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get cached user info for {user.username} on {server.name}: {e}")
            return mark_safe(f"<span style='color: red;'>Cache error: {e}</span>")

    @admin.display(description='User Links')
    def display_links(self, obj):
        links_count = obj.links.count()
        portal_url = f"{EXTERNAL_ADDRESS}/u/{obj.user.hash}"
        
        return format_html(
            '<div style="font-size: 12px; margin-bottom: 8px;">'
            '<strong>🔗 {} link(s)</strong>'
            '</div>'
            '<a href="{}" target="_blank" style="background: #4ade80; color: #000; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; font-weight: bold;">🌐 User Portal</a>',
            links_count, portal_url
        )


# Note: UserStatistics is not registered separately as admin model.
# All user statistics functionality is integrated into ACLLinkAdmin below.
@admin.register(ACLLink)
class ACLLinkAdmin(admin.ModelAdmin):
    list_display = ('link_display', 'user_display', 'server_display', 'comment_display', 'stats_display', 'usage_chart_display', 'last_access_display', 'created_display')
    list_filter = ('acl__server__name', 'acl__server__server_type', LastAccessFilter, 'acl__user__username')
    search_fields = ('link', 'comment', 'acl__user__username', 'acl__server__name')
    list_per_page = 100
    actions = ['delete_selected_links', 'update_statistics_action']
    list_select_related = ('acl__user', 'acl__server')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('acl__user', 'acl__server')
        return qs

    @admin.display(description='Link', ordering='link')
    def link_display(self, obj):
        link_url = f"{EXTERNAL_ADDRESS}/ss/{obj.link}#{obj.acl.server.name}"
        return format_html(
            '<a href="{}" target="_blank" style="color: #2563eb; text-decoration: none; font-family: monospace;">{}</a>',
            link_url, obj.link[:16] + '...' if len(obj.link) > 16 else obj.link
        )

    @admin.display(description='User', ordering='acl__user__username')
    def user_display(self, obj):
        return obj.acl.user.username

    @admin.display(description='Server', ordering='acl__server__name')
    def server_display(self, obj):
        server_type_icons = {
            'outline': '🔵',
            'wireguard': '🟢',
            'xray_core': '🟣',
        }
        icon = server_type_icons.get(obj.acl.server.server_type, '⚪')
        return f"{icon} {obj.acl.server.name}"

    @admin.display(description='Comment', ordering='comment')
    def comment_display(self, obj):
        if obj.comment:
            return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
        return '-'

    @admin.display(description='Statistics')
    def stats_display(self, obj):
        try:
            from .models import UserStatistics
            stats = UserStatistics.objects.get(
                user=obj.acl.user,
                server_name=obj.acl.server.name,
                acl_link_id=obj.link
            )
            
            # Color coding based on usage
            if stats.total_connections > 100:
                color = '#16a34a'  # green - high usage
            elif stats.total_connections > 10:
                color = '#eab308'  # yellow - medium usage
            elif stats.total_connections > 0:
                color = '#f97316'  # orange - low usage
            else:
                color = '#9ca3af'  # gray - no usage
            
            return mark_safe(
                f'<div style="font-size: 12px;">'
                f'<span style="color: {color}; font-weight: bold;">✨ {stats.total_connections} total</span><br>'
                f'<span style="color: #6b7280;">📅 {stats.recent_connections} last 30d</span>'
                f'</div>'
            )
        except:
            return mark_safe('<span style="color: #dc2626; font-size: 12px;">No cache</span>')

    @admin.display(description='30-day Chart')
    def usage_chart_display(self, obj):
        try:
            from .models import UserStatistics
            stats = UserStatistics.objects.get(
                user=obj.acl.user,
                server_name=obj.acl.server.name,
                acl_link_id=obj.link
            )
            
            if not stats.daily_usage:
                return mark_safe('<span style="color: #9ca3af; font-size: 11px;">No data</span>')
            
            # Create wider mini chart for better visibility
            max_val = max(stats.daily_usage) if stats.daily_usage else 1
            chart_html = '<div style="display: flex; align-items: end; gap: 1px; height: 35px; width: 180px;">'
            
            # Show last 30 days with wider bars for better visibility
            for day_count in stats.daily_usage[-30:]:  # Last 30 days
                if max_val > 0:
                    height_percent = (day_count / max_val) * 100
                else:
                    height_percent = 0
                
                color = '#4ade80' if day_count > 0 else '#e5e7eb'
                chart_html += f'<div style="background: {color}; width: 5px; height: {height_percent}%; min-height: 1px; border-radius: 1px;" title="{day_count} connections"></div>'
            
            chart_html += '</div>'
            
            # Add summary info below chart
            total_last_30 = sum(stats.daily_usage[-30:]) if stats.daily_usage else 0
            avg_daily = total_last_30 / 30 if total_last_30 > 0 else 0
            chart_html += f'<div style="font-size: 10px; color: #6b7280; margin-top: 2px;">'
            chart_html += f'Max: {max_val} | Avg: {avg_daily:.1f}'
            chart_html += f'</div>'
            
            return mark_safe(chart_html)
        except:
            return mark_safe('<span style="color: #dc2626; font-size: 11px;">-</span>')

    @admin.display(description='Last Access', ordering='last_access_time')
    def last_access_display(self, obj):
        if obj.last_access_time:
            from django.utils import timezone
            from datetime import timedelta
            
            local_time = localtime(obj.last_access_time)
            now = timezone.now()
            diff = now - obj.last_access_time
            
            # Color coding based on age
            if diff <= timedelta(days=7):
                color = '#16a34a'  # green - recent
            elif diff <= timedelta(days=30):
                color = '#eab308'  # yellow - medium
            elif diff <= timedelta(days=90):
                color = '#f97316'  # orange - old
            else:
                color = '#dc2626'  # red - very old
            
            formatted_date = local_time.strftime('%Y-%m-%d %H:%M')
            
            # Add relative time info
            if diff.days > 365:
                relative = f'{diff.days // 365}y ago'
            elif diff.days > 30:
                relative = f'{diff.days // 30}mo ago'
            elif diff.days > 0:
                relative = f'{diff.days}d ago'
            elif diff.seconds > 3600:
                relative = f'{diff.seconds // 3600}h ago'
            else:
                relative = 'Recently'
            
            return mark_safe(
                f'<span style="color: {color}; font-weight: bold; font-size: 12px;">{formatted_date}</span>'
                f'<br><small style="color: {color}; font-size: 10px;">{relative}</small>'
            )
        return mark_safe('<span style="color: #dc2626; font-weight: bold; font-size: 12px;">Never</span>')

    @admin.display(description='Created', ordering='acl__created_at')
    def created_display(self, obj):
        local_time = localtime(obj.acl.created_at)
        return local_time.strftime('%Y-%m-%d %H:%M')

    def delete_selected_links(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Successfully deleted {count} ACL link(s).')
    delete_selected_links.short_description = "Delete selected ACL links"
    
    def update_statistics_action(self, request, queryset):
        """Trigger comprehensive statistics update for all users and links"""
        # This action doesn't require selected items
        try:
            from vpn.tasks import update_user_statistics
            
            # Start the statistics update task
            task = update_user_statistics.delay()
            
            self.message_user(
                request,
                f'📊 Statistics update started successfully! Task ID: {task.id}. '
                f'This will recalculate usage statistics for all users and links. '
                f'Refresh this page in a few moments to see updated data.',
                level=messages.SUCCESS
            )
            
        except Exception as e:
            self.message_user(
                request,
                f'❌ Failed to start statistics update: {e}',
                level=messages.ERROR
            )
    update_statistics_action.short_description = "📊 Update all user statistics and usage data"

    def get_actions(self, request):
        """Remove default delete action and keep only custom one"""
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True
    
    def changelist_view(self, request, extra_context=None):
        # Handle actions that don't require item selection
        if 'action' in request.POST:
            action = request.POST['action']
            if action == 'update_statistics_action':
                # Call the action directly without queryset requirement
                self.update_statistics_action(request, None)
                # Return redirect to prevent AttributeError
                return redirect(request.get_full_path())
        
        # Add comprehensive statistics to the changelist
        extra_context = extra_context or {}
        
        # Get queryset for statistics
        queryset = self.get_queryset(request)
        
        total_links = queryset.count()
        never_accessed = queryset.filter(last_access_time__isnull=True).count()
        
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count, Max, Min
        
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)
        one_month_ago = now - timedelta(days=30)
        three_months_ago = now - timedelta(days=90)
        
        # Access time statistics
        old_links = queryset.filter(
            Q(last_access_time__lt=three_months_ago) | Q(last_access_time__isnull=True)
        ).count()
        
        recent_week = queryset.filter(last_access_time__gte=one_week_ago).count()
        recent_month = queryset.filter(last_access_time__gte=one_month_ago).count()
        
        # Calculate comprehensive statistics from cache
        try:
            from .models import UserStatistics
            from django.db import models
            
            # Total usage statistics
            cached_stats = UserStatistics.objects.aggregate(
                total_uses=models.Sum('total_connections'),
                recent_uses=models.Sum('recent_connections'),
                max_daily_peak=models.Max('max_daily')
            )
            total_uses = cached_stats['total_uses'] or 0
            recent_uses = cached_stats['recent_uses'] or 0
            max_daily_peak = cached_stats['max_daily_peak'] or 0
            
            # Server and user breakdown
            server_stats = UserStatistics.objects.values('server_name').annotate(
                total_connections=models.Sum('total_connections'),
                link_count=models.Count('id')
            ).order_by('-total_connections')[:5]  # Top 5 servers
            
            user_stats = UserStatistics.objects.values('user__username').annotate(
                total_connections=models.Sum('total_connections'),
                link_count=models.Count('id')
            ).order_by('-total_connections')[:5]  # Top 5 users
            
            # Links with cache data count
            cached_links_count = UserStatistics.objects.filter(
                acl_link_id__isnull=False
            ).count()
            
        except Exception as e:
            total_uses = 0
            recent_uses = 0
            max_daily_peak = 0
            server_stats = []
            user_stats = []
            cached_links_count = 0
        
        # Active vs inactive breakdown
        active_links = total_links - never_accessed - old_links
        if active_links < 0:
            active_links = 0
        
        extra_context.update({
            'total_links': total_links,
            'never_accessed': never_accessed,
            'old_links': old_links,
            'active_links': active_links,
            'recent_week': recent_week,
            'recent_month': recent_month,
            'total_uses': total_uses,
            'recent_uses': recent_uses,
            'max_daily_peak': max_daily_peak,
            'server_stats': server_stats,
            'user_stats': user_stats,
            'cached_links_count': cached_links_count,
            'cache_coverage_percent': (cached_links_count * 100 // total_links) if total_links > 0 else 0,
        })
        
        return super().changelist_view(request, extra_context)
    
    def get_ordering(self, request):
        """Allow sorting by annotated fields"""
        # Handle sorting by last_access_time if requested
        order_var = request.GET.get('o')
        if order_var:
            try:
                field_index = int(order_var.lstrip('-'))
                # Check if this corresponds to the last_access column (index 6 in list_display)
                if field_index == 6:  # last_access_display is at index 6
                    if order_var.startswith('-'):
                        return ['-last_access_time']
                    else:
                        return ['last_access_time']
            except (ValueError, IndexError):
                pass
        
        # Default ordering
        return ['-acl__created_at', 'acl__user__username']


try:
    from django_celery_results.models import GroupResult, TaskResult
    from django_celery_beat.models import (
        PeriodicTask, 
        ClockedSchedule, 
        CrontabSchedule, 
        IntervalSchedule, 
        SolarSchedule
    )
    from django.contrib.auth.models import Group
    
    # Unregister celery models that we don't want in admin
    admin.site.unregister(GroupResult)
    admin.site.unregister(PeriodicTask)
    admin.site.unregister(ClockedSchedule)
    admin.site.unregister(CrontabSchedule)
    admin.site.unregister(IntervalSchedule)
    admin.site.unregister(SolarSchedule)
    admin.site.unregister(TaskResult)
    
    # Unregister Django's default Group model
    admin.site.unregister(Group)
    
except (ImportError, admin.sites.NotRegistered):
    pass

# Custom Celery admin interfaces
try:
    from django_celery_results.models import TaskResult
    
    @admin.register(TaskResult)
    class CustomTaskResultAdmin(admin.ModelAdmin):
        list_display = ('task_name_display', 'status', 'date_created', 'date_done', 'worker', 'result_display', 'traceback_display')
        list_filter = ('status', 'date_created', 'worker', 'task_name')
        search_fields = ('task_name', 'task_id', 'worker')
        readonly_fields = ('task_id', 'task_name', 'status', 'result_formatted', 'date_created', 'date_done', 'traceback', 'worker', 'task_args', 'task_kwargs', 'meta')
        ordering = ('-date_created',)
        list_per_page = 50
        
        fieldsets = (
            ('Task Information', {
                'fields': ('task_id', 'task_name', 'status', 'worker')
            }),
            ('Timing', {
                'fields': ('date_created', 'date_done')
            }),
            ('Result', {
                'fields': ('result_formatted',),
                'classes': ('collapse',)
            }),
            ('Arguments', {
                'fields': ('task_args', 'task_kwargs'),
                'classes': ('collapse',)
            }),
            ('Error Details', {
                'fields': ('traceback',),
                'classes': ('collapse',)
            }),
            ('Metadata', {
                'fields': ('meta',),
                'classes': ('collapse',)
            }),
        )
        
        @admin.display(description='Task Name', ordering='task_name')
        def task_name_display(self, obj):
            task_names = {
                'sync_all_servers': '🔄 Sync All Servers',
                'sync_all_users_on_server': '👥 Sync Users on Server',
                'sync_server_info': '⚙️ Sync Server Info',
                'sync_user_on_server': '👤 Sync User on Server',
                'cleanup_task_logs': '🧹 Cleanup Old Logs',
                'update_user_statistics': '📊 Update Statistics',
            }
            return task_names.get(obj.task_name, obj.task_name)
        
        @admin.display(description='Result')
        def result_display(self, obj):
            if obj.status == 'SUCCESS' and obj.result:
                try:
                    import json
                    result = json.loads(obj.result) if isinstance(obj.result, str) else obj.result
                    if isinstance(result, str):
                        return result[:100] + '...' if len(result) > 100 else result
                    elif isinstance(result, dict):
                        return ', '.join(f'{k}: {v}' for k, v in result.items())[:100]
                except:
                    return str(obj.result)[:100] if obj.result else '-'
            elif obj.status == 'FAILURE':
                return '❌ Failed'
            elif obj.status == 'PENDING':
                return '⏳ Pending'
            elif obj.status == 'RETRY':
                return '🔄 Retrying'
            return '-'
        
        @admin.display(description='Result Details')
        def result_formatted(self, obj):
            if obj.result:
                try:
                    import json
                    result = json.loads(obj.result) if isinstance(obj.result, str) else obj.result
                    formatted = json.dumps(result, indent=2)
                    return mark_safe(f"<pre>{formatted}</pre>")
                except:
                    return mark_safe(f"<pre>{obj.result}</pre>")
            return '-'
        
        @admin.display(description='Error Info')
        def traceback_display(self, obj):
            if obj.traceback:
                # Show first 200 chars of traceback
                short_tb = obj.traceback[:200] + '...' if len(obj.traceback) > 200 else obj.traceback
                return mark_safe(f"<pre style='color: red; font-size: 12px;'>{short_tb}</pre>")
            return '-'
        
        def has_add_permission(self, request):
            return False
        
        def has_change_permission(self, request, obj=None):
            return False
        
except ImportError:
    pass

# Register XrayServerV2 admin
admin.site.register(XrayServerV2, XrayServerV2Admin)

# Add subscription management to User admin
from django.contrib.admin import site
for model, admin_instance in site._registry.items():
    if model.__name__ == 'User' and hasattr(admin_instance, 'fieldsets'):
        add_subscription_management_to_user(admin_instance.__class__)
        break
