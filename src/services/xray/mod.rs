use anyhow::Result;
use serde_json::Value;
use uuid::Uuid;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{Duration, Instant};

pub mod client;
pub mod config;
pub mod stats;
pub mod inbounds;
pub mod users;

pub use client::XrayClient;
pub use config::XrayConfig;

/// Service for managing Xray servers via gRPC
#[derive(Clone)]
pub struct XrayService {}

#[allow(dead_code)]
impl XrayService {
    pub fn new() -> Self {
        Self {}
    }

    /// Create a client for the specified server
    async fn create_client(&self, endpoint: &str) -> Result<XrayClient> {
        XrayClient::connect(endpoint).await
    }

    /// Test connection to Xray server
    pub async fn test_connection(&self, _server_id: Uuid, endpoint: &str) -> Result<bool> {
        match self.create_client(endpoint).await {
            Ok(_client) => {
                // Instead of getting stats (which might fail), just test connection
                // If we successfully created the client, connection is working
                Ok(true)
            },
            Err(_) => Ok(false),
        }
    }

    /// Apply full configuration to Xray server
    pub async fn apply_config(&self, _server_id: Uuid, endpoint: &str, config: &XrayConfig) -> Result<()> {
        let client = self.create_client(endpoint).await?;
        client.restart_with_config(config).await
    }

    /// Create inbound from template
    pub async fn create_inbound(
        &self,
        _server_id: Uuid,
        endpoint: &str,
        tag: &str,
        port: i32,
        protocol: &str,
        base_settings: Value,
        stream_settings: Value,
    ) -> Result<()> {
        // Build inbound configuration from template
        let inbound_config = serde_json::json!({
            "tag": tag,
            "port": port,
            "protocol": protocol,
            "settings": base_settings,
            "streamSettings": stream_settings
        });
        
        self.add_inbound(_server_id, endpoint, &inbound_config).await
    }

    /// Create inbound from template with TLS certificate
    pub async fn create_inbound_with_certificate(
        &self,
        _server_id: Uuid,
        endpoint: &str,
        tag: &str,
        port: i32,
        protocol: &str,
        base_settings: Value,
        stream_settings: Value,
        cert_pem: Option<&str>,
        key_pem: Option<&str>,
    ) -> Result<()> {
        // Build inbound configuration from template
        let inbound_config = serde_json::json!({
            "tag": tag,
            "port": port,
            "protocol": protocol,
            "settings": base_settings,
            "streamSettings": stream_settings
        });
        
        self.add_inbound_with_certificate(_server_id, endpoint, &inbound_config, cert_pem, key_pem).await
    }

    /// Add inbound to running Xray instance
    pub async fn add_inbound(&self, _server_id: Uuid, endpoint: &str, inbound: &Value) -> Result<()> {
        let client = self.create_client(endpoint).await?;
        client.add_inbound(inbound).await
    }

    /// Add inbound with certificate to running Xray instance
    pub async fn add_inbound_with_certificate(&self, _server_id: Uuid, endpoint: &str, inbound: &Value, cert_pem: Option<&str>, key_pem: Option<&str>) -> Result<()> {
        let client = self.create_client(endpoint).await?;
        client.add_inbound_with_certificate(inbound, cert_pem, key_pem).await
    }

    /// Add inbound with users and certificate to running Xray instance
    pub async fn add_inbound_with_users_and_certificate(&self, _server_id: Uuid, endpoint: &str, inbound: &Value, users: &[Value], cert_pem: Option<&str>, key_pem: Option<&str>) -> Result<()> {
        let client = self.create_client(endpoint).await?;
        client.add_inbound_with_users_and_certificate(inbound, users, cert_pem, key_pem).await
    }

    /// Remove inbound from running Xray instance
    pub async fn remove_inbound(&self, _server_id: Uuid, endpoint: &str, tag: &str) -> Result<()> {
        let client = self.create_client(endpoint).await?;
        client.remove_inbound(tag).await
    }

    /// Add user to inbound by recreating the inbound with updated user list
    pub async fn add_user(&self, _server_id: Uuid, endpoint: &str, inbound_tag: &str, user: &Value) -> Result<()> {
        
        // TODO: Implement inbound recreation approach:
        // 1. Get current inbound configuration from database
        // 2. Get existing users from database  
        // 3. Remove old inbound from xray
        // 4. Create new inbound with all users (existing + new)
        // For now, return error to indicate this needs to be implemented
        
        Err(anyhow::anyhow!("User addition requires inbound recreation - not yet implemented. Use web interface to recreate inbound with users."))
    }

    /// Create inbound with users list (for inbound recreation approach)
    pub async fn create_inbound_with_users(
        &self,
        _server_id: Uuid,
        endpoint: &str,
        tag: &str,
        port: i32,
        protocol: &str,
        base_settings: Value,
        stream_settings: Value,
        users: &[Value],
        cert_pem: Option<&str>,
        key_pem: Option<&str>,
    ) -> Result<()> {
        
        // Build inbound configuration with users
        let mut inbound_config = serde_json::json!({
            "tag": tag,
            "port": port,
            "protocol": protocol,
            "settings": base_settings,
            "streamSettings": stream_settings
        });
        
        // Add users to settings based on protocol
        if !users.is_empty() {
            let mut settings = inbound_config["settings"].clone();
            match protocol {
                "vless" | "vmess" => {
                    settings["clients"] = serde_json::Value::Array(users.to_vec());
                },
                "trojan" => {
                    settings["clients"] = serde_json::Value::Array(users.to_vec());
                },
                "shadowsocks" => {
                    // For shadowsocks, users are handled differently
                    if let Some(user) = users.first() {
                        settings["password"] = user["password"].clone();
                    }
                },
                _ => {
                    return Err(anyhow::anyhow!("Unsupported protocol for users: {}", protocol));
                }
            }
            inbound_config["settings"] = settings;
        }
        
        
        // Use the new method with users support
        self.add_inbound_with_users_and_certificate(_server_id, endpoint, &inbound_config, users, cert_pem, key_pem).await
    }

    /// Remove user from inbound
    pub async fn remove_user(&self, _server_id: Uuid, endpoint: &str, inbound_tag: &str, email: &str) -> Result<()> {
        let client = self.create_client(endpoint).await?;
        client.remove_user(inbound_tag, email).await
    }

    /// Get server statistics
    pub async fn get_stats(&self, _server_id: Uuid, endpoint: &str) -> Result<Value> {
        let client = self.create_client(endpoint).await?;
        client.get_stats().await
    }

    /// Query specific statistics
    pub async fn query_stats(&self, _server_id: Uuid, endpoint: &str, pattern: &str, reset: bool) -> Result<Value> {
        let client = self.create_client(endpoint).await?;
        client.query_stats(pattern, reset).await
    }
}

impl Default for XrayService {
    fn default() -> Self {
        Self::new()
    }
}