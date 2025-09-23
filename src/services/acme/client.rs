use instant_acme::{
    Account, AuthorizationStatus, ChallengeType, Identifier, NewAccount, NewOrder, OrderStatus,
};
use rcgen::{CertificateParams, DistinguishedName, KeyPair};
use std::time::{Duration, Instant};
use tokio::time::sleep;
use tracing::{debug, info, warn};

use crate::services::acme::{CloudflareClient, AcmeError};

pub struct AcmeClient {
    cloudflare: CloudflareClient,
    account: Account,
    directory_url: String,
}

impl AcmeClient {
    pub async fn new(
        cloudflare_token: String,
        email: &str,
        directory_url: String,
    ) -> Result<Self, AcmeError> {
        info!("Creating ACME client for directory: {}", directory_url);
        
        let cloudflare = CloudflareClient::new(cloudflare_token)?;

        // Create Let's Encrypt account
        info!("Creating Let's Encrypt account for: {}", email);
        let (account, _credentials) = Account::builder()
            .map_err(|e| AcmeError::AccountCreation(e.to_string()))?
            .create(
                &NewAccount {
                    contact: &[&format!("mailto:{}", email)],
                    terms_of_service_agreed: true,
                    only_return_existing: false,
                },
                directory_url.clone(),
                None,
            )
            .await
            .map_err(|e| AcmeError::AccountCreation(e.to_string()))?;

        Ok(Self {
            cloudflare,
            account,
            directory_url,
        })
    }

    pub async fn get_certificate(&mut self, domain: &str, base_domain: &str) -> Result<(String, String), AcmeError> {
        info!("Starting certificate request for domain: {}", domain);

        // Validate domain
        if domain.is_empty() || base_domain.is_empty() {
            return Err(AcmeError::InvalidDomain("Domain cannot be empty".to_string()));
        }

        // Create a new order
        let identifiers = vec![Identifier::Dns(domain.to_string())];
        let mut order = self.account
            .new_order(&NewOrder::new(&identifiers))
            .await
            .map_err(|e| AcmeError::OrderCreation(e.to_string()))?;

        debug!("Created order");

        // Process authorizations
        let mut authorizations = order.authorizations();
        
        while let Some(authz_result) = authorizations.next().await {
            let mut authz = authz_result
                .map_err(|e| AcmeError::Challenge(e.to_string()))?;
            
            let identifier = format!("{:?}", authz.identifier());
            
            if authz.status == AuthorizationStatus::Valid {
                info!("Authorization already valid for: {:?}", identifier);
                continue;
            }

            // Get challenge value and record ID first
            let (challenge_value, record_id) = {
                // Find DNS challenge
                let mut challenge = authz
                    .challenge(ChallengeType::Dns01)
                    .ok_or_else(|| AcmeError::Challenge("No DNS challenge found".to_string()))?;

                info!("Processing DNS challenge for: {:?}", identifier);

                // Get challenge value - use key authorization from challenge
                let challenge_value = challenge.key_authorization().dns_value();
                debug!("Challenge value: {}", challenge_value);

                // Create DNS record
                let challenge_domain = format!("_acme-challenge.{}", domain);
                let record_id = self.cloudflare
                    .create_txt_record(base_domain, &challenge_domain, &challenge_value)
                    .await?;

                info!("Created DNS TXT record, waiting for propagation...");

                // Wait for DNS propagation
                self.wait_for_dns_propagation(&challenge_domain, &challenge_value)
                    .await?;

                // Submit challenge
                info!("Submitting challenge...");
                challenge.set_ready().await
                    .map_err(|e| AcmeError::Challenge(e.to_string()))?;
                
                (challenge_value, record_id)
            };

            // Wait for challenge completion
            info!("Waiting for challenge validation (5 seconds)...");
            sleep(Duration::from_secs(5)).await;

            // Cleanup DNS record
            self.cleanup_dns_record(base_domain, &record_id).await;
        }

        // Wait for order to be ready
        info!("Waiting for order to be ready...");
        let start = Instant::now();
        let timeout = Duration::from_secs(300);

        loop {
            if start.elapsed() > timeout {
                return Err(AcmeError::Challenge("Order processing timeout".to_string()));
            }

            order.refresh().await
                .map_err(|e| AcmeError::OrderCreation(e.to_string()))?;

            match order.state().status {
                OrderStatus::Ready => {
                    info!("Order is ready for finalization");
                    break;
                }
                OrderStatus::Invalid => {
                    return Err(AcmeError::Challenge("Order became invalid".to_string()));
                }
                OrderStatus::Pending => {
                    debug!("Order still pending, waiting...");
                    sleep(Duration::from_secs(5)).await;
                }
                _ => {
                    debug!("Order status: {:?}", order.state().status);
                    sleep(Duration::from_secs(5)).await;
                }
            }
        }

        // Generate CSR
        info!("Generating certificate signing request...");
        let mut params = CertificateParams::new(vec![domain.to_string()]);
        
        params.distinguished_name = DistinguishedName::new();
        
        let key_pair = KeyPair::generate(&rcgen::PKCS_ECDSA_P256_SHA256)
            .map_err(|e| AcmeError::CertificateGeneration(e.to_string()))?;
        
        // Set the key pair for CSR generation
        params.key_pair = Some(key_pair);
        
        // Generate CSR using rcgen certificate
        let cert = rcgen::Certificate::from_params(params)
            .map_err(|e| AcmeError::CertificateGeneration(e.to_string()))?;
        let csr_der = cert.serialize_request_der()
            .map_err(|e| AcmeError::CertificateGeneration(e.to_string()))?;

        // Finalize order with CSR
        info!("Finalizing order with CSR...");
        order.finalize_csr(&csr_der).await
            .map_err(|e| AcmeError::CertificateGeneration(e.to_string()))?;
        
        // Wait for certificate to be ready
        info!("Waiting for certificate to be generated...");
        let start = Instant::now();
        let timeout = Duration::from_secs(300); // 5 minutes
        
        let cert_chain_pem = loop {
            if start.elapsed() > timeout {
                return Err(AcmeError::CertificateGeneration("Certificate generation timeout".to_string()));
            }

            order.refresh().await
                .map_err(|e| AcmeError::CertificateGeneration(e.to_string()))?;

            match order.state().status {
                OrderStatus::Valid => {
                    info!("Certificate is ready!");
                    break order.certificate().await
                        .map_err(|e| AcmeError::CertificateGeneration(e.to_string()))?
                        .ok_or_else(|| AcmeError::CertificateGeneration("Certificate not available".to_string()))?;
                }
                OrderStatus::Invalid => {
                    return Err(AcmeError::CertificateGeneration("Order became invalid during certificate generation".to_string()));
                }
                OrderStatus::Processing => {
                    debug!("Certificate still being processed, waiting...");
                    sleep(Duration::from_secs(3)).await;
                }
                _ => {
                    debug!("Waiting for certificate, order status: {:?}", order.state().status);
                    sleep(Duration::from_secs(3)).await;
                }
            }
        };

        let private_key_pem = cert.serialize_private_key_pem();

        info!("Certificate successfully obtained!");
        Ok((cert_chain_pem, private_key_pem))
    }

    async fn wait_for_dns_propagation(&self, record_name: &str, expected_value: &str) -> Result<(), AcmeError> {
        info!("Checking DNS propagation for: {}", record_name);
        
        let start = Instant::now();
        let timeout = Duration::from_secs(120); // 2 minutes
        
        while start.elapsed() < timeout {
            match self.check_dns_txt_record(record_name, expected_value).await {
                Ok(true) => {
                    info!("DNS propagation confirmed");
                    return Ok(());
                }
                Ok(false) => {
                    debug!("DNS not yet propagated, waiting...");
                }
                Err(e) => {
                    debug!("DNS check failed: {:?}", e);
                }
            }
            
            sleep(Duration::from_secs(10)).await;
        }
        
        warn!("DNS propagation timeout, but continuing anyway");
        Ok(())
    }

    async fn check_dns_txt_record(&self, record_name: &str, expected_value: &str) -> Result<bool, AcmeError> {
        use std::process::Command;
        
        let output = Command::new("dig")
            .args(&["+short", "TXT", record_name])
            .output()
            .map_err(|e| AcmeError::Io(e))?;

        if !output.status.success() {
            return Err(AcmeError::Challenge("dig command failed".to_string()));
        }

        let stdout = String::from_utf8(output.stdout)
            .map_err(|_| AcmeError::Challenge("Invalid UTF-8 in dig output".to_string()))?;

        // Parse TXT record (remove quotes)
        for line in stdout.lines() {
            let cleaned = line.trim().trim_matches('"');
            if cleaned == expected_value {
                return Ok(true);
            }
        }

        Ok(false)
    }

    async fn cleanup_dns_record(&self, base_domain: &str, record_id: &str) {
        if let Err(e) = self.cloudflare.delete_txt_record(base_domain, record_id).await {
            warn!("Failed to cleanup DNS record {}: {:?}", record_id, e);
        }
    }

    /// Get the base domain from a full domain (e.g., "api.example.com" -> "example.com")
    pub fn get_base_domain(domain: &str) -> Result<String, AcmeError> {
        let parts: Vec<&str> = domain.split('.').collect();
        if parts.len() < 2 {
            return Err(AcmeError::InvalidDomain("Domain must have at least 2 parts".to_string()));
        }
        
        // Take the last two parts for base domain
        let base_domain = format!("{}.{}", parts[parts.len() - 2], parts[parts.len() - 1]);
        Ok(base_domain)
    }
}