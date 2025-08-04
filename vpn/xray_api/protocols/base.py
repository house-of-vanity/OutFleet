"""
Base protocol implementation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models import User


class BaseProtocol(ABC):
    """Base class for all protocol implementations."""
    
    def __init__(self, port: int, tag: Optional[str] = None, listen: str = "0.0.0.0", network: str = "tcp"):
        self.port = port
        self.tag = tag or self._default_tag()
        self.listen = listen
        self.network = network
    
    @abstractmethod
    def _default_tag(self) -> str:
        """Return default tag for this protocol."""
        pass
    
    @abstractmethod
    def create_inbound_config(self, users: List[User]) -> Dict[str, Any]:
        """Create inbound configuration for this protocol."""
        pass
    
    @abstractmethod
    def create_user_config(self, user: User) -> Dict[str, Any]:
        """Create user configuration for adding to existing inbound."""
        pass
    
    @abstractmethod
    def generate_client_link(self, user: User, hostname: str, network: str = None, security: str = None, **kwargs) -> str:
        """Generate client connection link."""
        pass
    
    def _base_inbound_config(self) -> Dict[str, Any]:
        """Common inbound configuration."""
        return {
            "listen": self.listen,
            "port": self.port,
            "tag": self.tag
        }