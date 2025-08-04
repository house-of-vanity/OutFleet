"""
Trojan protocol implementation.
"""

from typing import List, Dict, Any, Optional
from .base import BaseProtocol
from ..models import User, TrojanUser
from ..utils import generate_self_signed_cert, pem_to_lines
from ..exceptions import CertificateError


class TrojanProtocol(BaseProtocol):
    """Trojan protocol handler."""
    
    def __init__(self, port: int, tag: Optional[str] = None, listen: str = "0.0.0.0", 
                 network: str = "tcp", cert_pem: Optional[str] = None, 
                 key_pem: Optional[str] = None, hostname: str = "localhost"):
        super().__init__(port, tag, listen, network)
        self.hostname = hostname
        
        if cert_pem and key_pem:
            self.cert_pem = cert_pem
            self.key_pem = key_pem
        else:
            # Generate self-signed certificate
            self.cert_pem, self.key_pem = generate_self_signed_cert(hostname)
    
    def _default_tag(self) -> str:
        return "trojan-inbound"
    
    def create_inbound_config(self, users: List[TrojanUser]) -> Dict[str, Any]:
        """Create Trojan inbound configuration."""
        config = self._base_inbound_config()
        config.update({
            "protocol": "trojan",
            "settings": {
                "_TypedMessage_": "xray.proxy.trojan.Config",
                "clients": [self._user_to_client(user) for user in users],
                "fallbacks": [{"dest": 80}]
            },
            "streamSettings": {
                "network": self.network,
                "security": "tls",
                "tlsSettings": {
                    "alpn": ["http/1.1"],
                    "certificates": [{
                        "certificate": pem_to_lines(self.cert_pem),
                        "key": pem_to_lines(self.key_pem),
                        "usage": "encipherment"
                    }]
                }
            }
        })
        return {"inbounds": [config]}
    
    def create_user_config(self, user: TrojanUser) -> Dict[str, Any]:
        """Create user configuration for Trojan."""
        return {
            "inboundTag": self.tag,
            "proxySettings": {
                "_TypedMessage_": "xray.proxy.trojan.Config",
                "clients": [self._user_to_client(user)]
            }
        }
    
    def generate_client_link(self, user: TrojanUser, hostname: str, network: str = None, security: str = None, **kwargs) -> str:
        """Generate Trojan client link."""
        from urllib.parse import urlencode
        
        # Use provided parameters or defaults
        network_type = network or self.network
        
        params = {
            'type': network_type
        }
        
        # Add security if provided
        if security and security != 'none':
            params['security'] = security
            
        query_string = urlencode(params)
        return f"trojan://{user.password}@{hostname}:{self.port}?{query_string}#{user.email}"
    
    def get_client_note(self) -> str:
        """Get note for client configuration when using self-signed certificates."""
        return "Add 'allowInsecure: true' to TLS settings for self-signed certificates"
    
    def _user_to_client(self, user: TrojanUser) -> Dict[str, Any]:
        """Convert TrojanUser to client configuration."""
        return {
            "password": user.password,
            "level": user.level,
            "email": user.email
        }