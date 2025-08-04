"""
VMess protocol implementation.
"""

import json
import base64
from typing import List, Dict, Any, Optional
from .base import BaseProtocol
from ..models import User, VmessUser


class VmessProtocol(BaseProtocol):
    """VMess protocol handler."""
    
    def __init__(self, port: int, tag: Optional[str] = None, listen: str = "0.0.0.0", network: str = "tcp"):
        super().__init__(port, tag, listen, network)
    
    def _default_tag(self) -> str:
        return "vmess-inbound"
    
    def create_inbound_config(self, users: List[VmessUser]) -> Dict[str, Any]:
        """Create VMess inbound configuration."""
        config = self._base_inbound_config()
        config.update({
            "protocol": "vmess",
            "settings": {
                "_TypedMessage_": "xray.proxy.vmess.inbound.Config",
                "clients": [self._user_to_client(user) for user in users]
            },
            "streamSettings": {
                "network": self.network
            }
        })
        return {"inbounds": [config]}
    
    def create_user_config(self, user: VmessUser) -> Dict[str, Any]:
        """Create user configuration for VMess."""
        return {
            "inboundTag": self.tag,
            "proxySettings": {
                "_TypedMessage_": "xray.proxy.vmess.inbound.Config",
                "clients": [self._user_to_client(user)]
            }
        }
    
    def generate_client_link(self, user: VmessUser, hostname: str, network: str = None, security: str = None, **kwargs) -> str:
        """Generate VMess client link."""
        # Use provided parameters or defaults
        network_type = network or self.network
        encryption = kwargs.get('encryption', 'auto')
        
        config = {
            "v": "2",
            "ps": user.email,
            "add": hostname,
            "port": str(self.port),
            "id": user.uuid,
            "aid": str(user.alter_id),
            "net": network_type,
            "type": "none",
            "host": "",
            "path": "",
            "tls": security if security and security != 'none' else ""
        }
        
        config_json = json.dumps(config, separators=(',', ':'))
        encoded = base64.b64encode(config_json.encode()).decode()
        return f"vmess://{encoded}"
    
    def _user_to_client(self, user: VmessUser) -> Dict[str, Any]:
        """Convert VmessUser to client configuration."""
        return {
            "id": user.uuid,
            "alterId": user.alter_id,
            "level": user.level,
            "email": user.email
        }