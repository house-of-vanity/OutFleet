"""
VLESS protocol implementation.
"""

from typing import List, Dict, Any, Optional
from .base import BaseProtocol
from ..models import User, VlessUser


class VlessProtocol(BaseProtocol):
    """VLESS protocol handler."""
    
    def __init__(self, port: int, tag: Optional[str] = None, listen: str = "0.0.0.0", network: str = "tcp"):
        super().__init__(port, tag, listen, network)
    
    def _default_tag(self) -> str:
        return "vless-inbound"
    
    def create_inbound_config(self, users: List[VlessUser]) -> Dict[str, Any]:
        """Create VLESS inbound configuration."""
        config = self._base_inbound_config()
        config.update({
            "protocol": "vless",
            "settings": {
                "_TypedMessage_": "xray.proxy.vless.inbound.Config",
                "clients": [self._user_to_client(user) for user in users],
                "decryption": "none"
            },
            "streamSettings": {
                "network": self.network
            }
        })
        return {"inbounds": [config]}
    
    def create_user_config(self, user: VlessUser) -> Dict[str, Any]:
        """Create user configuration for VLESS."""
        return {
            "inboundTag": self.tag,
            "proxySettings": {
                "_TypedMessage_": "xray.proxy.vless.inbound.Config",
                "clients": [self._user_to_client(user)]
            }
        }
    
    def generate_client_link(self, user: VlessUser, hostname: str, network: str = None, security: str = None, **kwargs) -> str:
        """Generate VLESS client link."""
        from urllib.parse import urlencode
        
        # Use provided parameters or defaults
        network_type = network or self.network
        encryption = kwargs.get('encryption', 'none')
        
        params = {
            'encryption': encryption,
            'type': network_type
        }
        
        # Add security if provided
        if security and security != 'none':
            params['security'] = security
            
        query_string = urlencode(params)
        return f"vless://{user.uuid}@{hostname}:{self.port}?{query_string}#{user.email}"
    
    def _user_to_client(self, user: VlessUser) -> Dict[str, Any]:
        """Convert VlessUser to client configuration."""
        return {
            "id": user.uuid,
            "level": user.level,
            "email": user.email
        }