use rcgen::{Certificate, CertificateParams, DistinguishedName, DnType, SanType, KeyPair, PKCS_ECDSA_P256_SHA256};
use std::net::IpAddr;
use time::{Duration, OffsetDateTime};
use uuid::Uuid;

use crate::database::repository::DnsProviderRepository;
use crate::database::entities::dns_provider::DnsProviderType;
use crate::services::acme::{AcmeClient, AcmeError};
use sea_orm::DatabaseConnection;

/// Certificate management service
#[derive(Clone)]
pub struct CertificateService {
    db: Option<DatabaseConnection>,
}

#[allow(dead_code)]
impl CertificateService {
    pub fn new() -> Self {
        Self { db: None }
    }
    
    pub fn with_db(db: DatabaseConnection) -> Self {
        Self { db: Some(db) }
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


    /// Generate Let's Encrypt certificate using DNS challenge
    pub async fn generate_letsencrypt_certificate(
        &self,
        domain: &str,
        dns_provider_id: Uuid,
        acme_email: &str,
        staging: bool,
    ) -> Result<(String, String), AcmeError> {
        tracing::info!("Generating Let's Encrypt certificate for domain: {} using DNS challenge", domain);
        
        // Get database connection
        let db = self.db.as_ref()
            .ok_or_else(|| AcmeError::DnsProviderNotFound)?;
        
        // Get DNS provider
        let dns_repo = DnsProviderRepository::new(db.clone());
        let dns_provider = dns_repo.find_by_id(dns_provider_id)
            .await
            .map_err(|_| AcmeError::DnsProviderNotFound)?
            .ok_or_else(|| AcmeError::DnsProviderNotFound)?;
        
        // Verify provider is Cloudflare (only supported provider for now)
        if dns_provider.provider_type != DnsProviderType::Cloudflare.as_str() {
            return Err(AcmeError::CloudflareApi("Only Cloudflare provider is supported".to_string()));
        }
        
        if !dns_provider.is_active {
            return Err(AcmeError::DnsProviderNotFound);
        }
        
        // Determine ACME directory URL
        let directory_url = if staging {
            "https://acme-staging-v02.api.letsencrypt.org/directory"
        } else {
            "https://acme-v02.api.letsencrypt.org/directory"
        };
        
        // Create ACME client
        let mut acme_client = AcmeClient::new(
            dns_provider.api_token.clone(),
            acme_email,
            directory_url.to_string(),
        ).await?;
        
        // Get base domain for DNS operations
        let base_domain = AcmeClient::get_base_domain(domain)?;
        
        // Generate certificate
        let (cert_pem, key_pem) = acme_client
            .get_certificate(domain, &base_domain)
            .await?;
        
        tracing::info!("Successfully generated Let's Encrypt certificate for domain: {}", domain);
        Ok((cert_pem, key_pem))
    }

    /// Renew certificate by ID (used for manual renewal)
    pub async fn renew_certificate_by_id(&self, cert_id: Uuid) -> anyhow::Result<(String, String)> {
        let db = self.db.as_ref()
            .ok_or_else(|| anyhow::anyhow!("Database connection not available"))?;
        
        // Get the certificate from database
        let cert_repo = crate::database::repository::CertificateRepository::new(db.clone());
        let certificate = cert_repo.find_by_id(cert_id)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Certificate not found"))?;
        
        tracing::info!("Renewing certificate '{}' for domain: {}", certificate.name, certificate.domain);
        
        match certificate.cert_type.as_str() {
            "letsencrypt" => {
                // For Let's Encrypt, we need to regenerate using ACME
                // Find an active Cloudflare DNS provider
                let dns_repo = crate::database::repository::DnsProviderRepository::new(db.clone());
                let providers = dns_repo.find_active_by_type("cloudflare").await?;
                
                if providers.is_empty() {
                    return Err(anyhow::anyhow!("No active Cloudflare DNS provider found for Let's Encrypt renewal"));
                }
                
                let dns_provider = &providers[0];
                let acme_email = "admin@example.com"; // TODO: Store this with certificate
                
                // Generate new certificate
                let (cert_pem, key_pem) = self.generate_letsencrypt_certificate(
                    &certificate.domain,
                    dns_provider.id,
                    acme_email,
                    false, // Production
                ).await?;
                
                // Update in database
                cert_repo.update_certificate_data(
                    cert_id,
                    &cert_pem,
                    &key_pem,
                    chrono::Utc::now() + chrono::Duration::days(90),
                ).await?;
                
                Ok((cert_pem, key_pem))
            }
            "self_signed" => {
                // For self-signed, generate a new one
                let (cert_pem, key_pem) = self.generate_self_signed(&certificate.domain).await?;
                
                // Update in database
                cert_repo.update_certificate_data(
                    cert_id,
                    &cert_pem,
                    &key_pem,
                    chrono::Utc::now() + chrono::Duration::days(365),
                ).await?;
                
                Ok((cert_pem, key_pem))
            }
            _ => {
                Err(anyhow::anyhow!("Cannot renew imported certificates automatically"))
            }
        }
    }

    /// Renew certificate (legacy method for backward compatibility)
    pub async fn renew_certificate(&self, domain: &str) -> anyhow::Result<(String, String)> {
        tracing::info!("Renewing certificate for domain: {}", domain);
        
        // For backward compatibility, just generate a new self-signed certificate
        self.generate_self_signed(domain).await
    }
}

impl Default for CertificateService {
    fn default() -> Self {
        Self::new()
    }
}