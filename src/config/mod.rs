use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use validator::Validate;

pub mod args;
pub mod env;
pub mod file;

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct AppConfig {
    pub database: DatabaseConfig,
    pub web: WebConfig,
    pub telegram: TelegramConfig,
    pub xray: XrayConfig,
    pub logging: LoggingConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct DatabaseConfig {
    #[validate(url)]
    pub url: String,
    #[validate(range(min = 1, max = 100))]
    pub max_connections: u32,
    #[validate(range(min = 1))]
    pub connection_timeout: u64,
    pub auto_migrate: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct WebConfig {
    #[validate(ip)]
    pub host: String,
    #[validate(range(min = 1024, max = 65535))]
    pub port: u16,
    pub cors_origins: Vec<String>,
    pub jwt_secret: String,
    #[validate(range(min = 3600))]
    pub jwt_expiry: u64,
    /// Base URL for the application (used in subscription links and Telegram messages)
    /// Example: "https://vpn.hexor.cy"
    #[validate(url)]
    pub base_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct TelegramConfig {
    pub bot_token: String,
    pub webhook_url: Option<String>,
    pub admin_chat_ids: Vec<i64>,
    pub allowed_users: Vec<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct XrayConfig {
    pub default_api_port: u16,
    pub config_template_path: PathBuf,
    pub certificates_path: PathBuf,
    #[validate(range(min = 1))]
    pub health_check_interval: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoggingConfig {
    pub level: String,
    pub file_path: Option<PathBuf>,
    pub json_format: bool,
    pub max_file_size: Option<u64>,
    pub max_files: Option<u32>,
}

impl Default for DatabaseConfig {
    fn default() -> Self {
        Self {
            url: "postgresql://xray:password@localhost/xray_admin".to_string(),
            max_connections: 10,
            connection_timeout: 30,
            auto_migrate: true,
        }
    }
}

impl Default for WebConfig {
    fn default() -> Self {
        Self {
            host: "127.0.0.1".to_string(),
            port: 8080,
            cors_origins: vec!["http://localhost:3000".to_string()],
            jwt_secret: "your-secret-key-change-in-production".to_string(),
            jwt_expiry: 86400, // 24 hours
            base_url: "http://localhost:8080".to_string(),
        }
    }
}

impl Default for TelegramConfig {
    fn default() -> Self {
        Self {
            bot_token: "".to_string(),
            webhook_url: None,
            admin_chat_ids: vec![],
            allowed_users: vec![],
        }
    }
}

impl Default for XrayConfig {
    fn default() -> Self {
        Self {
            default_api_port: 62789,
            config_template_path: PathBuf::from("./templates"),
            certificates_path: PathBuf::from("./certs"),
            health_check_interval: 30,
        }
    }
}

impl Default for LoggingConfig {
    fn default() -> Self {
        Self {
            level: "info".to_string(),
            file_path: None,
            json_format: false,
            max_file_size: Some(10 * 1024 * 1024), // 10MB
            max_files: Some(5),
        }
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            database: DatabaseConfig::default(),
            web: WebConfig::default(),
            telegram: TelegramConfig::default(),
            xray: XrayConfig::default(),
            logging: LoggingConfig::default(),
        }
    }
}

impl AppConfig {
    /// Load configuration from multiple sources with priority:
    /// 1. Command line arguments (highest)
    /// 2. Environment variables
    /// 3. Configuration file
    /// 4. Default values (lowest)
    pub fn load() -> Result<Self> {
        let args = args::parse_args();

        let mut builder = config::Config::builder()
            // Start with defaults
            .add_source(config::Config::try_from(&AppConfig::default())?);

        // Add configuration file if specified or exists
        if let Some(config_file) = &args.config {
            builder = builder.add_source(config::File::from(config_file.as_path()));
        } else if std::path::Path::new("config.toml").exists() {
            builder = builder.add_source(config::File::with_name("config"));
        }

        // Add environment variables with prefix
        builder = builder.add_source(
            config::Environment::with_prefix("XRAY_ADMIN")
                .separator("__")
                .try_parsing(true),
        );

        // Override with command line arguments
        if let Some(host) = &args.host {
            builder = builder.set_override("web.host", host.as_str())?;
        }
        if let Some(port) = args.port {
            builder = builder.set_override("web.port", port)?;
        }
        if let Some(db_url) = &args.database_url {
            builder = builder.set_override("database.url", db_url.as_str())?;
        }
        if let Some(log_level) = &args.log_level {
            builder = builder.set_override("logging.level", log_level.as_str())?;
        }
        if let Some(base_url) = &args.base_url {
            builder = builder.set_override("web.base_url", base_url.as_str())?;
        }

        let config: AppConfig = builder.build()?.try_deserialize()?;

        // Validate configuration
        config.validate()?;

        Ok(config)
    }

    pub fn display_summary(&self) {
        tracing::info!("Configuration loaded:");
        tracing::info!("  Database URL: {}", mask_sensitive(&self.database.url));
        tracing::info!("  Web server: {}:{}", self.web.host, self.web.port);
        tracing::info!("  Log level: {}", self.logging.level);
        tracing::info!(
            "  Telegram bot: {}",
            if self.telegram.bot_token.is_empty() {
                "disabled"
            } else {
                "enabled"
            }
        );
        tracing::info!(
            "  Xray config path: {}",
            self.xray.config_template_path.display()
        );
    }
}

/// Mask sensitive information in URLs for logging
fn mask_sensitive(url: &str) -> String {
    // Simple string-based approach to mask passwords
    if let Some(scheme_end) = url.find("://") {
        let after_scheme = &url[scheme_end + 3..];
        if let Some(at_pos) = after_scheme.find('@') {
            let auth_part = &after_scheme[..at_pos];
            if let Some(colon_pos) = auth_part.find(':') {
                // Found user:password@host pattern
                let user = &auth_part[..colon_pos];
                let host_part = &after_scheme[at_pos..];
                return format!("{}://{}:***{}", &url[..scheme_end], user, host_part);
            }
        }
    }

    // Fallback to URL parsing if simple approach fails
    if let Ok(parsed) = url::Url::parse(url) {
        if parsed.password().is_some() {
            let mut masked = parsed.clone();
            masked.set_password(Some("***")).unwrap();
            masked.to_string()
        } else {
            url.to_string()
        }
    } else {
        url.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config_validation() {
        let config = AppConfig::default();
        // Default configuration should be valid
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_mask_sensitive() {
        let url = "postgresql://user:password@localhost/db";
        let masked = mask_sensitive(url);
        assert!(masked.contains("***"));
        assert!(!masked.contains("password"));
    }
}
