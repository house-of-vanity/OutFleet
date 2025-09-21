use rcgen::{Certificate, CertificateParams, DistinguishedName, DnType, SanType, KeyPair, PKCS_ECDSA_P256_SHA256};
use std::net::IpAddr;
use time::{Duration, OffsetDateTime};

/// Certificate management service
#[derive(Clone)]
pub struct CertificateService {
}

#[allow(dead_code)]
impl CertificateService {
    pub fn new() -> Self {
        Self {}
    }

    /// Generate self-signed certificate optimized for Xray
    pub async fn generate_self_signed(&self, domain: &str) -> anyhow::Result<(String, String)> {
        tracing::info!("Generating self-signed certificate for domain: {}", domain);
        
        // Create certificate parameters with ECDSA (recommended for Xray)
        let mut params = CertificateParams::new(vec![domain.to_string()]);
        
        // Use ECDSA P-256 which is recommended for Xray (equivalent to RSA-3072 in strength)
        params.alg = &PKCS_ECDSA_P256_SHA256;
        
        // Generate ECDSA key pair
        let key_pair = KeyPair::generate(&PKCS_ECDSA_P256_SHA256)?;
        params.key_pair = Some(key_pair);
        
        // Set certificate subject with proper fields
        let mut distinguished_name = DistinguishedName::new();
        distinguished_name.push(DnType::CommonName, domain);
        distinguished_name.push(DnType::OrganizationName, "OutFleet");
        distinguished_name.push(DnType::OrganizationalUnitName, "VPN");
        distinguished_name.push(DnType::CountryName, "US");
        distinguished_name.push(DnType::StateOrProvinceName, "State");
        distinguished_name.push(DnType::LocalityName, "City");
        params.distinguished_name = distinguished_name;
        
        // Add comprehensive Subject Alternative Names for better compatibility
        let mut san_list = vec![
            SanType::DnsName(domain.to_string()),
            SanType::DnsName("localhost".to_string()),
        ];
        
        // Add IP addresses if domain looks like an IP
        if let Ok(ip) = domain.parse::<IpAddr>() {
            san_list.push(SanType::IpAddress(ip));
        }
        
        // Always add localhost IP for local testing
        san_list.push(SanType::IpAddress(IpAddr::V4(std::net::Ipv4Addr::new(127, 0, 0, 1))));
        
        // If domain is not an IP, also add wildcard subdomain
        if domain.parse::<IpAddr>().is_err() && !domain.starts_with("*.") {
            san_list.push(SanType::DnsName(format!("*.{}", domain)));
        }
        
        params.subject_alt_names = san_list;
        
        // Set validity period (1 year as recommended)
        params.not_before = OffsetDateTime::now_utc();
        params.not_after = OffsetDateTime::now_utc() + Duration::days(365);
        
        // Set serial number
        params.serial_number = Some(rcgen::SerialNumber::from_slice(&[1, 2, 3, 4]));
        
        // Generate certificate
        let cert = Certificate::from_params(params)?;
        
        // Get PEM format with proper formatting
        let cert_pem = cert.serialize_pem()?;
        let key_pem = cert.serialize_private_key_pem();
        
        // Validate PEM format
        if !cert_pem.starts_with("-----BEGIN CERTIFICATE-----") || !cert_pem.ends_with("-----END CERTIFICATE-----\n") {
            return Err(anyhow::anyhow!("Invalid certificate PEM format"));
        }
        
        if !key_pem.starts_with("-----BEGIN") || !key_pem.contains("PRIVATE KEY-----") {
            return Err(anyhow::anyhow!("Invalid private key PEM format"));
        }
        
        tracing::debug!("Generated ECDSA P-256 certificate for domain: {}", domain);
        
        Ok((cert_pem, key_pem))
    }


    /// Renew certificate
    pub async fn renew_certificate(&self, domain: &str) -> anyhow::Result<(String, String)> {
        tracing::info!("Renewing certificate for domain: {}", domain);
        
        // For now, just generate a new self-signed certificate
        self.generate_self_signed(domain).await
    }
}

impl Default for CertificateService {
    fn default() -> Self {
        Self::new()
    }
}