"""
Utility functions for Xray Manager.
"""

import uuid
import base64
import secrets
from typing import List
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime


def generate_uuid() -> str:
    """Generate a random UUID for VLESS/VMess users."""
    return str(uuid.uuid4())




def generate_self_signed_cert(hostname: str = "localhost") -> tuple[str, str]:
    """
    Generate self-signed certificate for Trojan.
    
    Args:
        hostname: Common name for certificate
        
    Returns:
        Tuple of (certificate_pem, private_key_pem)
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(hostname),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256())
    
    # Convert to PEM format
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    return cert_pem.decode(), key_pem.decode()


def pem_to_lines(pem_data: str) -> List[str]:
    """Convert PEM data to list of lines for Xray JSON format."""
    return pem_data.strip().split('\n')