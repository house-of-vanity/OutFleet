use crate::services::uri_generator::{error::UriGeneratorError, ClientConfigData};

pub mod shadowsocks;
pub mod trojan;
pub mod vless;
pub mod vmess;

pub use shadowsocks::ShadowsocksUriBuilder;
pub use trojan::TrojanUriBuilder;
pub use vless::VlessUriBuilder;
pub use vmess::VmessUriBuilder;

/// Common trait for all URI builders
pub trait UriBuilder {
    /// Build URI string from client configuration data
    fn build_uri(&self, config: &ClientConfigData) -> Result<String, UriGeneratorError>;

    /// Validate configuration for this protocol
    fn validate_config(&self, config: &ClientConfigData) -> Result<(), UriGeneratorError> {
        if config.hostname.is_empty() {
            return Err(UriGeneratorError::MissingRequiredField(
                "hostname".to_string(),
            ));
        }
        if config.port <= 0 || config.port > 65535 {
            return Err(UriGeneratorError::InvalidConfiguration(
                "Invalid port number".to_string(),
            ));
        }
        if config.xray_user_id.is_empty() {
            return Err(UriGeneratorError::MissingRequiredField(
                "xray_user_id".to_string(),
            ));
        }
        Ok(())
    }
}

/// Helper functions for URI building
pub mod utils {
    use crate::services::uri_generator::error::UriGeneratorError;
    use serde_json::Value;
    use std::collections::HashMap;

    /// URL encode a string safely
    pub fn url_encode(input: &str) -> String {
        urlencoding::encode(input).to_string()
    }

    /// Build query string from parameters
    pub fn build_query_string(params: &HashMap<String, String>) -> String {
        let mut query_parts: Vec<String> = Vec::new();

        for (key, value) in params {
            if !value.is_empty() {
                query_parts.push(format!("{}={}", url_encode(key), url_encode(value)));
            }
        }

        query_parts.join("&")
    }

    /// Extract transport type from stream settings
    pub fn extract_transport_type(stream_settings: &Value) -> String {
        stream_settings
            .get("network")
            .and_then(|v| v.as_str())
            .unwrap_or("tcp")
            .to_string()
    }

    /// Extract security type from stream settings
    pub fn extract_security_type(stream_settings: &Value, has_certificate: bool) -> String {
        if has_certificate {
            stream_settings
                .get("security")
                .and_then(|v| v.as_str())
                .unwrap_or("tls")
                .to_string()
        } else {
            "none".to_string()
        }
    }

    /// Extract WebSocket path from stream settings
    pub fn extract_ws_path(stream_settings: &Value) -> Option<String> {
        stream_settings
            .get("wsSettings")
            .and_then(|ws| ws.get("path"))
            .and_then(|p| p.as_str())
            .map(|s| s.to_string())
    }

    /// Extract WebSocket host from stream settings
    pub fn extract_ws_host(stream_settings: &Value) -> Option<String> {
        stream_settings
            .get("wsSettings")
            .and_then(|ws| ws.get("headers"))
            .and_then(|headers| headers.get("Host"))
            .and_then(|host| host.as_str())
            .map(|s| s.to_string())
    }

    /// Extract gRPC service name from stream settings
    pub fn extract_grpc_service_name(stream_settings: &Value) -> Option<String> {
        stream_settings
            .get("grpcSettings")
            .and_then(|grpc| grpc.get("serviceName"))
            .and_then(|name| name.as_str())
            .map(|s| s.to_string())
    }

    /// Extract TLS SNI from stream settings
    pub fn extract_tls_sni(
        stream_settings: &Value,
        certificate_domain: Option<&str>,
    ) -> Option<String> {
        // Try stream settings first
        if let Some(sni) = stream_settings
            .get("tlsSettings")
            .and_then(|tls| tls.get("serverName"))
            .and_then(|sni| sni.as_str())
        {
            return Some(sni.to_string());
        }

        // Fall back to certificate domain
        certificate_domain.map(|s| s.to_string())
    }

    /// Determine alias for the URI
    pub fn generate_alias(server_name: &str, template_name: &str) -> String {
        format!("{} - {}", server_name, template_name)
    }
}
