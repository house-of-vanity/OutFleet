#!/usr/bin/env python3
"""
Let's Encrypt/ZeroSSL Certificate Library with Cloudflare DNS Challenge
Generate publicly trusted SSL certificates using ACME DNS-01 challenge
"""

import time
import logging
from typing import List, Tuple

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from acme import client, messages, challenges, errors
from acme.client import ClientV2
import josepy as jose
from cloudflare import Cloudflare

logger = logging.getLogger(__name__)

class AcmeDnsChallenge:
    """ACME DNS-01 Challenge handler with Cloudflare API"""
    
    def __init__(self, cloudflare_token: str, acme_directory: str = None):
        """
        Initialize ACME DNS challenge handler
        
        Args:
            cloudflare_token: Cloudflare API token with DNS edit permissions
            acme_directory: ACME directory URL (defaults to Let's Encrypt production)
        """
        self.cf_token = cloudflare_token
        self.cf = Cloudflare(api_token=cloudflare_token)
        
        # ACME directory URLs
        self.acme_directories = {
            'letsencrypt': 'https://acme-v02.api.letsencrypt.org/directory',
            'letsencrypt_staging': 'https://acme-staging-v02.api.letsencrypt.org/directory',
            'zerossl': 'https://acme.zerossl.com/v2/DV90'
        }
        
        self.acme_directory = acme_directory or self.acme_directories['letsencrypt']
        self.acme_client = None
        self.account_key = None
        
    def _generate_account_key(self) -> jose.JWKRSA:
        """Generate RSA private key for ACME account"""
        # Generate cryptography key first
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        # Convert to josepy format for ACME
        return jose.JWKRSA(key=private_key)
    
    def _get_zone_id(self, domain: str) -> str:
        """Get Cloudflare zone ID for domain"""
        try:
            # Get base domain (remove subdomains)
            parts = domain.split('.')
            if len(parts) >= 2:
                base_domain = '.'.join(parts[-2:])
            else:
                base_domain = domain
                
            zones = self.cf.zones.list(name=base_domain)
            if not zones.result:
                raise ValueError(f"Domain {base_domain} not found in Cloudflare")
            
            return zones.result[0].id
        except Exception as e:
            logger.error(f"Failed to get zone ID for {domain}: {e}")
            raise
    
    def _create_dns_record(self, domain: str, name: str, content: str) -> str:
        """Create DNS TXT record for ACME challenge"""
        try:
            zone_id = self._get_zone_id(domain)
            
            result = self.cf.dns.records.create(
                zone_id=zone_id,
                name=name,
                type='TXT',
                content=content,
                ttl=60  # 1 minute TTL for faster propagation
            )
            logger.info(f"Created DNS record: {name} = {content}")
            return result.id
            
        except Exception as e:
            logger.error(f"Failed to create DNS record {name}: {e}")
            raise
    
    def _delete_dns_record(self, domain: str, record_id: str):
        """Delete DNS TXT record"""
        try:
            zone_id = self._get_zone_id(domain)
            self.cf.dns.records.delete(zone_id=zone_id, dns_record_id=record_id)
            logger.info(f"Deleted DNS record: {record_id}")
        except Exception as e:
            logger.warning(f"Failed to delete DNS record {record_id}: {e}")
    
    def _wait_for_dns_propagation(self, record_name: str, expected_value: str, wait_time: int = 20):
        """Wait for DNS record to propagate - no local checks, just wait"""
        logger.info(f"Waiting {wait_time} seconds for DNS propagation of {record_name}...")
        logger.info(f"Record value: {expected_value}")
        logger.info("(No local DNS checks - Let's Encrypt servers will verify)")
        
        time.sleep(wait_time)
        
        logger.info("DNS propagation wait completed - proceeding with challenge")
        return True
    
    def create_acme_client(self, email: str, accept_tos: bool = True) -> ClientV2:
        """Create and register ACME client"""
        if self.acme_client:
            return self.acme_client
            
        try:
            logger.info("Generating ACME account key...")
            # Generate account key
            self.account_key = self._generate_account_key()
            logger.info("Account key generated successfully")
            
            logger.info(f"Connecting to ACME directory: {self.acme_directory}")
            # Create ACME client
            net = client.ClientNetwork(self.account_key, user_agent='letsencrypt-dns-lib/1.0')
            logger.info("Getting ACME directory...")
            directory_response = net.get(self.acme_directory)
            logger.info(f"Directory response status: {directory_response.status_code}")
            directory = messages.Directory.from_json(directory_response.json())
            logger.info("ACME directory loaded successfully")
            
            self.acme_client = ClientV2(directory, net=net)
            logger.info("ACME client created successfully")
            
            # Register account
            logger.info(f"Registering ACME account for email: {email}")
            try:
                registration = messages.NewRegistration.from_data(
                    email=email,
                    terms_of_service_agreed=accept_tos
                )
                logger.info("Sending account registration...")
                account = self.acme_client.new_account(registration)
                logger.info(f"ACME account registered: {account.uri}")
                
            except errors.ConflictError as e:
                logger.info(f"Account already exists (ConflictError): {e}")
                # Account already exists
                account = self.acme_client.query_registration(messages.NewRegistration())
                logger.info("Using existing ACME account")
            except Exception as reg_e:
                logger.error(f"Account registration failed: {reg_e}")
                logger.error(f"Registration error type: {type(reg_e).__name__}")
                raise
            
            return self.acme_client
            
        except Exception as e:
            logger.error(f"Failed to create ACME client: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
    
    def request_certificate(self, domains: List[str], email: str, 
                          key_size: int = 2048) -> Tuple[str, str]:
        """
        Request certificate using DNS-01 challenge
        
        Args:
            domains: List of domain names for certificate
            email: Email for ACME account registration
            key_size: RSA key size for certificate
            
        Returns:
            Tuple of (certificate_pem, private_key_pem)
        """
        logger.info(f"Requesting certificate for domains: {domains}")
        
        try:
            # Create ACME client
            logger.info("Creating ACME client...")
            acme_client = self.create_acme_client(email)
            logger.info("ACME client created successfully")
        except Exception as e:
            logger.error(f"Failed to create ACME client: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        try:
            # Generate private key for certificate
            logger.info(f"Generating {key_size}-bit RSA private key...")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            logger.info("Private key generated successfully")
            
            # Create CSR
            logger.info(f"Creating CSR for domains: {domains}")
            csr_obj = x509.CertificateSigningRequestBuilder().subject_name(
                x509.Name([
                    x509.NameAttribute(NameOID.COMMON_NAME, domains[0])
                ])
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(domain) for domain in domains
                ]),
                critical=False
            ).sign(private_key, hashes.SHA256())
            
            # Convert CSR to PEM format for ACME
            csr_pem = csr_obj.public_bytes(serialization.Encoding.PEM)
            logger.info("CSR created successfully")
            
            # Request certificate
            logger.info("Requesting certificate order from ACME...")
            order = acme_client.new_order(csr_pem)
            logger.info(f"Created ACME order: {order.uri}")
        except Exception as e:
            logger.error(f"Failed during CSR/order creation: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Process challenges - collect all challenges first, then create DNS records
        dns_records = []
        challenges_to_answer = []
        
        try:
            # First pass: collect all challenges and create DNS records
            for authorization in order.authorizations:
                domain = authorization.body.identifier.value
                logger.info(f"Processing authorization for: {domain}")
                
                # Find DNS-01 challenge
                dns_challenge = None
                for challenge in authorization.body.challenges:
                    if isinstance(challenge.chall, challenges.DNS01):
                        dns_challenge = challenge
                        break
                
                if not dns_challenge:
                    raise ValueError(f"No DNS-01 challenge found for {domain}")
                
                # Calculate challenge response
                response, validation = dns_challenge.response_and_validation(acme_client.net.key)
                
                # For wildcard domains, use base domain for DNS record
                if domain.startswith('*.'):
                    dns_domain = domain[2:]  # Remove *. prefix
                else:
                    dns_domain = domain
                
                # Create DNS record
                record_name = f"_acme-challenge.{dns_domain}"
                
                # Check if we already created this DNS record
                existing_record = None
                for existing_domain, existing_id, existing_validation in dns_records:
                    if existing_domain == dns_domain:
                        existing_record = (existing_domain, existing_id, existing_validation)
                        break
                
                if existing_record:
                    logger.info(f"DNS record already exists for {dns_domain}, reusing...")
                    record_id = existing_record[1]
                    # Verify the validation value matches
                    if existing_record[2] != validation:
                        logger.warning(f"Validation values differ for {dns_domain}! This may cause issues.")
                else:
                    logger.info(f"Creating DNS record for {dns_domain}...")
                    record_id = self._create_dns_record(dns_domain, record_name, validation)
                    dns_records.append((dns_domain, record_id, validation))
                
                # Store challenge to answer later
                challenges_to_answer.append((dns_challenge, response, domain, dns_domain))
            
            # Wait for DNS propagation once for all records
            if dns_records:
                logger.info(f"Waiting for DNS propagation for {len(dns_records)} DNS records...")
                for dns_domain, record_id, validation in dns_records:
                    record_name = f"_acme-challenge.{dns_domain}"
                    self._wait_for_dns_propagation(record_name, validation)
            
            # Second pass: answer all challenges
            for dns_challenge, response, domain, dns_domain in challenges_to_answer:
                logger.info(f"Responding to DNS challenge for {domain}...")
                challenge_response = acme_client.answer_challenge(dns_challenge, response)
                logger.info(f"Challenge response sent for {domain}")
            
            # Finalize order
            logger.info("Finalizing certificate order...")
            order = acme_client.poll_and_finalize(order)
            
            # Get certificate
            certificate_pem = order.fullchain_pem
            private_key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            logger.info("Certificate obtained successfully!")
            return certificate_pem, private_key_pem
            
        finally:
            # Clean up DNS records
            for dns_domain, record_id, validation in dns_records:
                try:
                    self._delete_dns_record(dns_domain, record_id)
                except Exception as e:
                    logger.warning(f"Failed to cleanup DNS record for {dns_domain}: {e}")

def get_certificate(domains: List[str], email: str, cloudflare_token: str,
                   provider: str = 'letsencrypt', staging: bool = False) -> Tuple[str, str]:
    """
    Simple function to get Let's Encrypt/ZeroSSL certificate
    
    Args:
        domains: List of domains for certificate
        email: Email for ACME registration
        cloudflare_token: Cloudflare API token
        provider: 'letsencrypt' or 'zerossl'
        staging: Use staging environment (for testing)
        
    Returns:
        Tuple of (certificate_pem, private_key_pem)
    """
    # Select ACME directory
    acme_dns = AcmeDnsChallenge(cloudflare_token)
    
    if provider == 'letsencrypt':
        if staging:
            acme_dns.acme_directory = acme_dns.acme_directories['letsencrypt_staging']
        else:
            acme_dns.acme_directory = acme_dns.acme_directories['letsencrypt']
    elif provider == 'zerossl':
        acme_dns.acme_directory = acme_dns.acme_directories['zerossl']
    else:
        raise ValueError("Provider must be 'letsencrypt' or 'zerossl'")
    
    return acme_dns.request_certificate(domains, email)

def get_certificate_for_domain(domain: str, email: str, cloudflare_token: str,
                              include_wildcard: bool = False, **kwargs) -> Tuple[str, str]:
    """
    Helper function to get certificate for single domain (compatible with Cloudflare cert lib)
    
    Args:
        domain: Primary domain
        email: Email for ACME registration  
        cloudflare_token: Cloudflare API token
        include_wildcard: Include wildcard subdomain
        **kwargs: Additional arguments (provider, staging)
        
    Returns:
        Tuple of (certificate_pem, private_key_pem)
    """
    domains = [domain]
    if include_wildcard:
        domains.append(f"*.{domain}")
    
    return get_certificate(domains, email, cloudflare_token, **kwargs)

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) != 4:
        print("Usage: python letsencrypt_dns.py <domain> <email> <cloudflare_token>")
        sys.exit(1)
    
    domain, email, token = sys.argv[1:4]
    
    try:
        cert_pem, key_pem = get_certificate_for_domain(
            domain=domain,
            email=email,
            cloudflare_token=token,
            include_wildcard=True,
            staging=True  # Use staging for testing
        )
        
        print(f"Certificate obtained for {domain}")
        print(f"Certificate length: {len(cert_pem)} bytes")
        print(f"Private key length: {len(key_pem)} bytes")
        
        # Save to files
        with open(f"{domain}.crt", 'w') as f:
            f.write(cert_pem)
        with open(f"{domain}.key", 'w') as f:
            f.write(key_pem)
        
        print(f"Saved: {domain}.crt, {domain}.key")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)