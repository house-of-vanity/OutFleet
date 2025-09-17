"""
Server admin interface
"""
import re
from polymorphic.admin import PolymorphicParentModelAdmin
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.db.models import Count, Case, When, Value, IntegerField, F, Subquery, OuterRef
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import path, reverse
from django.http import HttpResponseRedirect, JsonResponse

from mysite.settings import EXTERNAL_ADDRESS
from vpn.models import Server, ACL, ACLLink
from .base import BaseVPNAdmin, format_bytes
from vpn.server_plugins import (
    OutlineServer,
    WireguardServer,
    XrayServerV2
)


@admin.register(Server)
class ServerAdmin(PolymorphicParentModelAdmin, BaseVPNAdmin):
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
        """Custom action to move client links between servers"""
        if queryset.count() == 0:
            self.message_user(request, "Please select at least one server.", level=messages.ERROR)
            return
        
        # Redirect to move clients page
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
                        regex_parts = comment_regex.split(' -> ')
                        if len(regex_parts) != 2:
                            messages.error(request, "Invalid regex format. Use: pattern -> replacement")
                            return redirect(request.get_full_path())
                        
                        pattern_str = regex_parts[0]
                        replacement_str = regex_parts[1]
                        
                        # Convert JavaScript-style $1, $2, $3 to Python-style \1, \2, \3
                        python_replacement = replacement_str
                        # Replace $1, $2, etc. with \1, \2, etc. for Python regex
                        python_replacement = re.sub(r'\$(\d+)', r'\\\1', replacement_str)
                        
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
            from vpn.tasks import sync_server_users
            from celery import current_app
            
            tasks_started = 0
            errors = []
            scheduled_tasks = set()  # Track already scheduled tasks to avoid duplicates
            
            for server in queryset:
                try:
                    # Check if a task is already running for this server
                    task_key = f"sync_server_{server.id}"
                    
                    # Use Celery's inspect to check active tasks (optional, for better UX)
                    try:
                        inspect = current_app.control.inspect()
                        active_tasks = inspect.active()
                        
                        # Check if task is already scheduled for this server
                        task_already_running = False
                        if active_tasks:
                            for worker, tasks in active_tasks.items():
                                for task_info in tasks:
                                    if task_info.get('name') == 'sync_server_users':
                                        # Check if server.id is in the task args
                                        task_args = task_info.get('args', [])
                                        if task_args and len(task_args) > 0 and task_args[0] == server.id:
                                            task_already_running = True
                                            break
                        
                        if task_already_running:
                            self.message_user(
                                request,
                                f"⏳ Sync already in progress for '{server.name}'",
                                level=messages.WARNING
                            )
                            continue
                    except Exception as e:
                        # If we can't check active tasks, just proceed
                        logger.debug(f"Could not check active tasks: {e}")
                    
                    # Avoid scheduling duplicate tasks in this batch
                    if server.id in scheduled_tasks:
                        continue
                        
                    task = sync_server_users.delay(server.id)
                    scheduled_tasks.add(server.id)
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
            
            # Different logic for Xray vs legacy servers
            if obj.server_type == 'xray_v2':
                # For Xray servers, count inbounds and active subscriptions
                from vpn.models_xray import ServerInbound
                total_inbounds = ServerInbound.objects.filter(server=obj, active=True).count()
                
                # Count recent subscription accesses via AccessLog
                thirty_days_ago = timezone.now() - timedelta(days=30)
                from vpn.models import AccessLog
                active_accesses = AccessLog.objects.filter(
                    server='Xray-Subscription',
                    action='Success',
                    timestamp__gte=thirty_days_ago
                ).values('user').distinct().count()
                
                total_links = total_inbounds
                active_links = min(active_accesses, user_count)  # Can't be more than total users
            else:
                # Legacy servers: use ACL links as before
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
                color = '#dc2626'  # red - no links/inbounds
            elif obj.server_type == 'xray_v2':
                # For Xray: base on user activity rather than link activity
                if active_links > user_count * 0.5:  # More than half users active
                    color = '#16a34a'  # green
                elif active_links > user_count * 0.2:  # More than 20% users active
                    color = '#eab308'  # yellow
                else:
                    color = '#f97316'  # orange - low activity
            else:
                # Legacy servers: base on link activity
                if total_links > 0 and active_links > total_links * 0.7:  # High activity
                    color = '#16a34a'  # green
                elif total_links > 0 and active_links > total_links * 0.3:  # Medium activity
                    color = '#eab308'  # yellow
                else:
                    color = '#f97316'  # orange - low activity
            
            # Different display for Xray vs legacy
            if obj.server_type == 'xray_v2':
                # Try to get traffic stats if stats enabled
                traffic_info = ""
                # Get the real XrayServerV2 instance to access its fields
                xray_server = obj.get_real_instance()
                if hasattr(xray_server, 'stats_enabled') and xray_server.stats_enabled and xray_server.api_enabled:
                    try:
                        from vpn.xray_api_v2.client import XrayClient
                        from vpn.xray_api_v2.stats import StatsManager
                        
                        client = XrayClient(server=xray_server.api_address)
                        stats_manager = StatsManager(client)
                        traffic_summary = stats_manager.get_traffic_summary()
                        
                        # Calculate total traffic
                        total_uplink = 0
                        total_downlink = 0
                        
                        # Sum up user traffic
                        for user_email, user_traffic in traffic_summary.get('users', {}).items():
                            total_uplink += user_traffic.get('uplink', 0)
                            total_downlink += user_traffic.get('downlink', 0)
                        
                        # Format traffic
                        
                        if total_uplink > 0 or total_downlink > 0:
                            traffic_info = f'<div style="color: #6b7280; font-size: 11px;">↑{format_bytes(total_uplink)} ↓{format_bytes(total_downlink)}</div>'
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.debug(f"Could not get stats for Xray server {xray_server.name}: {e}")
                
                return mark_safe(
                    f'<div style="font-size: 12px;">' +
                    f'<div style="color: {color}; font-weight: bold;">👥 {user_count} users</div>' +
                    f'<div style="color: #6b7280;">📡 {total_links} inbounds</div>' +
                    traffic_info +
                    f'</div>'
                )
            else:
                return mark_safe(
                    f'<div style="font-size: 12px;">' +
                    f'<div style="color: {color}; font-weight: bold;">👥 {user_count} users</div>' +
                    f'<div style="color: #6b7280;">🔗 {active_links}/{total_links} active</div>' +
                    f'</div>'
                )
        except Exception as e:
            import traceback
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in user_stats for server {obj.name}: {e}", exc_info=True)
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
        from vpn.models_xray import UserSubscription, ServerInbound
        
        qs = super().get_queryset(request)
        
        # Count ACL users for all servers
        qs = qs.annotate(
            acl_user_count=Count('acl__user', distinct=True)
        )
        
        # For Xray servers, calculate user count separately
        # Create subquery to count Xray users
        xray_user_count_subquery = ServerInbound.objects.filter(
            server_id=OuterRef('pk'),
            active=True,
            inbound__subscriptiongroup__usersubscription__active=True,
            inbound__subscriptiongroup__is_active=True
        ).values('server_id').annotate(
            count=Count('inbound__subscriptiongroup__usersubscription__user', distinct=True)
        ).values('count')
        
        qs = qs.annotate(
            xray_user_count=Subquery(xray_user_count_subquery, output_field=IntegerField()),
            user_count=Case(
                When(server_type='xray_v2', then=F('xray_user_count')),
                default=F('acl_user_count'),
                output_field=IntegerField()
            )
        )
        
        # Handle None values from subquery
        qs = qs.annotate(
            user_count=Case(
                When(server_type='xray_v2', user_count__isnull=True, then=Value(0)),
                When(server_type='xray_v2', then=F('xray_user_count')),
                default=F('acl_user_count'),
                output_field=IntegerField()
            )
        )
        
        qs = qs.prefetch_related(
            'acl_set__links',
            'acl_set__user'
        )
        return qs
    
    def sync_server_view(self, request, object_id):
        """Dispatch sync to appropriate server type."""
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


# Inline for legacy VPN access (Outline/Wireguard)
class UserACLInline(admin.TabularInline):
    model = ACL
    extra = 0
    fields = ('server', 'created_at', 'link_count')
    readonly_fields = ('created_at', 'link_count')
    verbose_name = "Legacy VPN Server Access"
    verbose_name_plural = "Legacy VPN Server Access (Outline/Wireguard)"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "server":
            # Only show old-style servers (Outline/Wireguard)
            kwargs["queryset"] = Server.objects.exclude(server_type='xray_v2')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    @admin.display(description='Links')
    def link_count(self, obj):
        count = obj.links.count()
        return format_html(
            '<span style="font-weight: bold;">{}</span> link(s)',
            count
        )