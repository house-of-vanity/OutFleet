use std::collections::HashMap;
use serde_json::{Value, json};
use base64::{Engine as _, engine::general_purpose};

use crate::services::uri_generator::{ClientConfigData, error::UriGeneratorError};
use super::{UriBuilder, utils};

pub struct VmessUriBuilder;

impl VmessUriBuilder {
    pub fn new() -> Self {
        Self
    }
    
    /// Build VMess URI in Base64 JSON format (following Marzban approach)
    fn build_base64_json_uri(&self, config: &ClientConfigData) -> Result<String, UriGeneratorError> {
        // Apply variable substitution to stream settings
        let stream_settings = if !config.variable_values.is_null() {
            apply_variables(&config.stream_settings, &config.variable_values)?
        } else {
            config.stream_settings.clone()
        };
        
        let transport_type = utils::extract_transport_type(&stream_settings);
        let has_certificate = config.certificate_domain.is_some();
        let security = utils::extract_security_type(&stream_settings, has_certificate);
        
        // Build VMess JSON configuration following Marzban structure
        let mut vmess_config = json!({
            "add": config.hostname,
            "aid": "0",
            "host": "",
            "id": config.xray_user_id,
            "net": transport_type,
            "path": "",
            "port": config.port,
            "ps": utils::generate_alias(&config.server_name, &config.template_name),
            "scy": "auto",
            "tls": if security == "none" { "none" } else { &security },
            "type": "none",
            "v": "2"
        });
        
        // Transport-specific settings
        match transport_type.as_str() {
            "ws" => {
                if let Some(path) = utils::extract_ws_path(&stream_settings) {
                    vmess_config["path"] = Value::String(path);
                }
                if let Some(host) = utils::extract_ws_host(&stream_settings) {
                    vmess_config["host"] = Value::String(host);
                }
            },
            "grpc" => {
                if let Some(service_name) = utils::extract_grpc_service_name(&stream_settings) {
                    vmess_config["path"] = Value::String(service_name);
                }
                // For gRPC in VMess, use "gun" type
                vmess_config["type"] = Value::String("gun".to_string());
            },
            "tcp" => {
                // Check for HTTP header type
                if let Some(header_type) = stream_settings
                    .get("tcpSettings")
                    .and_then(|tcp| tcp.get("header"))
                    .and_then(|header| header.get("type"))
                    .and_then(|t| t.as_str()) {
                    vmess_config["type"] = Value::String(header_type.to_string());
                    
                    // If HTTP headers, get host and path
                    if header_type == "http" {
                        if let Some(host) = stream_settings
                            .get("tcpSettings")
                            .and_then(|tcp| tcp.get("header"))
                            .and_then(|header| header.get("request"))
                            .and_then(|request| request.get("headers"))
                            .and_then(|headers| headers.get("Host"))
                            .and_then(|host| host.as_array())
                            .and_then(|arr| arr.first())
                            .and_then(|h| h.as_str()) {
                            vmess_config["host"] = Value::String(host.to_string());
                        }
                        
                        if let Some(path) = stream_settings
                            .get("tcpSettings")
                            .and_then(|tcp| tcp.get("header"))
                            .and_then(|header| header.get("request"))
                            .and_then(|request| request.get("path"))
                            .and_then(|path| path.as_array())
                            .and_then(|arr| arr.first())
                            .and_then(|p| p.as_str()) {
                            vmess_config["path"] = Value::String(path.to_string());
                        }
                    }
                }
            },
            _ => {} // Other transport types
        }
        
        // TLS settings
        if security != "none" {
            if let Some(sni) = utils::extract_tls_sni(&stream_settings, config.certificate_domain.as_deref()) {
                vmess_config["sni"] = Value::String(sni);
            }
            
            // TLS fingerprint
            if let Some(fp) = stream_settings
                .get("tlsSettings")
                .and_then(|tls| tls.get("fingerprint"))
                .and_then(|fp| fp.as_str()) {
                vmess_config["fp"] = Value::String(fp.to_string());
            }
            
            // ALPN
            if let Some(alpn) = stream_settings
                .get("tlsSettings")
                .and_then(|tls| tls.get("alpn"))
                .and_then(|alpn| alpn.as_array()) {
                let alpn_str = alpn
                    .iter()
                    .filter_map(|v| v.as_str())
                    .collect::<Vec<_>>()
                    .join(",");
                if !alpn_str.is_empty() {
                    vmess_config["alpn"] = Value::String(alpn_str);
                }
            }
        }
        
        // Convert to JSON string and encode in Base64
        let json_string = vmess_config.to_string();
        let encoded = general_purpose::STANDARD.encode(json_string.as_bytes());
        
        Ok(format!("vmess://{}", encoded))
    }
    
    /// Build VMess URI in query parameter format (alternative)
    fn build_query_param_uri(&self, config: &ClientConfigData) -> Result<String, UriGeneratorError> {
        // Apply variable substitution to stream settings
        let stream_settings = if !config.variable_values.is_null() {
            apply_variables(&config.stream_settings, &config.variable_values)?
        } else {
            config.stream_settings.clone()
        };
        
        let mut params = HashMap::new();
        
        // VMess uses auto encryption
        params.insert("encryption".to_string(), "auto".to_string());
        
        // Determine security layer
        let has_certificate = config.certificate_domain.is_some();
        let security = utils::extract_security_type(&stream_settings, has_certificate);
        if security != "none" {
            params.insert("security".to_string(), security.clone());
        }
        
        // Transport type
        let transport_type = utils::extract_transport_type(&stream_settings);
        if transport_type != "tcp" {
            params.insert("type".to_string(), transport_type.clone());
        }
        
        // Transport-specific parameters
        match transport_type.as_str() {
            "ws" => {
                if let Some(path) = utils::extract_ws_path(&stream_settings) {
                    params.insert("path".to_string(), path);
                }
                if let Some(host) = utils::extract_ws_host(&stream_settings) {
                    params.insert("host".to_string(), host);
                }
            },
            "grpc" => {
                if let Some(service_name) = utils::extract_grpc_service_name(&stream_settings) {
                    params.insert("serviceName".to_string(), service_name);
                }
                params.insert("mode".to_string(), "gun".to_string());
            },
            _ => {}
        }
        
        // TLS specific parameters
        if security != "none" {
            if let Some(sni) = utils::extract_tls_sni(&stream_settings, config.certificate_domain.as_deref()) {
                params.insert("sni".to_string(), sni);
            }
            
            if let Some(fp) = stream_settings
                .get("tlsSettings")
                .and_then(|tls| tls.get("fingerprint"))
                .and_then(|fp| fp.as_str()) {
                params.insert("fp".to_string(), fp.to_string());
            }
        }
        
        // Build the URI
        let query_string = utils::build_query_string(&params);
        let alias = utils::generate_alias(&config.server_name, &config.template_name);
        
        let uri = if query_string.is_empty() {
            format!(
                "vmess://{}@{}:{}#{}",
                config.xray_user_id,
                config.hostname,
                config.port,
                utils::url_encode(&alias)
            )
        } else {
            format!(
                "vmess://{}@{}:{}?{}#{}",
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

impl UriBuilder for VmessUriBuilder {
    fn build_uri(&self, config: &ClientConfigData) -> Result<String, UriGeneratorError> {
        self.validate_config(config)?;
        
        // Prefer Base64 JSON format as it's more widely supported
        self.build_base64_json_uri(config)
    }
}

impl Default for VmessUriBuilder {
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