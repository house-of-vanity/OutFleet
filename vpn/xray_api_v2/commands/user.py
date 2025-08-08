"""User management command wrappers"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from ..models.base import BaseXrayModel


@dataclass
class AddUserRequest(BaseXrayModel):
    """Request to add user to inbound"""
    inboundTag: str
    user: Dict[str, Any]  # Protocol-specific user config
    

@dataclass
class RemoveUserRequest(BaseXrayModel):
    """Request to remove user from inbound"""
    inboundTag: str
    email: str


@dataclass
class UserStats(BaseXrayModel):
    """User statistics data"""
    email: str
    uplink: int = 0
    downlink: int = 0
    online: bool = False
    ips: List[str] = None
    
    def __post_init__(self):
        if self.ips is None:
            self.ips = []