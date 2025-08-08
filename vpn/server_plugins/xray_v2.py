import logging
from django.db import models
from django.contrib import admin
from .generic import Server
from vpn.models_xray import XrayConfiguration, Inbound, UserSubscription

logger = logging.getLogger(__name__)


class XrayServerV2(Server):
    """
    New Xray server that works with subscription groups and inbounds.
    This server can host multiple inbounds and users access them through subscription groups.
    """
    client_hostname = models.CharField(
        max_length=255, 
        help_text="Client connection hostname (what users see in their configs)"
    )
    api_address = models.CharField(
        max_length=255, 
        default="127.0.0.1:10085",
        help_text="Xray gRPC API address for management"
    )
    api_enabled = models.BooleanField(
        default=True,
        help_text="Enable gRPC API for user management"
    )
    stats_enabled = models.BooleanField(
        default=True,
        help_text="Enable traffic statistics collection"
    )
    
    class Meta:
        verbose_name = "Xray Server v2"
        verbose_name_plural = "Xray Servers v2"
    
    def save(self, *args, **kwargs):
        if not self.server_type:
            self.server_type = 'xray_v2'
        super().save(*args, **kwargs)
    
    def get_server_status(self):
        """Get server status including active inbounds"""
        try:
            # Get basic server information
            active_inbounds = self.get_active_inbounds()
            
            # Try to connect to Xray API if enabled
            api_status = False
            api_error = None
            api_stats = {}
            
            if self.api_enabled:
                try:
                    # Try different methods to check server status
                    import socket
                    import json
                    
                    # Parse API address
                    host, port = self.api_address.split(':')
                    port = int(port)
                    
                    # Test basic connection
                    logger.info(f"Testing connection to Xray API at {host}:{port}")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    
                    if result == 0:
                        api_status = True
                        logger.info(f"Successfully connected to Xray API at {self.api_address}")
                        
                        # Try to get stats if library is available
                        try:
                            from vpn.xray_api_v2.server_manager import ServerManager
                            manager = ServerManager(self.api_address)
                            api_stats = manager.get_server_stats()
                            logger.info(f"Got server stats: {api_stats}")
                        except ImportError:
                            logger.info("Xray API v2 library not available, but connection successful")
                            api_stats = {"connection": "ok", "library": "not_available"}
                        except Exception as stats_e:
                            logger.warning(f"Connection OK but stats failed: {stats_e}")
                            api_stats = {"connection": "ok", "stats_error": str(stats_e)}
                    else:
                        api_error = f"Connection failed to {host}:{port}"
                        logger.warning(f"Failed to connect to Xray API at {self.api_address}: {api_error}")
                        
                except Exception as e:
                    api_error = f"Connection test failed: {str(e)}"
                    logger.warning(f"Failed to test connection to Xray API for server {self.name}: {e}")
            else:
                api_error = "API disabled in server settings"
                logger.info(f"API disabled for server {self.name}")
            
            # Build status response
            status = {
                'server_name': self.name,
                'server_type': 'Xray Server v2',
                'client_hostname': self.client_hostname,
                'api_address': self.api_address,
                'api_enabled': self.api_enabled,
                'api_connected': api_status,
                'api_error': api_error,
                'api_stats': api_stats,
                'stats_enabled': self.stats_enabled,
                'total_inbounds': active_inbounds.count(),
                'inbound_ports': [],  # Will be populated when ServerInbound model is fully implemented
                'accessible': api_status if self.api_enabled else True,  # Consider accessible if API disabled
                'status': 'Connected' if api_status else 'API Issue' if self.api_enabled else 'No API Check'
            }
            
            logger.info(f"Server status for {self.name}: {status['status']}")
            return status
            
        except Exception as e:
            logger.error(f"Failed to get status for Xray server {self.name}: {e}")
            return {
                'error': str(e),
                'server_name': self.name,
                'server_type': 'Xray Server v2',
                'accessible': False,
                'status': 'Error'
            }
    
    def get_active_inbounds(self):
        """Get all inbounds that are deployed on this server"""
        try:
            from vpn.models_xray import ServerInbound
            return ServerInbound.objects.filter(server=self, active=True).select_related('inbound')
        except ImportError:
            # ServerInbound model doesn't exist yet, return empty queryset
            from django.db.models import QuerySet
            from vpn.models_xray import Inbound
            return Inbound.objects.none()
        except Exception as e:
            logger.warning(f"Error getting active inbounds for server {self.name}: {e}")
            from vpn.models_xray import Inbound
            return Inbound.objects.none()
    
    def sync_users(self):
        """Sync all users who have subscription groups containing inbounds on this server"""
        try:
            from vpn.tasks import sync_server_users
            task = sync_server_users.delay(self.id)
            logger.info(f"Scheduled user sync for Xray server {self.name} - task ID: {task.id}")
            # Return success to indicate task was scheduled
            return {"status": "scheduled", "task_id": str(task.id)}
        except Exception as e:
            logger.error(f"Failed to schedule user sync for server {self.name}: {e}")
            return {"status": "failed", "error": str(e)}
    
    def sync_inbounds(self):
        """Deploy all required inbounds on this server based on subscription groups"""
        try:
            from vpn.tasks import sync_server_inbounds
            task = sync_server_inbounds.delay(self.id)
            logger.info(f"Scheduled inbound sync for Xray server {self.name} - task ID: {task.id}")
            # Return None to match old behavior
            return None
        except Exception as e:
            logger.error(f"Failed to schedule inbound sync for server {self.name}: {e}")
            return None
    
    def deploy_inbound(self, inbound, users=None):
        """Deploy a specific inbound on this server with optional users"""
        try:
            from vpn.xray_api_v2.client import XrayClient
            import uuid
            
            logger.info(f"Deploying inbound {inbound.name} with protocol {inbound.protocol} on port {inbound.port}")
            client = XrayClient(server=self.api_address)
            
            # Build user configs if users are provided
            user_configs = []
            if users:
                for user in users:
                    user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user.username}-{inbound.name}"))
                    
                    if inbound.protocol == 'vless':
                        user_config = {
                            "email": f"{user.username}@{self.name}",
                            "id": user_uuid,
                            "level": 0
                        }
                    elif inbound.protocol == 'vmess':
                        user_config = {
                            "email": f"{user.username}@{self.name}",
                            "id": user_uuid,
                            "level": 0,
                            "alterId": 0
                        }
                    elif inbound.protocol == 'trojan':
                        user_config = {
                            "email": f"{user.username}@{self.name}",
                            "password": user_uuid,
                            "level": 0
                        }
                    else:
                        logger.warning(f"Unsupported protocol {inbound.protocol} for user {user.username}")
                        continue
                    
                    user_configs.append(user_config)
                    logger.info(f"Added user {user.username} to inbound config")
            
            # Build proper inbound configuration based on protocol
            if inbound.full_config:
                inbound_config = inbound.full_config.copy()  # Make a copy to modify
                logger.info(f"Using existing full_config for inbound {inbound.name}")
                
                # Add users to the config if provided
                if user_configs:
                    if 'settings' not in inbound_config:
                        inbound_config['settings'] = {}
                    inbound_config['settings']['clients'] = user_configs
                    logger.info(f"Added {len(user_configs)} users to full_config")
                
                # If inbound has a certificate, update the config to use inline certificates
                if inbound.certificate and inbound.certificate.certificate_pem:
                    logger.info(f"Updating full_config with inline certificate for {inbound.certificate.domain}")
                    
                    # Convert PEM to lines for Xray format
                    cert_lines = inbound.certificate.certificate_pem.strip().split('\n')
                    key_lines = inbound.certificate.private_key_pem.strip().split('\n')
                    
                    # Update streamSettings if it exists
                    if "streamSettings" in inbound_config and "tlsSettings" in inbound_config["streamSettings"]:
                        inbound_config["streamSettings"]["tlsSettings"]["certificates"] = [{
                            "certificate": cert_lines,
                            "key": key_lines,
                            "usage": "encipherment"
                        }]
                        logger.info("Updated existing tlsSettings with inline certificate")
            else:
                # Build full config based on protocol
                inbound_config = {
                    "tag": inbound.name,
                    "port": inbound.port,
                    "protocol": inbound.protocol,
                    "listen": inbound.listen_address or "0.0.0.0",
                }
                
                # Add protocol-specific settings
                if inbound.protocol == 'vless':
                    inbound_config["settings"] = {
                        "clients": user_configs,  # Add users during creation
                        "decryption": "none"
                    }
                    if inbound.network == 'ws':
                        inbound_config["streamSettings"] = {
                            "network": "ws",
                            "wsSettings": {
                                "path": f"/{inbound.name}"
                            }
                        }
                    elif inbound.network == 'tcp':
                        inbound_config["streamSettings"] = {
                            "network": "tcp"
                        }
                elif inbound.protocol == 'vmess':
                    inbound_config["settings"] = {
                        "clients": user_configs  # Add users during creation
                    }
                    if inbound.network == 'ws':
                        inbound_config["streamSettings"] = {
                            "network": "ws",
                            "wsSettings": {
                                "path": f"/{inbound.name}"
                            }
                        }
                    elif inbound.network == 'tcp':
                        inbound_config["streamSettings"] = {
                            "network": "tcp"
                        }
                elif inbound.protocol == 'trojan':
                    inbound_config["settings"] = {
                        "clients": user_configs  # Add users during creation
                    }
                    inbound_config["streamSettings"] = {
                        "network": "tcp",
                        "security": "tls"
                    }
                    
                    # Trojan always requires TLS certificate
                    if inbound.certificate and inbound.certificate.certificate_pem:
                        logger.info(f"Using certificate for Trojan inbound on domain {inbound.certificate.domain}")
                        # Convert PEM to lines for Xray format
                        cert_lines = inbound.certificate.certificate_pem.strip().split('\n')
                        key_lines = inbound.certificate.private_key_pem.strip().split('\n')
                        
                        inbound_config["streamSettings"]["tlsSettings"] = {
                            "certificates": [{
                                "certificate": cert_lines,
                                "key": key_lines,
                                "usage": "encipherment"
                            }]
                        }
                    else:
                        logger.error(f"Trojan protocol requires certificate, but none found for inbound {inbound.name}!")
                        inbound_config["streamSettings"]["tlsSettings"] = {
                            "certificates": []
                        }
                
                # Add TLS if specified
                if inbound.security == 'tls' and inbound.protocol != 'trojan':
                    if "streamSettings" not in inbound_config:
                        inbound_config["streamSettings"] = {}
                    inbound_config["streamSettings"]["security"] = "tls"
                    
                    # Check if inbound has a certificate
                    if inbound.certificate and inbound.certificate.certificate_pem:
                        logger.info(f"Using certificate for domain {inbound.certificate.domain}")
                        # Convert PEM to lines for Xray format
                        cert_lines = inbound.certificate.certificate_pem.strip().split('\n')
                        key_lines = inbound.certificate.private_key_pem.strip().split('\n')
                        
                        inbound_config["streamSettings"]["tlsSettings"] = {
                            "certificates": [{
                                "certificate": cert_lines,
                                "key": key_lines,
                                "usage": "encipherment"
                            }]
                        }
                    else:
                        logger.warning(f"No certificate found for inbound {inbound.name}, TLS will not work!")
                        inbound_config["streamSettings"]["tlsSettings"] = {
                            "certificates": []
                        }
            
            logger.info(f"Inbound config: {inbound_config}")
            
            # Add inbound using the client's add_inbound method which handles wrapping
            try:
                result = client.add_inbound(inbound_config)
                logger.info(f"Deploy inbound result: {result}")
                
                # Check if command was successful
                if result is not None and not (isinstance(result, dict) and 'error' in result):
                    # Mark as deployed on this server
                    from vpn.models_xray import ServerInbound
                    ServerInbound.objects.update_or_create(
                        server=self,
                        inbound=inbound,
                        defaults={'active': True}
                    )
                    logger.info(f"Successfully deployed inbound {inbound.name} on server {self.name}")
                    return True
                else:
                    logger.error(f"Failed to deploy inbound {inbound.name} on server {self.name}. Result: {result}")
                    return False
            except Exception as cmd_error:
                logger.error(f"Command execution error: {cmd_error}")
                return False
            
        except Exception as e:
            logger.error(f"Error deploying inbound {inbound.name} on server {self.name}: {e}")
            return False
    
    def add_user_to_inbound(self, user, inbound):
        """Add a user to a specific inbound on this server using inbound recreation approach"""
        try:
            from vpn.xray_api_v2.client import XrayClient
            import uuid
            
            logger.info(f"Adding user {user.username} to inbound {inbound.name} using inbound recreation")
            client = XrayClient(server=self.api_address)
            
            # Generate user UUID based on username and inbound
            user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user.username}-{inbound.name}"))
            logger.info(f"Generated UUID for user {user.username}: {user_uuid}")
            
            # Build user config based on protocol
            if inbound.protocol == 'vless':
                user_config = {
                    "email": f"{user.username}@{self.name}",
                    "id": user_uuid,
                    "level": 0
                }
            elif inbound.protocol == 'vmess':
                user_config = {
                    "email": f"{user.username}@{self.name}",
                    "id": user_uuid,
                    "level": 0,
                    "alterId": 0
                }
            elif inbound.protocol == 'trojan':
                user_config = {
                    "email": f"{user.username}@{self.name}",
                    "password": user_uuid,
                    "level": 0
                }
            else:
                logger.error(f"Unsupported protocol: {inbound.protocol}")
                return False
            
            try:
                # First, get existing inbound to check for other users
                existing_result = client.execute_command('lsi')
                existing_inbound = None
                
                if existing_result and 'inbounds' in existing_result:
                    for ib in existing_result['inbounds']:
                        if ib.get('tag') == inbound.name:
                            existing_inbound = ib
                            break
                
                if not existing_inbound:
                    logger.warning(f"Inbound {inbound.name} not found on server, deploying it first")
                    # Deploy the inbound if it doesn't exist
                    if not self.deploy_inbound(inbound):
                        logger.error(f"Failed to deploy inbound {inbound.name}")
                        return False
                    # Get the inbound config we just created
                    existing_inbound = {"settings": {"clients": []}}
                
                # Get existing users from the inbound
                existing_users = existing_inbound.get('settings', {}).get('clients', [])
                logger.info(f"Found {len(existing_users)} existing users in inbound {inbound.name}")
                
                # Check if user already exists
                for existing_user in existing_users:
                    if existing_user.get('email') == f"{user.username}@{self.name}":
                        logger.info(f"User {user.username} already exists in inbound {inbound.name}")
                        return True
                
                # Add new user to existing users list
                existing_users.append(user_config)
                logger.info(f"Creating new inbound with {len(existing_users)} users including {user.username}")
                
                # Remove the old inbound
                logger.info(f"Removing old inbound {inbound.name}")
                client.remove_inbound(inbound.name)
                
                # Recreate inbound with updated user list
                if inbound.full_config:
                    inbound_config = inbound.full_config.copy()
                    if 'settings' not in inbound_config:
                        inbound_config['settings'] = {}
                    inbound_config['settings']['clients'] = existing_users
                    
                    # Handle certificate embedding if needed
                    if inbound.certificate and inbound.certificate.certificate_pem:
                        cert_lines = inbound.certificate.certificate_pem.strip().split('\n')
                        key_lines = inbound.certificate.private_key_pem.strip().split('\n')
                        
                        if "streamSettings" in inbound_config and "tlsSettings" in inbound_config["streamSettings"]:
                            inbound_config["streamSettings"]["tlsSettings"]["certificates"] = [{
                                "certificate": cert_lines,
                                "key": key_lines,
                                "usage": "encipherment"
                            }]
                else:
                    # Build config from scratch with the users
                    inbound_config = {
                        "tag": inbound.name,
                        "port": inbound.port,
                        "protocol": inbound.protocol,
                        "listen": inbound.listen_address or "0.0.0.0",
                        "settings": {}
                    }
                    
                    if inbound.protocol in ['vless', 'vmess']:
                        inbound_config["settings"]["clients"] = existing_users
                        if inbound.protocol == 'vless':
                            inbound_config["settings"]["decryption"] = "none"
                    elif inbound.protocol == 'trojan':
                        inbound_config["settings"]["clients"] = existing_users
                
                logger.info(f"Deploying updated inbound with users: {[u.get('email') for u in existing_users]}")
                result = client.add_inbound(inbound_config)
                
                if result is not None and not (isinstance(result, dict) and 'error' in result):
                    logger.info(f"Successfully added user {user.username} to inbound {inbound.name} via inbound recreation")
                    return True
                else:
                    logger.error(f"Failed to recreate inbound {inbound.name} with user. Result: {result}")
                    return False
                    
            except Exception as cmd_error:
                logger.error(f"Error during inbound recreation: {cmd_error}")
                return False
            
        except Exception as e:
            logger.error(f"Error adding user {user.username} to inbound {inbound.name} on server {self.name}: {e}")
            return False
    
    def remove_user_from_inbound(self, user, inbound):
        """Remove a user from a specific inbound on this server"""
        try:
            from vpn.xray_api_v2.client import XrayClient
            
            client = XrayClient(server=self.api_address)
            
            # Remove user using the client's remove_users method
            user_email = f"{user.username}@{self.name}"
            logger.info(f"Removing user {user_email} from inbound {inbound.name}")
            
            result = client.remove_users(inbound.name, user_email)
            logger.info(f"Remove user result: {result}")
            
            if result is not None and not (isinstance(result, dict) and 'error' in result):
                logger.info(f"Successfully removed user {user.username} from inbound {inbound.name} on server {self.name}")
                return True
            else:
                logger.error(f"Failed to remove user {user.username} from inbound {inbound.name} on server {self.name}. Result: {result}")
                return False
            
        except Exception as e:
            logger.error(f"Error removing user {user.username} from inbound {inbound.name} on server {self.name}: {e}")
            return False
    
    def get_user_configs(self, user):
        """Generate all connection configs for a user on this server"""
        configs = []
        
        try:
            # Get all subscription groups for this user
            user_subscriptions = UserSubscription.objects.filter(
                user=user,
                active=True,
                subscription_group__is_active=True
            ).select_related('subscription_group').prefetch_related('subscription_group__inbounds')
            
            for subscription in user_subscriptions:
                group = subscription.subscription_group
                
                # Check which inbounds from this group are active on this server
                active_inbounds = self.get_active_inbounds().filter(
                    inbound__in=group.inbounds.all()
                )
                
                for server_inbound in active_inbounds:
                    inbound = server_inbound.inbound
                    
                    try:
                        # Generate connection string directly
                        from vpn.views import generate_xray_connection_string
                        connection_string = generate_xray_connection_string(user, inbound)
                        
                        if connection_string:
                            configs.append({
                                'protocol': inbound.protocol,
                                'inbound_name': inbound.name,
                                'group_name': group.name,
                                'connection_string': connection_string,
                                'port': inbound.port,
                                'network': inbound.network,
                                'security': inbound.security
                            })
                    
                    except Exception as e:
                        logger.warning(f"Failed to generate config for user {user.username} on inbound {inbound.name}: {e}")
                        continue
            
            logger.info(f"Generated {len(configs)} configs for user {user.username} on server {self.name}")
            return configs
            
        except Exception as e:
            logger.error(f"Error generating user configs for {user.username} on server {self.name}: {e}")
            return []
    
    def sync(self):
        """Sync server configuration and users"""
        try:
            self.sync_inbounds()
            self.sync_users()
            logger.info(f"Full sync completed for server {self.name}")
        except Exception as e:
            logger.error(f"Sync failed for server {self.name}: {e}")
    
    def add_user(self, user, **kwargs):
        """Add user to server - implemented through subscription groups"""
        try:
            from vpn.xray_api_v2.client import XrayClient
            client = XrayClient(server=self.api_address)
            
            # Users are added through subscription groups in the new architecture
            subscriptions = user.xray_subscriptions.filter(active=True)
            added_count = 0
            
            logger.info(f"User {user.username} has {subscriptions.count()} active subscriptions")
            
            if subscriptions.count() == 0:
                logger.warning(f"User {user.username} has no active Xray subscriptions - cannot add to server")
                return False
            
            # Get all inbounds that this user should have access to
            inbounds_to_process = []
            for subscription in subscriptions:
                logger.info(f"Processing subscription group: {subscription.subscription_group.name}")
                for inbound in subscription.subscription_group.inbounds.all():
                    if inbound not in inbounds_to_process:
                        inbounds_to_process.append(inbound)
                        logger.info(f"Added inbound {inbound.name} to processing list")
            
            # Get existing inbounds on server
            try:
                existing_result = client.execute_command('lsi')  # List inbounds
                existing_inbound_tags = set()
                if existing_result and 'inbounds' in existing_result:
                    existing_inbound_tags = {ib.get('tag') for ib in existing_result['inbounds'] if ib.get('tag')}
                logger.info(f"Existing inbound tags on server: {existing_inbound_tags}")
            except Exception as e:
                logger.warning(f"Failed to list inbounds: {e}")
                existing_inbound_tags = set()
            
            # Process each inbound
            for inbound in inbounds_to_process:
                logger.info(f"Processing inbound: {inbound.name} (protocol: {inbound.protocol})")
                
                # Check if inbound exists on server
                if inbound.name not in existing_inbound_tags:
                    logger.info(f"Inbound {inbound.name} doesn't exist on server, creating with user")
                    # Create the inbound with the user directly
                    if self.deploy_inbound(inbound, users=[user]):
                        logger.info(f"Successfully created inbound {inbound.name} with user {user.username}")
                        added_count += 1
                        existing_inbound_tags.add(inbound.name)
                        
                        # Mark as deployed on this server
                        from vpn.models_xray import ServerInbound
                        ServerInbound.objects.update_or_create(
                            server=self,
                            inbound=inbound,
                            defaults={'active': True}
                        )
                    else:
                        logger.error(f"Failed to create inbound {inbound.name} with user")
                        continue
                else:
                    # Inbound exists, add user using recreation approach
                    logger.info(f"Inbound {inbound.name} exists, adding user via recreation")
                    if self.add_user_to_inbound(user, inbound):
                        added_count += 1
                        logger.info(f"Successfully added user {user.username} to existing inbound {inbound.name}")
                    else:
                        logger.error(f"Failed to add user {user.username} to existing inbound {inbound.name}")
            
            logger.info(f"Added user {user.username} to {added_count} inbounds on server {self.name}")
            return added_count > 0
            
        except Exception as e:
            logger.error(f"Failed to add user {user.username} to server {self.name}: {e}")
            return False
    
    def get_user(self, user, raw=False):
        """Get user configurations from server"""
        try:
            configs = self.get_user_configs(user)
            if raw:
                return {
                    'configs': configs,
                    'total_configs': len(configs)
                }
            return configs
            
        except Exception as e:
            logger.error(f"Failed to get user {user.username} from server {self.name}: {e}")
            return [] if not raw else {'error': str(e)}
    
    def delete_user(self, user):
        """Remove user from server"""
        try:
            removed_count = 0
            subscriptions = user.xray_subscriptions.filter(active=True)
            
            for subscription in subscriptions:
                for inbound in subscription.subscription_group.inbounds.all():
                    if self.remove_user_from_inbound(user, inbound):
                        removed_count += 1
            
            logger.info(f"Removed user {user.username} from {removed_count} inbounds on server {self.name}")
            return removed_count > 0
            
        except Exception as e:
            logger.error(f"Failed to remove user {user.username} from server {self.name}: {e}")
            return False
    
    def __str__(self):
        return f"Xray Server v2: {self.name}"


class XrayServerV2Admin(admin.ModelAdmin):
    list_display = ['name', 'client_hostname', 'api_address', 'api_enabled', 'stats_enabled', 'registration_date']
    list_filter = ['api_enabled', 'stats_enabled', 'registration_date']
    search_fields = ['name', 'client_hostname', 'comment']
    readonly_fields = ['server_type', 'registration_date']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ('name', 'comment', 'server_type')
        }),
        ('Connection Settings', {
            'fields': ('client_hostname', 'api_address')
        }),
        ('Features', {
            'fields': ('api_enabled', 'stats_enabled')
        }),
        ('Timestamps', {
            'fields': ('registration_date',),
            'classes': ('collapse',)
        })
    ]
    
    actions = ['sync_users', 'sync_inbounds', 'get_status']
    
    def sync_users(self, request, queryset):
        for server in queryset:
            server.sync_users()
        self.message_user(request, f"Scheduled user sync for {queryset.count()} servers")
    sync_users.short_description = "Sync users for selected servers"
    
    def sync_inbounds(self, request, queryset):
        for server in queryset:
            server.sync_inbounds()
        self.message_user(request, f"Scheduled inbound sync for {queryset.count()} servers")
    sync_inbounds.short_description = "Sync inbounds for selected servers"
    
    def get_status(self, request, queryset):
        statuses = []
        for server in queryset:
            status = server.get_server_status()
            statuses.append(f"{server.name}: {status.get('accessible', 'Unknown')}")
        self.message_user(request, f"Server statuses: {', '.join(statuses)}")
    get_status.short_description = "Check status of selected servers"