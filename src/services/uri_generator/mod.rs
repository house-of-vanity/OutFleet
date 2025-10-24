use anyhow::Result;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

pub mod builders;
pub mod error;

use builders::{
    ShadowsocksUriBuilder, TrojanUriBuilder, UriBuilder, VlessUriBuilder, VmessUriBuilder,
};
use error::UriGeneratorError;

/// Complete client configuration data aggregated from database
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientConfigData {
    // User credentials
    pub user_name: String,
    pub xray_user_id: String,
    pub password: Option<String>,
    pub level: i32,

    // Server connection
    pub hostname: String,
    pub port: i32,

    // Protocol & transport
    pub protocol: String,
    pub stream_settings: Value,
    pub base_settings: Value,

    // Security
    pub certificate_domain: Option<String>,
    pub requires_tls: bool,

    // Variable substitution
    pub variable_values: Value,

    // Metadata
    pub server_name: String,
    pub inbound_tag: String,
    pub template_name: String,
}

/// Generated client configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientConfig {
    pub user_id: Uuid,
    pub server_name: String,
    pub inbound_tag: String,
    pub template_name: String,
    pub protocol: String,
    pub uri: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub qr_code: Option<String>,
}

/// URI Generator Service
pub struct UriGeneratorService;

impl UriGeneratorService {
    pub fn new() -> Self {
        Self
    }

    /// Generate URI for specific protocol and configuration
    pub fn generate_uri(&self, config: &ClientConfigData) -> Result<String, UriGeneratorError> {
        let protocol = config.protocol.as_str();

        match protocol {
            "vless" => {
                let builder = VlessUriBuilder::new();
                builder.build_uri(config)
            }
            "vmess" => {
                let builder = VmessUriBuilder::new();
                builder.build_uri(config)
            }
            "trojan" => {
                let builder = TrojanUriBuilder::new();
                builder.build_uri(config)
            }
            "shadowsocks" => {
                let builder = ShadowsocksUriBuilder::new();
                builder.build_uri(config)
            }
            _ => Err(UriGeneratorError::UnsupportedProtocol(protocol.to_string())),
        }
    }

    /// Generate complete client configuration
    pub fn generate_client_config(
        &self,
        user_id: Uuid,
        config: &ClientConfigData,
    ) -> Result<ClientConfig, UriGeneratorError> {
        let uri = self.generate_uri(config)?;

        Ok(ClientConfig {
            user_id,
            server_name: config.server_name.clone(),
            inbound_tag: config.inbound_tag.clone(),
            template_name: config.template_name.clone(),
            protocol: config.protocol.clone(),
            uri,
            qr_code: None, // TODO: Implement QR code generation if needed
        })
    }

    /// Apply variable substitution to JSON values
    pub fn apply_variable_substitution(
        &self,
        template: &Value,
        variables: &Value,
    ) -> Result<Value, UriGeneratorError> {
        let template_str = template.to_string();
        let mut result = template_str;

        if let Value::Object(var_map) = variables {
            for (key, value) in var_map {
                let placeholder = format!("${{{}}}", key);
                let replacement = match value {
                    Value::String(s) => s.clone(),
                    Value::Number(n) => n.to_string(),
                    Value::Bool(b) => b.to_string(),
                    _ => value.to_string().trim_matches('"').to_string(),
                };
                result = result.replace(&placeholder, &replacement);
            }
        }

        serde_json::from_str(&result)
            .map_err(|e| UriGeneratorError::VariableSubstitution(e.to_string()))
    }
}

impl Default for UriGeneratorService {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use uuid::Uuid;

    fn create_test_config(protocol: &str) -> ClientConfigData {
        ClientConfigData {
            user_name: "testuser".to_string(),
            xray_user_id: "test-uuid-123".to_string(),
            password: Some("test-password".to_string()),
            level: 0,
            hostname: "example.com".to_string(),
            port: 8443,
            protocol: protocol.to_string(),
            stream_settings: json!({
                "network": "tcp",
                "security": "tls"
            }),
            base_settings: json!({
                "clients": []
            }),
            certificate_domain: Some("example.com".to_string()),
            requires_tls: true,
            variable_values: json!({
                "domain": "example.com",
                "port": "8443"
            }),
            server_name: "test-server".to_string(),
            inbound_tag: "test-inbound".to_string(),
            template_name: "test-template".to_string(),
        }
    }

    #[test]
    fn test_uri_generator_service_creation() {
        let service = UriGeneratorService::new();
        // Service should be created successfully
        assert_eq!(std::mem::size_of_val(&service), 0); // Zero-sized struct
    }

    #[test]
    fn test_generate_uri_vless() {
        let service = UriGeneratorService::new();
        let config = create_test_config("vless");

        let result = service.generate_uri(&config);
        assert!(result.is_ok());

        let uri = result.unwrap();
        assert!(uri.starts_with("vless://"));
        assert!(uri.contains("test-uuid-123"));
        assert!(uri.contains("example.com:8443"));
    }

    #[test]
    fn test_generate_uri_vmess() {
        let service = UriGeneratorService::new();
        let config = create_test_config("vmess");

        let result = service.generate_uri(&config);
        assert!(result.is_ok());

        let uri = result.unwrap();
        assert!(uri.starts_with("vmess://"));
    }

    #[test]
    fn test_generate_uri_trojan() {
        let service = UriGeneratorService::new();
        let config = create_test_config("trojan");

        let result = service.generate_uri(&config);
        assert!(result.is_ok());

        let uri = result.unwrap();
        assert!(uri.starts_with("trojan://"));
        assert!(uri.contains("test-uuid-123")); // trojan uses xray_user_id as password
        assert!(uri.contains("example.com:8443"));
    }

    #[test]
    fn test_generate_uri_shadowsocks() {
        let service = UriGeneratorService::new();
        let config = create_test_config("shadowsocks");

        let result = service.generate_uri(&config);
        assert!(result.is_ok());

        let uri = result.unwrap();
        assert!(uri.starts_with("ss://"));
    }

    #[test]
    fn test_generate_uri_unsupported_protocol() {
        let service = UriGeneratorService::new();
        let config = create_test_config("unsupported");

        let result = service.generate_uri(&config);
        assert!(result.is_err());

        match result.unwrap_err() {
            UriGeneratorError::UnsupportedProtocol(protocol) => {
                assert_eq!(protocol, "unsupported");
            }
            _ => panic!("Expected UnsupportedProtocol error"),
        }
    }

    #[test]
    fn test_generate_client_config() {
        let service = UriGeneratorService::new();
        let config_data = create_test_config("vless");
        let user_id = Uuid::new_v4();

        let result = service.generate_client_config(user_id, &config_data);
        assert!(result.is_ok());

        let client_config = result.unwrap();
        assert_eq!(client_config.user_id, user_id);
        assert_eq!(client_config.server_name, "test-server");
        assert_eq!(client_config.inbound_tag, "test-inbound");
        assert_eq!(client_config.template_name, "test-template");
        assert_eq!(client_config.protocol, "vless");
        assert!(client_config.uri.starts_with("vless://"));
        assert!(client_config.qr_code.is_none());
    }

    #[test]
    fn test_apply_variable_substitution() {
        let service = UriGeneratorService::new();

        let template = json!({
            "hostname": "${domain}",
            "port": "${port}",
            "fixed": "value"
        });

        let variables = json!({
            "domain": "test.example.com",
            "port": "9443"
        });

        let result = service.apply_variable_substitution(&template, &variables);
        assert!(result.is_ok());

        let substituted = result.unwrap();
        assert_eq!(substituted["hostname"], "test.example.com");
        assert_eq!(substituted["port"], "9443");
        assert_eq!(substituted["fixed"], "value");
    }

    #[test]
    fn test_apply_variable_substitution_no_variables() {
        let service = UriGeneratorService::new();

        let template = json!({
            "hostname": "static.example.com",
            "port": "8443"
        });

        let variables = json!({});

        let result = service.apply_variable_substitution(&template, &variables);
        assert!(result.is_ok());

        let substituted = result.unwrap();
        assert_eq!(substituted["hostname"], "static.example.com");
        assert_eq!(substituted["port"], "8443");
    }

    #[test]
    fn test_apply_variable_substitution_partial_match() {
        let service = UriGeneratorService::new();

        let template = json!({
            "hostname": "${domain}",
            "port": "${unknown_var}",
            "static": "value"
        });

        let variables = json!({
            "domain": "test.example.com"
        });

        let result = service.apply_variable_substitution(&template, &variables);
        assert!(result.is_ok());

        let substituted = result.unwrap();
        assert_eq!(substituted["hostname"], "test.example.com");
        assert_eq!(substituted["port"], "${unknown_var}"); // Should remain unchanged
        assert_eq!(substituted["static"], "value");
    }

    #[test]
    fn test_client_config_data_fields() {
        let config = create_test_config("vless");

        assert_eq!(config.user_name, "testuser");
        assert_eq!(config.xray_user_id, "test-uuid-123");
        assert_eq!(config.password, Some("test-password".to_string()));
        assert_eq!(config.level, 0);
        assert_eq!(config.hostname, "example.com");
        assert_eq!(config.port, 8443);
        assert_eq!(config.protocol, "vless");
        assert_eq!(config.certificate_domain, Some("example.com".to_string()));
        assert!(config.requires_tls);
        assert_eq!(config.server_name, "test-server");
        assert_eq!(config.inbound_tag, "test-inbound");
        assert_eq!(config.template_name, "test-template");
    }

    #[test]
    fn test_client_config_serialization() {
        let user_id = Uuid::new_v4();
        let client_config = ClientConfig {
            user_id,
            server_name: "test-server".to_string(),
            inbound_tag: "test-inbound".to_string(),
            template_name: "test-template".to_string(),
            protocol: "vless".to_string(),
            uri: "vless://test-uri".to_string(),
            qr_code: Some("qr-code-data".to_string()),
        };

        // Test serialization
        let serialized = serde_json::to_string(&client_config);
        assert!(serialized.is_ok());

        // Test deserialization
        let deserialized: Result<ClientConfig, _> = serde_json::from_str(&serialized.unwrap());
        assert!(deserialized.is_ok());

        let config = deserialized.unwrap();
        assert_eq!(config.user_id, user_id);
        assert_eq!(config.server_name, "test-server");
        assert_eq!(config.protocol, "vless");
        assert_eq!(config.uri, "vless://test-uri");
        assert_eq!(config.qr_code, Some("qr-code-data".to_string()));
    }

    #[test]
    fn test_client_config_qr_code_optional() {
        let user_id = Uuid::new_v4();
        let client_config = ClientConfig {
            user_id,
            server_name: "test-server".to_string(),
            inbound_tag: "test-inbound".to_string(),
            template_name: "test-template".to_string(),
            protocol: "vless".to_string(),
            uri: "vless://test-uri".to_string(),
            qr_code: None,
        };

        let serialized = serde_json::to_string(&client_config).unwrap();

        // QR code field should be omitted when None due to skip_serializing_if
        assert!(!serialized.contains("qr_code"));
    }
}
