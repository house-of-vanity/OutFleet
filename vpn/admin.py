import json
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
from .models import User, AccessLog, TaskExecutionLog
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
    OutlineServerAdmin)

@admin.register(TaskExecutionLog)
class TaskExecutionLogAdmin(admin.ModelAdmin):
    list_display = ('task_name_display', 'action', 'status_display', 'server', 'user', 'execution_time_display', 'created_at')
    list_filter = ('task_name', 'status', 'server', 'created_at')
    search_fields = ('task_id', 'task_name', 'action', 'user__username', 'server__name', 'message')
    readonly_fields = ('task_id', 'task_name', 'server', 'user', 'action', 'status', 'message_formatted', 'execution_time', 'created_at')
    ordering = ('-created_at',)
    list_per_page = 100
    date_hierarchy = 'created_at'
    actions = ['trigger_full_sync']
    
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
            from datetime import timedelta
            from django.utils import timezone
            
            # Check if sync is already running (last 10 minutes)
            recent_cutoff = timezone.now() - timedelta(minutes=10)
            running_syncs = TaskExecutionLog.objects.filter(
                created_at__gte=recent_cutoff,
                task_name='sync_all_servers',
                status='STARTED'
            )
            
            if running_syncs.exists():
                self.message_user(
                    request,
                    'Synchronization is already running. Please wait for completion.',
                    level=messages.WARNING
                )
                return
            
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
        """Override to handle actions that don't require item selection and add sync status"""
        # Handle actions that don't require selection
        if 'action' in request.POST:
            action = request.POST['action']
            if action == 'trigger_full_sync':
                # Call the action directly without queryset requirement
                self.trigger_full_sync(request, None)
                # Return redirect to prevent AttributeError
                return redirect(request.get_full_path())
        
        # Add sync status and controls to the changelist
        extra_context = extra_context or {}
        
        # Add sync statistics
        from datetime import timedelta
        from django.utils import timezone
        
        # Get recent sync tasks (last 24 hours)
        recent_cutoff = timezone.now() - timedelta(hours=24)
        recent_syncs = TaskExecutionLog.objects.filter(
            created_at__gte=recent_cutoff,
            task_name='sync_all_servers'
        )
        
        total_recent = recent_syncs.count()
        successful_recent = recent_syncs.filter(status='SUCCESS').count()
        failed_recent = recent_syncs.filter(status='FAILURE').count()
        running_recent = recent_syncs.filter(status='STARTED').count()
        
        # Check if sync is currently running
        currently_running = recent_syncs.filter(status='STARTED').exists()
        
        extra_context.update({
            'total_recent_syncs': total_recent,
            'successful_recent_syncs': successful_recent,
            'failed_recent_syncs': failed_recent,
            'running_recent_syncs': running_recent,
            'sync_currently_running': currently_running,
        })
        
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
            # Links that have no access logs
            return queryset.filter(last_access__isnull=True)
        elif self.value() == 'week':
            # Links accessed in the last week
            week_ago = timezone.now() - timedelta(days=7)
            return queryset.filter(last_access__gte=week_ago)
        elif self.value() == 'month':
            # Links accessed in the last month
            month_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(last_access__gte=month_ago)
        elif self.value() == 'old':
            # Links not accessed for more than 3 months
            three_months_ago = timezone.now() - timedelta(days=90)
            return queryset.filter(last_access__lt=three_months_ago)
        return queryset

@admin.register(Server)
class ServerAdmin(PolymorphicParentModelAdmin):
    base_model = Server
    child_models = (OutlineServer, WireguardServer)
    list_display = ('name', 'server_type', 'comment', 'registration_date', 'user_count', 'server_status_inline')
    search_fields = ('name', 'comment')
    list_filter = ('server_type', )
    actions = ['move_clients_action', 'purge_all_keys_action']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('move-clients/', self.admin_site.admin_view(self.move_clients_view), name='server_move_clients'),
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
                # Check if this is an Outline server by checking the actual type
                from vpn.server_plugins.outline import OutlineServer
                
                if isinstance(server, OutlineServer) and hasattr(server, 'client'):
                    # For Outline servers, get all keys and delete them
                    try:
                        keys = server.client.get_keys()
                        keys_count = len(keys)
                        
                        for key in keys:
                            try:
                                server.client.delete_key(key.key_id)
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
                    # Show server type for debugging
                    server_type = type(server).__name__
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

    @admin.display(description='User Count', ordering='user_count')
    def user_count(self, obj):
        return obj.user_count

    @admin.display(description='Status')
    def server_status_inline(self, obj):
        try:
            status = obj.get_server_status()
            if 'error' in status:
                return mark_safe(f"<span style='color: red;'>Error: {status['error']}</span>")
            import json
            pretty_status = ", ".join(f"{key}: {value}" for key, value in status.items())
            return mark_safe(f"<pre>{pretty_status}</pre>")
        except Exception as e:
            # Don't let server connectivity issues break the admin interface
            return mark_safe(f"<span style='color: orange;'>Status unavailable: {e}</span>")
    server_status_inline.short_description = "Status"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(user_count=Count('acl'))
        return qs

#admin.site.register(User, UserAdmin)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserForm
    list_display = ('username', 'comment', 'registration_date', 'hash_link', 'server_count')
    search_fields = ('username', 'hash')
    readonly_fields = ('hash_link',)

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

    @admin.display(description='Allowed servers', ordering='server_count')
    def server_count(self, obj):
        return obj.server_count

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(server_count=Count('acl'))
        return qs

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
    list_display = ('user', 'server', 'action', 'formatted_timestamp')
    list_filter = ('user', 'server', 'action', 'timestamp')
    search_fields = ('user', 'server', 'action', 'timestamp', 'data')
    readonly_fields = ('server', 'user', 'formatted_timestamp', 'action', 'formated_data')

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
            data = server.get_user(user)
            return format_object(data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get user info for {user.username} on {server.name}: {e}")
            return mark_safe(f"<span style='color: red;'>Server connection error: {e}</span>")

    @admin.display(description='User Links')
    def display_links(self, obj):
        links = obj.links.all()
        portal_url = f"{EXTERNAL_ADDRESS}/u/{obj.user.hash}"
        
        links_html = []
        for link in links:
            link_url = f"{EXTERNAL_ADDRESS}/ss/{link.link}#{obj.server.name}"
            links_html.append(f"{link.comment} - {link_url}")
        
        links_text = '<br>'.join(links_html) if links_html else 'No links'
        
        return format_html(
            '<div style="margin-bottom: 10px;">{}</div>' +
            '<a href="{}" target="_blank" style="background: #4ade80; color: #000; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; font-weight: bold;">🌐 User Portal</a>',
            links_text, portal_url
        )


@admin.register(ACLLink)
class ACLLinkAdmin(admin.ModelAdmin):
    list_display = ('link_display', 'user_display', 'server_display', 'comment_display', 'last_access_display', 'created_display')
    list_filter = ('acl__server__name', 'acl__server__server_type', LastAccessFilter, 'acl__user__username')
    search_fields = ('link', 'comment', 'acl__user__username', 'acl__server__name')
    list_per_page = 100
    actions = ['delete_selected_links']
    list_select_related = ('acl__user', 'acl__server')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('acl__user', 'acl__server')
        
        # Add last access annotation
        qs = qs.annotate(
            last_access=Subquery(
                AccessLog.objects.filter(
                    user=OuterRef('acl__user__username'),
                    server=OuterRef('acl__server__name')
                ).order_by('-timestamp').values('timestamp')[:1]
            )
        )
        
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
        }
        icon = server_type_icons.get(obj.acl.server.server_type, '⚪')
        return f"{icon} {obj.acl.server.name}"

    @admin.display(description='Comment', ordering='comment')
    def comment_display(self, obj):
        if obj.comment:
            return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
        return '-'

    @admin.display(description='Last Access', ordering='last_access')
    def last_access_display(self, obj):
        if hasattr(obj, 'last_access') and obj.last_access:
            from django.utils import timezone
            from datetime import timedelta
            
            local_time = localtime(obj.last_access)
            now = timezone.now()
            diff = now - obj.last_access
            
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
                f'<span style="color: {color}; font-weight: bold;">{formatted_date}</span>'
                f'<br><small style="color: {color};">{relative}</small>'
            )
        return mark_safe('<span style="color: #dc2626; font-weight: bold;">Never</span>')

    @admin.display(description='Created', ordering='acl__created_at')
    def created_display(self, obj):
        local_time = localtime(obj.acl.created_at)
        return local_time.strftime('%Y-%m-%d %H:%M')

    def delete_selected_links(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Successfully deleted {count} ACL link(s).')
    delete_selected_links.short_description = "Delete selected ACL links"

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
        # Add summary statistics to the changelist
        extra_context = extra_context or {}
        
        # Get queryset with annotations for statistics
        queryset = self.get_queryset(request)
        
        total_links = queryset.count()
        never_accessed = queryset.filter(last_access__isnull=True).count()
        
        from django.utils import timezone
        from datetime import timedelta
        three_months_ago = timezone.now() - timedelta(days=90)
        old_links = queryset.filter(
            Q(last_access__lt=three_months_ago) | Q(last_access__isnull=True)
        ).count()
        
        extra_context.update({
            'total_links': total_links,
            'never_accessed': never_accessed,
            'old_links': old_links,
        })
        
        return super().changelist_view(request, extra_context)
    
    def get_ordering(self, request):
        """Allow sorting by annotated fields"""
        # Handle sorting by last_access if requested
        order_var = request.GET.get('o')
        if order_var:
            try:
                field_index = int(order_var.lstrip('-'))
                # Check if this corresponds to the last_access column (index 4 in list_display)
                if field_index == 4:  # last_access_display is at index 4
                    if order_var.startswith('-'):
                        return ['-last_access']
                    else:
                        return ['last_access']
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
