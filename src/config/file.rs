use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

use super::AppConfig;

/// Configuration file utilities
#[allow(dead_code)]
pub struct ConfigFile;

#[allow(dead_code)]
impl ConfigFile {
    /// Load configuration from TOML file
    pub fn load_toml<P: AsRef<Path>>(path: P) -> Result<AppConfig> {
        let content = fs::read_to_string(&path)
            .with_context(|| format!("Failed to read config file: {}", path.as_ref().display()))?;
        
        let config: AppConfig = toml::from_str(&content)
            .with_context(|| format!("Failed to parse TOML config file: {}", path.as_ref().display()))?;
        
        Ok(config)
    }

    /// Load configuration from YAML file
    pub fn load_yaml<P: AsRef<Path>>(path: P) -> Result<AppConfig> {
        let content = fs::read_to_string(&path)
            .with_context(|| format!("Failed to read config file: {}", path.as_ref().display()))?;
        
        let config: AppConfig = serde_yaml::from_str(&content)
            .with_context(|| format!("Failed to parse YAML config file: {}", path.as_ref().display()))?;
        
        Ok(config)
    }

    /// Load configuration from JSON file
    pub fn load_json<P: AsRef<Path>>(path: P) -> Result<AppConfig> {
        let content = fs::read_to_string(&path)
            .with_context(|| format!("Failed to read config file: {}", path.as_ref().display()))?;
        
        let config: AppConfig = serde_json::from_str(&content)
            .with_context(|| format!("Failed to parse JSON config file: {}", path.as_ref().display()))?;
        
        Ok(config)
    }

    /// Auto-detect format and load configuration file
    pub fn load_auto<P: AsRef<Path>>(path: P) -> Result<AppConfig> {
        let path = path.as_ref();
        
        match path.extension().and_then(|ext| ext.to_str()) {
            Some("toml") => Self::load_toml(path),
            Some("yaml") | Some("yml") => Self::load_yaml(path),
            Some("json") => Self::load_json(path),
            _ => {
                // Try TOML first, then YAML, then JSON
                Self::load_toml(path)
                    .or_else(|_| Self::load_yaml(path))
                    .or_else(|_| Self::load_json(path))
                    .with_context(|| {
                        format!(
                            "Failed to load config file '{}' - tried TOML, YAML, and JSON formats",
                            path.display()
                        )
                    })
            }
        }
    }

    /// Save configuration to TOML file
    pub fn save_toml<P: AsRef<Path>>(config: &AppConfig, path: P) -> Result<()> {
        let content = toml::to_string_pretty(config)
            .context("Failed to serialize config to TOML")?;
        
        fs::write(&path, content)
            .with_context(|| format!("Failed to write config file: {}", path.as_ref().display()))?;
        
        Ok(())
    }

    /// Save configuration to YAML file
    pub fn save_yaml<P: AsRef<Path>>(config: &AppConfig, path: P) -> Result<()> {
        let content = serde_yaml::to_string(config)
            .context("Failed to serialize config to YAML")?;
        
        fs::write(&path, content)
            .with_context(|| format!("Failed to write config file: {}", path.as_ref().display()))?;
        
        Ok(())
    }

    /// Save configuration to JSON file
    pub fn save_json<P: AsRef<Path>>(config: &AppConfig, path: P) -> Result<()> {
        let content = serde_json::to_string_pretty(config)
            .context("Failed to serialize config to JSON")?;
        
        fs::write(&path, content)
            .with_context(|| format!("Failed to write config file: {}", path.as_ref().display()))?;
        
        Ok(())
    }

    /// Check if config file exists and is readable
    pub fn exists_and_readable<P: AsRef<Path>>(path: P) -> bool {
        let path = path.as_ref();
        path.exists() && path.is_file() && fs::metadata(path).map(|m| !m.permissions().readonly()).unwrap_or(false)
    }

    /// Find default config file in common locations
    pub fn find_default() -> Option<std::path::PathBuf> {
        let candidates = [
            "config.toml",
            "config.yaml",
            "config.yml",
            "config.json",
            "xray-admin.toml",
            "xray-admin.yaml",
            "xray-admin.yml",
            "/etc/xray-admin/config.toml",
            "/etc/xray-admin/config.yaml",
            "~/.config/xray-admin/config.toml",
        ];

        for candidate in &candidates {
            let path = std::path::Path::new(candidate);
            if Self::exists_and_readable(path) {
                return Some(path.to_path_buf());
            }
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;

    #[test]
    fn test_save_and_load_toml() -> Result<()> {
        let config = AppConfig::default();
        let temp_file = NamedTempFile::new()?;
        
        ConfigFile::save_toml(&config, temp_file.path())?;
        let loaded_config = ConfigFile::load_toml(temp_file.path())?;
        
        assert_eq!(config.web.port, loaded_config.web.port);
        assert_eq!(config.database.max_connections, loaded_config.database.max_connections);
        
        Ok(())
    }

    #[test]
    fn test_auto_detect_format() -> Result<()> {
        let config = AppConfig::default();
        
        // Test with .toml extension
        let temp_file = NamedTempFile::with_suffix(".toml")?;
        ConfigFile::save_toml(&config, temp_file.path())?;
        let loaded_config = ConfigFile::load_auto(temp_file.path())?;
        assert_eq!(config.web.port, loaded_config.web.port);
        
        Ok(())
    }
}