"""Transport configuration models for Xray"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from .base import BaseXrayModel, XrayConfig, TransportProtocol


# TCP Transport
@dataclass
class TCPSettings(XrayConfig):
    """TCP transport settings"""
    __xray_type__ = "xray.transport.internet.tcp.Config"
    
    acceptProxyProtocol: bool = False
    header: Optional[Dict[str, Any]] = None


# KCP Transport
@dataclass 
class KCPSettings(XrayConfig):
    """KCP transport settings"""
    __xray_type__ = "xray.transport.internet.kcp.Config"
    
    mtu: int = 1350
    tti: int = 50
    uplinkCapacity: int = 5
    downlinkCapacity: int = 20
    congestion: bool = False
    readBufferSize: int = 2
    writeBufferSize: int = 2
    header: Optional[Dict[str, Any]] = None


# WebSocket Transport
@dataclass
class WebSocketSettings(XrayConfig):
    """WebSocket transport settings"""
    __xray_type__ = "xray.transport.internet.websocket.Config"
    
    path: str = "/"
    headers: Optional[Dict[str, str]] = None
    acceptProxyProtocol: bool = False
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray format"""
        config = super().to_xray_json()
        # Ensure headers is a dict even if empty
        if self.headers:
            config["headers"] = self.headers
        return config


# HTTP/2 Transport
@dataclass
class HTTPSettings(XrayConfig):
    """HTTP/2 transport settings"""
    __xray_type__ = "xray.transport.internet.http.Config"
    
    path: str = "/"
    host: Optional[List[str]] = None
    method: str = "PUT"
    headers: Optional[Dict[str, List[str]]] = None


# XHTTP Transport (New)
@dataclass 
class XHTTPSettings(XrayConfig):
    """XHTTP transport settings"""
    __xray_type__ = "xray.transport.internet.xhttp.Config"
    
    path: str = "/"
    host: Optional[str] = None
    method: str = "GET"
    headers: Optional[Dict[str, Any]] = None
    mode: str = "auto"


# Domain Socket Transport
@dataclass
class DomainSocketSettings(XrayConfig):
    """Domain socket transport settings"""
    __xray_type__ = "xray.transport.internet.domainsocket.Config"
    
    path: str
    abstract: bool = False
    padding: bool = False


# QUIC Transport
@dataclass
class QUICSettings(XrayConfig):
    """QUIC transport settings"""
    __xray_type__ = "xray.transport.internet.quic.Config"
    
    security: str = "none"
    key: str = ""
    header: Optional[Dict[str, Any]] = None


# gRPC Transport
@dataclass
class GRPCSettings(XrayConfig):
    """gRPC transport settings"""
    __xray_type__ = "xray.transport.internet.grpc.encoding.Config"
    
    serviceName: str = ""
    multiMode: bool = False
    idle_timeout: int = 60
    health_check_timeout: int = 20
    permit_without_stream: bool = False
    initial_windows_size: int = 0


# Stream Settings
@dataclass
class StreamSettings(BaseXrayModel):
    """Stream settings for inbound/outbound"""
    
    network: TransportProtocol = TransportProtocol.TCP
    security: Optional[str] = None
    tlsSettings: Optional[Any] = None
    xtlsSettings: Optional[Any] = None
    realitySettings: Optional[Any] = None
    tcpSettings: Optional[TCPSettings] = None
    kcpSettings: Optional[KCPSettings] = None
    wsSettings: Optional[WebSocketSettings] = None
    httpSettings: Optional[HTTPSettings] = None
    xhttpSettings: Optional[XHTTPSettings] = None
    dsSettings: Optional[DomainSocketSettings] = None
    quicSettings: Optional[QUICSettings] = None
    grpcSettings: Optional[GRPCSettings] = None
    sockopt: Optional[Dict[str, Any]] = None
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray format with correct field names"""
        config = {
            "network": self.network.value if isinstance(self.network, TransportProtocol) else self.network
        }
        
        if self.security:
            config["security"] = self.security
            
        # Map transport settings
        transport_map = {
            TransportProtocol.TCP: ("tcpSettings", self.tcpSettings),
            TransportProtocol.KCP: ("kcpSettings", self.kcpSettings),
            TransportProtocol.WS: ("wsSettings", self.wsSettings),
            TransportProtocol.HTTP: ("httpSettings", self.httpSettings),
            TransportProtocol.XHTTP: ("xhttpSettings", self.xhttpSettings),
            TransportProtocol.DOMAINSOCKET: ("dsSettings", self.dsSettings),
            TransportProtocol.QUIC: ("quicSettings", self.quicSettings),
            TransportProtocol.GRPC: ("grpcSettings", self.grpcSettings),
        }
        
        network = self.network if isinstance(self.network, TransportProtocol) else TransportProtocol(self.network)
        field_name, settings = transport_map.get(network, (None, None))
        
        if field_name and settings:
            config[field_name] = settings.to_xray_json() if hasattr(settings, 'to_xray_json') else settings
            
        # Add security settings
        if self.tlsSettings:
            config["tlsSettings"] = self.tlsSettings if isinstance(self.tlsSettings, dict) else self.tlsSettings.to_xray_json()
        if self.xtlsSettings:
            config["xtlsSettings"] = self.xtlsSettings if isinstance(self.xtlsSettings, dict) else self.xtlsSettings.to_xray_json()
        if self.realitySettings:
            config["realitySettings"] = self.realitySettings if isinstance(self.realitySettings, dict) else self.realitySettings.to_xray_json()
            
        if self.sockopt:
            config["sockopt"] = self.sockopt
            
        return config


# Factory functions
def create_tcp_stream(
    security: Optional[str] = None,
    **kwargs
) -> StreamSettings:
    """Create TCP stream settings"""
    return StreamSettings(
        network=TransportProtocol.TCP,
        security=security,
        tcpSettings=TCPSettings(**kwargs) if kwargs else None
    )


def create_ws_stream(
    path: str = "/",
    headers: Optional[Dict[str, str]] = None,
    security: Optional[str] = None,
    **kwargs
) -> StreamSettings:
    """Create WebSocket stream settings"""
    return StreamSettings(
        network=TransportProtocol.WS,
        security=security,
        wsSettings=WebSocketSettings(path=path, headers=headers, **kwargs)
    )


def create_grpc_stream(
    service_name: str = "",
    security: Optional[str] = None,
    **kwargs
) -> StreamSettings:
    """Create gRPC stream settings"""
    return StreamSettings(
        network=TransportProtocol.GRPC,
        security=security,
        grpcSettings=GRPCSettings(serviceName=service_name, **kwargs)
    )


def create_http_stream(
    path: str = "/",
    host: Optional[List[str]] = None,
    security: Optional[str] = None,
    **kwargs
) -> StreamSettings:
    """Create HTTP/2 stream settings"""
    return StreamSettings(
        network=TransportProtocol.HTTP,
        security=security,
        httpSettings=HTTPSettings(path=path, host=host, **kwargs)
    )


def create_xhttp_stream(
    path: str = "/",
    host: Optional[str] = None,
    security: Optional[str] = None,
    mode: str = "auto",
    **kwargs
) -> StreamSettings:
    """Create XHTTP stream settings"""
    return StreamSettings(
        network=TransportProtocol.XHTTP,
        security=security,
        xhttpSettings=XHTTPSettings(path=path, host=host, mode=mode, **kwargs)
    )