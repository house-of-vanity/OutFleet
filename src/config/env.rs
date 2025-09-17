use std::env;

/// Environment variable utilities
pub struct EnvVars;

impl EnvVars {
    /// Get environment variable with fallback
    #[allow(dead_code)]
    pub fn get_or_default(key: &str, default: &str) -> String {
        env::var(key).unwrap_or_else(|_| default.to_string())
    }

    /// Get required environment variable
    #[allow(dead_code)]
    pub fn get_required(key: &str) -> Result<String, env::VarError> {
        env::var(key)
    }

    /// Check if running in development mode
    #[allow(dead_code)]
    pub fn is_development() -> bool {
        matches!(
            env::var("RUST_ENV").as_deref(),
            Ok("development") | Ok("dev")
        ) || matches!(
            env::var("ENVIRONMENT").as_deref(),
            Ok("development") | Ok("dev")
        )
    }

    /// Check if running in production mode
    #[allow(dead_code)]
    pub fn is_production() -> bool {
        matches!(
            env::var("RUST_ENV").as_deref(),
            Ok("production") | Ok("prod")
        ) || matches!(
            env::var("ENVIRONMENT").as_deref(),
            Ok("production") | Ok("prod")
        )
    }

    /// Get database URL from environment
    #[allow(dead_code)]
    pub fn database_url() -> Option<String> {
        env::var("DATABASE_URL").ok()
            .or_else(|| env::var("XRAY_ADMIN__DATABASE__URL").ok())
    }

    /// Get telegram bot token from environment
    #[allow(dead_code)]
    pub fn telegram_token() -> Option<String> {
        env::var("TELEGRAM_BOT_TOKEN").ok()
            .or_else(|| env::var("XRAY_ADMIN__TELEGRAM__BOT_TOKEN").ok())
    }

    /// Get JWT secret from environment
    #[allow(dead_code)]
    pub fn jwt_secret() -> Option<String> {
        env::var("JWT_SECRET").ok()
            .or_else(|| env::var("XRAY_ADMIN__WEB__JWT_SECRET").ok())
    }

    /// Print environment info for debugging
    pub fn print_env_info() {
        tracing::debug!("Environment information:");
        tracing::debug!("  RUST_ENV: {:?}", env::var("RUST_ENV"));
        tracing::debug!("  ENVIRONMENT: {:?}", env::var("ENVIRONMENT"));
        tracing::debug!("  DATABASE_URL: {}", 
            if env::var("DATABASE_URL").is_ok() { "set" } else { "not set" }
        );
        tracing::debug!("  TELEGRAM_BOT_TOKEN: {}", 
            if env::var("TELEGRAM_BOT_TOKEN").is_ok() { "set" } else { "not set" }
        );
        tracing::debug!("  JWT_SECRET: {}", 
            if env::var("JWT_SECRET").is_ok() { "set" } else { "not set" }
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    #[test]
    fn test_get_or_default() {
        let result = EnvVars::get_or_default("NON_EXISTENT_VAR", "default_value");
        assert_eq!(result, "default_value");
    }

    #[test]
    fn test_environment_detection() {
        env::set_var("RUST_ENV", "development");
        assert!(EnvVars::is_development());
        assert!(!EnvVars::is_production());

        env::set_var("RUST_ENV", "production");
        assert!(!EnvVars::is_development());
        assert!(EnvVars::is_production());

        env::remove_var("RUST_ENV");
    }
}