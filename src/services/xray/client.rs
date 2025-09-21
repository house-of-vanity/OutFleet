use anyhow::{Result, anyhow};
use serde_json::Value;
use xray_core::Client;
use std::sync::Arc;

// Import submodules from the same directory
use super::stats::StatsClient;
use super::inbounds::InboundClient;
use super::users::UserClient;

/// Xray gRPC client wrapper
#[derive(Clone)]
pub struct XrayClient {
    endpoint: String,
    client: Arc<Client>,
}

#[allow(dead_code)]
impl XrayClient {
    /// Connect to Xray gRPC server
    pub async fn connect(endpoint: &str) -> Result<Self> {
        let client = Client::from_url(endpoint).await
            .map_err(|e| anyhow!("Failed to connect to Xray at {}: {}", endpoint, e))?;

        // Don't clone - we'll use &self.client when calling methods

        Ok(Self {
            endpoint: endpoint.to_string(),
            client: Arc::new(client),
        })
    }

    /// Get server statistics
    pub async fn get_stats(&self) -> Result<Value> {
        let stats_client = StatsClient::new(self.endpoint.clone(), &*self.client);
        stats_client.get_stats().await
    }

    /// Query specific statistics with pattern
    pub async fn query_stats(&self, pattern: &str, reset: bool) -> Result<Value> {
        let stats_client = StatsClient::new(self.endpoint.clone(), &*self.client);
        stats_client.query_stats(pattern, reset).await
    }

    /// Restart Xray with new configuration
    pub async fn restart_with_config(&self, config: &crate::services::xray::XrayConfig) -> Result<()> {
        let inbound_client = InboundClient::new(self.endpoint.clone(), &*self.client);
        inbound_client.restart_with_config(config).await
    }

    /// Add inbound configuration
    pub async fn add_inbound(&self, inbound: &Value) -> Result<()> {
        let inbound_client = InboundClient::new(self.endpoint.clone(), &*self.client);
        inbound_client.add_inbound(inbound).await
    }

    /// Add inbound configuration with TLS certificate
    pub async fn add_inbound_with_certificate(&self, inbound: &Value, cert_pem: Option<&str>, key_pem: Option<&str>) -> Result<()> {
        let inbound_client = InboundClient::new(self.endpoint.clone(), &*self.client);
        inbound_client.add_inbound_with_certificate(inbound, None, cert_pem, key_pem).await
    }

    /// Add inbound configuration with users and TLS certificate
    pub async fn add_inbound_with_users_and_certificate(&self, inbound: &Value, users: &[Value], cert_pem: Option<&str>, key_pem: Option<&str>) -> Result<()> {
        let inbound_client = InboundClient::new(self.endpoint.clone(), &*self.client);
        inbound_client.add_inbound_with_certificate(inbound, Some(users), cert_pem, key_pem).await
    }

    /// Remove inbound by tag
    pub async fn remove_inbound(&self, tag: &str) -> Result<()> {
        let inbound_client = InboundClient::new(self.endpoint.clone(), &*self.client);
        inbound_client.remove_inbound(tag).await
    }

    /// Add user to inbound
    pub async fn add_user(&self, inbound_tag: &str, user: &Value) -> Result<()> {
        let user_client = UserClient::new(self.endpoint.clone(), &*self.client);
        user_client.add_user(inbound_tag, user).await
    }

    /// Remove user from inbound
    pub async fn remove_user(&self, inbound_tag: &str, email: &str) -> Result<()> {
        let user_client = UserClient::new(self.endpoint.clone(), &*self.client);
        user_client.remove_user(inbound_tag, email).await
    }

    /// Get connection endpoint
    pub fn endpoint(&self) -> &str {
        &self.endpoint
    }
}