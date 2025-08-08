"""Security configuration models for Xray"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import secrets
from datetime import datetime, timedelta

from .base import BaseXrayModel, XrayConfig, SecurityType


# TLS Configuration
@dataclass
class Certificate(BaseXrayModel):
    """TLS certificate configuration"""
    certificateFile: Optional[str] = None
    keyFile: Optional[str] = None
    certificate: Optional[List[str]] = None  # PEM format lines
    key: Optional[List[str]] = None  # PEM format lines
    usage: str = "encipherment"
    ocspStapling: int = 3600
    oneTimeLoading: bool = False
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray format"""
        config = {}
        
        if self.certificateFile and self.keyFile:
            config["certificateFile"] = self.certificateFile
            config["keyFile"] = self.keyFile
        elif self.certificate and self.key:
            config["certificate"] = self.certificate
            config["key"] = self.key
            
        config["usage"] = self.usage
        
        if self.ocspStapling:
            config["ocspStapling"] = self.ocspStapling
            
        if self.oneTimeLoading:
            config["OneTimeLoading"] = self.oneTimeLoading
            
        return config


@dataclass
class TLSConfig(XrayConfig):
    """TLS configuration"""
    __xray_type__ = "xray.transport.internet.tls.Config"
    
    serverName: Optional[str] = None
    allowInsecure: bool = False
    alpn: Optional[List[str]] = None
    minVersion: str = "1.2"
    maxVersion: str = "1.3"
    preferServerCipherSuites: bool = True
    cipherSuites: Optional[str] = None
    certificates: Optional[List[Certificate]] = None
    disableSystemRoot: bool = False
    enableSessionResumption: bool = False
    fingerprint: Optional[str] = None  # Client-side
    pinnedPeerCertificateChainSha256: Optional[List[str]] = None
    rejectUnknownSni: bool = False  # Server-side
    
    def to_xray_json(self) -> Dict[str, Any]:
        """Convert to Xray format with proper field handling"""
        config = super().to_xray_json()
        
        # Handle certificates properly
        if self.certificates:
            config["certificates"] = [cert.to_xray_json() for cert in self.certificates]
            
        return config


# REALITY Configuration
@dataclass
class REALITYConfig(XrayConfig):
    """REALITY configuration"""
    __xray_type__ = "xray.transport.internet.reality.Config"
    
    # Server-side
    show: bool = False
    dest: Optional[str] = None  # e.g., "example.com:443"
    xver: int = 0
    serverNames: Optional[List[str]] = None
    privateKey: Optional[str] = None
    shortIds: Optional[List[str]] = None
    
    # Client-side
    serverName: Optional[str] = None
    fingerprint: str = "chrome"
    publicKey: Optional[str] = None
    shortId: Optional[str] = None
    spiderX: Optional[str] = None
    
    @classmethod
    def generate_keys(cls) -> Dict[str, str]:
        """Generate REALITY key pair using xray x25519"""
        import subprocess
        try:
            # Use xray x25519 to generate proper keys
            result = subprocess.run(['xray', 'x25519'], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            
            private_key = ""
            public_key = ""
            
            for line in lines:
                if line.startswith('Private key:'):
                    private_key = line.split(': ')[1].strip()
                elif line.startswith('Public key:'):
                    public_key = line.split(': ')[1].strip()
            
            return {
                "privateKey": private_key,
                "publicKey": public_key
            }
        except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
            # Fallback to base64 encoded random bytes (32 bytes for X25519)
            import base64
            private_bytes = secrets.token_bytes(32)
            public_bytes = secrets.token_bytes(32)
            return {
                "privateKey": base64.b64encode(private_bytes).decode().rstrip('='),
                "publicKey": base64.b64encode(public_bytes).decode().rstrip('=')
            }
    
    @classmethod
    def generate_short_id(cls) -> str:
        """Generate random short ID (1-16 hex chars)"""
        # Generate 1-8 bytes (2-16 hex chars)
        length = secrets.randbelow(8) + 1
        return secrets.token_hex(length)


# XTLS Configuration (deprecated but still supported)
@dataclass
class XTLSConfig(XrayConfig):
    """XTLS configuration (legacy)"""
    __xray_type__ = "xray.transport.internet.xtls.Config"
    
    serverName: Optional[str] = None
    allowInsecure: bool = False
    alpn: Optional[List[str]] = None
    minVersion: str = "1.2"
    maxVersion: str = "1.3"
    preferServerCipherSuites: bool = True
    cipherSuites: Optional[str] = None
    certificates: Optional[List[Certificate]] = None
    disableSystemRoot: bool = False
    fingerprint: Optional[str] = None
    rejectUnknownSni: bool = False


# Security factory
def create_tls_config(
    server_name: Optional[str] = None,
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None,
    alpn: Optional[List[str]] = None,
    fingerprint: Optional[str] = None,
    **kwargs
) -> TLSConfig:
    """Create TLS configuration"""
    config = TLSConfig(
        serverName=server_name,
        alpn=alpn or ["h2", "http/1.1"],
        fingerprint=fingerprint,
        **kwargs
    )
    
    if cert_file and key_file:
        config.certificates = [Certificate(
            certificateFile=cert_file,
            keyFile=key_file
        )]
        
    return config


def create_reality_config(
    dest: str,
    server_names: Optional[List[str]] = None,
    private_key: Optional[str] = None,
    short_ids: Optional[List[str]] = None,
    **kwargs
) -> REALITYConfig:
    """Create REALITY configuration for server"""
    if not private_key:
        keys = REALITYConfig.generate_keys()
        private_key = keys["privateKey"]
        
    if not short_ids:
        short_ids = [REALITYConfig.generate_short_id()]
        
    return REALITYConfig(
        show=False,
        dest=dest,
        serverNames=server_names or [dest.split(":")[0]],
        privateKey=private_key,
        shortIds=short_ids,
        **kwargs
    )


def create_reality_client_config(
    server_name: str,
    public_key: str,
    short_id: str,
    fingerprint: str = "chrome",
    **kwargs
) -> REALITYConfig:
    """Create REALITY configuration for client"""
    return REALITYConfig(
        serverName=server_name,
        publicKey=public_key,
        shortId=short_id,
        fingerprint=fingerprint,
        **kwargs
    )


# Certificate generation utilities
def generate_self_signed_certificate(
    common_name: str = "localhost",
    san_list: Optional[List[str]] = None,
    days: int = 365,
    key_size: int = 2048,
    save_to_files: bool = False,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None
) -> Tuple[str, str]:
    """
    Generate self-signed certificate
    
    Args:
        common_name: Certificate common name
        san_list: Subject Alternative Names (domains/IPs)
        days: Certificate validity in days
        key_size: RSA key size
        save_to_files: Whether to save to files
        cert_path: Path to save certificate
        key_path: Path to save private key
        
    Returns:
        Tuple of (certificate_pem, private_key_pem)
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID, ExtensionOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        raise ImportError("cryptography package is required for certificate generation. Install with: pip install cryptography")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # Create certificate subject
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Xray Self-Signed"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    
    # Create certificate builder
    builder = x509.CertificateBuilder()
    builder = builder.subject_name(subject)
    builder = builder.issuer_name(issuer)
    builder = builder.public_key(private_key.public_key())
    builder = builder.serial_number(x509.random_serial_number())
    builder = builder.not_valid_before(datetime.utcnow())
    builder = builder.not_valid_after(datetime.utcnow() + timedelta(days=days))
    
    # Add Subject Alternative Names
    san_list = san_list or [common_name]
    alt_names = []
    for san in san_list:
        if san.replace('.', '').isdigit():  # IP address
            alt_names.append(x509.IPAddress(ipaddress.ip_address(san)))
        else:  # Domain name
            alt_names.append(x509.DNSName(san))
    
    builder = builder.add_extension(
        x509.SubjectAlternativeName(alt_names),
        critical=False,
    )
    
    # Add basic constraints
    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=0),
        critical=True,
    )
    
    # Add key usage
    builder = builder.add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=True,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True,
    )
    
    # Sign certificate
    certificate = builder.sign(private_key, hashes.SHA256(), default_backend())
    
    # Serialize to PEM
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode('utf-8')
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Save to files if requested
    if save_to_files:
        cert_file = cert_path or f"{common_name}_cert.pem"
        key_file = key_path or f"{common_name}_key.pem"
        
        with open(cert_file, 'w') as f:
            f.write(cert_pem)
        
        with open(key_file, 'w') as f:
            f.write(key_pem)
            
        # Set appropriate permissions
        Path(key_file).chmod(0o600)
    
    return cert_pem, key_pem


def create_tls_config_with_self_signed(
    common_name: str = "localhost",
    san_list: Optional[List[str]] = None,
    alpn: Optional[List[str]] = None,
    **tls_kwargs
) -> Tuple[TLSConfig, str, str]:
    """
    Create TLS configuration with self-signed certificate
    
    Returns:
        Tuple of (TLSConfig, certificate_pem, private_key_pem)
    """
    cert_pem, key_pem = generate_self_signed_certificate(
        common_name=common_name,
        san_list=san_list
    )
    
    # Convert PEM to lines for Xray format
    cert_lines = cert_pem.strip().split('\n')
    key_lines = key_pem.strip().split('\n')
    
    # Create certificate config
    certificate = Certificate(
        certificate=cert_lines,
        key=key_lines,
        oneTimeLoading=True
    )
    
    # Create TLS config
    tls_config = TLSConfig(
        serverName=common_name,
        alpn=alpn or ["h2", "http/1.1"],
        certificates=[certificate],
        **tls_kwargs
    )
    
    return tls_config, cert_pem, key_pem


# Add missing import
try:
    import ipaddress
except ImportError:
    ipaddress = None