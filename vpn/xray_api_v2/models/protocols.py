"""Protocol models for Xray"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from uuid import uuid4
import re

from .base import BaseXrayModel, XrayConfig, XrayProtocol


def validate_uuid(uuid_str: str) -> bool:
    """Validate UUID format"""
    pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
    return bool(pattern.match(uuid_str))


def generate_uuid() -> str:
    """Generate new UUID"""
    return str(uuid4())


# VLESS Protocol
@dataclass
class VLESSAccount(XrayConfig):
    """VLESS account configuration"""
    __xray_type__ = "xray.proxy.vless.Account"
    
    id: str
    flow: Optional[str] = None
    encryption: str = "none"
    
    def __post_init__(self):
        super().__post_init__()
        if not validate_uuid(self.id):
            raise ValueError(f"Invalid UUID: {self.id}")


@dataclass
class VLESSClient(BaseXrayModel):
    """VLESS client configuration"""
    email: str
    account: VLESSAccount
    level: int = 0
    
    @classmethod
    def create(cls, email: str, uuid: Optional[str] = None, flow: Optional[str] = None) -> 'VLESSClient':
        """Create VLESS client with optional UUID generation"""
        if uuid is None:
            uuid = generate_uuid()
        account = VLESSAccount(id=uuid, flow=flow)
        return cls(email=email, account=account)


@dataclass
class VLESSInboundConfig(XrayConfig):
    """VLESS inbound configuration"""
    __xray_type__ = "xray.proxy.vless.inbound.Config"
    
    clients: List[VLESSClient] = field(default_factory=list)
    decryption: str = "none"
    fallbacks: Optional[List[Dict[str, Any]]] = None
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray API format with proper structure"""
        config = {
            "_TypedMessage_": self.__xray_type__,
            "clients": [],
            "decryption": self.decryption
        }
        
        # Convert clients to proper format
        for client in self.clients:
            client_data = {
                "id": client.account.id,
                "level": client.level,
                "email": client.email
            }
            if client.account.flow:
                client_data["flow"] = client.account.flow
            config["clients"].append(client_data)
        
        if self.fallbacks:
            config["fallbacks"] = self.fallbacks
            
        return config


# VMess Protocol
@dataclass
class VMeSSSecurityConfig(BaseXrayModel):
    """VMess security configuration"""
    type: str = "AUTO"  # AUTO, AES-128-GCM, CHACHA20-POLY1305, NONE


@dataclass
class VMeSSAccount(XrayConfig):
    """VMess account configuration"""
    __xray_type__ = "xray.proxy.vmess.Account"
    
    id: str
    securitySettings: Optional[VMeSSSecurityConfig] = None
    
    def __post_init__(self):
        super().__post_init__()
        if not validate_uuid(self.id):
            raise ValueError(f"Invalid UUID: {self.id}")
        if self.securitySettings is None:
            self.securitySettings = VMeSSSecurityConfig()


@dataclass 
class VMeSSUser(BaseXrayModel):
    """VMess user configuration"""
    email: str
    account: VMeSSAccount
    level: int = 0
    
    @classmethod
    def create(cls, email: str, uuid: Optional[str] = None, security: str = "AUTO") -> 'VMeSSUser':
        """Create VMess user with optional UUID generation"""
        if uuid is None:
            uuid = generate_uuid()
        account = VMeSSAccount(
            id=uuid,
            securitySettings=VMeSSSecurityConfig(type=security)
        )
        return cls(email=email, account=account)


@dataclass
class VMeSSInboundConfig(XrayConfig):
    """VMess inbound configuration"""
    __xray_type__ = "xray.proxy.vmess.inbound.Config"
    
    user: List[VMeSSUser] = field(default_factory=list)
    disableInsecureEncryption: bool = False
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray API format with proper structure"""
        config = {
            "_TypedMessage_": self.__xray_type__,
            "clients": []
        }
        
        # Convert users to proper format
        for user in self.user:
            client_data = {
                "id": user.account.id,
                "level": user.level,
                "email": user.email,
                "alterId": 0  # VMess specific
            }
            config["clients"].append(client_data)
            
        return config


# Trojan Protocol
@dataclass
class TrojanAccount(XrayConfig):
    """Trojan account configuration"""
    __xray_type__ = "xray.proxy.trojan.Account"
    
    password: str
    
    @classmethod
    def generate_password(cls) -> str:
        """Generate secure password"""
        return generate_uuid()


@dataclass
class TrojanUser(BaseXrayModel):
    """Trojan user configuration"""
    email: str
    account: TrojanAccount
    level: int = 0
    
    @classmethod
    def create(cls, email: str, password: Optional[str] = None) -> 'TrojanUser':
        """Create Trojan user with optional password generation"""
        if password is None:
            password = TrojanAccount.generate_password()
        account = TrojanAccount(password=password)
        return cls(email=email, account=account)


@dataclass
class TrojanFallback(BaseXrayModel):
    """Trojan fallback configuration"""
    dest: str
    type: str = "tcp"
    xver: int = 0


@dataclass
class TrojanServerConfig(XrayConfig):
    """Trojan server configuration"""
    __xray_type__ = "xray.proxy.trojan.ServerConfig"
    
    users: List[TrojanUser] = field(default_factory=list)
    fallbacks: Optional[List[TrojanFallback]] = None
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray API format with proper structure"""
        config = {
            "_TypedMessage_": self.__xray_type__,
            "clients": []
        }
        
        # Convert users to proper format  
        for user in self.users:
            client_data = {
                "password": user.account.password,
                "level": user.level,
                "email": user.email
            }
            config["clients"].append(client_data)
        
        if self.fallbacks:
            config["fallbacks"] = [fb.to_dict() for fb in self.fallbacks]
            
        return config


# Shadowsocks Protocol
@dataclass
class ShadowsocksAccount(XrayConfig):
    """Shadowsocks account configuration"""
    __xray_type__ = "xray.proxy.shadowsocks.Account"
    
    method: str  # aes-256-gcm, aes-128-gcm, chacha20-poly1305, etc.
    password: str


@dataclass
class ShadowsocksUser(BaseXrayModel):
    """Shadowsocks user configuration"""
    email: str
    account: ShadowsocksAccount
    level: int = 0


@dataclass
class ShadowsocksServerConfig(XrayConfig):
    """Shadowsocks server configuration"""
    __xray_type__ = "xray.proxy.shadowsocks.ServerConfig"
    
    users: List[ShadowsocksUser] = field(default_factory=list)
    network: str = "tcp,udp"


# Protocol config factory
def create_protocol_config(protocol: XrayProtocol, **kwargs) -> XrayConfig:
    """Factory to create protocol configurations"""
    protocol_map = {
        XrayProtocol.VLESS: VLESSInboundConfig,
        XrayProtocol.VMESS: VMeSSInboundConfig,
        XrayProtocol.TROJAN: TrojanServerConfig,
        XrayProtocol.SHADOWSOCKS: ShadowsocksServerConfig,
    }
    
    config_class = protocol_map.get(protocol)
    if not config_class:
        raise ValueError(f"Unsupported protocol: {protocol}")
    
    return config_class(**kwargs)