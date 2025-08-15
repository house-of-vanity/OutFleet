"""
Minimal admin test to check execution
"""

import logging
logger = logging.getLogger(__name__)
import json
from django.contrib import admin
from django.utils.safestring import mark_safe

# Try importing server plugins
try:
    from .server_plugins import (
        XrayServerV2,
        XrayServerV2Admin
    )
except Exception as e:
    logger.error(f"🔴 Failed to import server plugins: {e}")

# Try importing refactored admin modules
try:
    from .admin import *
except Exception as e:
    logger.error(f"🔴 Failed to import refactored admin modules: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")

# Try importing Xray admin classes
try:
    from .admin_xray import *
except Exception as e:
    logger.error(f"🔴 Failed to import Xray admin classes: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")

# Set custom admin site configuration
admin.site.site_title = "VPN Manager"
admin.site.site_header = "VPN Manager"
admin.site.index_title = "OutFleet"

# Try adding custom Celery admin interfaces
try:
    from django_celery_results.models import TaskResult
    
    # Unregister default TaskResult admin if it exists
    try:
        admin.site.unregister(TaskResult)
    except admin.sites.NotRegistered:
        pass
    
    
    @admin.register(TaskResult)
    class CustomTaskResultAdmin(admin.ModelAdmin):
        list_display = ('task_name_display', 'status', 'date_created')
        
        @admin.display(description='Task Name', ordering='task_name')
        def task_name_display(self, obj):
            return obj.task_name
    
    
except ImportError:
    pass  # Celery not available

# Add subscription management to User admin
try:
    from vpn.admin.user import add_subscription_management_to_user
    from django.contrib.admin import site
    for model, admin_instance in site._registry.items():
        if model.__name__ == 'User' and hasattr(admin_instance, 'fieldsets'):
            add_subscription_management_to_user(admin_instance.__class__)
            break
except Exception as e:
    logger.error(f"Failed to add subscription management: {e}")