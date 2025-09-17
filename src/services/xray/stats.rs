use anyhow::{Result, anyhow};
use serde_json::Value;
use xray_core::{
    tonic::Request,
    app::stats::command::{GetStatsRequest, QueryStatsRequest},
    Client,
};

pub struct StatsClient<'a> {
    endpoint: String,
    client: &'a Client,
}

impl<'a> StatsClient<'a> {
    pub fn new(endpoint: String, client: &'a Client) -> Self {
        Self { endpoint, client }
    }

    /// Get server statistics
    pub async fn get_stats(&self) -> Result<Value> {
        tracing::info!("Getting stats from Xray server at {}", self.endpoint);
        
        let request = Request::new(GetStatsRequest {
            name: "".to_string(),
            reset: false,
        });

        let mut stats_client = self.client.stats();
        match stats_client.get_stats(request).await {
            Ok(response) => {
                let stats = response.into_inner();
                tracing::debug!("Stats: {:?}", stats);
                let stats_json = serde_json::json!({
                    "stats": format!("{:?}", stats.stat)
                });
                Ok(stats_json)
            }
            Err(e) => {
                tracing::error!("Failed to get stats: {}", e);
                Err(anyhow!("Failed to get stats: {}", e))
            }
        }
    }

    /// Query specific statistics with pattern
    pub async fn query_stats(&self, pattern: &str, reset: bool) -> Result<Value> {
        tracing::info!("Querying stats with pattern '{}', reset: {} from {}", pattern, reset, self.endpoint);
        
        let request = Request::new(QueryStatsRequest {
            pattern: pattern.to_string(),
            reset,
        });

        let mut stats_client = self.client.stats();
        match stats_client.query_stats(request).await {
            Ok(response) => {
                let stats = response.into_inner();
                tracing::debug!("Query stats: {:?}", stats);
                let stats_json = serde_json::json!({
                    "stat": format!("{:?}", stats.stat)
                });
                Ok(stats_json)
            }
            Err(e) => {
                tracing::error!("Failed to query stats: {}", e);
                Err(anyhow!("Failed to query stats: {}", e))
            }
        }
    }
}