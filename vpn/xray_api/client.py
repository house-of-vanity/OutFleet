"""
Main Xray client for managing proxy server via gRPC API.
"""

import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from .exceptions import APIError, InboundNotFoundError, UserNotFoundError
from .models import Stats, TrojanUser, User, VlessUser, VmessUser
from .protocols import TrojanProtocol, VlessProtocol, VmessProtocol

logger = logging.getLogger(__name__)


class XrayClient:
    """Main client for Xray server management."""
    
    def __init__(self, server: str):
        """
        Initialize Xray client.
        
        Args:
            server: Xray gRPC API server address (host:port)
        """
        self.server = server
        self.hostname = server.split(':')[0]  # Extract hostname for client links
        
        # Protocol handlers
        self._protocols = {}
    
    # Inbound management
    
    def add_vless_inbound(self, port: int, users: List[VlessUser], tag: Optional[str] = None, 
                         listen: str = "0.0.0.0", network: str = "tcp") -> None:
        """Add VLESS inbound with users."""
        protocol = VlessProtocol(port, tag, listen, network)
        self._protocols[protocol.tag] = protocol
        config = protocol.create_inbound_config(users)
        self._add_inbound(config)
    
    def add_vmess_inbound(self, port: int, users: List[VmessUser], tag: Optional[str] = None,
                         listen: str = "0.0.0.0", network: str = "tcp") -> None:
        """Add VMess inbound with users."""
        protocol = VmessProtocol(port, tag, listen, network)
        self._protocols[protocol.tag] = protocol
        config = protocol.create_inbound_config(users)
        self._add_inbound(config)
    
    def add_trojan_inbound(self, port: int, users: List[TrojanUser], tag: Optional[str] = None,
                          listen: str = "0.0.0.0", network: str = "tcp",
                          cert_pem: Optional[str] = None, key_pem: Optional[str] = None,
                          hostname: Optional[str] = None) -> None:
        """Add Trojan inbound with users and optional custom certificates."""
        hostname = hostname or self.hostname
        protocol = TrojanProtocol(port, tag, listen, network, cert_pem, key_pem, hostname)
        self._protocols[protocol.tag] = protocol
        config = protocol.create_inbound_config(users)
        self._add_inbound(config)
    
    
    def remove_inbound(self, protocol_type_or_tag: str) -> None:
        """
        Remove inbound by protocol type or tag.
        
        Args:
            protocol_type_or_tag: Protocol type ('vless', 'vmess', 'trojan') or specific tag
        """
        # Try to find by protocol type first
        tag_map = {
            'vless': 'vless-inbound',
            'vmess': 'vmess-inbound', 
            'trojan': 'trojan-inbound'
        }
        
        tag = tag_map.get(protocol_type_or_tag, protocol_type_or_tag)
        
        config = {"tag": tag}
        self._remove_inbound(config)
        
        if tag in self._protocols:
            del self._protocols[tag]
    
    def list_inbounds(self) -> List[Dict[str, Any]]:
        """List all inbounds."""
        return self._list_inbounds()
    
    # User management
    
    def add_user(self, protocol_type_or_tag: str, user: User) -> None:
        """
        Add user to existing inbound by recreating it with updated users.
        
        Args:
            protocol_type_or_tag: Protocol type ('vless', 'vmess', 'trojan') or specific tag
            user: User object matching the protocol type
        """
        tag_map = {
            'vless': 'vless-inbound',
            'vmess': 'vmess-inbound',
            'trojan': 'trojan-inbound'
        }
        
        # Check if it's a protocol type or direct tag
        tag = tag_map.get(protocol_type_or_tag, protocol_type_or_tag)
        
        # If protocol not registered, we need to get inbound info first
        if tag not in self._protocols:
            logger.debug(f"Protocol for tag '{tag}' not registered, attempting to retrieve inbound info")
            
            # Try to get inbound info to determine protocol
            try:
                inbounds = self._list_inbounds()
                if isinstance(inbounds, dict) and 'inbounds' in inbounds:
                    inbound_list = inbounds['inbounds']
                else:
                    inbound_list = inbounds if isinstance(inbounds, list) else []
                
                # Find the inbound by tag
                for inbound in inbound_list:
                    if inbound.get('tag') == tag:
                        # Determine protocol from proxySettings
                        proxy_settings = inbound.get('proxySettings', {})
                        typed_message = proxy_settings.get('_TypedMessage_', '')
                        
                        if 'vless' in typed_message.lower():
                            from .protocols import VlessProtocol
                            port = inbound.get('receiverSettings', {}).get('portList', 443)
                            listen = inbound.get('receiverSettings', {}).get('listen', '0.0.0.0')
                            network = inbound.get('receiverSettings', {}).get('streamSettings', {}).get('protocolName', 'tcp')
                            protocol = VlessProtocol(port, tag, listen, network)
                            self._protocols[tag] = protocol
                        elif 'vmess' in typed_message.lower():
                            from .protocols import VmessProtocol
                            port = inbound.get('receiverSettings', {}).get('portList', 443)
                            listen = inbound.get('receiverSettings', {}).get('listen', '0.0.0.0')
                            network = inbound.get('receiverSettings', {}).get('streamSettings', {}).get('protocolName', 'tcp')
                            protocol = VmessProtocol(port, tag, listen, network)
                            self._protocols[tag] = protocol
                        elif 'trojan' in typed_message.lower():
                            from .protocols import TrojanProtocol
                            port = inbound.get('receiverSettings', {}).get('portList', 443)
                            listen = inbound.get('receiverSettings', {}).get('listen', '0.0.0.0')
                            network = inbound.get('receiverSettings', {}).get('streamSettings', {}).get('protocolName', 'tcp')
                            protocol = TrojanProtocol(port, tag, listen, network, hostname=self.hostname)
                            self._protocols[tag] = protocol
                        break
            except Exception as e:
                logger.error(f"Failed to retrieve inbound info for tag '{tag}': {e}")
        
        if tag not in self._protocols:
            raise InboundNotFoundError(f"Inbound {protocol_type_or_tag} not found or could not determine protocol")
        
        protocol = self._protocols[tag]
        
        # Use the recreate method since direct API doesn't work reliably
        self._recreate_inbound_with_user(protocol, user)
    
    def remove_user(self, protocol_type_or_tag: str, email: str) -> None:
        """
        Remove user from inbound by recreating it without the user.
        
        Args:
            protocol_type_or_tag: Protocol type ('vless', 'vmess', 'trojan') or specific tag  
            email: User email to remove
        """
        tag_map = {
            'vless': 'vless-inbound',
            'vmess': 'vmess-inbound',
            'trojan': 'trojan-inbound'
        }
        
        tag = tag_map.get(protocol_type_or_tag, protocol_type_or_tag)
        
        # Use same logic as add_user to find/register protocol
        if tag not in self._protocols:
            logger.debug(f"Protocol for tag '{tag}' not registered, attempting to retrieve inbound info")
            
            # Try to get inbound info to determine protocol
            try:
                inbounds = self._list_inbounds()
                if isinstance(inbounds, dict) and 'inbounds' in inbounds:
                    inbound_list = inbounds['inbounds']
                else:
                    inbound_list = inbounds if isinstance(inbounds, list) else []
                
                # Find the inbound by tag
                for inbound in inbound_list:
                    if inbound.get('tag') == tag:
                        # Determine protocol from proxySettings
                        proxy_settings = inbound.get('proxySettings', {})
                        typed_message = proxy_settings.get('_TypedMessage_', '')
                        
                        if 'vless' in typed_message.lower():
                            from .protocols import VlessProtocol
                            port = inbound.get('receiverSettings', {}).get('portList', 443)
                            listen = inbound.get('receiverSettings', {}).get('listen', '0.0.0.0')
                            network = inbound.get('receiverSettings', {}).get('streamSettings', {}).get('protocolName', 'tcp')
                            protocol = VlessProtocol(port, tag, listen, network)
                            self._protocols[tag] = protocol
                        elif 'vmess' in typed_message.lower():
                            from .protocols import VmessProtocol
                            port = inbound.get('receiverSettings', {}).get('portList', 443)
                            listen = inbound.get('receiverSettings', {}).get('listen', '0.0.0.0')
                            network = inbound.get('receiverSettings', {}).get('streamSettings', {}).get('protocolName', 'tcp')
                            protocol = VmessProtocol(port, tag, listen, network)
                            self._protocols[tag] = protocol
                        elif 'trojan' in typed_message.lower():
                            from .protocols import TrojanProtocol
                            port = inbound.get('receiverSettings', {}).get('portList', 443)
                            listen = inbound.get('receiverSettings', {}).get('listen', '0.0.0.0')
                            network = inbound.get('receiverSettings', {}).get('streamSettings', {}).get('protocolName', 'tcp')
                            protocol = TrojanProtocol(port, tag, listen, network, hostname=self.hostname)
                            self._protocols[tag] = protocol
                        break
            except Exception as e:
                logger.error(f"Failed to retrieve inbound info for tag '{tag}': {e}")
        
        if tag not in self._protocols:
            raise InboundNotFoundError(f"Inbound {protocol_type_or_tag} not found or could not determine protocol")
        
        protocol = self._protocols[tag]
        
        # Use the recreate method
        self._recreate_inbound_without_user(protocol, email)
    
    # Client link generation
    
    def generate_client_link(self, protocol_type_or_tag: str, user: User) -> str:
        """
        Generate client connection link.
        
        Args:
            protocol_type_or_tag: Protocol type ('vless', 'vmess', 'trojan') or specific tag
            user: User object
            
        Returns:
            Client connection link (vless://, vmess://, trojan://)
        """
        # First try to find by protocol type
        tag_map = {
            'vless': 'vless-inbound',
            'vmess': 'vmess-inbound',
            'trojan': 'trojan-inbound'
        }
        
        # Check if it's a protocol type or direct tag
        tag = tag_map.get(protocol_type_or_tag)
        if tag and tag in self._protocols:
            protocol = self._protocols[tag]
        elif protocol_type_or_tag in self._protocols:
            protocol = self._protocols[protocol_type_or_tag]
        else:
            # Try to find any protocol matching the type
            for stored_tag, stored_protocol in self._protocols.items():
                if protocol_type_or_tag in ['vless', 'vmess', 'trojan']:
                    protocol_class_name = f"{protocol_type_or_tag.title()}Protocol"
                    if stored_protocol.__class__.__name__ == protocol_class_name:
                        protocol = stored_protocol
                        break
            else:
                raise InboundNotFoundError(f"Protocol {protocol_type_or_tag} not configured")
        
        return protocol.generate_client_link(user, self.hostname)
    
    # Statistics
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get server system statistics."""
        return self._get_stats_sys()
    
    def get_user_stats(self, protocol_type: str, email: str) -> Stats:
        """
        Get user traffic statistics.
        
        Args:
            protocol_type: Protocol type
            email: User email
            
        Returns:
            Stats object with uplink/downlink data
        """
        # Implementation would require stats queries
        # This is a placeholder for the interface
        return Stats(uplink=0, downlink=0)
    
    # Private API methods
    
    def _add_inbound(self, config: Dict[str, Any]) -> None:
        """Add inbound via API."""
        result = self._run_api_command("adi", stdin_data=json.dumps(config))
        if "error" in result.get("stderr", "").lower():
            raise APIError(f"Failed to add inbound: {result['stderr']}")
    
    def _remove_inbound(self, config: Dict[str, Any]) -> None:
        """Remove inbound via API."""
        tag = config.get("tag")
        if tag:
            # Use tag directly as argument instead of JSON
            result = self._run_api_command("rmi", args=[tag])
        else:
            # Fallback to JSON if no tag
            result = self._run_api_command("rmi", stdin_data=json.dumps(config))
        
        if result["returncode"] != 0 and "no inbound to remove" not in result.get("stderr", ""):
            raise APIError(f"Failed to remove inbound: {result['stderr']}")
    
    def _list_inbounds(self) -> List[Dict[str, Any]]:
        """List inbounds via API."""
        result = self._run_api_command("lsi")
        if result["returncode"] != 0:
            raise APIError(f"Failed to list inbounds: {result['stderr']}")
        
        try:
            return json.loads(result["stdout"])
        except json.JSONDecodeError:
            raise APIError("Invalid JSON response from API")
    
    def _add_user(self, config: Dict[str, Any]) -> None:
        """Add user via API."""
        logger.debug(f"Adding user with config: {json.dumps(config, indent=2)}")
        result = self._run_api_command("adu", stdin_data=json.dumps(config))
        
        if result["returncode"] != 0 or "error" in result.get("stderr", "").lower():
            logger.error(f"Failed to add user. stdout: {result['stdout']}, stderr: {result['stderr']}")
            raise APIError(f"Failed to add user: {result['stderr'] or result['stdout']}")
        
        logger.info(f"User {config.get('email')} added successfully to inbound {config.get('tag')}")
    
    def _remove_user(self, inbound_tag: str, email: str) -> None:
        """Remove user via API."""
        result = self._run_api_command("rmu", args=[f"--email={email}", inbound_tag])
        if "error" in result.get("stderr", "").lower():
            raise APIError(f"Failed to remove user: {result['stderr']}")
    
    def _get_stats_sys(self) -> Dict[str, Any]:
        """Get system stats via API."""
        result = self._run_api_command("statssys")
        if result["returncode"] != 0:
            raise APIError(f"Failed to get stats: {result['stderr']}")
        
        try:
            return json.loads(result["stdout"])
        except json.JSONDecodeError:
            raise APIError("Invalid JSON response from API")
    
    def _build_user_config(self, tag: str, user: User, protocol) -> Dict[str, Any]:
        """
        Build user configuration for Xray API.
        
        Args:
            tag: Inbound tag
            user: User object (VlessUser, VmessUser, or TrojanUser)
            protocol: Protocol handler
            
        Returns:
            User configuration dict for Xray API
        """
        from .models import VlessUser, VmessUser, TrojanUser
        
        base_config = {
            "tag": tag,
            "email": user.email
        }
        
        if isinstance(user, VlessUser):
            base_config["account"] = {
                "_TypedMessage_": "xray.proxy.vless.Account",
                "id": user.uuid
            }
        elif isinstance(user, VmessUser):
            base_config["account"] = {
                "_TypedMessage_": "xray.proxy.vmess.Account",
                "id": user.uuid,
                "alterId": getattr(user, 'alter_id', 0)
            }
        elif isinstance(user, TrojanUser):
            base_config["account"] = {
                "_TypedMessage_": "xray.proxy.trojan.Account",
                "password": user.password
            }
        else:
            raise ValueError(f"Unsupported user type: {type(user)}")
        
        return base_config
    
    def _recreate_inbound_without_user(self, protocol, email: str) -> None:
        """
        Recreate inbound without specified user.
        """
        # Get existing users from the inbound
        existing_users = self._get_existing_users(protocol.tag)
        
        # Filter out the user to remove
        all_users = [user for user in existing_users if user.email != email]
        
        if len(all_users) == len(existing_users):
            logger.warning(f"User {email} not found in inbound {protocol.tag}")
            return
        
        # Remove existing inbound
        try:
            self.remove_inbound(protocol.tag)
        except Exception as e:
            logger.warning(f"Failed to remove inbound {protocol.tag}: {e}")
        
        # Recreate inbound with remaining users
        if hasattr(protocol, '__class__') and 'Vless' in protocol.__class__.__name__:
            self.add_vless_inbound(
                port=protocol.port,
                users=all_users,
                tag=protocol.tag,
                listen=protocol.listen,
                network=protocol.network
            )
        elif hasattr(protocol, '__class__') and 'Vmess' in protocol.__class__.__name__:
            self.add_vmess_inbound(
                port=protocol.port,
                users=all_users,
                tag=protocol.tag,
                listen=protocol.listen,
                network=protocol.network
            )
        elif hasattr(protocol, '__class__') and 'Trojan' in protocol.__class__.__name__:
            self.add_trojan_inbound(
                port=protocol.port,
                users=all_users,
                tag=protocol.tag,
                listen=protocol.listen,
                network=protocol.network,
                hostname=getattr(protocol, 'hostname', 'localhost')
            )
    
    def _recreate_inbound_with_user(self, protocol, new_user: User) -> None:
        """
        Recreate inbound with existing users plus new user.
        This is a workaround since Xray API doesn't support reliable dynamic user addition.
        """
        # Get existing users from the inbound
        existing_users = self._get_existing_users(protocol.tag)
        
        # Check if user already exists
        for existing_user in existing_users:
            if existing_user.email == new_user.email:
                return  # User already exists, no need to recreate
        
        # Add new user to existing users list
        all_users = existing_users + [new_user]
        
        # Remove existing inbound
        try:
            self.remove_inbound(protocol.tag)
        except Exception as e:
            # If removal fails, log but continue - inbound might not exist
            pass
        
        # Recreate inbound with all users
        if hasattr(protocol, '__class__') and 'Vless' in protocol.__class__.__name__:
            self.add_vless_inbound(
                port=protocol.port,
                users=all_users,
                tag=protocol.tag,
                listen=protocol.listen,
                network=protocol.network
            )
        elif hasattr(protocol, '__class__') and 'Vmess' in protocol.__class__.__name__:
            self.add_vmess_inbound(
                port=protocol.port,
                users=all_users,
                tag=protocol.tag,
                listen=protocol.listen,
                network=protocol.network
            )
        elif hasattr(protocol, '__class__') and 'Trojan' in protocol.__class__.__name__:
            self.add_trojan_inbound(
                port=protocol.port,
                users=all_users,
                tag=protocol.tag,
                listen=protocol.listen,
                network=protocol.network,
                hostname=getattr(protocol, 'hostname', 'localhost')
            )
    
    def _get_existing_users(self, tag: str) -> List[User]:
        """
        Get existing users from an inbound.
        """
        from .models import VlessUser, VmessUser, TrojanUser
        
        try:
            # Use inbounduser API command to get existing users
            result = self._run_api_command("inbounduser", args=[f"-tag={tag}"])
            
            if result["returncode"] != 0:
                return []  # No users or inbound doesn't exist
            
            import json
            user_data = json.loads(result["stdout"])
            users = []
            
            if "users" in user_data:
                for user_info in user_data["users"]:
                    email = user_info.get("email", "")
                    account = user_info.get("account", {})
                    
                    # Determine protocol based on account type
                    account_type = account.get("_TypedMessage_", "")
                    
                    if "vless" in account_type.lower():
                        users.append(VlessUser(
                            email=email,
                            uuid=account.get("id", "")
                        ))
                    elif "vmess" in account_type.lower():
                        users.append(VmessUser(
                            email=email,
                            uuid=account.get("id", ""),
                            alter_id=account.get("alterId", 0)
                        ))
                    elif "trojan" in account_type.lower():
                        users.append(TrojanUser(
                            email=email,
                            password=account.get("password", "")
                        ))
            
            return users
            
        except Exception as e:
            # If we can't get existing users, return empty list
            return []
    
    def _run_api_command(self, command: str, args: List[str] = None, stdin_data: str = None) -> Dict[str, Any]:
        """
        Run xray api command.
        
        Args:
            command: API command (adi, rmi, lsi, etc.)
            args: Additional command arguments
            stdin_data: Data to pass via stdin
            
        Returns:
            Dict with stdout, stderr, returncode
        """
        cmd = ["xray", "api", command, f"--server={self.server}"]
        if args:
            cmd.extend(args)
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        if stdin_data:
            logger.debug(f"With stdin data: {stdin_data}")
        
        try:
            result = subprocess.run(
                cmd,
                input=stdin_data,
                text=True,
                capture_output=True,
                timeout=30
            )
            
            logger.debug(f"Command result - returncode: {result.returncode}, stdout: {result.stdout}, stderr: {result.stderr}")
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            logger.error(f"API command timeout for: {' '.join(cmd)}")
            raise APIError("API command timeout")
        except FileNotFoundError:
            logger.error("xray command not found in PATH")
            raise APIError("xray command not found")
        except Exception as e:
            logger.error(f"Unexpected error running command: {e}")
            raise APIError(f"Failed to run command: {e}")