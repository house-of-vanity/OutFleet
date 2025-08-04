"""
Data models for Xray Manager.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from .utils import generate_uuid


@dataclass
class User:
    """Base user model."""
    email: str
    level: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary representation."""
        return {
            "email": self.email,
            "level": self.level
        }


@dataclass
class VlessUser(User):
    """VLESS protocol user."""
    uuid: str = field(default_factory=generate_uuid)

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "id": self.uuid
        })
        return base


@dataclass
class VmessUser(User):
    """VMess protocol user."""
    uuid: str = field(default_factory=generate_uuid)
    alter_id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "id": self.uuid,
            "alterId": self.alter_id
        })
        return base


@dataclass
class TrojanUser(User):
    """Trojan protocol user."""
    password: str = ""

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "password": self.password
        })
        return base




@dataclass
class Inbound:
    """Inbound configuration."""
    tag: str
    protocol: str
    port: int
    listen: str = "0.0.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "protocol": self.protocol,
            "port": self.port,
            "listen": self.listen
        }


@dataclass
class Stats:
    """Statistics data."""
    uplink: int = 0
    downlink: int = 0

    @property
    def total(self) -> int:
        """Total traffic (uplink + downlink)."""
        return self.uplink + self.downlink