"""Subscription link generation for Xray protocols"""
import json
import base64
import urllib.parse
from typing import Dict, Any, Optional, List, Union
from .models.base import BaseXrayModel
from .models.inbound import InboundConfig
from .models.protocols import VLESSInboundConfig, VMeSSInboundConfig, TrojanServerConfig


class SubscriptionLinkGenerator:
    """Generate subscription links for various Xray protocols"""
    
    @staticmethod
    def _url_encode(value: str) -> str:
        """URL encode string with safe characters"""
        return urllib.parse.quote(value, safe='')
    
    @staticmethod
    def _format_ipv6(address: str) -> str:
        """Format IPv6 address with brackets if needed"""
        if ':' in address and not address.startswith('['):
            return f'[{address}]'
        return address
    
    @classmethod
    def generate_vless_link(cls,
                           uuid: str,
                           address: str,
                           port: int,
                           remark: str = "VLESS",
                           encryption: str = "none",
                           security: str = "none",
                           sni: Optional[str] = None,
                           transport_type: str = "tcp",
                           path: Optional[str] = None,
                           host: Optional[str] = None,
                           alpn: Optional[str] = None,
                           fp: str = "chrome",
                           flow: Optional[str] = None,
                           allow_insecure: bool = False,
                           # REALITY parameters
                           pbk: Optional[str] = None,
                           sid: Optional[str] = None,
                           spx: Optional[str] = None,
                           **kwargs) -> str:
        """
        Generate VLESS subscription link
        
        Args:
            uuid: Client UUID
            address: Server address
            port: Server port
            remark: Link description/name
            encryption: Encryption method (default: none)
            security: Security layer (none, tls, reality)
            sni: SNI for TLS
            transport_type: Transport type (tcp, ws, grpc, xhttp, h2, kcp)
            path: Path for WebSocket/HTTP2/gRPC
            host: Host header for WebSocket
            alpn: ALPN negotiation
            fp: Fingerprint
            flow: Flow control (xtls-rprx-vision, etc.)
            pbk: REALITY public key
            sid: REALITY short ID
            spx: REALITY spider X
            **kwargs: Additional parameters
            
        Returns:
            VLESS subscription link
        """
        # Build query parameters
        params = {
            'encryption': encryption,
            'security': security,
            'type': transport_type,
            'fp': fp
        }
        
        # Add optional parameters
        if sni:
            params['sni'] = sni
        if path:
            params['path'] = path  # Don't double encode - urlencode will handle it
        if host:
            params['host'] = host
        if alpn:
            params['alpn'] = alpn
        if flow:
            params['flow'] = flow
        if allow_insecure:
            params['allowInsecure'] = '1'
            
        # Add REALITY parameters
        if pbk:
            params['pbk'] = pbk
        if sid:
            params['sid'] = sid
        if spx:
            params['spx'] = spx
            
        # Add any additional parameters
        params.update(kwargs)
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        # Build query string (keep - and _ safe for REALITY keys)
        query_string = urllib.parse.urlencode(params, safe='-_')
        
        # Format address (handle IPv6)
        formatted_address = cls._format_ipv6(address)
        
        # Build VLESS URL
        url = f"vless://{uuid}@{formatted_address}:{port}?{query_string}#{cls._url_encode(remark)}"
        
        return url
    
    @classmethod
    def generate_vmess_link(cls,
                           uuid: str,
                           address: str,
                           port: int,
                           remark: str = "VMess",
                           alterId: int = 0,
                           security: str = "auto",
                           network: str = "tcp",
                           transport_type: Optional[str] = None,
                           path: Optional[str] = None,
                           host: Optional[str] = None,
                           tls: str = "",
                           sni: Optional[str] = None,
                           alpn: Optional[str] = None,
                           fp: Optional[str] = None,
                           allow_insecure: bool = False,
                           **kwargs) -> str:
        """
        Generate VMess subscription link
        
        Args:
            uuid: Client UUID
            address: Server address
            port: Server port
            remark: Link description/name
            alterId: Alter ID (default: 0)
            security: Security method (auto, aes-128-gcm, chacha20-poly1305, none)
            network: Network type (tcp, kcp, ws, h2, quic, grpc)
            transport_type: Transport type (same as network for compatibility)
            path: Path for WebSocket/HTTP2/gRPC
            host: Host header
            tls: TLS settings ("" for none, "tls" for TLS)
            sni: SNI for TLS
            alpn: ALPN negotiation
            fp: Fingerprint
            **kwargs: Additional parameters
            
        Returns:
            VMess subscription link
        """
        # Use transport_type if provided, otherwise use network
        net = transport_type or network
        
        # Build VMess configuration object
        vmess_config = {
            'v': '2',
            'ps': remark,
            'add': address,
            'port': str(port),
            'id': uuid,
            'aid': str(alterId),
            'scy': security,
            'net': net,
            'type': kwargs.get('type', 'none'),
            'host': host or '',
            'path': path or '',
            'tls': tls,
            'sni': sni or '',
            'alpn': alpn or '',
            'fp': fp or ''
        }
        
        # Add allowInsecure only if True (VMess format - try multiple approaches)
        if allow_insecure:
            vmess_config['allowInsecure'] = 1
            vmess_config['skip-cert-verify'] = True  # For compatibility with some clients
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in vmess_config and value is not None:
                vmess_config[key] = str(value)
        
        # Convert to JSON and base64 encode
        json_str = json.dumps(vmess_config, separators=(',', ':'))
        encoded = base64.b64encode(json_str.encode('utf-8')).decode('ascii')
        
        return f"vmess://{encoded}"
    
    @classmethod
    def generate_trojan_link(cls,
                           password: str,
                           address: str,
                           port: int,
                           remark: str = "Trojan",
                           security: str = "tls",
                           sni: Optional[str] = None,
                           transport_type: str = "tcp",
                           path: Optional[str] = None,
                           host: Optional[str] = None,
                           alpn: Optional[str] = None,
                           fp: str = "chrome",
                           allow_insecure: bool = False,
                           **kwargs) -> str:
        """
        Generate Trojan subscription link
        
        Args:
            password: Trojan password
            address: Server address
            port: Server port
            remark: Link description/name
            security: Security layer (tls, none)
            sni: SNI for TLS
            transport_type: Transport type (tcp, ws, grpc)
            path: Path for WebSocket/gRPC
            host: Host header
            alpn: ALPN negotiation
            fp: Fingerprint
            **kwargs: Additional parameters
            
        Returns:
            Trojan subscription link
        """
        # Build query parameters
        params = {
            'security': security,
            'type': transport_type,
            'fp': fp
        }
        
        # Add optional parameters
        if sni:
            params['sni'] = sni
        if path:
            params['path'] = path  # Don't double encode - urlencode will handle it
        if host:
            params['host'] = host
        if alpn:
            params['alpn'] = alpn
        if allow_insecure:
            params['allowInsecure'] = '1'
            
        # Add any additional parameters
        params.update(kwargs)
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        # Build query string
        query_string = urllib.parse.urlencode(params)
        
        # Format address (handle IPv6)
        formatted_address = cls._format_ipv6(address)
        
        # URL encode password
        encoded_password = cls._url_encode(password)
        
        # Build Trojan URL
        url = f"trojan://{encoded_password}@{formatted_address}:{port}?{query_string}#{cls._url_encode(remark)}"
        
        return url
    
    @classmethod
    def generate_shadowsocks_link(cls,
                                method: str,
                                password: str,
                                address: str,
                                port: int,
                                remark: str = "Shadowsocks") -> str:
        """
        Generate Shadowsocks subscription link
        
        Args:
            method: Encryption method
            password: SS password
            address: Server address
            port: Server port
            remark: Link description/name
            
        Returns:
            Shadowsocks subscription link
        """
        # Format: ss://base64(method:password)@server:port#remark
        user_info = f"{method}:{password}"
        encoded_user_info = base64.b64encode(user_info.encode('utf-8')).decode('ascii')
        
        # Format address (handle IPv6)
        formatted_address = cls._format_ipv6(address)
        
        return f"ss://{encoded_user_info}@{formatted_address}:{port}#{cls._url_encode(remark)}"
    
    @classmethod
    def generate_subscription_from_inbound(cls,
                                         inbound: InboundConfig,
                                         server_address: str,
                                         remark_prefix: str = "",
                                         **transport_params) -> List[str]:
        """
        Generate subscription links from inbound configuration
        
        Args:
            inbound: Inbound configuration
            server_address: Public server address
            remark_prefix: Prefix for link remarks
            **transport_params: Additional transport parameters
            
        Returns:
            List of subscription links for all users
        """
        links = []
        protocol = inbound.protocol.lower()
        port = inbound.port
        tag = inbound.tag
        
        # Extract protocol-specific settings
        if isinstance(inbound.settings, VLESSInboundConfig):
            for client in inbound.settings.clients:
                remark = f"{remark_prefix}{tag}_{client.email}" if remark_prefix else f"{tag}_{client.email}"
                link = cls.generate_vless_link(
                    uuid=client.account.id,
                    address=server_address,
                    port=port,
                    remark=remark,
                    **transport_params
                )
                links.append(link)
                
        elif isinstance(inbound.settings, VMeSSInboundConfig):
            for client in inbound.settings.user:
                remark = f"{remark_prefix}{tag}_{client.email}" if remark_prefix else f"{tag}_{client.email}"
                link = cls.generate_vmess_link(
                    uuid=client.account.id,
                    address=server_address,
                    port=port,
                    remark=remark,
                    **transport_params
                )
                links.append(link)
                
        elif isinstance(inbound.settings, TrojanServerConfig):
            for client in inbound.settings.users:
                remark = f"{remark_prefix}{tag}_{client.email}" if remark_prefix else f"{tag}_{client.email}"
                link = cls.generate_trojan_link(
                    password=client.password,
                    address=server_address,
                    port=port,
                    remark=remark,
                    **transport_params
                )
                links.append(link)
        
        return links
    
    @classmethod
    def create_subscription_content(cls, links: List[str]) -> str:
        """
        Create base64 encoded subscription content
        
        Args:
            links: List of subscription links
            
        Returns:
            Base64 encoded subscription content
        """
        content = '\n'.join(links)
        return base64.b64encode(content.encode('utf-8')).decode('ascii')
    
    @classmethod
    def parse_subscription_content(cls, content: str) -> List[str]:
        """
        Parse base64 encoded subscription content
        
        Args:
            content: Base64 encoded subscription content
            
        Returns:
            List of subscription links
        """
        try:
            decoded = base64.b64decode(content).decode('utf-8')
            return [link.strip() for link in decoded.split('\n') if link.strip()]
        except Exception as e:
            raise ValueError(f"Invalid subscription content: {e}")