"""
Xray Manager - Python library for managing Xray proxy server via gRPC API.

Supports VLESS, VMess, and Trojan protocols.
"""

from .client import XrayClient
from .models import User, VlessUser, VmessUser, TrojanUser, Stats
from .exceptions import XrayError, APIError, InboundNotFoundError, UserNotFoundError

__version__ = "1.0.0"
__all__ = [
    "XrayClient", 
    "User", 
    "VlessUser", 
    "VmessUser", 
    "TrojanUser", 
    "Stats",
    "XrayError",
    "APIError",
    "InboundNotFoundError", 
    "UserNotFoundError"
]