use serde_json::Value;
use std::collections::HashMap;

use super::{utils, UriBuilder};
use crate::services::uri_generator::{error::UriGeneratorError, ClientConfigData};

pub struct VlessUriBuilder;

impl VlessUriBuilder {
    pub fn new() -> Self {
        Self
    }
}

impl UriBuilder for VlessUriBuilder {
    fn build_uri(&self, config: &ClientConfigData) -> Result<String, UriGeneratorError> {
        self.validate_config(config)?;

        // Apply variable substitution to stream settings
        let stream_settings = if !config.variable_values.is_null() {
            // Simple variable substitution for stream settings
            apply_variables(&config.stream_settings, &config.variable_values)?
        } else {
            config.stream_settings.clone()
        };

        let mut params = HashMap::new();

        // VLESS always uses no encryption
        params.insert("encryption".to_string(), "none".to_string());

        // Determine security layer
        let has_certificate = config.certificate_domain.is_some();
        let security = utils::extract_security_type(&stream_settings, has_certificate);
        if security != "none" {
            params.insert("security".to_string(), security.clone());
        }

        // Transport type - always specify explicitly
        let transport_type = utils::extract_transport_type(&stream_settings);
        params.insert("type".to_string(), transport_type.clone());

        // Transport-specific parameters
        match transport_type.as_str() {
            "ws" => {
                if let Some(path) = utils::extract_ws_path(&stream_settings) {
                    params.insert("path".to_string(), path);
                }
                if let Some(host) = utils::extract_ws_host(&stream_settings) {
                    params.insert("host".to_string(), host);
                }
            }
            "grpc" => {
                if let Some(service_name) = utils::extract_grpc_service_name(&stream_settings) {
                    params.insert("serviceName".to_string(), service_name);
                }
                // Default gRPC mode
                params.insert("mode".to_string(), "gun".to_string());
            }
            "tcp" => {
                // Check for HTTP header type
                if let Some(header_type) = stream_settings
                    .get("tcpSettings")
                    .and_then(|tcp| tcp.get("header"))
                    .and_then(|header| header.get("type"))
                    .and_then(|t| t.as_str())
                {
                    if header_type != "none" {
                        params.insert("headerType".to_string(), header_type.to_string());
                    }
                }
            }
            _ => {} // Other transport types can be added as needed
        }

        // TLS/Security specific parameters
        if security == "tls" || security == "reality" {
            if let Some(sni) =
                utils::extract_tls_sni(&stream_settings, config.certificate_domain.as_deref())
            {
                params.insert("sni".to_string(), sni);
            }

            // TLS fingerprint
            if let Some(fp) = stream_settings
                .get("tlsSettings")
                .and_then(|tls| tls.get("fingerprint"))
                .and_then(|fp| fp.as_str())
            {
                params.insert("fp".to_string(), fp.to_string());
            }

            // REALITY specific parameters
            if security == "reality" {
                if let Some(pbk) = stream_settings
                    .get("realitySettings")
                    .and_then(|reality| reality.get("publicKey"))
                    .and_then(|pbk| pbk.as_str())
                {
                    params.insert("pbk".to_string(), pbk.to_string());
                }

                if let Some(sid) = stream_settings
                    .get("realitySettings")
                    .and_then(|reality| reality.get("shortId"))
                    .and_then(|sid| sid.as_str())
                {
                    params.insert("sid".to_string(), sid.to_string());
                }
            }
        }

        // Flow control for XTLS
        if let Some(flow) = stream_settings.get("flow").and_then(|f| f.as_str()) {
            params.insert("flow".to_string(), flow.to_string());
        }

        // Build the URI
        let query_string = utils::build_query_string(&params);
        let alias = utils::generate_alias(&config.server_name, &config.template_name);

        let uri = if query_string.is_empty() {
            format!(
                "vless://{}@{}:{}#{}",
                config.xray_user_id,
                config.hostname,
                config.port,
                utils::url_encode(&alias)
            )
        } else {
            format!(
                "vless://{}@{}:{}?{}#{}",
                config.xray_user_id,
                config.hostname,
                config.port,
                query_string,
                utils::url_encode(&alias)
            )
        };

        Ok(uri)
    }
}

impl Default for VlessUriBuilder {
    fn default() -> Self {
        Self::new()
    }
}

/// Apply variable substitution to JSON value
fn apply_variables(template: &Value, variables: &Value) -> Result<Value, UriGeneratorError> {
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
