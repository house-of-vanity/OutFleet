"""
VPN Admin Module

This module provides Django admin interfaces for the VPN application.
The admin interface has been refactored into separate modules for better organization:

- base.py: Common utilities and base classes
- user.py: User management admin interface
- server.py: Server management admin interface  
- access.py: Access control (ACL/ACLLink) admin interfaces
- logs.py: Logging (TaskExecutionLog/AccessLog) admin interfaces

All admin classes are automatically registered with Django admin.
"""

# Import all admin classes to ensure they are registered
from .user import UserAdmin
from .server import ServerAdmin, UserACLInline
from .access import (
    ACLAdmin, 
    ACLLinkAdmin, 
    UserNameFilter, 
    ServerNameFilter, 
    LastAccessFilter,
    ACLLinkInline
)
from .logs import TaskExecutionLogAdmin, AccessLogAdmin
from .base import BaseVPNAdmin, format_bytes

# Re-export for backward compatibility
__all__ = [
    'UserAdmin',
    'ServerAdmin',
    'UserACLInline', 
    'ACLAdmin',
    'ACLLinkAdmin',
    'TaskExecutionLogAdmin',
    'AccessLogAdmin',
    'BaseVPNAdmin',
    'format_bytes',
    'UserNameFilter',
    'ServerNameFilter', 
    'LastAccessFilter',
    'ACLLinkInline'
]