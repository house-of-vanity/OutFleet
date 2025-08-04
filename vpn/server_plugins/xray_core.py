"""
Xray Core VPN server plugin implementation.

This module provides Django models and admin interfaces for managing Xray Core
servers, inbounds, and clients. Supports VLESS, VMess, and Trojan protocols.
"""

import base64
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from django.contrib import admin, messages
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Count, Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from polymorphic.admin import PolymorphicChildModelAdmin, PolymorphicChildModelFilter

from .generic import Server

logger = logging.getLogger(__name__)


class XrayConnectionError(Exception):
    """Custom exception for Xray connection errors."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception


class XrayCoreServer(Server):
    """
    Xray Core VPN Server implementation.
    
    Supports VLESS, VMess, Shadowsocks, and Trojan protocols through gRPC API.
    """

    # gRPC API Configuration
    grpc_address = models.CharField(
        max_length=255,
        default="127.0.0.1",
        help_text="Xray Core gRPC API address"
    )
    grpc_port = models.IntegerField(
        default=10085,
        help_text="gRPC API port (usually 10085)"
    )

    # Client connection hostname
    client_hostname = models.CharField(
        max_length=255,
        default="127.0.0.1",
        help_text="Hostname or IP address for client connections"
    )

    # Stats Configuration
    enable_stats = models.BooleanField(
        default=True,
        help_text="Enable traffic statistics tracking"
    )

    class Meta:
        verbose_name = "Xray Core Server"
        verbose_name_plural = "Xray Core Servers"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self._client = None

    def save(self, *args, **kwargs):
        """Set server type on save."""
        self.server_type = 'xray_core'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (Xray Core)"

    @property
    def client(self):
        """Get or create Xray gRPC client for communication."""
        if self._client is None:
            try:
                from vpn.xray_api.client import XrayClient
                from vpn.xray_api.exceptions import APIError

                server_address = f"{self.grpc_address}:{self.grpc_port}"
                self._client = XrayClient(server_address)

                logger.info(f"[{self.name}] Created XrayClient for {server_address}")

            except Exception as e:
                logger.error(f"[{self.name}] Failed to create XrayClient: {e}")
                raise XrayConnectionError(
                    "Failed to connect to Xray Core", 
                    original_exception=e
                )

        return self._client

    def create_inbound(
        self, 
        protocol: str, 
        port: int, 
        tag: Optional[str] = None, 
        network: str = 'tcp', 
        security: str = 'none', 
        **kwargs
    ):
        """Create a new inbound dynamically."""
        try:
            from vpn.xray_api.exceptions import APIError

            logger.info(f"[{self.name}] Creating {protocol} inbound on port {port}")

            # Create inbound in database first
            inbound = XrayInbound.objects.create(
                server=self,
                protocol=protocol,
                port=port,
                tag=tag or f"{protocol}-{port}",
                network=network,
                security=security,
                listen=kwargs.get('listen', '0.0.0.0'),
                enabled=True,
                **{k: v for k, v in kwargs.items() 
                   if k in ['ss_method', 'ss_password', 'stream_settings', 'sniffing_settings']}
            )

            # Create inbound on Xray server using API library
            if protocol == 'vless':
                self.client.add_vless_inbound(
                    port=port,
                    users=[],
                    tag=inbound.tag,
                    listen=inbound.listen,
                    network=network
                )
            elif protocol == 'vmess':
                self.client.add_vmess_inbound(
                    port=port,
                    users=[],
                    tag=inbound.tag,
                    listen=inbound.listen,
                    network=network
                )
            elif protocol == 'trojan':
                self.client.add_trojan_inbound(
                    port=port,
                    users=[],
                    tag=inbound.tag,
                    listen=inbound.listen,
                    network=network
                )
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")

            logger.info(f"[{self.name}] Inbound {inbound.tag} created successfully")
            return inbound

        except Exception as e:
            logger.error(f"[{self.name}] Failed to create inbound: {e}")
            if 'inbound' in locals():
                inbound.delete()
            raise XrayConnectionError(f"Failed to create inbound: {e}")

    def delete_inbound(self, inbound_or_tag):
        """Delete an inbound."""
        try:
            from vpn.xray_api.exceptions import APIError

            if isinstance(inbound_or_tag, str):
                inbound = self.inbounds.get(tag=inbound_or_tag)
                tag = inbound_or_tag
            else:
                inbound = inbound_or_tag
                tag = inbound.tag

            logger.info(f"[{self.name}] Deleting inbound {tag}")

            # Remove from Xray server first
            self.client.remove_inbound(tag)

            # Remove from database
            inbound.delete()

            logger.info(f"[{self.name}] Inbound {tag} deleted successfully")
            return True

        except Exception as e:
            logger.error(f"[{self.name}] Failed to delete inbound: {e}")
            raise XrayConnectionError(f"Failed to delete inbound: {e}")

    def get_server_status(self, raw: bool = False) -> Dict[str, Any]:
        """Get server status and statistics."""
        status = {}

        try:
            # Get basic stats
            stats_info = self.client.get_server_stats()

            status.update({
                'online': True,
                'stats_enabled': self.enable_stats,
                'inbounds_count': self.inbounds.count(),
                'total_users': 0,
                'total_traffic': {
                    'uplink': 0,
                    'downlink': 0
                }
            })

            # Count users across all inbounds
            for inbound in self.inbounds.all():
                status['total_users'] += inbound.clients.count()

            # Get traffic stats if available
            if stats_info and hasattr(stats_info, 'stat'):
                for stat in stats_info.stat:
                    if 'user>>>' in stat.name:
                        if '>>>traffic>>>uplink' in stat.name:
                            status['total_traffic']['uplink'] += stat.value
                        elif '>>>traffic>>>downlink' in stat.name:
                            status['total_traffic']['downlink'] += stat.value

            if raw:
                status['raw_stats'] = stats_info

        except Exception as e:
            status.update({
                'online': False,
                'error': str(e)
            })

        return status

    def sync_inbounds(self) -> Dict[str, Any]:
        """Sync inbounds - create missing inbounds and register protocols."""
        logger.info(f"[{self.name}] Starting inbound sync")
        try:
            inbound_results = []

            # Get list of existing inbounds
            existing_inbound_tags = set()
            try:
                existing_inbounds = self.client.list_inbounds()
                logger.debug(f"[{self.name}] Raw inbounds response: {existing_inbounds}")

                # Handle both dict with 'inbounds' key and direct list
                if isinstance(existing_inbounds, dict) and 'inbounds' in existing_inbounds:
                    inbound_list = existing_inbounds['inbounds']
                elif isinstance(existing_inbounds, list):
                    inbound_list = existing_inbounds
                else:
                    logger.warning(f"[{self.name}] Unexpected inbounds format: {type(existing_inbounds)}")
                    inbound_list = []

                existing_inbound_tags = {
                    inbound.get('tag') for inbound in inbound_list 
                    if isinstance(inbound, dict) and inbound.get('tag')
                }
                logger.info(f"[{self.name}] Found existing inbounds: {existing_inbound_tags}")
            except Exception as e:
                logger.debug(f"[{self.name}] Could not list existing inbounds: {e}")

            # Create missing inbounds and register protocols
            for inbound in self.inbounds.filter(enabled=True):
                try:
                    if inbound.tag in existing_inbound_tags:
                        logger.info(f"[{self.name}] Inbound {inbound.tag} already exists, registering protocol")
                        inbound_results.append(f"✓ {inbound.tag} (existing)")
                    else:
                        logger.info(f"[{self.name}] Creating new inbound {inbound.tag}")

                        # Create inbound with empty user list
                        if inbound.protocol == 'vless':
                            self.client.add_vless_inbound(
                                port=inbound.port,
                                users=[],
                                tag=inbound.tag,
                                listen=inbound.listen or "0.0.0.0",
                                network=inbound.network or "tcp"
                            )
                        elif inbound.protocol == 'vmess':
                            self.client.add_vmess_inbound(
                                port=inbound.port,
                                users=[],
                                tag=inbound.tag,
                                listen=inbound.listen or "0.0.0.0",
                                network=inbound.network or "tcp"
                            )
                        elif inbound.protocol == 'trojan':
                            self.client.add_trojan_inbound(
                                port=inbound.port,
                                users=[],
                                tag=inbound.tag,
                                listen=inbound.listen or "0.0.0.0",
                                network=inbound.network or "tcp",
                                hostname=self.client_hostname
                            )

                        inbound_results.append(f"✓ {inbound.tag} (created)")
                        logger.info(f"[{self.name}] Created new inbound {inbound.tag}")
                        existing_inbound_tags.add(inbound.tag)

                    # Register protocol in client (needed for add_user to work)
                    self._register_protocol_for_inbound(inbound)

                except Exception as e:
                    logger.error(f"[{self.name}] Failed to create/register inbound {inbound.tag}: {e}")
                    inbound_results.append(f"✗ {inbound.tag}: {e}")

            logger.info(f"[{self.name}] Inbound sync completed")
            return {
                "status": "Inbounds synced successfully",
                "inbounds": inbound_results,
                "existing_tags": list(existing_inbound_tags)
            }

        except Exception as e:
            logger.error(f"[{self.name}] Inbound sync failed: {e}")
            raise XrayConnectionError("Failed to sync inbounds", original_exception=e)

    def sync_users(self) -> Dict[str, Any]:
        """Sync users - add all users with ACL links to their inbounds."""
        logger.info(f"[{self.name}] Starting user sync")
        try:
            from vpn.models import ACL

            # Get all users that have ACL links to this server
            all_acls = ACL.objects.filter(server=self)
            acl_users = set(acl.user for acl in all_acls)
            logger.info(f"[{self.name}] Found {len(acl_users)} users with ACL links")

            if not acl_users:
                logger.info(f"[{self.name}] No users to sync")
                return {
                    "status": "No users to sync",
                    "users_added": 0
                }

            # First, refresh protocol registrations to ensure they exist
            self._register_all_protocols()

            user_results = []
            total_added = 0

            for inbound in self.inbounds.filter(enabled=True):
                logger.info(f"[{self.name}] Adding users to inbound {inbound.tag}")

                # Get or create clients for users with ACL links
                for user in acl_users:
                    try:
                        # Get or create Django client
                        client, created = XrayClient.objects.get_or_create(
                            user=user,
                            inbound=inbound,
                            defaults={
                                'email': f"{user.username}@{inbound.tag}",
                                'uuid': str(uuid.uuid4()),
                                'enable': True
                            }
                        )

                        # For Trojan, ensure password exists
                        if inbound.protocol == 'trojan' and not client.password:
                            client.password = str(uuid.uuid4())
                            client.save()

                        # Create user object for API
                        user_obj = inbound._client_to_user_obj(client)

                        # Add user to inbound via API
                        try:
                            self.client.add_user(inbound.tag, user_obj)

                            if created:
                                logger.info(f"[{self.name}] Created and added user {user.username} to {inbound.tag}")
                            else:
                                logger.info(f"[{self.name}] Added existing user {user.username} to {inbound.tag}")
                            total_added += 1

                        except Exception as api_error:
                            logger.error(f"[{self.name}] API error adding user {user.username} to {inbound.tag}: {api_error}")
                            user_results.append(f"✗ {user.username}@{inbound.tag}: {api_error}")

                    except Exception as e:
                        logger.error(f"[{self.name}] Failed to add user {user.username} to {inbound.tag}: {e}")
                        user_results.append(f"✗ {user.username}@{inbound.tag}: {e}")

            user_sync_result = f"Added {total_added} users across all inbounds"
            logger.info(f"[{self.name}] {user_sync_result}")

            return {
                "status": "Users synced successfully",
                "users_added": total_added,
                "errors": user_results
            }

        except Exception as e:
            logger.error(f"[{self.name}] User sync failed: {e}")
            raise XrayConnectionError("Failed to sync users", original_exception=e)

    def _register_protocol_for_inbound(self, inbound):
        """Register protocol for a specific inbound."""
        if inbound.tag not in self.client._protocols:
            logger.debug(f"[{self.name}] Registering protocol for inbound {inbound.tag}")
            
            if inbound.protocol == 'vless':
                from vpn.xray_api.protocols import VlessProtocol
                protocol = VlessProtocol(
                    port=inbound.port,
                    tag=inbound.tag,
                    listen=inbound.listen or "0.0.0.0",
                    network=inbound.network or "tcp"
                )
                self.client._protocols[inbound.tag] = protocol
            elif inbound.protocol == 'vmess':
                from vpn.xray_api.protocols import VmessProtocol
                protocol = VmessProtocol(
                    port=inbound.port,
                    tag=inbound.tag,
                    listen=inbound.listen or "0.0.0.0",
                    network=inbound.network or "tcp"
                )
                self.client._protocols[inbound.tag] = protocol
            elif inbound.protocol == 'trojan':
                from vpn.xray_api.protocols import TrojanProtocol
                protocol = TrojanProtocol(
                    port=inbound.port,
                    tag=inbound.tag,
                    listen=inbound.listen or "0.0.0.0",
                    network=inbound.network or "tcp",
                    hostname=self.client_hostname or "localhost"
                )
                self.client._protocols[inbound.tag] = protocol

            logger.debug(f"[{self.name}] Registered protocol {inbound.protocol} for inbound {inbound.tag}")

    def _register_all_protocols(self):
        """Register all inbound protocols in client for user management."""
        logger.debug(f"[{self.name}] Registering all protocols")
        for inbound in self.inbounds.filter(enabled=True):
            self._register_protocol_for_inbound(inbound)

    def sync(self) -> Dict[str, Any]:
        """Comprehensive sync - calls inbound sync then user sync."""
        logger.info(f"[{self.name}] Starting comprehensive sync")
        try:
            # Step 1: Sync inbounds
            inbound_result = self.sync_inbounds()

            # Step 2: Sync users
            user_result = self.sync_users()

            logger.info(f"[{self.name}] Comprehensive sync completed")
            return {
                "status": "Server synced successfully",
                "inbounds": inbound_result.get("inbounds", []),
                "users": f"Added {user_result.get('users_added', 0)} users across all inbounds"
            }

        except Exception as e:
            logger.error(f"[{self.name}] Comprehensive sync failed: {e}")
            raise XrayConnectionError("Failed to sync configuration", original_exception=e)

    def add_user(self, user):
        """Add a user to the server."""
        logger.info(f"[{self.name}] Adding user {user.username}")

        try:
            # Check if user already exists
            existing_client = XrayClient.objects.filter(
                inbound__server=self,
                user=user
            ).first()

            if existing_client:
                logger.debug(f"[{self.name}] User {user.username} already exists")
                return self._build_user_response(existing_client)

            # Get first available enabled inbound
            inbound = self.inbounds.filter(enabled=True).first()

            if not inbound:
                logger.warning(f"[{self.name}] No enabled inbounds available for user {user.username}")
                return {"status": "No enabled inbounds available. Please create an inbound first."}

            # Create client
            client = XrayClient.objects.create(
                inbound=inbound,
                user=user,
                uuid=uuid.uuid4(),
                email=user.username,
                enable=True
            )

            # Apply to Xray through gRPC
            result = self._apply_client_to_xray(user, target_inbound=inbound, action='add')
            if not result:
                # If direct API call fails, try using inbound sync method
                logger.warning(f"[{self.name}] Direct API add failed, trying inbound sync for user {user.username}")
                try:
                    inbound.sync_to_server()
                    logger.info(f"[{self.name}] Successfully synced inbound {inbound.tag} with user {user.username}")
                except Exception as sync_error:
                    logger.error(f"[{self.name}] Inbound sync also failed: {sync_error}")
                    raise XrayConnectionError(f"Failed to add user via API and sync: {sync_error}")

            logger.info(f"[{self.name}] User {user.username} added successfully")
            return self._build_user_response(client)

        except Exception as e:
            logger.error(f"[{self.name}] Failed to add user {user.username}: {e}")
            raise XrayConnectionError(f"Failed to add user: {e}")

    def get_user(self, user, raw: bool = False):
        """Get user information from server."""
        try:
            client = XrayClient.objects.filter(
                inbound__server=self,
                user=user
            ).first()

            if not client:
                # Try to add user if not found (auto-create)
                logger.warning(f"[{self.name}] User {user.username} not found, attempting to create")
                return self.add_user(user)

            if raw:
                return client

            return self._build_user_response(client)

        except Exception as e:
            logger.error(f"[{self.name}] Failed to get user {user.username}: {e}")
            raise XrayConnectionError(f"Failed to get user: {e}")

    def delete_user(self, user):
        """Remove user from server."""
        logger.info(f"[{self.name}] Deleting user {user.username}")

        try:
            clients = XrayClient.objects.filter(
                inbound__server=self,
                user=user
            )

            if not clients.exists():
                return {"status": "User not found on server. Nothing to do."}

            for client in clients:
                # Remove from Xray through gRPC
                self._apply_client_to_xray(user, target_inbound=client.inbound, action='remove')
                client.delete()

            logger.info(f"[{self.name}] User {user.username} deleted successfully")
            return {"status": "User was deleted"}

        except Exception as e:
            logger.error(f"[{self.name}] Failed to delete user {user.username}: {e}")
            raise XrayConnectionError(f"Failed to delete user: {e}")

    def get_user_statistics(self, user) -> Dict[str, Any]:
        """Get user traffic statistics."""
        try:
            stats = {
                'user': user.username,
                'total_upload': 0,
                'total_download': 0,
                'clients': []
            }

            clients = XrayClient.objects.filter(
                inbound__server=self,
                user=user
            )

            for client in clients:
                client_stats = self._get_client_stats(client)
                stats['total_upload'] += client_stats['upload']
                stats['total_download'] += client_stats['download']
                stats['clients'].append({
                    'inbound': client.inbound.tag,
                    'protocol': client.inbound.protocol,
                    'upload': client_stats['upload'],
                    'download': client_stats['download'],
                    'enable': client.enable
                })

            return stats

        except Exception as e:
            logger.error(f"[{self.name}] Failed to get statistics for {user.username}: {e}")
            return {
                'user': user.username,
                'error': str(e)
            }

    def _apply_client_to_xray(
        self, 
        user, 
        target_inbound=None, 
        action: str = 'add'
    ) -> bool:
        """Apply user to Xray inbound through gRPC API."""
        try:
            from vpn.xray_api.models import VlessUser, VmessUser, TrojanUser
            from vpn.xray_api.exceptions import APIError

            # Determine which inbound to use
            if target_inbound:
                inbound = target_inbound
            else:
                # Fallback to first available inbound
                inbound = self.inbounds.filter(enabled=True).first()
                if not inbound:
                    raise XrayConnectionError("No enabled inbounds available")

            # Get or create client for this user and inbound
            client, created = XrayClient.objects.get_or_create(
                user=user,
                inbound=inbound,
                defaults={
                    'email': f"{user.username}@{inbound.tag}",
                    'uuid': str(uuid.uuid4()),
                    'enable': True,
                    'protocol': inbound.protocol
                }
            )

            # Create user object based on protocol
            if inbound.protocol == 'vless':
                user_obj = VlessUser(email=client.email, uuid=str(client.uuid))
            elif inbound.protocol == 'vmess':
                user_obj = VmessUser(email=client.email, uuid=str(client.uuid), alter_id=0)
            elif inbound.protocol == 'trojan':
                # For Trojan, we use password field (could be UUID or custom password)
                password = getattr(client, 'password', str(client.uuid))
                user_obj = TrojanUser(email=client.email, password=password)
            else:
                raise ValueError(f"Unsupported protocol: {inbound.protocol}")

            if action == 'add':
                logger.debug(f"[{self.name}] Adding client {client.email} to inbound {inbound.tag}")
                self.client.add_user(inbound.tag, user_obj)
                logger.info(f"[{self.name}] User {user.username} added to inbound {inbound.tag}")
                return True

            elif action == 'remove':
                logger.debug(f"[{self.name}] Removing client {client.email} from inbound {inbound.tag}")
                self.client.remove_user(inbound.tag, client.email)
                return {"status": "User removed successfully"}

            return True

        except Exception as e:
            client_info = getattr(client, 'email', user.username) if 'client' in locals() else user.username
            logger.error(f"[{self.name}] Failed to {action} client {client_info}: {e}")
            return False

    def _get_client_stats(self, client) -> Dict[str, int]:
        """Get traffic statistics for a specific client."""
        try:
            # Try to get real stats from Xray
            if hasattr(self.client, 'get_user_stats'):
                # Query user statistics from Xray
                stats_result = self.client.get_user_stats(client.protocol or 'vless', client.email)

                # Stats object has uplink and downlink attributes
                upload = getattr(stats_result, 'uplink', 0)
                download = getattr(stats_result, 'downlink', 0)

                # Update client model with fresh stats
                if upload > 0 or download > 0:
                    client.up = upload
                    client.down = download
                    client.save(update_fields=['up', 'down'])

                return {
                    'upload': upload,
                    'download': download
                }
            else:
                # Fallback to stored values
                logger.debug(f"[{self.name}] Using stored stats for client {client.email}")
                return {
                    'upload': client.up,
                    'download': client.down
                }

        except Exception as e:
            logger.error(f"[{self.name}] Failed to get stats for client {client.email}: {e}")
            # Return stored values as fallback
            return {
                'upload': client.up,
                'download': client.down
            }

    def _build_user_response(self, client) -> Dict[str, Any]:
        """Build user response with connection details."""
        inbound = client.inbound
        connection_string = self._generate_connection_string(client)

        return {
            'user_id': str(client.uuid),
            'email': client.email,
            'protocol': inbound.protocol,
            'connection_string': connection_string,
            'qr_code': f"https://api.qrserver.com/v1/create-qr-code/?data={quote(connection_string)}",
            'enable': client.enable,
            'upload': client.up,
            'download': client.down,
            'total': client.up + client.down,
            'expiry_time': client.expiry_time.isoformat() if client.expiry_time else None,
            'total_gb': client.total_gb
        }

    def _generate_connection_string(self, client) -> str:
        """Generate connection string with proper hostname and parameters."""
        try:
            # Use client_hostname instead of internal server address
            client_hostname = self.client_hostname or self.grpc_address
            inbound = client.inbound

            # Try API library first, but it might use wrong hostname
            from vpn.xray_api.models import VlessUser, VmessUser, TrojanUser

            # Create user object based on protocol
            if inbound.protocol == 'vless':
                user_obj = VlessUser(email=client.email, uuid=str(client.uuid))
                try:
                    # Use protocol library with database parameters
                    from vpn.xray_api.protocols import VlessProtocol
                    protocol_handler = VlessProtocol(inbound.port, inbound.tag, inbound.listen, inbound.network)
                    
                    # Get encryption setting from inbound
                    encryption = getattr(inbound, 'vless_encryption', 'none')
                    
                    ctx_link = protocol_handler.generate_client_link(
                        user_obj, 
                        client_hostname,
                        network=inbound.network,
                        security=inbound.security,
                        encryption=encryption
                    )
                    return ctx_link
                except Exception:
                    return self._generate_fallback_uri(inbound, client, client_hostname, inbound.port)

            elif inbound.protocol == 'vmess':
                user_obj = VmessUser(email=client.email, uuid=str(client.uuid), alter_id=client.alter_id or 0)
                try:
                    # Use protocol library with database parameters
                    from vpn.xray_api.protocols import VmessProtocol
                    protocol_handler = VmessProtocol(inbound.port, inbound.tag, inbound.listen, inbound.network)
                    
                    # Get encryption setting from inbound
                    encryption = getattr(inbound, 'vmess_encryption', 'auto')
                    
                    ctx_link = protocol_handler.generate_client_link(
                        user_obj,
                        client_hostname,
                        network=inbound.network,
                        security=inbound.security,
                        encryption=encryption
                    )
                    return ctx_link
                except Exception:
                    return self._generate_fallback_uri(inbound, client, client_hostname, inbound.port)

            elif inbound.protocol == 'trojan':
                # For Trojan, ensure we have a proper password
                password = getattr(client, 'password', None)
                if not password:
                    # Generate a password based on UUID if none exists
                    password = str(client.uuid).replace('-', '')[:16]  # 16 char password
                    # Save password to client
                    client.password = password
                    client.save(update_fields=['password'])

                user_obj = TrojanUser(email=client.email, password=password)
                try:
                    # Use protocol library with database parameters
                    from vpn.xray_api.protocols import TrojanProtocol
                    protocol_handler = TrojanProtocol(inbound.port, inbound.tag, inbound.listen, inbound.network)
                    
                    ctx_link = protocol_handler.generate_client_link(
                        user_obj,
                        client_hostname,
                        network=inbound.network,
                        security=inbound.security
                    )
                    return ctx_link
                except Exception:
                    return self._generate_fallback_uri(inbound, client, client_hostname, inbound.port)

            # Fallback for unsupported protocols
            return self._generate_fallback_uri(inbound, client, client_hostname, inbound.port)

        except Exception as e:
            logger.warning(f"[{self.name}] Failed to generate client link: {e}")
            # Final fallback
            client_hostname = self.client_hostname or self.grpc_address
            return self._generate_fallback_uri(client.inbound, client, client_hostname, client.inbound.port)

    def _generate_fallback_uri(self, inbound, client, server_address: str, server_port: int) -> str:
        """Generate fallback URI with proper parameters for v2ray clients."""
        from urllib.parse import urlencode

        if inbound.protocol == 'vless':
            # VLESS format: vless://uuid@host:port?encryption=none&type=network#name
            # Use encryption and network from inbound settings
            encryption = getattr(inbound, 'vless_encryption', 'none')
            network = inbound.network or 'tcp'
            security = inbound.security or 'none'
            
            params = {
                'encryption': encryption,
                'type': network
            }
            
            # Add security if enabled
            if security != 'none':
                params['security'] = security
                
            query_string = urlencode(params)
            return f"vless://{client.uuid}@{server_address}:{server_port}?{query_string}#{self.name}"

        elif inbound.protocol == 'vmess':
            # VMess format: vmess://uuid@host:port?encryption=method&type=network#name
            # Use encryption and network from inbound settings
            encryption = getattr(inbound, 'vmess_encryption', 'auto')
            network = inbound.network or 'tcp'
            security = inbound.security or 'none'
            
            params = {
                'encryption': encryption,
                'type': network
            }
            
            # Add security if enabled
            if security != 'none':
                params['security'] = security
                
            query_string = urlencode(params)
            return f"vmess://{client.uuid}@{server_address}:{server_port}?{query_string}#{self.name}"

        elif inbound.protocol == 'trojan':
            # Trojan format: trojan://password@host:port?type=network#name
            password = getattr(client, 'password', None)
            if not password:
                # Generate and save password if not exists
                password = str(client.uuid).replace('-', '')[:16]  # 16 char password
                client.password = password
                client.save(update_fields=['password'])

            network = inbound.network or 'tcp'
            security = inbound.security or 'none'
            
            params = {
                'type': network
            }
            
            # Add security if enabled  
            if security != 'none':
                params['security'] = security
                
            query_string = urlencode(params)
            return f"trojan://{password}@{server_address}:{server_port}?{query_string}#{self.name}"

        else:
            # Generic fallback
            return f"{inbound.protocol}://{client.uuid}@{server_address}:{server_port}#{self.name}"

    def _build_full_config(self) -> Dict[str, Any]:
        """Build full Xray configuration based on production template."""
        config = {
            "log": {
                "access": "/var/log/xray/access.log",
                "error": "/var/log/xray/error.log",
                "loglevel": "info"
            },
            "api": {
                "tag": "api",
                "listen": f"{self.grpc_address}:{self.grpc_port}",
                "services": [
                    "HandlerService",
                    "LoggerService",
                    "StatsService",
                    "ReflectionService"
                ]
            },
            "stats": {},
            "policy": {
                "levels": {
                    "0": {
                        "statsUserUplink": True,
                        "statsUserDownlink": True
                    }
                },
                "system": {
                    "statsInboundUplink": True,
                    "statsInboundDownlink": True,
                    "statsOutboundUplink": True,
                    "statsOutboundDownlink": True
                }
            },
            "dns": {
                "servers": [
                    "https+local://cloudflare-dns.com/dns-query",
                    "1.1.1.1",
                    "8.8.8.8"
                ]
            },
            "inbounds": [
                {
                    "tag": "api",
                    "listen": "127.0.0.1",
                    "port": 8080,  # Different from main API port for internal use
                    "protocol": "dokodemo-door",
                    "settings": {
                        "address": "127.0.0.1"
                    }
                }
            ],
            "outbounds": [
                {
                    "tag": "direct",
                    "protocol": "freedom",
                    "settings": {}
                },
                {
                    "tag": "blocked",
                    "protocol": "blackhole",
                    "settings": {
                        "response": {
                            "type": "http"
                        }
                    }
                }
            ],
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": [
                    {
                        "type": "field",
                        "inboundTag": ["api"],
                        "outboundTag": "api"
                    },
                    {
                        "type": "field",
                        "protocol": ["bittorrent"],
                        "outboundTag": "blocked"
                    }
                ]
            }
        }

        # Add user inbounds
        for inbound in self.inbounds.filter(enabled=True):
            config["inbounds"].append(inbound.to_xray_config())

        return config


class XrayInbound(models.Model):
    """Xray inbound configuration."""

    PROTOCOL_CHOICES = [
        ('vless', 'VLESS'),
        ('vmess', 'VMess'),
        ('trojan', 'Trojan'),
        ('shadowsocks', 'Shadowsocks'),
    ]

    NETWORK_CHOICES = [
        ('tcp', 'TCP'),
        ('ws', 'WebSocket'),
        ('http', 'HTTP/2'),
        ('grpc', 'gRPC'),
        ('quic', 'QUIC'),
    ]

    SECURITY_CHOICES = [
        ('none', 'None'),
        ('tls', 'TLS'),
        ('reality', 'REALITY'),
    ]

    # Default configurations for different protocols
    PROTOCOL_DEFAULTS = {
        'vless': {
            'port': 443,
            'network': 'tcp',
            'security': 'tls',
            'sniffing_settings': {
                'enabled': True,
                'destOverride': ['http', 'tls'],
                'metadataOnly': False
            }
        },
        'vmess': {
            'port': 443,
            'network': 'ws',
            'security': 'tls',
            'stream_settings': {
                'wsSettings': {
                    'path': '/ws',
                    'headers': {
                        'Host': 'www.cloudflare.com'
                    }
                }
            },
            'sniffing_settings': {
                'enabled': True,
                'destOverride': ['http', 'tls'],
                'metadataOnly': False
            }
        },
        'trojan': {
            'port': 443,
            'network': 'tcp',
            'security': 'tls',
            'sniffing_settings': {
                'enabled': True,
                'destOverride': ['http', 'tls'],
                'metadataOnly': False
            }
        },
        'shadowsocks': {
            'port': 8388,
            'network': 'tcp',
            'security': 'none',
            'ss_method': 'chacha20-ietf-poly1305',
            'sniffing_settings': {
                'enabled': True,
                'destOverride': ['http', 'tls'],
                'metadataOnly': False
            }
        }
    }

    server = models.ForeignKey(XrayCoreServer, on_delete=models.CASCADE, related_name='inbounds')
    tag = models.CharField(max_length=100, help_text="Unique identifier for this inbound")
    port = models.IntegerField(help_text="Port to listen on")
    listen = models.CharField(max_length=255, default="0.0.0.0", help_text="IP address to listen on")
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES)
    enabled = models.BooleanField(default=True)

    # Network settings
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES, default='tcp')
    security = models.CharField(max_length=20, choices=SECURITY_CHOICES, default='none')

    # Server address for clients (if different from listen)
    server_address = models.CharField(
        max_length=255,
        blank=True,
        help_text="Public server address for client connections"
    )

    # Protocol-specific settings
    # Shadowsocks
    ss_method = models.CharField(
        max_length=50,
        blank=True,
        default='chacha20-ietf-poly1305',
        help_text="Shadowsocks encryption method"
    )
    ss_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="Shadowsocks password (for single-user mode)"
    )

    # TLS settings
    tls_cert_file = models.CharField(max_length=255, blank=True)
    tls_key_file = models.CharField(max_length=255, blank=True)
    tls_alpn = ArrayField(models.CharField(max_length=20), default=list, blank=True)

    # Advanced settings (JSON)
    stream_settings = models.JSONField(default=dict, blank=True)
    sniffing_settings = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [('server', 'tag'), ('server', 'port')]
        ordering = ['port']

    def __str__(self):
        return f"{self.tag} ({self.protocol.upper()}:{self.port})"

    def save(self, *args, **kwargs):
        """Apply protocol defaults on creation."""
        if not self.pk and self.protocol in self.PROTOCOL_DEFAULTS:
            defaults = self.PROTOCOL_DEFAULTS[self.protocol]

            # Apply defaults only if fields are not set
            if not self.port:
                self.port = defaults.get('port', 443)
            if not self.network:
                self.network = defaults.get('network', 'tcp')
            if not self.security:
                self.security = defaults.get('security', 'none')
            if not self.ss_method and 'ss_method' in defaults:
                self.ss_method = defaults['ss_method']
            if not self.stream_settings and 'stream_settings' in defaults:
                self.stream_settings = defaults['stream_settings']
            if not self.sniffing_settings and 'sniffing_settings' in defaults:
                self.sniffing_settings = defaults['sniffing_settings']

        super().save(*args, **kwargs)

    def to_xray_config(self) -> Dict[str, Any]:
        """Convert to Xray inbound configuration."""
        config = {
            "tag": self.tag,
            "port": self.port,
            "listen": self.listen,
            "protocol": self.protocol,
            "settings": self._build_protocol_settings(),
            "streamSettings": self._build_stream_settings()
        }

        if self.sniffing_settings:
            config["sniffing"] = self.sniffing_settings

        return config

    def _build_protocol_settings(self) -> Dict[str, Any]:
        """Build protocol-specific settings."""
        settings = {}

        if self.protocol == 'vless':
            settings = {
                "decryption": "none",
                "clients": []
            }
        elif self.protocol == 'vmess':
            settings = {
                "clients": []
            }
        elif self.protocol == 'trojan':
            settings = {
                "clients": []
            }
        elif self.protocol == 'shadowsocks':
            settings = {
                "method": self.ss_method,
                "password": self.ss_password,
                "clients": []
            }

        # Add clients
        for client in self.clients.filter(enable=True):
            settings["clients"].append(client.to_xray_config())

        return settings

    def _build_stream_settings(self) -> Dict[str, Any]:
        """Build stream settings."""
        settings = {
            "network": self.network,
            "security": self.security
        }

        # Add custom stream settings
        if self.stream_settings:
            settings.update(self.stream_settings)

        # Add TLS settings if needed
        if self.security == 'tls' and (self.tls_cert_file or self.tls_key_file):
            settings["tlsSettings"] = {
                "certificates": [{
                    "certificateFile": self.tls_cert_file,
                    "keyFile": self.tls_key_file
                }]
            }
            if self.tls_alpn:
                settings["tlsSettings"]["alpn"] = self.tls_alpn

        return settings

    def sync_to_server(self) -> bool:
        """Sync this inbound to the Xray server using API library."""
        try:
            logger.info(f"Syncing inbound {self.tag} to server")

            # 1. First remove existing inbound if it exists
            try:
                self.server.client.remove_inbound(self.tag)
                logger.info(f"Removed existing inbound {self.tag}")
            except Exception:
                logger.debug(f"Inbound {self.tag} doesn't exist yet, proceeding with creation")

            # 2. Get all enabled users for this inbound
            users = []
            for client in self.clients.filter(enable=True):
                users.append(self._client_to_user_obj(client))

            logger.info(f"Preparing to add {len(users)} users to inbound {self.tag}")

            # 3. Add inbound with users using protocol-specific method
            if self.protocol == 'vless':
                result = self.server.client.add_vless_inbound(
                    port=self.port,
                    users=users,
                    tag=self.tag,
                    listen=self.listen or "0.0.0.0",
                    network=self.network or "tcp"
                )
            elif self.protocol == 'vmess':
                result = self.server.client.add_vmess_inbound(
                    port=self.port,
                    users=users,
                    tag=self.tag,
                    listen=self.listen or "0.0.0.0",
                    network=self.network or "tcp"
                )
            elif self.protocol == 'trojan':
                result = self.server.client.add_trojan_inbound(
                    port=self.port,
                    users=users,
                    tag=self.tag,
                    listen=self.listen or "0.0.0.0",
                    network=self.network or "tcp"
                )
            else:
                raise ValueError(f"Unsupported protocol: {self.protocol}")

            logger.info(f"Inbound {self.tag} created successfully with {len(users)} users. Result: {result}")
            return True

        except Exception as e:
            logger.error(f"Failed to sync inbound {self.tag}: {e}")
            return False

    def remove_from_server(self) -> bool:
        """Remove this inbound from the Xray server."""
        try:
            logger.info(f"Removing inbound {self.tag} from server")
            self.server.client.remove_inbound(self.tag)
            logger.info(f"Inbound {self.tag} removed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to remove inbound {self.tag}: {e}")
            return False

    def _client_to_user_obj(self, client):
        """Convert XrayClient to API library user object."""
        from vpn.xray_api.models import VlessUser, VmessUser, TrojanUser

        if self.protocol == 'vless':
            return VlessUser(email=client.email, uuid=str(client.uuid))
        elif self.protocol == 'vmess':
            return VmessUser(email=client.email, uuid=str(client.uuid), alter_id=client.alter_id or 0)
        elif self.protocol == 'trojan':
            password = getattr(client, 'password', str(client.uuid))
            return TrojanUser(email=client.email, password=password)
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}")

    def add_user(self, user):
        """Add user to this inbound."""
        try:
            # Create XrayClient for this user in this inbound
            client = XrayClient.objects.create(
                inbound=self,
                user=user,
                email=user.username,
                enable=True
            )

            # Add user to actual Xray server
            user_obj = self._client_to_user_obj(client)
            self.server.client.add_user(self.tag, user_obj)

            logger.info(f"Added user {user.username} to inbound {self.tag}")
            return client

        except Exception as e:
            logger.error(f"Failed to add user {user.username} to inbound {self.tag}: {e}")
            raise

    def remove_user(self, user) -> bool:
        """Remove user from this inbound."""
        try:
            # Find and remove XrayClient
            client = self.clients.filter(user=user).first()
            if client:
                # Remove from Xray server
                self.server.client.remove_user(self.tag, client.email)

                # Remove from database
                client.delete()
                logger.info(f"Removed user {user.username} from inbound {self.tag}")
                return True
            else:
                logger.warning(f"User {user.username} not found in inbound {self.tag}")
                return False

        except Exception as e:
            logger.error(f"Failed to remove user {user.username} from inbound {self.tag}: {e}")
            raise


class XrayInboundServer(Server):
    """Server model that represents a single Xray inbound as a server."""

    # Reference to the actual XrayInbound
    xray_inbound = models.OneToOneField(
        XrayInbound,
        on_delete=models.CASCADE,
        related_name='server_proxy',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Xray Inbound Server"
        verbose_name_plural = "Xray Inbound Servers"

    def save(self, *args, **kwargs):
        if self.xray_inbound:
            self.server_type = f'xray_{self.xray_inbound.protocol}'
            if not self.name:
                self.name = f"{self.xray_inbound.server.name}-{self.xray_inbound.tag}"
            if not self.comment:
                self.comment = f"{self.xray_inbound.protocol.upper()} inbound on port {self.xray_inbound.port}"
        super().save(*args, **kwargs)

    def __str__(self):
        if self.xray_inbound:
            return f"{self.xray_inbound.server.name}-{self.xray_inbound.tag}"
        return self.name or "Xray Inbound"

    def get_server_status(self, raw: bool = False) -> Dict[str, Any]:
        """Get status from parent Xray server."""
        if self.xray_inbound:
            return self.xray_inbound.server.get_server_status(raw=raw)
        return {"error": "No inbound configured"}

    def add_user(self, user):
        """Add user to this specific inbound via parent server."""
        if not self.xray_inbound:
            raise XrayConnectionError("No inbound configured")

        logger.info(f"[{self.name}] Adding user {user.username} to inbound {self.xray_inbound.tag}")

        try:
            # Delegate to parent server but specify the inbound
            parent_server = self.xray_inbound.server
            return parent_server._apply_client_to_xray(user, target_inbound=self.xray_inbound)

        except Exception as e:
            logger.error(f"[{self.name}] Failed to add user {user.username}: {e}")
            raise XrayConnectionError(f"Failed to add user: {e}")

    def remove_user(self, user):
        """Remove user from this specific inbound."""
        if not self.xray_inbound:
            raise XrayConnectionError("No inbound configured")

        logger.info(f"[{self.name}] Removing user {user.username} from inbound {self.xray_inbound.tag}")

        try:
            # Find client for this user and inbound
            client = self.xray_inbound.clients.filter(user=user).first()

            if not client:
                return {"status": "User not found on this inbound"}

            # Use parent server to remove user from Xray via API
            parent_server = self.xray_inbound.server

            try:
                parent_server.client.remove_user(self.xray_inbound.tag, client.email)
                logger.info(f"[{self.name}] User {user.username} removed from Xray")
            except Exception as api_error:
                logger.warning(f"[{self.name}] API removal failed: {api_error}")

            # Remove from database
            client.delete()

            logger.info(f"[{self.name}] User {user.username} removed successfully")
            return {"status": "User was removed"}

        except Exception as e:
            logger.error(f"[{self.name}] Failed to remove user {user.username}: {e}")
            raise XrayConnectionError(f"Failed to remove user: {e}")

    def get_user(self, user, raw: bool = False):
        """Get user information from this inbound."""
        if not self.xray_inbound:
            raise XrayConnectionError("No inbound configured")

        try:
            client = self.xray_inbound.clients.filter(user=user).first()

            if not client:
                # Auto-create user in this inbound
                logger.warning(f"[{self.name}] User {user.username} not found, attempting to create")
                return self.add_user(user)

            return self.xray_inbound.server._build_user_response(client)

        except Exception as e:
            logger.error(f"[{self.name}] Failed to get user {user.username}: {e}")
            raise XrayConnectionError(f"Failed to get user: {e}")

    def sync_users(self) -> bool:
        """Sync users for this inbound only."""
        if not self.xray_inbound:
            logger.error(f"[{self.name}] No inbound configured")
            return False

        from vpn.models import User, ACL
        logger.debug(f"[{self.name}] Sync users for this inbound")

        try:
            # Get ACLs for this inbound server (not the parent Xray server)
            acls = ACL.objects.filter(server=self)
            acl_users = set(acl.user for acl in acls)

            # Get existing clients for this inbound only
            existing_clients = {client.user.id: client for client in self.xray_inbound.clients.all()}

            added = 0
            removed = 0

            # Add missing users to this inbound
            for user in acl_users:
                if user.id not in existing_clients:
                    try:
                        self.add_user(user=user)
                        added += 1
                        logger.debug(f"[{self.name}] Added user {user.username}")
                    except Exception as e:
                        logger.error(f"[{self.name}] Failed to add user {user.username}: {e}")

            # Remove users without ACL from this inbound
            for user_id, client in existing_clients.items():
                if client.user not in acl_users:
                    try:
                        self.delete_user(user=client.user)
                        removed += 1
                        logger.debug(f"[{self.name}] Removed user {client.user.username}")
                    except Exception as e:
                        logger.error(f"[{self.name}] Failed to remove user {client.user.username}: {e}")

            logger.info(f"[{self.name}] Sync completed: {added} added, {removed} removed")
            return True

        except Exception as e:
            logger.error(f"[{self.name}] User sync failed: {e}")
            return False


class XrayClient(models.Model):
    """Xray client (user) configuration."""

    inbound = models.ForeignKey(XrayInbound, on_delete=models.CASCADE, related_name='clients')
    user = models.ForeignKey('vpn.User', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    email = models.CharField(max_length=255, help_text="Email for statistics")
    level = models.IntegerField(default=0)
    enable = models.BooleanField(default=True)

    # Protocol-specific fields
    flow = models.CharField(max_length=50, blank=True, help_text="VLESS flow control")
    alter_id = models.IntegerField(default=0, help_text="VMess alterId")
    password = models.CharField(max_length=255, blank=True, help_text="Password for Trojan/Shadowsocks")

    # Limits
    total_gb = models.IntegerField(null=True, blank=True, help_text="Traffic limit in GB")
    expiry_time = models.DateTimeField(null=True, blank=True, help_text="Account expiration time")

    # Statistics
    up = models.BigIntegerField(default=0, help_text="Upload bytes")
    down = models.BigIntegerField(default=0, help_text="Download bytes")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('inbound', 'user')]
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} @ {self.inbound.tag}"

    def to_xray_config(self) -> Dict[str, Any]:
        """Convert to Xray client configuration."""
        config = {
            "id": str(self.uuid),
            "email": self.email,
            "level": self.level
        }

        # Add protocol-specific fields
        if self.inbound.protocol == 'vless' and self.flow:
            config["flow"] = self.flow
        elif self.inbound.protocol == 'vmess':
            config["alterId"] = self.alter_id
        elif self.inbound.protocol in ['trojan', 'shadowsocks'] and self.password:
            config["password"] = self.password

        return config


# Admin classes
class XrayInboundInline(admin.TabularInline):
    model = XrayInbound
    extra = 0
    fields = ('tag', 'port', 'protocol', 'network', 'security', 'enabled', 'client_count')
    readonly_fields = ('client_count',)

    def client_count(self, obj):
        if obj.pk:
            return obj.clients.count()
        return 0
    client_count.short_description = 'Clients'


class XrayClientInline(admin.TabularInline):
    model = XrayClient
    extra = 0
    fields = ('user', 'email', 'enable', 'traffic_display', 'created_at')
    readonly_fields = ('traffic_display', 'created_at')
    raw_id_fields = ('user',)

    def traffic_display(self, obj):
        if obj.pk:
            up_gb = obj.up / (1024**3)
            down_gb = obj.down / (1024**3)
            return f"↑ {up_gb:.2f} GB ↓ {down_gb:.2f} GB"
        return "-"
    traffic_display.short_description = 'Traffic'


@admin.register(XrayCoreServer)
class XrayCoreServerAdmin(PolymorphicChildModelAdmin):
    base_model = XrayCoreServer
    show_in_index = False

    list_display = (
        'name',
        'grpc_address',
        'grpc_port',
        'client_hostname',
        'inbound_count',
        'user_count',
        'server_status_inline',
        'registration_date'
    )

    list_editable = ('grpc_address', 'grpc_port', 'client_hostname')
    exclude = ('server_type',)

    def get_fieldsets(self, request, obj=None):
        """Customize fieldsets based on whether object exists."""
        if obj is None:  # Adding new server
            return (
                ('Basic Configuration', {
                    'fields': ('name', 'comment')
                }),
                ('gRPC API Configuration', {
                    'fields': ('grpc_address', 'grpc_port', 'client_hostname'),
                    'description': 'Configure connection to Xray Core gRPC API and client connection hostname'
                }),
                ('Settings', {
                    'fields': ('enable_stats',)
                }),
            )
        else:  # Editing existing server
            return (
                ('Server Configuration', {
                    'fields': ('name', 'comment', 'registration_date')
                }),
                ('gRPC API Configuration', {
                    'fields': ('grpc_address', 'grpc_port', 'client_hostname')
                }),
                ('Settings', {
                    'fields': ('enable_stats',)
                }),
                ('Server Status', {
                    'fields': ('server_status_full',)
                }),
                ('Configuration Management', {
                    'fields': ('export_configuration_display', 'create_inbound_button')
                }),
                ('Statistics & Users', {
                    'fields': ('server_statistics_display',),
                    'classes': ('collapse',)
                }),
            )

    inlines = [XrayInboundInline]
    readonly_fields = ('server_status_full', 'registration_date', 'export_configuration_display', 'server_statistics_display', 'create_inbound_button')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            user_count=Count('inbounds__clients__user', distinct=True)
        )
        return qs

    @admin.display(description='Inbounds', ordering='inbound_count')
    def inbound_count(self, obj):
        return obj.inbounds.count()

    @admin.display(description='Users', ordering='user_count')
    def user_count(self, obj):
        return obj.user_count

    @admin.display(description='Status')
    def server_status_inline(self, obj):
        try:
            status = obj.get_server_status()
            if status.get('online'):
                return mark_safe('<span style="color: green;">✅ Online</span>')
            else:
                return mark_safe(f'<span style="color: red;">❌ {status.get("error", "Offline")}</span>')
        except Exception as e:
            return mark_safe(f'<span style="color: red;">❌ Error: {str(e)}</span>')

    @admin.display(description='Server Status')
    def server_status_full(self, obj):
        if obj and obj.pk:
            try:
                status = obj.get_server_status()
                if 'error' in status:
                    return mark_safe(f'<span style="color: red;">Error: {status["error"]}</span>')

                html = '<div style="font-family: monospace; background: #f8f9fa; padding: 10px; border-radius: 4px;">'
                html += f'<div><strong>Status:</strong> {"🟢 Online" if status.get("online") else "🔴 Offline"}</div>'
                html += f'<div><strong>Inbounds:</strong> {status.get("inbounds_count", 0)}</div>'
                html += f'<div><strong>Total Users:</strong> {status.get("total_users", 0)}</div>'

                if 'total_traffic' in status:
                    up_gb = status['total_traffic']['uplink'] / (1024**3)
                    down_gb = status['total_traffic']['downlink'] / (1024**3)
                    html += f'<div><strong>Total Traffic:</strong> ↑ {up_gb:.2f} GB ↓ {down_gb:.2f} GB</div>'

                html += '</div>'
                return mark_safe(html)

            except Exception as e:
                return mark_safe(f'<span style="color: red;">Error: {str(e)}</span>')
        return "N/A"

    @admin.display(description='Export Configuration')
    def export_configuration_display(self, obj):
        """Display export configuration and actions."""
        if not obj or not obj.pk:
            return mark_safe('<div style="color: #6c757d; font-style: italic;">Export will be available after saving</div>')

        try:
            # Build export data
            export_data = {
                'name': obj.name,
                'type': 'xray_core',
                'grpc': {
                    'address': obj.grpc_address,
                    'port': obj.grpc_port
                },
                'inbounds': []
            }

            # Add inbound configurations
            for inbound in obj.inbounds.all():
                inbound_data = {
                    'tag': inbound.tag,
                    'port': inbound.port,
                    'protocol': inbound.protocol,
                    'network': inbound.network,
                    'security': inbound.security,
                    'clients': inbound.clients.count()
                }
                export_data['inbounds'].append(inbound_data)

            json_str = json.dumps(export_data, indent=2)
            from django.utils.html import escape
            escaped_json = escape(json_str)

            html = f'''
            <div>
                <textarea id="export-json-config" class="vLargeTextField" rows="10" readonly 
                          style="font-family: 'Courier New', monospace; font-size: 0.875rem; background-color: #f8f9fa; width: 100%;">{escaped_json}</textarea>
                <div style="margin-top: 1rem;">
                    <button type="button" class="btn btn-sm btn-secondary" 
                            onclick="var btn=this; document.getElementById('export-json-config').select(); document.execCommand('copy'); btn.innerHTML='✅ Copied!'; setTimeout(function(){{btn.innerHTML='📋 Copy Configuration';}}, 2000);">
                        📋 Copy Configuration
                    </button>
                    <button type="button" class="btn btn-sm btn-primary" style="margin-left: 10px;"
                            onclick="if(confirm('This will sync all inbounds and clients with Xray Core. Continue?')) {{ window.location.href='/admin/vpn/xraycoreserver/{obj.id}/sync/'; }}">
                        🔄 Sync with Xray
                    </button>
                </div>
            </div>
            '''

            return mark_safe(html)

        except Exception as e:
            return mark_safe(f'<div style="color: #dc3545;">Error generating export: {e}</div>')

    @admin.display(description='Server Statistics & Users')
    def server_statistics_display(self, obj):
        """Display server statistics and user management."""
        if not obj or not obj.pk:
            return mark_safe('<div style="color: #6c757d; font-style: italic;">Statistics will be available after saving</div>')

        try:
            from vpn.models import ACL, UserStatistics
            from django.utils import timezone
            from django.utils.timezone import localtime
            from datetime import timedelta

            # Get statistics
            user_count = ACL.objects.filter(server=obj).count()
            client_count = XrayClient.objects.filter(inbound__server=obj).count()

            html = '<div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 0.375rem; padding: 1rem;">'

            # Overall Statistics
            html += '<div style="background: #e7f3ff; border-left: 4px solid #007cba; padding: 12px; margin-bottom: 16px; border-radius: 4px;">'
            html += '<div style="display: flex; gap: 20px; margin-bottom: 8px; flex-wrap: wrap;">'
            html += f'<div><strong>ACL Users:</strong> {user_count}</div>'
            html += f'<div><strong>Configured Clients:</strong> {client_count}</div>'
            html += f'<div><strong>Inbounds:</strong> {obj.inbounds.count()}</div>'
            html += '</div>'
            html += '</div>'

            # Users with access
            acls = ACL.objects.filter(server=obj).select_related('user')

            if acls:
                html += '<h5 style="color: #495057; margin: 16px 0 8px 0;">👥 Users with Access</h5>'

                for acl in acls:
                    user = acl.user

                    # Get client info
                    clients = XrayClient.objects.filter(inbound__server=obj, user=user)

                    html += '<div style="background: #ffffff; border: 1px solid #e9ecef; border-radius: 0.25rem; padding: 0.75rem; margin-bottom: 0.5rem;">'
                    html += f'<div style="font-weight: 500; font-size: 14px; color: #495057;">{user.username}'
                    if user.comment:
                        html += f' <span style="color: #6c757d; font-size: 12px; font-weight: normal;">- {user.comment}</span>'
                    html += '</div>'

                    if clients.exists():
                        for client in clients:
                            up_gb = client.up / (1024**3)
                            down_gb = client.down / (1024**3)
                            status = '🟢' if client.enable else '🔴'
                            html += f'<div style="font-size: 12px; color: #6c757d; margin-left: 20px;">'
                            html += f'{status} {client.inbound.tag} ({client.inbound.protocol}) - ↑ {up_gb:.2f} GB ↓ {down_gb:.2f} GB'
                            html += '</div>'
                    else:
                        html += '<div style="font-size: 12px; color: #dc3545; margin-left: 20px;">⚠️ No client configured</div>'

                    html += '</div>'
            else:
                html += '<div style="color: #6c757d; font-style: italic; text-align: center; padding: 20px;">No users assigned to this server</div>'

            html += '</div>'
            return mark_safe(html)

        except Exception as e:
            return mark_safe(f'<div style="color: #dc3545;">Error loading statistics: {e}</div>')

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/sync/', self.admin_site.admin_view(self.sync_server_view), name='xraycoreserver_sync'),
        ]
        return custom_urls + urls

    def sync_server_view(self, request, object_id):
        """View to sync server configuration."""
        from django.http import JsonResponse
        from django.shortcuts import redirect
        from django.contrib import messages

        try:
            server = XrayCoreServer.objects.get(pk=object_id)
            result = server.sync()

            if request.headers.get('Accept') == 'application/json':
                # AJAX request
                return JsonResponse({
                    'success': True,
                    'message': f'Server "{server.name}" synchronized successfully',
                    'details': result
                })
            else:
                # Regular HTTP request - redirect back with message
                messages.success(request, f'Server "{server.name}" synchronized successfully!')
                return redirect(f'/admin/vpn/xraycoreserver/{object_id}/change/')

        except Exception as e:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
            else:
                messages.error(request, f'Sync failed: {str(e)}')
                return redirect(f'/admin/vpn/xraycoreserver/{object_id}/change/')

    @admin.display(description='Create Inbound')
    def create_inbound_button(self, obj):
        if obj and obj.pk:
            create_url = reverse('admin:create_xray_inbound', args=[obj.pk])
            return mark_safe(f'''
                <a href="{create_url}" class="btn btn-primary btn-sm">
                    ➕ Create Inbound
                </a>
            ''')
        return "-"

    def get_urls(self):
        """Add custom URLs for inbound management."""
        urls = super().get_urls()
        custom_urls = [
            path('<int:server_id>/create-inbound/',
                 self.admin_site.admin_view(self.create_inbound_view),
                 name='create_xray_inbound'),
        ]
        return custom_urls + urls

    def create_inbound_view(self, request, server_id):
        """View for creating new inbounds."""
        try:
            server = XrayCoreServer.objects.get(pk=server_id)

            if request.method == 'POST':
                protocol = request.POST.get('protocol')
                port = int(request.POST.get('port'))
                tag = request.POST.get('tag')
                network = request.POST.get('network', 'tcp')
                security = request.POST.get('security', 'none')

                # Create inbound using server method
                inbound = server.create_inbound(
                    protocol=protocol,
                    port=port,
                    tag=tag,
                    network=network,
                    security=security
                )

                messages.success(request, f'Inbound "{inbound.tag}" created successfully!')
                return redirect(f'/admin/vpn/xrayinbound/{inbound.pk}/change/')

            # GET request - show form
            context = {
                'title': f'Create Inbound for {server.name}',
                'server': server,
                'protocols': ['vless', 'vmess', 'trojan'],
                'networks': ['tcp', 'ws', 'grpc', 'h2'],
                'securities': ['none', 'tls', 'reality'],
            }

            return render(request, 'admin/create_xray_inbound.html', context)

        except XrayCoreServer.DoesNotExist:
            messages.error(request, 'Server not found')
            return redirect('/admin/vpn/xraycoreserver/')
        except Exception as e:
            messages.error(request, f'Failed to create inbound: {e}')
            return redirect(f'/admin/vpn/xraycoreserver/{server_id}/change/')

    def save_model(self, request, obj, form, change):
        """Override save to set server_type."""
        obj.server_type = 'xray_core'
        super().save_model(request, obj, form, change)

    def get_model_perms(self, request):
        """It disables display for sub-model."""
        return {}

    class Media:
        js = ('admin/js/xray_inbound_defaults.js',)
        css = {'all': ('admin/css/vpn_admin.css',)}


@admin.register(XrayInboundServer)
class XrayInboundServerAdmin(PolymorphicChildModelAdmin):
    """Admin for XrayInboundServer to display inbounds as servers."""
    base_model = XrayInboundServer
    show_in_index = True  # Show in main server list

    list_display = ('name', 'server_type', 'comment', 'client_count', 'registration_date')
    list_filter = ('server_type', 'xray_inbound__protocol', 'xray_inbound__network')
    search_fields = ('name', 'comment', 'xray_inbound__tag')
    readonly_fields = ('server_type', 'registration_date', 'client_count')

    fieldsets = (
        ('Server Information', {
            'fields': ('name', 'server_type', 'comment', 'registration_date')
        }),
        ('Inbound Configuration', {
            'fields': ('xray_inbound',),
            'description': 'The actual Xray inbound this server represents'
        }),
    )

    def client_count(self, obj):
        if obj.xray_inbound:
            return obj.xray_inbound.clients.count()
        return 0
    client_count.short_description = 'Clients'

    def has_add_permission(self, request):
        # Prevent manual creation - these should be auto-created
        return False

    def has_delete_permission(self, request, obj=None):
        # Allow deleting individual inbound servers
        return True

    def save_model(self, request, obj, form, change):
        """Set server_type on save."""
        if obj.xray_inbound:
            obj.server_type = f'xray_{obj.xray_inbound.protocol}'
        super().save_model(request, obj, form, change)

    def get_urls(self):
        """Add sync URL for XrayInboundServer."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/sync/', self.admin_site.admin_view(self.sync_server_view), name='xrayinboundserver_sync'),
        ]
        return custom_urls + urls

    def sync_server_view(self, request, object_id):
        """Sync this inbound server by delegating to parent server."""
        try:
            inbound_server = XrayInboundServer.objects.get(pk=object_id)
            if not inbound_server.xray_inbound:
                messages.error(request, "No inbound configuration found")
                return redirect('admin:vpn_server_changelist')

            # Delegate to parent server's sync
            parent_server = inbound_server.xray_inbound.server
            parent_admin = XrayCoreServerAdmin(XrayCoreServer, self.admin_site)

            # Call parent server's sync method
            return parent_admin.sync_server_view(request, parent_server.pk)

        except XrayInboundServer.DoesNotExist:
            messages.error(request, f"Xray Inbound Server with ID {object_id} not found")
            return redirect('admin:vpn_server_changelist')
        except Exception as e:
            messages.error(request, f"Error during sync: {e}")
            return redirect('admin:vpn_server_changelist')

    def get_model_perms(self, request):
        """Show this model in admin."""
        return {
            'add': self.has_add_permission(request),
            'change': self.has_change_permission(request),
            'delete': self.has_delete_permission(request),
            'view': self.has_view_permission(request),
        }


@admin.register(XrayInbound)
class XrayInboundAdmin(admin.ModelAdmin):
    list_display = ('tag', 'server', 'port', 'protocol', 'network', 'security', 'enabled', 'client_count')
    list_filter = ('server', 'protocol', 'network', 'security', 'enabled')
    search_fields = ('tag', 'server__name')
    list_editable = ('enabled',)

    inlines = [XrayClientInline]

    def get_fieldsets(self, request, obj=None):
        """Customize fieldsets based on whether object exists."""
        if obj is None:  # Adding new inbound
            return (
                ('Basic Information', {
                    'fields': ('server', 'tag', 'protocol', 'port', 'listen', 'server_address', 'enabled')
                }),
                ('Transport & Security', {
                    'fields': ('network', 'security')
                }),
                ('Protocol-Specific Settings', {
                    'fields': ('ss_method', 'ss_password'),
                    'classes': ('collapse',),
                    'description': 'Settings specific to certain protocols'
                }),
                ('TLS Configuration', {
                    'fields': ('tls_cert_file', 'tls_key_file', 'tls_alpn'),
                    'classes': ('collapse',),
                }),
                ('Advanced Settings', {
                    'fields': ('stream_settings', 'sniffing_settings'),
                    'classes': ('collapse',),
                }),
            )
        else:  # Editing existing inbound
            return (
                ('Basic Information', {
                    'fields': ('server', 'tag', 'protocol', 'port', 'listen', 'server_address', 'enabled')
                }),
                ('Transport & Security', {
                    'fields': ('network', 'security')
                }),
                ('Protocol-Specific Settings', {
                    'fields': ('ss_method', 'ss_password'),
                    'classes': ('collapse',),
                    'description': 'Settings specific to certain protocols'
                }),
                ('TLS Configuration', {
                    'fields': ('tls_cert_file', 'tls_key_file', 'tls_alpn'),
                    'classes': ('collapse',),
                }),
                ('Advanced Settings', {
                    'fields': ('stream_settings', 'sniffing_settings'),
                    'classes': ('collapse',),
                }),
            )

    def get_readonly_fields(self, request, obj=None):
        """Set readonly fields based on context."""
        if obj is None:  # Adding new inbound
            return ()
        else:  # Editing existing inbound
            return ()

    def client_count(self, obj):
        return obj.clients.count()
    client_count.short_description = 'Clients'

    class Media:
        js = ('admin/js/xray_inbound_defaults.js',)
        css = {'all': ('admin/css/vpn_admin.css',)}


@admin.register(XrayClient)
class XrayClientAdmin(admin.ModelAdmin):
    list_display = ('user', 'inbound', 'email', 'enable', 'traffic_display', 'created_at')
    list_filter = ('inbound__server', 'inbound', 'enable', 'created_at')
    search_fields = ('user__username', 'email', 'uuid')
    list_editable = ('enable',)
    raw_id_fields = ('user',)

    fieldsets = (
        ('Basic Information', {
            'fields': ('inbound', 'user', 'email', 'enable')
        }),
        ('Authentication', {
            'fields': ('uuid', 'level')
        }),
        ('Protocol-Specific', {
            'fields': ('flow', 'alter_id', 'password'),
            'classes': ('collapse',),
        }),
        ('Limits', {
            'fields': ('total_gb', 'expiry_time'),
            'classes': ('collapse',),
        }),
        ('Statistics', {
            'fields': ('up', 'down', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('uuid', 'created_at', 'updated_at')

    def traffic_display(self, obj):
        up_gb = obj.up / (1024**3)
        down_gb = obj.down / (1024**3)
        return f"↑ {up_gb:.2f} GB ↓ {down_gb:.2f} GB"
    traffic_display.short_description = 'Traffic'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'inbound', 'inbound__server')


# Automatic sync triggers
@receiver(post_save, sender=XrayInbound)
def trigger_sync_on_inbound_change(sender, instance, created, **kwargs):
    """Trigger sync when inbound is created or modified."""
    if created or instance.enabled:
        from vpn.tasks import sync_server
        logger.info(f"Triggering sync for server {instance.server.name} due to inbound {instance.tag} change")
        sync_server.delay(instance.server.id)


@receiver(post_save, sender=XrayClient)
def trigger_sync_on_client_change(sender, instance, created, **kwargs):
    """Trigger sync when client is created or modified."""
    from vpn.tasks import sync_server
    server = instance.inbound.server
    logger.info(f"Triggering sync for server {server.name} due to client {instance.email} change")
    sync_server.delay(server.id)


@receiver(post_delete, sender=XrayClient)
def trigger_sync_on_client_delete(sender, instance, **kwargs):
    """Trigger sync when client is deleted."""
    from vpn.tasks import sync_server
    server = instance.inbound.server
    logger.info(f"Triggering sync for server {server.name} due to client {instance.email} deletion")
    sync_server.delay(server.id)


@receiver(post_save, sender='vpn.ACL')
def trigger_sync_on_acl_change(sender, instance, created, **kwargs):
    """Trigger sync when ACL is created or modified to ensure users are added to inbounds."""
    server = instance.server.get_real_instance()
    if isinstance(server, XrayCoreServer):
        from vpn.tasks import sync_server
        logger.info(f"Triggering sync for server {server.name} due to ACL change for user {instance.user.username}")
        sync_server.delay(server.id)


@receiver(post_delete, sender='vpn.ACL')
def trigger_sync_on_acl_delete(sender, instance, **kwargs):
    """Trigger sync when ACL is deleted to ensure users are removed from inbounds."""
    server = instance.server.get_real_instance()
    if isinstance(server, XrayCoreServer):
        from vpn.tasks import sync_server
        logger.info(f"Triggering sync for server {server.name} due to ACL deletion for user {instance.user.username}")
        sync_server.delay(server.id)