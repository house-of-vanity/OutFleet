"""Statistics functionality for Xray API"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

from .client import XrayClient
from .models.base import BaseXrayModel


@dataclass
class StatItem(BaseXrayModel):
    """Single statistics item"""
    name: str
    value: int
    
    @property
    def parts(self) -> List[str]:
        """Split stat name into parts"""
        return self.name.split(">>>")
    
    @property
    def stat_type(self) -> str:
        """Get stat type (inbound/outbound/user)"""
        return self.parts[0] if self.parts else ""
    
    @property
    def tag(self) -> str:
        """Get inbound/outbound tag"""
        return self.parts[1] if len(self.parts) > 1 else ""
    
    @property
    def metric(self) -> str:
        """Get metric name (traffic/uplink/downlink)"""
        return self.parts[-1] if self.parts else ""


@dataclass
class SystemStats(BaseXrayModel):
    """System statistics"""
    numGoroutine: int = 0
    numGC: int = 0
    alloc: int = 0
    totalAlloc: int = 0
    sys: int = 0
    mallocs: int = 0
    frees: int = 0
    liveObjects: int = 0
    pauseTotalNs: int = 0
    uptime: int = 0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemStats':
        """Create from API response with proper field mapping"""
        # Map API response fields to model fields
        field_mapping = {
            'NumGoroutine': 'numGoroutine',
            'NumGC': 'numGC', 
            'Alloc': 'alloc',
            'TotalAlloc': 'totalAlloc',
            'Sys': 'sys',
            'Mallocs': 'mallocs',
            'Frees': 'frees',
            'LiveObjects': 'liveObjects',
            'PauseTotalNs': 'pauseTotalNs',
            'Uptime': 'uptime'
        }
        
        normalized = {}
        for api_key, model_key in field_mapping.items():
            if api_key in data:
                normalized[model_key] = data[api_key]
                
        return cls(**normalized)
    
    @property
    def uptime_seconds(self) -> int:
        """Get uptime in seconds"""
        return self.uptime
    
    @property
    def memory_mb(self) -> float:
        """Get allocated memory in MB"""
        return self.alloc / 1024 / 1024


class StatsManager:
    """Manager for Xray statistics"""
    
    def __init__(self, client: XrayClient):
        self.client = client
        
    def get_all_stats(self, reset: bool = False) -> List[StatItem]:
        """Get all statistics"""
        stats = self.client.get_stats("", reset=reset)
        result = []
        for stat in stats:
            if isinstance(stat, dict) and 'name' in stat and 'value' in stat:
                result.append(StatItem(name=stat['name'], value=stat['value']))
        return result
    
    def get_inbound_stats(self, tag: str, reset: bool = False) -> Dict[str, int]:
        """Get statistics for specific inbound"""
        pattern = f"inbound>>>{tag}>>>traffic>>>"
        stats = self.client.get_stats(pattern, reset=reset)
        
        result = {"uplink": 0, "downlink": 0}
        for stat in stats:
            item = StatItem(**stat)
            if item.metric in result:
                result[item.metric] = item.value
                
        return result
    
    def get_outbound_stats(self, tag: str, reset: bool = False) -> Dict[str, int]:
        """Get statistics for specific outbound"""
        pattern = f"outbound>>>{tag}>>>traffic>>>"
        stats = self.client.get_stats(pattern, reset=reset)
        
        result = {"uplink": 0, "downlink": 0}
        for stat in stats:
            item = StatItem(**stat)
            if item.metric in result:
                result[item.metric] = item.value
                
        return result
    
    def get_user_stats(self, email: str, reset: bool = False) -> Dict[str, int]:
        """Get statistics for specific user"""
        pattern = f"user>>>{email}>>>traffic>>>"
        stats = self.client.get_stats(pattern, reset=reset)
        
        result = {"uplink": 0, "downlink": 0}
        for stat in stats:
            item = StatItem(**stat)
            if item.metric in result:
                result[item.metric] = item.value
                
        return result
    
    def get_user_online_info(self, email: str) -> Dict[str, Any]:
        """Get user online information"""
        online = self.client.get_online_stats(email)
        ips_data = self.client.get_online_ips(email)
        
        return {
            "email": email,
            "online": online.get("count", 0) > 0,
            "sessions": online.get("count", 0),
            "ips": ips_data
        }
    
    def get_system_stats(self) -> SystemStats:
        """Get system statistics"""
        stats = self.client.get_system_stats()
        return SystemStats.from_dict(stats)
    
    def get_traffic_summary(self) -> Dict[str, Dict[str, int]]:
        """Get traffic summary for all inbounds/outbounds"""
        all_stats = self.get_all_stats()
        summary = {
            "inbounds": {},
            "outbounds": {},
            "users": {}
        }
        
        for stat in all_stats:
            if stat.stat_type == "inbound":
                if stat.tag not in summary["inbounds"]:
                    summary["inbounds"][stat.tag] = {"uplink": 0, "downlink": 0}
                summary["inbounds"][stat.tag][stat.metric] = stat.value
                
            elif stat.stat_type == "outbound":
                if stat.tag not in summary["outbounds"]:
                    summary["outbounds"][stat.tag] = {"uplink": 0, "downlink": 0}
                summary["outbounds"][stat.tag][stat.metric] = stat.value
                
            elif stat.stat_type == "user":
                user_email = stat.parts[1] if len(stat.parts) > 1 else ""
                if user_email and user_email not in summary["users"]:
                    summary["users"][user_email] = {"uplink": 0, "downlink": 0}
                if user_email:
                    summary["users"][user_email][stat.metric] = stat.value
                    
        return summary