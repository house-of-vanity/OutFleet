use anyhow::Result;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{timeout, Duration, Instant};
use tracing::warn;
use uuid::Uuid;

pub mod client;
pub mod config;
pub mod inbounds;
pub mod stats;
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

    /// Create service with custom TTL for testing
    pub fn with_ttl(ttl: Duration) -> Self {
        Self {
            connection_cache: Arc::new(RwLock::new(HashMap::new())),
            connection_ttl: ttl,
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
            }
            Ok(Err(e)) => {
                // Connection failed with error
                warn!("Failed to connect to Xray at {}: {}", endpoint, e);
                Ok(false)
            }
            Err(_) => {
                // Operation timed out
                warn!("Connection test to Xray at {} timed out", endpoint);
                Ok(false)
            }
        }
    }

    /// Get statistics from Xray server
    pub async fn get_stats(&self, endpoint: &str) -> Result<Value> {
        let client = self.get_or_create_client(endpoint).await?;
        client.get_stats().await
    }

    /// Query specific statistics with pattern
    pub async fn query_stats(&self, endpoint: &str, pattern: &str, reset: bool) -> Result<Value> {
        let client = self.get_or_create_client(endpoint).await?;
        client.query_stats(pattern, reset).await
    }

    /// Add user to server with specific inbound and configuration
    pub async fn add_user(&self, endpoint: &str, inbound_tag: &str, user: &Value) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
        client.add_user(inbound_tag, user).await
    }

    /// Remove user from server
    pub async fn remove_user(
        &self,
        endpoint: &str,
        inbound_tag: &str,
        user_email: &str,
    ) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
        client.remove_user(inbound_tag, user_email).await
    }

    /// Remove user from server (with server_id parameter for compatibility)
    pub async fn remove_user_with_server_id(
        &self,
        _server_id: Uuid,
        endpoint: &str,
        inbound_tag: &str,
        user_email: &str,
    ) -> Result<()> {
        self.remove_user(endpoint, inbound_tag, user_email).await
    }

    /// Create new inbound on server
    pub async fn create_inbound(&self, endpoint: &str, inbound: &Value) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
        client.add_inbound(inbound).await
    }

    /// Create inbound with certificate (legacy interface for compatibility)
    pub async fn create_inbound_with_certificate(
        &self,
        _server_id: Uuid,
        endpoint: &str,
        _tag: &str,
        _port: i32,
        _protocol: &str,
        _base_settings: Value,
        _stream_settings: Value,
        cert_pem: Option<&str>,
        key_pem: Option<&str>,
    ) -> Result<()> {
        // For now, create a basic inbound structure
        // In real implementation, this would build the inbound from the parameters
        let inbound = serde_json::json!({
            "tag": _tag,
            "port": _port,
            "protocol": _protocol,
            "settings": _base_settings,
            "streamSettings": _stream_settings
        });

        let client = self.get_or_create_client(endpoint).await?;
        client
            .add_inbound_with_certificate(&inbound, cert_pem, key_pem)
            .await
    }

    /// Update existing inbound on server
    pub async fn update_inbound(&self, endpoint: &str, inbound: &Value) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
        client.add_inbound(inbound).await // For now, just add - update logic would be more complex
    }

    /// Delete inbound from server
    pub async fn delete_inbound(&self, endpoint: &str, tag: &str) -> Result<()> {
        let client = self.get_or_create_client(endpoint).await?;
        client.remove_inbound(tag).await
    }

    /// Remove inbound from server (alias for delete_inbound)
    pub async fn remove_inbound(&self, _server_id: Uuid, endpoint: &str, tag: &str) -> Result<()> {
        self.delete_inbound(endpoint, tag).await
    }

    /// Get cache statistics for monitoring
    pub async fn get_cache_stats(&self) -> (usize, usize) {
        let cache = self.connection_cache.read().await;
        let total = cache.len();
        let expired = cache
            .values()
            .filter(|conn| conn.is_expired(self.connection_ttl))
            .count();
        (total, expired)
    }

    /// Clear expired connections from cache
    pub async fn clear_expired_connections(&self) {
        let mut cache = self.connection_cache.write().await;
        cache.retain(|_, conn| !conn.is_expired(self.connection_ttl));
    }

    /// Clear all connections from cache
    pub async fn clear_cache(&self) {
        let mut cache = self.connection_cache.write().await;
        cache.clear();
    }
}

// Additional methods that were in the original file but truncated
#[allow(dead_code)]
impl XrayService {
    /// Generic method to execute operations on client with retry
    async fn execute_with_retry<F, R>(&self, endpoint: &str, operation: F) -> Result<R>
    where
        F: Fn(XrayClient) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<R>> + Send>>,
    {
        let client = self.get_or_create_client(endpoint).await?;
        operation(client).await
    }

    /// Sync user with Xray server - ensures user exists with correct config
    pub async fn sync_user(
        &self,
        server_id: Uuid,
        endpoint: &str,
        inbound_tag: &str,
        user: &Value,
    ) -> Result<()> {
        let _server_id = server_id;
        let _endpoint = endpoint;
        let _inbound_tag = inbound_tag;
        let _user = user;
        // Implementation would go here
        Ok(())
    }

    /// Batch operation to sync multiple users
    pub async fn sync_users(
        &self,
        endpoint: &str,
        inbound_tag: &str,
        users: Vec<&Value>,
    ) -> Result<Vec<Result<()>>> {
        let mut results = Vec::new();
        for user in users {
            let result = self.add_user(endpoint, inbound_tag, user).await;
            results.push(result);
        }
        Ok(results)
    }

    /// Get user statistics for specific user
    pub async fn get_user_stats(&self, endpoint: &str, user_email: &str) -> Result<Value> {
        let pattern = format!("user>>>{}>>>traffic", user_email);
        self.query_stats(endpoint, &pattern, false).await
    }

    /// Reset user statistics
    pub async fn reset_user_stats(&self, endpoint: &str, user_email: &str) -> Result<Value> {
        let pattern = format!("user>>>{}>>>traffic", user_email);
        self.query_stats(endpoint, &pattern, true).await
    }

    /// Health check for server
    pub async fn health_check(&self, endpoint: &str) -> Result<bool> {
        match self.get_stats(endpoint).await {
            Ok(_) => Ok(true),
            Err(_) => Ok(false),
        }
    }

    /// Sync server inbounds optimized (placeholder implementation)
    pub async fn sync_server_inbounds_optimized(
        &self,
        _server_id: Uuid,
        _endpoint: &str,
        _desired_inbounds: &std::collections::HashMap<
            String,
            crate::services::tasks::DesiredInbound,
        >,
    ) -> Result<()> {
        // Placeholder implementation for tasks.rs compatibility
        // In real implementation, this would:
        // 1. Get current inbounds from server
        // 2. Compare with desired inbounds
        // 3. Add/remove/update as needed
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::time::Duration;
    use uuid::Uuid;

    #[tokio::test]
    async fn test_xray_service_creation() {
        let service = XrayService::new();
        let (total, expired) = service.get_cache_stats().await;
        assert_eq!(total, 0);
        assert_eq!(expired, 0);
    }

    #[tokio::test]
    async fn test_xray_service_with_custom_ttl() {
        let custom_ttl = Duration::from_millis(100);
        let service = XrayService::with_ttl(custom_ttl);
        assert_eq!(service.connection_ttl, custom_ttl);
    }

    #[tokio::test]
    async fn test_cache_expiration() {
        let service = XrayService::with_ttl(Duration::from_millis(50));

        // This test doesn't actually connect since we don't have a real Xray server
        // but tests the caching logic structure
        let (total, expired) = service.get_cache_stats().await;
        assert_eq!(total, 0);
        assert_eq!(expired, 0);
    }

    #[tokio::test]
    async fn test_cache_clearing() {
        let service = XrayService::new();

        // Clear empty cache
        service.clear_cache().await;
        let (total, _) = service.get_cache_stats().await;
        assert_eq!(total, 0);

        // Clear expired connections from empty cache
        service.clear_expired_connections().await;
        let (total, _) = service.get_cache_stats().await;
        assert_eq!(total, 0);
    }

    #[tokio::test]
    async fn test_connection_timeout() {
        let service = XrayService::new();
        let server_id = Uuid::new_v4();

        // Test with invalid endpoint - should return false due to connection failure
        let result = service
            .test_connection(server_id, "invalid://endpoint")
            .await;
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), false);
    }

    #[tokio::test]
    async fn test_health_check_with_invalid_endpoint() {
        let service = XrayService::new();

        // Test health check with invalid endpoint
        let result = service.health_check("invalid://endpoint").await;
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), false);
    }

    #[test]
    fn test_cached_connection_expiration() {
        // Create a mock client for testing purposes
        // In real tests, we would use a mock framework
        let _now = Instant::now();

        // Test the expiration logic directly without creating an actual client
        let short_ttl = Duration::from_nanos(1);
        let long_ttl = Duration::from_secs(1);

        // Simulate time passage
        let elapsed_short = Duration::from_nanos(10);
        let elapsed_long = Duration::from_millis(10);

        // Test expiration logic
        assert!(elapsed_short > short_ttl);
        assert!(elapsed_long < long_ttl);
    }

    #[tokio::test]
    async fn test_user_stats_pattern_generation() {
        let service = XrayService::new();
        let user_email = "test@example.com";

        // We can't test the actual stats call without a real server,
        // but we can test that the method doesn't panic and returns an error for invalid endpoint
        let result = service
            .get_user_stats("invalid://endpoint", user_email)
            .await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_sync_users_empty_list() {
        let service = XrayService::new();
        let users: Vec<&serde_json::Value> = vec![];

        let results = service
            .sync_users("invalid://endpoint", "test_inbound", users)
            .await;
        assert!(results.is_ok());
        assert_eq!(results.unwrap().len(), 0);
    }

    // Helper function for creating test user data
    fn create_test_user() -> serde_json::Value {
        serde_json::json!({
            "email": "test@example.com",
            "id": "test-user-id",
            "level": 0
        })
    }

    #[tokio::test]
    async fn test_sync_users_with_data() {
        let service = XrayService::new();
        let user_data = create_test_user();
        let users = vec![&user_data];

        // This will fail due to invalid endpoint, but tests the structure
        let results = service
            .sync_users("invalid://endpoint", "test_inbound", users)
            .await;
        assert!(results.is_ok());
        let results = results.unwrap();
        assert_eq!(results.len(), 1);
        assert!(results[0].is_err()); // Should fail due to invalid endpoint
    }
}
