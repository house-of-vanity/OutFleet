"""Inbound configuration models"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union

from .base import BaseXrayModel, XrayConfig, XrayProtocol
from .protocols import (
    VLESSInboundConfig, VMeSSInboundConfig, 
    TrojanServerConfig, ShadowsocksServerConfig
)
from .transports import StreamSettings


@dataclass
class SniffingConfig(BaseXrayModel):
    """Traffic sniffing configuration"""
    enabled: bool = True
    destOverride: Optional[List[str]] = None
    metadataOnly: bool = False
    
    def __post_init__(self):
        if self.destOverride is None:
            self.destOverride = ["http", "tls"]


@dataclass
class ReceiverConfig(XrayConfig):
    """Receiver configuration for inbound"""
    __xray_type__ = "xray.app.proxyman.ReceiverConfig"
    
    listen: str = "0.0.0.0"
    port: Optional[int] = None
    portList: Optional[Union[int, str]] = None  # Can be int or range like "10000-20000"
    streamSettings: Optional[StreamSettings] = None
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray format"""
        config = {"listen": self.listen}
        
        # Either port or portList must be set
        if self.port is not None:
            config["port"] = self.port
        elif self.portList is not None:
            config["portList"] = self.portList
        else:
            raise ValueError("Either port or portList must be specified")
            
        if self.streamSettings:
            config["streamSettings"] = self.streamSettings.to_xray_json()
            
        return config


@dataclass
class InboundConfig(BaseXrayModel):
    """Complete inbound configuration"""
    tag: str
    protocol: XrayProtocol
    settings: Union[VLESSInboundConfig, VMeSSInboundConfig, TrojanServerConfig, ShadowsocksServerConfig]
    listen: str = "0.0.0.0"
    port: Optional[int] = None
    portList: Optional[Union[int, str]] = None
    streamSettings: Optional[StreamSettings] = None
    sniffing: Optional[SniffingConfig] = None
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray API format with proper field order and structure"""
        config = {
            "listen": self.listen,
            "tag": self.tag,
            "protocol": self.protocol.value if hasattr(self.protocol, 'value') else str(self.protocol),
        }
        
        # Add port or portList (port comes before protocol in working format)
        if self.port is not None:
            config["port"] = self.port
        elif self.portList is not None:
            config["portList"] = self.portList
        else:
            raise ValueError("Either port or portList must be specified")
            
        # Add protocol settings with _TypedMessage_
        settings = self.settings.to_xray_json()
        if "_TypedMessage_" not in settings:
            # Add _TypedMessage_ based on protocol
            protocol_type_map = {
                "vless": "xray.proxy.vless.inbound.Config",
                "vmess": "xray.proxy.vmess.inbound.Config", 
                "trojan": "xray.proxy.trojan.inbound.Config",
                "shadowsocks": "xray.proxy.shadowsocks.inbound.Config"
            }
            protocol_name = self.protocol.value if hasattr(self.protocol, 'value') else str(self.protocol)
            if protocol_name in protocol_type_map:
                settings["_TypedMessage_"] = protocol_type_map[protocol_name]
                
        config["settings"] = settings
        
        # Add stream settings
        if self.streamSettings:
            config["streamSettings"] = self.streamSettings.to_xray_json()
        else:
            config["streamSettings"] = {"network": "tcp"}  # Default TCP
        
        # Add sniffing
        if self.sniffing:
            config["sniffing"] = self.sniffing.to_dict()
            
        return config


# Builder for easier configuration
class InboundBuilder:
    """Builder for creating inbound configurations"""
    
    def __init__(self, tag: str, protocol: XrayProtocol):
        self.tag = tag
        self.protocol = protocol
        self._settings = None
        self._listen = "0.0.0.0"
        self._port = None
        self._port_list = None
        self._stream_settings = None
        self._sniffing = None
        
    def listen(self, address: str) -> 'InboundBuilder':
        """Set listen address"""
        self._listen = address
        return self
        
    def port(self, port: int) -> 'InboundBuilder':
        """Set single port"""
        self._port = port
        self._port_list = None
        return self
        
    def port_range(self, start: int, end: int) -> 'InboundBuilder':
        """Set port range"""
        self._port_list = f"{start}-{end}"
        self._port = None
        return self
        
    def stream_settings(self, settings: StreamSettings) -> 'InboundBuilder':
        """Set stream settings"""
        self._stream_settings = settings
        return self
        
    def sniffing(self, enabled: bool = True, dest_override: Optional[List[str]] = None) -> 'InboundBuilder':
        """Configure sniffing"""
        self._sniffing = SniffingConfig(
            enabled=enabled,
            destOverride=dest_override
        )
        return self
        
    def protocol_settings(self, settings: Union[VLESSInboundConfig, VMeSSInboundConfig, TrojanServerConfig, ShadowsocksServerConfig]) -> 'InboundBuilder':
        """Set protocol-specific settings"""
        self._settings = settings
        return self
        
    def build(self) -> InboundConfig:
        """Build the inbound configuration"""
        if not self._settings:
            raise ValueError("Protocol settings must be specified")
            
        if not self._port and not self._port_list:
            raise ValueError("Either port or port range must be specified")
            
        return InboundConfig(
            tag=self.tag,
            protocol=self.protocol,
            settings=self._settings,
            listen=self._listen,
            port=self._port,
            portList=self._port_list,
            streamSettings=self._stream_settings,
            sniffing=self._sniffing
        )