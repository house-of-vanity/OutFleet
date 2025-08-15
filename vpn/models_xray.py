"""
New Xray models for flexible inbound and subscription management.
"""

import json
import uuid
from datetime import datetime, timedelta
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class Credentials(models.Model):
    """Universal credentials storage for various services"""
    CRED_TYPES = [
        ('cloudflare', 'Cloudflare API'),
        ('dns_provider', 'DNS Provider'),
        ('email', 'Email SMTP'),
        ('other', 'Other')
    ]
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Descriptive name for these credentials"
    )
    cred_type = models.CharField(
        max_length=20,
        choices=CRED_TYPES,
        help_text="Type of credentials"
    )
    credentials = models.JSONField(
        help_text="Credentials data (e.g., {'api_token': '...', 'email': '...'})"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what these credentials are used for"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Credentials"
        verbose_name_plural = "Credentials"
        ordering = ['cred_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_cred_type_display()})"
    
    def get_credential(self, key: str, default=None):
        """Safely get credential value"""
        return self.credentials.get(key, default)


class Certificate(models.Model):
    """SSL/TLS Certificate management"""
    CERT_TYPES = [
        ('self_signed', 'Self-Signed'),
        ('letsencrypt', "Let's Encrypt"),
        ('custom', 'Custom')
    ]
    
    domain = models.CharField(
        max_length=255,
        unique=True,
        help_text="Domain name for this certificate"
    )
    certificate_pem = models.TextField(
        blank=True,
        help_text="Certificate in PEM format (auto-generated for Let's Encrypt)"
    )
    private_key_pem = models.TextField(
        blank=True,
        help_text="Private key in PEM format (auto-generated for Let's Encrypt)"
    )
    cert_type = models.CharField(
        max_length=20,
        choices=CERT_TYPES,
        help_text="Type of certificate"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Certificate expiration date (auto-filled after generation)"
    )
    credentials = models.ForeignKey(
        Credentials,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Credentials for Let's Encrypt (Cloudflare API)"
    )
    acme_email = models.EmailField(
        blank=True,
        help_text="Email address for ACME account registration (required for Let's Encrypt)"
    )
    auto_renew = models.BooleanField(
        default=True,
        help_text="Automatically renew certificate before expiration"
    )
    last_renewed = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last renewal timestamp"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Certificate"
        verbose_name_plural = "Certificates"
        ordering = ['domain']
    
    def __str__(self):
        return f"{self.domain} ({self.get_cert_type_display()})"
    
    @property
    def is_expired(self):
        """Check if certificate is expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def days_until_expiration(self):
        """Days until certificate expires"""
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return delta.days
    
    @property
    def needs_renewal(self):
        """Check if certificate needs renewal"""
        if not self.auto_renew or not self.expires_at:
            return False
        
        # Default renewal period
        renewal_days = 60
        
        days_left = self.days_until_expiration
        if days_left is None:
            return False
            
        return days_left <= renewal_days


class Inbound(models.Model):
    """Independent inbound configuration"""
    PROTOCOLS = [
        ('vless', 'VLESS'),
        ('vmess', 'VMess'),
        ('trojan', 'Trojan'),
        ('shadowsocks', 'Shadowsocks')
    ]
    
    NETWORKS = [
        ('tcp', 'TCP'),
        ('ws', 'WebSocket'),
        ('grpc', 'gRPC'),
        ('http', 'HTTP/2'),
        ('quic', 'QUIC')
    ]
    
    SECURITIES = [
        ('none', 'None'),
        ('tls', 'TLS'),
        ('reality', 'REALITY')
    ]
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for this inbound"
    )
    protocol = models.CharField(
        max_length=20,
        choices=PROTOCOLS,
        help_text="Protocol type"
    )
    port = models.IntegerField(
        help_text="Port to listen on"
    )
    network = models.CharField(
        max_length=20,
        choices=NETWORKS,
        default='tcp',
        help_text="Transport protocol"
    )
    security = models.CharField(
        max_length=20,
        choices=SECURITIES,
        default='none',
        help_text="Security type"
    )
    
    # Full configuration for Xray
    full_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete configuration for creating inbound on server (auto-generated if empty)"
    )
    
    # Additional settings
    listen_address = models.CharField(
        max_length=45,
        default="0.0.0.0",
        help_text="IP address to listen on"
    )
    enable_sniffing = models.BooleanField(
        default=True,
        help_text="Enable protocol sniffing"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Inbound Template"
        verbose_name_plural = "Inbound Templates"
        ordering = ['protocol', 'port']
        unique_together = [['port', 'listen_address']]
    
    def __str__(self):
        return f"{self.name} ({self.protocol.upper()}:{self.port})"
    
    def generate_tag(self):
        """Generate unique tag for inbound"""
        return f"{self.protocol}-{self.port}-{uuid.uuid4().hex[:8]}"
    
    def build_config(self):
        """Build full configuration for Xray"""
        try:
            # Build basic Xray inbound configuration
            config = {
                "tag": self.name,
                "port": self.port,
                "listen": self.listen_address,
                "protocol": self.protocol,
                "settings": self._build_protocol_settings(),
                "streamSettings": self._build_stream_settings(),
                "sniffing": {
                    "enabled": self.enable_sniffing,
                    "destOverride": ["http", "tls"]
                } if self.enable_sniffing else {}
            }
            
            # Store the built config
            self.full_config = config
            return self.full_config
            
        except Exception as e:
            # Fallback to basic config if detailed build fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to build detailed config for {self.name}: {e}")
            
            self.full_config = {
                "tag": self.name,
                "port": self.port,
                "listen": self.listen_address,
                "protocol": self.protocol,
                "settings": {},
                "streamSettings": {}
            }
            return self.full_config
    
    def _build_protocol_settings(self):
        """Build protocol-specific settings"""
        settings = {}
        
        if self.protocol == 'vless':
            settings = {
                "clients": [],  # Will be populated when users are added
                "decryption": "none"
            }
        elif self.protocol == 'vmess':
            settings = {
                "clients": []  # Will be populated when users are added
            }
        elif self.protocol == 'trojan':
            settings = {
                "clients": []  # Will be populated when users are added
            }
        elif self.protocol == 'shadowsocks':
            settings = {
                "method": "aes-128-gcm",  # Default method
                "password": "",  # Will be set when configured
                "network": "tcp,udp"
            }
        
        return settings
    
    def _build_stream_settings(self):
        """Build stream transport settings"""
        stream_settings = {
            "network": self.network
        }
        
        # Add network-specific settings
        if self.network == "ws":
            stream_settings["wsSettings"] = {
                "path": f"/{self.name}",
                "headers": {}
            }
        elif self.network == "grpc":
            stream_settings["grpcSettings"] = {
                "serviceName": self.name
            }
        elif self.network == "http":
            stream_settings["httpSettings"] = {
                "path": f"/{self.name}",
                "host": []  # Will be filled when deployed to server
            }
        
        # Add security settings
        if self.security == "tls":
            stream_settings["security"] = "tls"
            tls_settings = {
                "serverName": "localhost",  # Will be replaced with server hostname when deployed
                "alpn": ["h2", "http/1.1"]
            }
            
            # Certificate will be set during deployment based on ServerInbound configuration
            
            stream_settings["tlsSettings"] = tls_settings
        
        elif self.security == "reality":
            stream_settings["security"] = "reality"
            # Reality settings would be configured here
            stream_settings["realitySettings"] = {
                "dest": "example.com:443",  # Will be replaced with server hostname when deployed
                "serverNames": ["example.com"],  # Will be replaced with server hostname when deployed
                "privateKey": "",  # Would be generated
                "shortIds": [""]   # Would be generated
            }
        
        return stream_settings


class SubscriptionGroup(models.Model):
    """Groups of inbounds for subscription management"""
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Group name (e.g., 'VLESS Premium', 'VMess Basic')"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this subscription group"
    )
    inbounds = models.ManyToManyField(
        Inbound,
        blank=True,
        help_text="Inbounds included in this group"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this group is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "XRay-core"
        verbose_name_plural = "XRay-core"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def inbound_count(self):
        """Number of inbounds in this group"""
        return self.inbounds.count()
    
    @property
    def user_count(self):
        """Number of users subscribed to this group"""
        return self.usersubscription_set.filter(active=True).count()


class UserSubscription(models.Model):
    """User subscriptions to groups"""
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='xray_subscriptions'
    )
    subscription_group = models.ForeignKey(
        SubscriptionGroup,
        on_delete=models.CASCADE
    )
    active = models.BooleanField(
        default=True,
        help_text="Whether this subscription is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Subscription"
        verbose_name_plural = "User Subscriptions"
        unique_together = ['user', 'subscription_group']
        ordering = ['user__username', 'subscription_group__name']
    
    def __str__(self):
        return f"{self.user.username} - {self.subscription_group.name}"


class ServerInbound(models.Model):
    """Many-to-many relationship between servers and inbounds to track deployment"""
    server = models.ForeignKey('Server', on_delete=models.CASCADE, related_name='deployed_inbounds')
    inbound = models.ForeignKey(Inbound, on_delete=models.CASCADE, related_name='deployed_servers')
    active = models.BooleanField(default=True, help_text="Whether this inbound is active on the server")
    
    deployed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Certificate for TLS on this specific server deployment
    certificate = models.ForeignKey(
        Certificate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Certificate for TLS on this specific server (overrides automatic selection)"
    )
    
    # Store deployment-specific configuration if needed
    deployment_config = models.JSONField(default=dict, blank=True, help_text="Server-specific deployment configuration")
    
    class Meta:
        verbose_name = "Server Inbound Deployment"
        verbose_name_plural = "Server Inbound Deployments"
        ordering = ['server__name', 'inbound__name']
        unique_together = [('server', 'inbound')]
    
    def __str__(self):
        status = "Active" if self.active else "Inactive"
        return f"{self.server.name} -> {self.inbound.name} ({status})"
    
    def get_certificate(self):
        """Get certificate for this deployment with fallback logic"""
        # 1. Use explicitly set certificate
        if self.certificate:
            return self.certificate
            
        # 2. Try to find certificate by server's client_hostname
        if hasattr(self.server.get_real_instance(), 'client_hostname'):
            server_hostname = self.server.get_real_instance().client_hostname
            try:
                return Certificate.objects.get(domain=server_hostname, cert_type='letsencrypt')
            except Certificate.DoesNotExist:
                try:
                    return Certificate.objects.get(domain=server_hostname)
                except Certificate.DoesNotExist:
                    pass
        
        # 3. No certificate found
        return None
    
    def requires_certificate(self):
        """Check if this inbound requires a certificate"""
        return self.inbound.security in ['tls'] or self.inbound.protocol == 'trojan'