"""
Logging admin interfaces (TaskExecutionLog, AccessLog)
"""
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.timezone import localtime

from vpn.models import TaskExecutionLog, AccessLog
from .base import BaseVPNAdmin
from vpn.utils import format_object


@admin.register(TaskExecutionLog)
class TaskExecutionLogAdmin(BaseVPNAdmin):
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
            'sync_server_users': '👥 Server Sync',
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


@admin.register(AccessLog)
class AccessLogAdmin(BaseVPNAdmin):
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