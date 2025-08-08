"""Base models for xray-api library"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, Type, TypeVar
import json
from enum import Enum

T = TypeVar('T', bound='BaseXrayModel')


class BaseXrayModel(ABC):
    """Base class for all Xray configuration models"""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for storage"""
        if hasattr(self, '__dataclass_fields__'):
            return self._clean_dict(asdict(self))
        return self._clean_dict(self.__dict__.copy())
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert model to Xray API format"""
        return self.to_dict()
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Create model instance from dictionary"""
        return cls(**data)
    
    def _clean_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove None values and empty collections"""
        cleaned = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            if isinstance(value, BaseXrayModel):
                cleaned[key] = value.to_dict()
            elif isinstance(value, list):
                cleaned[key] = [
                    item.to_dict() if isinstance(item, BaseXrayModel) else item
                    for item in value
                ]
            elif isinstance(value, Enum):
                cleaned[key] = value.value
            else:
                cleaned[key] = value
        return cleaned
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class XrayConfig(BaseXrayModel):
    """Base configuration class"""
    _TypedMessage_: Optional[str] = field(default=None, init=False)
    
    def __post_init__(self):
        """Set TypedMessage after initialization"""
        if self._TypedMessage_ is None and hasattr(self, '__xray_type__'):
            self._TypedMessage_ = self.__xray_type__


class XrayProtocol(str, Enum):
    """Supported Xray protocols"""
    VLESS = "vless"
    VMESS = "vmess"
    TROJAN = "trojan"
    SHADOWSOCKS = "shadowsocks"
    DOKODEMO = "dokodemo-door"
    FREEDOM = "freedom"
    BLACKHOLE = "blackhole"
    DNS = "dns"
    HTTP = "http"
    SOCKS = "socks"


class TransportProtocol(str, Enum):
    """Transport protocols"""
    TCP = "tcp"
    KCP = "kcp"
    WS = "ws"
    HTTP = "http"
    XHTTP = "xhttp"
    DOMAINSOCKET = "domainsocket"
    QUIC = "quic"
    GRPC = "grpc"


class SecurityType(str, Enum):
    """Security types"""
    NONE = "none"
    TLS = "tls"
    REALITY = "reality"
    XTLS = "xtls"