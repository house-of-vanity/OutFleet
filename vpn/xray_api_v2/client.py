"""Xray API client implementation"""
import json
import subprocess
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import tempfile
import os

from .exceptions import (
    XrayConnectionError, 
    XrayCommandError,
    XrayConfigError
)
from .models.base import BaseXrayModel


class XrayClient:
    """Client for interacting with Xray API via CLI commands"""
    
    def __init__(self, server: str = "127.0.0.1:8080", timeout: int = 3):
        """
        Initialize Xray client
        
        Args:
            server: API server address (host:port)
            timeout: Command timeout in seconds
        """
        self.server = server
        self.timeout = timeout
        self._xray_binary = "xray"
    
    def execute_command(self, 
                       command: str,
                       args: List[str] = None,
                       json_files: List[Union[str, Dict, BaseXrayModel]] = None) -> Dict[str, Any]:
        """
        Execute xray API command
        
        Args:
            command: API command (e.g., 'adi', 'adu', 'lsi')
            args: Additional command arguments
            json_files: JSON configurations (paths, dicts, or models)
            
        Returns:
            Command output as dictionary
        """
        cmd = [self._xray_binary, "api", command]
        cmd.extend([f"--server={self.server}", f"--timeout={self.timeout}"])
        
        if args:
            cmd.extend(args)
        
        temp_files = []
        try:
            # Handle JSON configurations
            if json_files:
                for config in json_files:
                    if isinstance(config, str):
                        # File path provided
                        cmd.append(config)
                    else:
                        # Create temporary file for dict or model
                        temp_file = self._create_temp_json(config)
                        temp_files.append(temp_file)
                        cmd.append(temp_file.name)
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 5  # Add buffer to subprocess timeout
            )
            
            if result.returncode != 0:
                raise XrayCommandError(f"Command failed: {result.stderr}")
            
            # Parse output
            output = result.stdout.strip()
            if not output:
                return {}
                
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                # Some commands return plain text
                return {"output": output}
                
        except subprocess.TimeoutExpired:
            raise XrayConnectionError(f"Command timed out after {self.timeout} seconds")
        except Exception as e:
            raise XrayCommandError(f"Command execution failed: {str(e)}")
        finally:
            # Cleanup temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
    
    def _create_temp_json(self, config: Union[Dict, BaseXrayModel]) -> tempfile.NamedTemporaryFile:
        """Create temporary JSON file from config"""
        if isinstance(config, BaseXrayModel):
            data = config.to_xray_json()
        else:
            data = config
        
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        )
        json.dump(data, temp_file, indent=2)
        temp_file.close()
        return temp_file
    
    # Inbound management
    def add_inbound(self, *configs: Union[Dict, BaseXrayModel]) -> Dict[str, Any]:
        """Add one or more inbounds"""
        # Wrap inbound configs in the required format
        wrapped_configs = []
        for config in configs:
            if isinstance(config, BaseXrayModel):
                config_dict = config.to_xray_json()
            else:
                config_dict = config
                
            # Wrap in inbounds array if not already wrapped
            if "inbounds" not in config_dict:
                wrapped_config = {"inbounds": [config_dict]}
            else:
                wrapped_config = config_dict
                
            wrapped_configs.append(wrapped_config)
        
        return self.execute_command("adi", json_files=wrapped_configs)
    
    def remove_inbound(self, tag: str) -> Dict[str, Any]:
        """Remove inbound by tag"""
        return self.execute_command("rmi", args=[tag])
    
    def list_inbounds(self) -> List[Dict[str, Any]]:
        """List all inbounds"""
        result = self.execute_command("lsi")
        return result.get("inbounds", [])
    
    # Outbound management
    def add_outbound(self, *configs: Union[Dict, BaseXrayModel]) -> Dict[str, Any]:
        """Add one or more outbounds"""
        return self.execute_command("ado", json_files=list(configs))
    
    def remove_outbound(self, tag: str) -> Dict[str, Any]:
        """Remove outbound by tag"""
        return self.execute_command("rmo", args=[tag])
    
    def list_outbounds(self) -> List[Dict[str, Any]]:
        """List all outbounds"""
        result = self.execute_command("lso")
        return result.get("outbounds", [])
    
    # User management
    def add_users(self, *configs: Union[Dict, BaseXrayModel]) -> Dict[str, Any]:
        """Add users to inbounds using JSON files"""
        return self.execute_command("adu", json_files=list(configs))
    
    def remove_users(self, tag: str, *emails: str) -> Dict[str, Any]:
        """Remove users from inbounds using tag and email list"""
        args = [f"-tag={tag}"] + list(emails)
        return self.execute_command("rmu", args=args)
    
    def get_inbound_user(self, tag: str, email: Optional[str] = None) -> Dict[str, Any]:
        """Get inbound user(s) information using -tag flag"""
        args = [f"-tag={tag}"]
        if email:
            args.append(f"-email={email}")
        return self.execute_command("inbounduser", args=args)
    
    def get_inbound_user_count(self, tag: str) -> int:
        """Get inbound user count using -tag flag"""
        args = [f"-tag={tag}"]
        result = self.execute_command("inboundusercount", args=args)
        # Parse the result - might be in output field or direct number
        if isinstance(result, dict):
            return result.get("count", 0)
        return 0
    
    # Statistics
    def get_stats(self, pattern: str = "", reset: bool = False) -> List[Dict[str, Any]]:
        """Get statistics"""
        args = [pattern]
        if reset:
            args.append("-reset")
        if pattern:
            args.extend(["-json"])
        result = self.execute_command("statsquery", args=args)
        return result.get("stat", [])
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return self.execute_command("statssys")
    
    def get_online_stats(self, email: str) -> Dict[str, Any]:
        """Get online session count for user"""
        return self.execute_command("statsonline", args=[email])
    
    def get_online_ips(self, email: str) -> List[Dict[str, Any]]:
        """Get user's online IP addresses"""
        result = self.execute_command("statsonlineiplist", args=[email])
        return result.get("ips", [])
    
    # Routing rules
    def add_routing_rules(self, *configs: Union[Dict, BaseXrayModel]) -> Dict[str, Any]:
        """Add routing rules"""
        return self.execute_command("adrules", json_files=list(configs))
    
    def remove_routing_rules(self, *tags: str) -> Dict[str, Any]:
        """Remove routing rules by tags"""
        return self.execute_command("rmrules", args=list(tags))
    
    # Other operations
    def restart_logger(self) -> Dict[str, Any]:
        """Restart the logger"""
        return self.execute_command("restartlogger")
    
    def get_balancer_info(self, tag: str) -> Dict[str, Any]:
        """Get balancer information"""
        return self.execute_command("bi", args=[tag])
    
    def override_balancer(self, tag: str, selectors: List[str]) -> Dict[str, Any]:
        """Override balancer selection"""
        return self.execute_command("bo", args=[tag] + selectors)
    
    def block_connection(self, source_ip: str, seconds: int) -> Dict[str, Any]:
        """Block connections from source IP"""
        return self.execute_command("sib", args=[source_ip, str(seconds)])