"""
Django admin configuration for VPN application

This module has been refactored for better organization. The admin classes
are now split across multiple modules in the vpn.admin package:

- vpn.admin.user: User management admin interface
- vpn.admin.server: Server management admin interface  
- vpn.admin.access: Access control (ACL/ACLLink) admin interfaces
- vpn.admin.logs: Logging (TaskExecutionLog/AccessLog) admin interfaces
- vpn.admin.base: Common utilities and base classes
"""

import logging
logger = logging.getLogger(__name__)

import json
from django.contrib import admin
from django.utils.safestring import mark_safe


# Import server plugins and their admin classes
try:
    from .server_plugins import (
        XrayServerV2,
        XrayServerV2Admin
    )
except Exception as e:
    logger.error(f"❌ Failed to import server plugins: {e}")

# Import admin interfaces from refactored modules
# This ensures all admin classes are registered
try:
    from .admin import *
except Exception as e:
    logger.error(f"❌ Failed to import refactored admin modules: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")

# Import Xray admin configuration and all Xray admin classes
try:
    from .admin_xray import *
except Exception as e:
    logger.error(f"❌ Failed to import Xray admin classes: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")

# Set custom admin site configuration
admin.site.site_title = "VPN Manager"
admin.site.site_header = "VPN Manager"
admin.site.index_title = "OutFleet"

# Custom Celery admin interfaces
try:
    from django_celery_results.models import TaskResult
    
    # Unregister default TaskResult admin if it exists
    try:
        admin.site.unregister(TaskResult)
    except admin.sites.NotRegistered:
        pass
    
    
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
                'sync_server_users': '👥 Sync Users on Server',
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
    pass  # Celery not available

# Add subscription management to User admin
try:
    from vpn.admin_xray import add_subscription_management_to_user
    from vpn.admin.user import UserAdmin
    add_subscription_management_to_user(UserAdmin)
    logger.info("✅ Successfully added subscription management to User admin")
except Exception as e:
    logger.error(f"Failed to add subscription management: {e}")

# Note: Unwanted admin interfaces are cleaned up in vpn/apps.py ready() method

# Force reload trigger