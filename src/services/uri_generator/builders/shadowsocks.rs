use base64::{Engine as _, engine::general_purpose};
use serde_json::Value;

use crate::services::uri_generator::{ClientConfigData, error::UriGeneratorError};
use super::{UriBuilder, utils};

pub struct ShadowsocksUriBuilder;

impl ShadowsocksUriBuilder {
    pub fn new() -> Self {
        Self
    }
    
    /// Map Xray cipher type to Shadowsocks method name
    fn map_xray_cipher_to_shadowsocks_method(&self, cipher: &str) -> &str {
        match cipher {
            // AES GCM variants
            "AES_256_GCM" | "aes-256-gcm" => "aes-256-gcm",
            "AES_128_GCM" | "aes-128-gcm" => "aes-128-gcm",
            
            // ChaCha20 variants  
            "CHACHA20_POLY1305" | "chacha20-ietf-poly1305" | "chacha20-poly1305" => "chacha20-ietf-poly1305",
            
            // AES CFB variants
            "AES_256_CFB" | "aes-256-cfb" => "aes-256-cfb",
            "AES_128_CFB" | "aes-128-cfb" => "aes-128-cfb",
            
            // Legacy ciphers
            "RC4_MD5" | "rc4-md5" => "rc4-md5",
            "AES_256_CTR" | "aes-256-ctr" => "aes-256-ctr",
            "AES_128_CTR" | "aes-128-ctr" => "aes-128-ctr",
            
            // Default to most secure and widely supported
            _ => "aes-256-gcm",
        }
    }
    
}

impl UriBuilder for ShadowsocksUriBuilder {
    fn build_uri(&self, config: &ClientConfigData) -> Result<String, UriGeneratorError> {
        self.validate_config(config)?;
        
        // Get cipher type from base_settings and map to Shadowsocks method
        let cipher = config.base_settings
            .get("cipherType")
            .and_then(|c| c.as_str())
            .or_else(|| config.base_settings.get("method").and_then(|m| m.as_str()))
            .unwrap_or("AES_256_GCM");
        
        let method = self.map_xray_cipher_to_shadowsocks_method(cipher);
        
        // Shadowsocks SIP002 format: ss://base64(method:password)@hostname:port#remark
        // Use xray_user_id as password (following Marzban approach)
        let credentials = format!("{}:{}", method, config.xray_user_id);
        let encoded_credentials = general_purpose::STANDARD.encode(credentials.as_bytes());
        
        // Generate alias for the URI
        let alias = utils::generate_alias(&config.user_name, &config.server_name, &config.inbound_tag);
        
        // Build simple SIP002 URI (no plugin parameters for standard Shadowsocks)
        let uri = format!(
            "ss://{}@{}:{}#{}",
            encoded_credentials,
            config.hostname,
            config.port,
            utils::url_encode(&alias)
        );
        
        Ok(uri)
    }
    
    fn validate_config(&self, config: &ClientConfigData) -> Result<(), UriGeneratorError> {
        // Basic validation
        if config.hostname.is_empty() {
            return Err(UriGeneratorError::MissingRequiredField("hostname".to_string()));
        }
        if config.port <= 0 || config.port > 65535 {
            return Err(UriGeneratorError::InvalidConfiguration("Invalid port number".to_string()));
        }
        if config.xray_user_id.is_empty() {
            return Err(UriGeneratorError::MissingRequiredField("xray_user_id".to_string()));
        }
        
        // Shadowsocks uses xray_user_id as password, already validated above
        
        Ok(())
    }
}

impl Default for ShadowsocksUriBuilder {
    fn default() -> Self {
        Self::new()
    }
}

