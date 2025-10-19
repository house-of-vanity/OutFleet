use anyhow::Result;
use serde_json::Value;
use uuid::Uuid;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{Duration, Instant, timeout};
use tracing::{error, warn};

pub mod client;
pub mod config;
pub mod stats;
pub mod inbounds;
pub mod users;

pub use client::XrayClient;
pub use config::XrayConfig;

/// Cached connection with TTL
#[derive(Clone)]
struct CachedConnection {
    client: XrayClient,
    created_at: Instant,
}

impl CachedConnection {
    fn new(client: XrayClient) -> Self {
        Self {
            client,
            created_at: Instant::now(),
        }
    }
    
    fn is_expired(&self, ttl: Duration) -> bool {
        self.created_at.elapsed() > ttl
    }
}

/// Service for managing Xray servers via gRPC
#[derive(Clone)]
pub struct XrayService {
    connection_cache: Arc<RwLock<HashMap<String, CachedConnection>>>,
    connection_ttl: Duration,
}

#[allow(dead_code)]
impl XrayService {
    pub fn new() -> Self {
        Self {
            connection_cache: Arc::new(RwLock::new(HashMap::new())),
            connection_ttl: Duration::from_secs(300), // 5 minutes TTL
        }
    }
    
    /// Get or create cached client for endpoint
    async fn get_or_create_client(&self, endpoint: &str) -> Result<XrayClient> {
        // Check cache first
        {
            let cache = self.connection_cache.read().await;
            if let Some(cached) = cache.get(endpoint) {
                if !cached.is_expired(self.connection_ttl) {
                    return Ok(cached.client.clone());
                }
            }
        }
        
        // Create new connection
        let client = XrayClient::connect(endpoint).await?;
        let cached_connection = CachedConnection::new(client.clone());
        
        // Update cache
        {
            let mut cache = self.connection_cache.write().await;
            cache.insert(endpoint.to_string(), cached_connection);
        }
        
        Ok(client)
    }


    /// Test connection to Xray server with timeout
    pub async fn test_connection(&self, _server_id: Uuid, endpoint: &str) -> Result<bool> {
        // Apply a 3-second timeout to the entire test operation
        match timeout(Duration::from_secs(3), self.get_or_create_client(endpoint)).await {
            Ok(Ok(_client)) => {
                // Connection successful
                Ok(true)
            },
            Ok(Err(e)) => {
                // Connection failed with error
                warn!("Failed to connect to Xray at {}: {}", endpoint, e);
                Ok(false)
            },
            Err(_) => {
                // Operation timed out
                warn!("Connection test to Xray at {} timed out", endpoint);
                Ok(false)
            }
        }
    }

    /// Apply full configuration to Xray server
    pub async fn apply_config(&self, _server_id: Uuid, endpoint: &str, config: &XrayConfig) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
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
        let client = self.get_or_create_client(endpoint).await?;
        client.add_inbound(inbound).await
    }

    /// Add inbound with certificate to running Xray instance
    pub async fn add_inbound_with_certificate(&self, _server_id: Uuid, endpoint: &str, inbound: &Value, cert_pem: Option<&str>, key_pem: Option<&str>) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
        client.add_inbound_with_certificate(inbound, cert_pem, key_pem).await
    }

    /// Add inbound with users and certificate to running Xray instance
    pub async fn add_inbound_with_users_and_certificate(&self, _server_id: Uuid, endpoint: &str, inbound: &Value, users: &[Value], cert_pem: Option<&str>, key_pem: Option<&str>) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
        client.add_inbound_with_users_and_certificate(inbound, users, cert_pem, key_pem).await
    }

    /// Remove inbound from running Xray instance
    pub async fn remove_inbound(&self, _server_id: Uuid, endpoint: &str, tag: &str) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
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
        let client = self.get_or_create_client(endpoint).await?;
        client.remove_user(inbound_tag, email).await
    }

    /// Get server statistics
    pub async fn get_stats(&self, _server_id: Uuid, endpoint: &str) -> Result<Value> {
        let client = self.get_or_create_client(endpoint).await?;
        client.get_stats().await
    }

    /// Query specific statistics
    pub async fn query_stats(&self, _server_id: Uuid, endpoint: &str, pattern: &str, reset: bool) -> Result<Value> {
        let client = self.get_or_create_client(endpoint).await?;
        client.query_stats(pattern, reset).await
    }
    
    /// Sync entire server with batch operations using single client
    pub async fn sync_server_inbounds_optimized(
        &self,
        server_id: Uuid,
        endpoint: &str,
        desired_inbounds: &HashMap<String, crate::services::tasks::DesiredInbound>,
    ) -> Result<()> {
        // Get single client for all operations
        let client = self.get_or_create_client(endpoint).await?;
        
        // Perform all operations with the same client
        for (tag, desired) in desired_inbounds {
            // Always try to remove inbound first (ignore errors if it doesn't exist)
            let _ = client.remove_inbound(tag).await;
            
            // Create inbound with users
            let users_json: Vec<Value> = desired.users.iter().map(|user| {
                serde_json::json!({
                    "id": user.id,
                    "email": user.email,
                    "level": user.level
                })
            }).collect();
            
            // Build inbound config
            let inbound_config = serde_json::json!({
                "tag": desired.tag,
                "port": desired.port,
                "protocol": desired.protocol,
                "settings": desired.settings,
                "streamSettings": desired.stream_settings
            });
            
            match client.add_inbound_with_users_and_certificate(
                &inbound_config,
                &users_json,
                desired.cert_pem.as_deref(),
                desired.key_pem.as_deref(),
            ).await {
                Err(e) => {
                    error!("Failed to create inbound {}: {}", tag, e);
                }
                _ => {}
            }
        }
        
        Ok(())
    }
}

impl Default for XrayService {
    fn default() -> Self {
        Self::new()
    }
}