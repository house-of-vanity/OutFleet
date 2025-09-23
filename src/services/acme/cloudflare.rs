use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, info};

use crate::services::acme::error::AcmeError;

#[derive(Debug, Serialize, Deserialize)]
struct CloudflareZone {
    id: String,
    name: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct CloudflareZonesResponse {
    result: Vec<CloudflareZone>,
    success: bool,
    errors: Option<Vec<CloudflareApiError>>,
}

#[derive(Debug, Serialize, Deserialize)]
struct CloudflareDnsRecord {
    id: String,
    #[serde(rename = "type")]
    record_type: String,
    name: String,
    content: String,
    ttl: u32,
    proxied: bool,
}

#[derive(Debug, Serialize, Deserialize)]
struct CloudflareDnsRecordsResponse {
    result: Vec<CloudflareDnsRecord>,
    success: bool,
    errors: Option<Vec<CloudflareApiError>>,
}

#[derive(Debug, Serialize)]
struct CreateDnsRecordRequest {
    #[serde(rename = "type")]
    record_type: String,
    name: String,
    content: String,
    ttl: u32,
}

#[derive(Debug, Serialize, Deserialize)]
struct CreateDnsRecordResponse {
    result: CloudflareDnsRecord,
    success: bool,
    errors: Option<Vec<CloudflareApiError>>,
}

#[derive(Debug, Serialize, Deserialize)]
struct CloudflareApiError {
    code: u32,
    message: String,
}

pub struct CloudflareClient {
    client: reqwest::Client,
    api_token: String,
}

impl CloudflareClient {
    pub fn new(api_token: String) -> Result<Self, AcmeError> {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .map_err(|e| AcmeError::HttpRequest(e))?;

        Ok(Self { client, api_token })
    }

    async fn get_zone_id(&self, domain: &str) -> Result<String, AcmeError> {
        info!("Getting Cloudflare zone ID for domain: {}", domain);
        
        let url = format!("https://api.cloudflare.com/client/v4/zones?name={}", domain);
        
        let response = self.client
            .get(&url)
            .header("Authorization", format!("Bearer {}", self.api_token))
            .header("Content-Type", "application/json")
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AcmeError::CloudflareApi(format!("HTTP {}: {}", status, body)));
        }

        let zones: CloudflareZonesResponse = response.json().await?;

        if !zones.success {
            let errors = zones.errors.unwrap_or_default();
            let error_messages: Vec<String> = errors.iter().map(|e| e.message.clone()).collect();
            return Err(AcmeError::CloudflareApi(format!("API errors: {}", error_messages.join(", "))));
        }

        zones.result
            .into_iter()
            .find(|z| z.name == domain)
            .map(|z| z.id)
            .ok_or_else(|| AcmeError::CloudflareApi(format!("Zone not found for domain: {}", domain)))
    }

    pub async fn create_txt_record(&self, domain: &str, record_name: &str, content: &str) -> Result<String, AcmeError> {
        let zone_id = self.get_zone_id(domain).await?;
        info!("Creating TXT record {} in zone {}", record_name, domain);

        let request = CreateDnsRecordRequest {
            record_type: "TXT".to_string(),
            name: record_name.to_string(),
            content: content.to_string(),
            ttl: 120, // 2 minutes TTL for quick propagation
        };

        let url = format!("https://api.cloudflare.com/client/v4/zones/{}/dns_records", zone_id);

        let response = self.client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_token))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AcmeError::CloudflareApi(format!("Failed to create DNS record ({}): {}", status, body)));
        }

        let result: CreateDnsRecordResponse = response.json().await?;

        if !result.success {
            let errors = result.errors.unwrap_or_default();
            let error_messages: Vec<String> = errors.iter().map(|e| e.message.clone()).collect();
            return Err(AcmeError::CloudflareApi(format!("Failed to create record: {}", error_messages.join(", "))));
        }

        debug!("Created DNS record with ID: {}", result.result.id);
        Ok(result.result.id)
    }

    pub async fn delete_txt_record(&self, domain: &str, record_id: &str) -> Result<(), AcmeError> {
        let zone_id = self.get_zone_id(domain).await?;
        info!("Deleting TXT record {} from zone {}", record_id, domain);

        let url = format!("https://api.cloudflare.com/client/v4/zones/{}/dns_records/{}", zone_id, record_id);

        let response = self.client
            .delete(&url)
            .header("Authorization", format!("Bearer {}", self.api_token))
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AcmeError::CloudflareApi(format!("Failed to delete DNS record ({}): {}", status, body)));
        }

        info!("Successfully deleted DNS record");
        Ok(())
    }

    pub async fn find_txt_record(&self, domain: &str, record_name: &str) -> Result<Option<String>, AcmeError> {
        let zone_id = self.get_zone_id(domain).await?;
        
        let url = format!(
            "https://api.cloudflare.com/client/v4/zones/{}/dns_records?type=TXT&name={}",
            zone_id, record_name
        );

        let response = self.client
            .get(&url)
            .header("Authorization", format!("Bearer {}", self.api_token))
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AcmeError::CloudflareApi(format!("Failed to list DNS records ({}): {}", status, body)));
        }

        let records: CloudflareDnsRecordsResponse = response.json().await?;

        if !records.success {
            let errors = records.errors.unwrap_or_default();
            let error_messages: Vec<String> = errors.iter().map(|e| e.message.clone()).collect();
            return Err(AcmeError::CloudflareApi(format!("Failed to list records: {}", error_messages.join(", "))));
        }

        Ok(records.result.first().map(|r| r.id.clone()))
    }
}