use anyhow::Result;
use sea_orm::{Database, DatabaseConnection, ConnectOptions, Statement, DatabaseBackend, ConnectionTrait};
use sea_orm_migration::MigratorTrait;
use std::time::Duration;
use tracing::{info, warn};

use crate::config::DatabaseConfig;

pub mod entities;
pub mod migrations;
pub mod repository;

use migrations::Migrator;

/// Database connection and management
#[derive(Clone)]
pub struct DatabaseManager {
    connection: DatabaseConnection,
}

impl DatabaseManager {
    /// Create a new database connection
    pub async fn new(config: &DatabaseConfig) -> Result<Self> {
        info!("Connecting to database...");
        
        // URL-encode the connection string to handle special characters in passwords
        let encoded_url = Self::encode_database_url(&config.url)?;
        
        let mut opt = ConnectOptions::new(&encoded_url);
        opt.max_connections(config.max_connections)
            .min_connections(1)
            .connect_timeout(Duration::from_secs(config.connection_timeout))
            .acquire_timeout(Duration::from_secs(config.connection_timeout))
            .idle_timeout(Duration::from_secs(600))
            .max_lifetime(Duration::from_secs(3600))
            .sqlx_logging(tracing::level_enabled!(tracing::Level::DEBUG))
            .sqlx_logging_level(log::LevelFilter::Debug);

        let connection = Database::connect(opt).await?;
        
        info!("Database connection established successfully");
        
        let manager = Self { connection };
        
        // Run migrations if auto_migrate is enabled
        if config.auto_migrate {
            manager.migrate().await?;
        }
        
        Ok(manager)
    }

    /// Get database connection
    pub fn connection(&self) -> DatabaseConnection {
        self.connection.clone()
    }

    /// Run database migrations
    pub async fn migrate(&self) -> Result<()> {
        info!("Running database migrations...");
        
        match Migrator::up(&self.connection, None).await {
            Ok(_) => {
                info!("Database migrations completed successfully");
                Ok(())
            }
            Err(e) => {
                warn!("Migration error: {}", e);
                Err(e.into())
            }
        }
    }

    /// Check database connection health
    pub async fn health_check(&self) -> Result<bool> {
        let stmt = Statement::from_string(DatabaseBackend::Postgres, "SELECT 1".to_owned());
        match self.connection.execute(stmt).await {
            Ok(_) => Ok(true),
            Err(e) => {
                warn!("Database health check failed: {}", e);
                Ok(false)
            }
        }
    }

    /// Get database schema information
    pub async fn get_schema_version(&self) -> Result<Option<String>> {
        // This would typically query a migrations table
        // For now, we'll just return a placeholder
        Ok(Some("1.0.0".to_string()))
    }

    /// Encode database URL to handle special characters in passwords
    fn encode_database_url(url: &str) -> Result<String> {
        // Parse URL manually to handle special characters in password
        if let Some(at_pos) = url.rfind('@') {
            if let Some(_colon_pos) = url[..at_pos].rfind(':') {
                if let Some(scheme_end) = url.find("://") {
                    let scheme = &url[..scheme_end + 3];
                    let user_pass = &url[scheme_end + 3..at_pos];
                    let host_db = &url[at_pos..];
                    
                    if let Some(user_colon) = user_pass.find(':') {
                        let user = &user_pass[..user_colon];
                        let password = &user_pass[user_colon + 1..];
                        
                        // URL-encode the password part only
                        let encoded_password = urlencoding::encode(password);
                        let encoded_url = format!("{}{}:{}{}", scheme, user, encoded_password, host_db);
                        
                        return Ok(encoded_url);
                    }
                }
            }
        }
        
        // If parsing fails, return original URL
        Ok(url.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::DatabaseConfig;

    #[test]
    fn test_encode_database_url() {
        let url_with_special_chars = "postgresql://user:pass#word@localhost:5432/db";
        let encoded = DatabaseManager::encode_database_url(url_with_special_chars).unwrap();
        assert_eq!(encoded, "postgresql://user:pass%23word@localhost:5432/db");

        let normal_url = "postgresql://user:password@localhost:5432/db";
        let encoded_normal = DatabaseManager::encode_database_url(normal_url).unwrap();
        assert_eq!(encoded_normal, "postgresql://user:password@localhost:5432/db");
    }

    #[tokio::test]
    async fn test_database_connection() {
        // This test requires a running PostgreSQL database
        // Skip in CI or when database is not available
        if std::env::var("DATABASE_URL").is_err() {
            return;
        }

        let config = DatabaseConfig {
            url: std::env::var("DATABASE_URL").unwrap(),
            max_connections: 5,
            connection_timeout: 30,
            auto_migrate: false,
        };

        let db = DatabaseManager::new(&config).await;
        assert!(db.is_ok());

        if let Ok(db) = db {
            let health = db.health_check().await;
            assert!(health.is_ok());
        }
    }
}