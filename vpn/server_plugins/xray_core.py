from django.db import models
from django.contrib import admin
from polymorphic.admin import PolymorphicChildModelAdmin, PolymorphicChildModelFilter
from .generic import Server
import logging
from typing import Optional, Dict, Any, List
import json

logger = logging.getLogger(__name__)


class XrayCoreServer(Server):
    """
    Xray Core VPN Server implementation.
    Supports VLESS, VMess, Shadowsocks, and Trojan protocols.
    """
    
    # API Configuration
    api_address = models.CharField(
        max_length=255,
        help_text="Xray Core API address (e.g., http://127.0.0.1:8080)"
    )
    api_port = models.IntegerField(
        default=8080,
        help_text="API port for management interface"
    )
    api_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="API authentication token"
    )
    
    # Server Configuration
    server_address = models.CharField(
        max_length=255,
        help_text="Server address for clients to connect"
    )
    server_port = models.IntegerField(
        default=443,
        help_text="Server port for client connections"
    )
    
    # Protocol Configuration
    protocol = models.CharField(
        max_length=20,
        choices=[
            ('vless', 'VLESS'),
            ('vmess', 'VMess'),
            ('shadowsocks', 'Shadowsocks'),
            ('trojan', 'Trojan'),
        ],
        default='vless',
        help_text="Primary protocol for this server"
    )
    
    # Security Configuration
    security = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('tls', 'TLS'),
            ('reality', 'REALITY'),
            ('xtls', 'XTLS'),
        ],
        default='tls',
        help_text="Security layer configuration"
    )
    
    # Transport Configuration
    transport = models.CharField(
        max_length=20,
        choices=[
            ('tcp', 'TCP'),
            ('ws', 'WebSocket'),
            ('http', 'HTTP/2'),
            ('grpc', 'gRPC'),
            ('quic', 'QUIC'),
        ],
        default='tcp',
        help_text="Transport protocol"
    )
    
    # Configuration JSON
    config_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete Xray configuration in JSON format"
    )
    
    # Panel Configuration (if using 3X-UI or similar)
    panel_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Web panel URL if using 3X-UI or similar management panel"
    )
    panel_username = models.CharField(
        max_length=100,
        blank=True,
        help_text="Panel admin username"
    )
    panel_password = models.CharField(
        max_length=100,
        blank=True,
        help_text="Panel admin password"
    )
    
    class Meta:
        verbose_name = "Xray Core Server"
        verbose_name_plural = "Xray Core Servers"
    
    def __str__(self):
        return f"Xray Core Server: {self.name} ({self.protocol.upper()})"
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get server status information.
        Mock implementation for now.
        """
        logger.info(f"Getting status for Xray Core server: {self.name}")
        
        # TODO: Implement actual API call to get server status
        return {
            'online': True,
            'version': '1.8.0',
            'uptime': '7 days',
            'clients_online': 42,
            'total_traffic': '1.2 TB',
            'protocol': self.protocol,
            'transport': self.transport,
            'security': self.security,
        }
    
    def sync(self) -> bool:
        """
        Sync server configuration.
        Mock implementation for now.
        """
        logger.info(f"Syncing Xray Core server: {self.name}")
        
        # TODO: Implement actual configuration sync
        # This would typically:
        # 1. Connect to Xray API or panel
        # 2. Push configuration updates
        # 3. Reload Xray service
        
        return True
    
    def sync_users(self) -> Dict[str, Any]:
        """
        Sync all users on the server.
        Mock implementation for now.
        """
        logger.info(f"Syncing users for Xray Core server: {self.name}")
        
        # TODO: Implement actual user sync
        # This would typically:
        # 1. Get list of users from database
        # 2. Get list of users from Xray server
        # 3. Add missing users
        # 4. Remove extra users
        # 5. Update user configurations
        
        return {
            'synced': 10,
            'added': 2,
            'removed': 1,
            'errors': 0,
        }
    
    def add_user(self, user_id: str, email: str) -> Dict[str, Any]:
        """
        Add a user to the server.
        Mock implementation for now.
        """
        logger.info(f"Adding user {email} to Xray Core server: {self.name}")
        
        # TODO: Implement actual user addition
        # This would typically:
        # 1. Generate user UUID
        # 2. Create user configuration based on protocol
        # 3. Add user to Xray server via API
        # 4. Return connection details
        
        import uuid
        user_uuid = str(uuid.uuid4())
        
        # Mock connection string based on protocol
        if self.protocol == 'vless':
            connection_string = f"vless://{user_uuid}@{self.server_address}:{self.server_port}?encryption=none&security={self.security}&type={self.transport}#{self.name}"
        elif self.protocol == 'vmess':
            # VMess requires base64 encoding of config
            vmess_config = {
                "v": "2",
                "ps": self.name,
                "add": self.server_address,
                "port": str(self.server_port),
                "id": user_uuid,
                "aid": "0",
                "net": self.transport,
                "type": "none",
                "tls": self.security,
            }
            import base64
            config_str = base64.b64encode(json.dumps(vmess_config).encode()).decode()
            connection_string = f"vmess://{config_str}"
        else:
            connection_string = f"{self.protocol}://{user_uuid}@{self.server_address}:{self.server_port}"
        
        return {
            'user_id': user_uuid,
            'email': email,
            'connection_string': connection_string,
            'qr_code': f"https://api.qrserver.com/v1/create-qr-code/?data={connection_string}",
        }
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from server.
        Mock implementation for now.
        """
        logger.info(f"Getting user {user_id} from Xray Core server: {self.name}")
        
        # TODO: Implement actual user retrieval
        # This would typically:
        # 1. Query Xray API for user info
        # 2. Return user configuration and statistics
        
        return {
            'user_id': user_id,
            'email': 'user@example.com',
            'created': '2024-01-01',
            'traffic_used': '100 GB',
            'traffic_limit': '1000 GB',
            'expire_date': '2024-12-31',
            'online': True,
        }
    
    def delete_user(self, user_id: str) -> bool:
        """
        Remove user from server.
        Mock implementation for now.
        """
        logger.info(f"Deleting user {user_id} from Xray Core server: {self.name}")
        
        # TODO: Implement actual user deletion
        # This would typically:
        # 1. Remove user from Xray configuration
        # 2. Reload Xray service
        # 3. Return success/failure
        
        return True
    
    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get user traffic statistics.
        Mock implementation for now.
        """
        logger.info(f"Getting statistics for user {user_id} on Xray Core server: {self.name}")
        
        # TODO: Implement actual statistics retrieval
        # This would typically:
        # 1. Query Xray stats API
        # 2. Parse and return traffic data
        
        return {
            'user_id': user_id,
            'download': 50 * 1024 * 1024 * 1024,  # 50 GB in bytes
            'upload': 10 * 1024 * 1024 * 1024,    # 10 GB in bytes
            'total': 60 * 1024 * 1024 * 1024,     # 60 GB in bytes
            'last_seen': '2024-01-27 12:00:00',
        }


@admin.register(XrayCoreServer)
class XrayCoreServerAdmin(PolymorphicChildModelAdmin):
    base_model = XrayCoreServer
    show_in_index = False
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'comment', 'server_type'),
        }),
        ('API Configuration', {
            'fields': ('api_address', 'api_port', 'api_token'),
            'classes': ('collapse',),
        }),
        ('Server Configuration', {
            'fields': ('server_address', 'server_port'),
        }),
        ('Protocol Settings', {
            'fields': ('protocol', 'security', 'transport'),
        }),
        ('Panel Configuration (Optional)', {
            'fields': ('panel_url', 'panel_username', 'panel_password'),
            'classes': ('collapse',),
        }),
        ('Advanced Configuration', {
            'fields': ('config_json',),
            'classes': ('collapse',),
        }),
    )
    
    list_display = ('name', 'server_address', 'protocol', 'security', 'transport', 'get_status_display')
    list_filter = ('protocol', 'security', 'transport')
    search_fields = ('name', 'server_address', 'comment')
    
    def get_status_display(self, obj):
        """Display server status in admin list."""
        try:
            status = obj.get_server_status()
            if status.get('online'):
                return '✅ Online'
            else:
                return '❌ Offline'
        except Exception:
            return '⚠️ Unknown'
    get_status_display.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        """Override save to set server_type."""
        obj.server_type = 'xray_core'
        super().save_model(request, obj, form, change)