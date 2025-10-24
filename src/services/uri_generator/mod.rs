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
