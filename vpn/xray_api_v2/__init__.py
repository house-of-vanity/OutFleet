"""Xray API Python Library"""
from .client import XrayClient
from .stats import StatsManager, StatItem, SystemStats
from .subscription import SubscriptionLinkGenerator
from .exceptions import (
    XrayAPIError, XrayConnectionError, XrayCommandError,
    XrayConfigError, XrayNotFoundError, XrayValidationError
)
from .models import (
    # Base
    XrayProtocol, TransportProtocol, SecurityType,
    
    # Protocols
    VLESSClient, VMeSSUser, TrojanUser, TrojanFallback,
    VLESSInboundConfig, VMeSSInboundConfig, TrojanServerConfig,
    generate_uuid, validate_uuid,
    
    # Transports
    StreamSettings, create_tcp_stream, create_ws_stream, 
    create_grpc_stream, create_http_stream, create_xhttp_stream,
    
    # Security
    TLSConfig, REALITYConfig,
    create_tls_config, create_reality_config,
    generate_self_signed_certificate, create_tls_config_with_self_signed,
    
    # Inbound
    InboundConfig, InboundBuilder, SniffingConfig
)

__version__ = "0.1.0"

__all__ = [
    # Client
    'XrayClient',
    
    # Stats
    'StatsManager', 'StatItem', 'SystemStats',
    
    # Subscription
    'SubscriptionLinkGenerator',
    
    # Exceptions
    'XrayAPIError', 'XrayConnectionError', 'XrayCommandError',
    'XrayConfigError', 'XrayNotFoundError', 'XrayValidationError',
    
    # Enums
    'XrayProtocol', 'TransportProtocol', 'SecurityType',
    
    # Models
    'VLESSClient', 'VMeSSUser', 'TrojanUser', 'TrojanFallback',
    'VLESSInboundConfig', 'VMeSSInboundConfig', 'TrojanServerConfig',
    'StreamSettings', 'TLSConfig', 'REALITYConfig',
    'InboundConfig', 'InboundBuilder', 'SniffingConfig',
    
    # Utils
    'generate_uuid', 'validate_uuid',
    'create_tcp_stream', 'create_ws_stream', 
    'create_grpc_stream', 'create_http_stream', 'create_xhttp_stream',
    'create_tls_config', 'create_reality_config',
    'generate_self_signed_certificate', 'create_tls_config_with_self_signed',
]