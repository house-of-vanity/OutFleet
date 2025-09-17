use anyhow::Result;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod database;
mod services;
mod web;

use config::{AppConfig, args::parse_args};
use database::DatabaseManager;
use services::{TaskScheduler, XrayService};

#[tokio::main]
async fn main() -> Result<()> {
    // Parse command line arguments first
    let args = parse_args();

    // Initialize logging early with basic configuration
    init_logging(&args.log_level.as_deref().unwrap_or("info"))?;

    tracing::info!("Starting Xray Admin Panel v{}", env!("CARGO_PKG_VERSION"));

    // Handle special flags
    if args.print_default_config {
        print_default_config()?;
        return Ok(());
    }

    // Load configuration
    let config = match AppConfig::load() {
        Ok(config) => {
            tracing::info!("Configuration loaded successfully");
            config
        }
        Err(e) => {
            tracing::error!("Failed to load configuration: {}", e);
            if args.validate_config {
                std::process::exit(1);
            }
            tracing::warn!("Using default configuration");
            AppConfig::default()
        }
    };

    // Validate configuration if requested
    if args.validate_config {
        tracing::info!("Configuration validation passed");
        return Ok(());
    }

    // Display configuration summary
    config.display_summary();

    // Print environment info in debug mode
    if tracing::level_enabled!(tracing::Level::DEBUG) {
        config::env::EnvVars::print_env_info();
    }


    // Initialize database connection
    tracing::info!("Initializing database connection...");
    let db = match DatabaseManager::new(&config.database).await {
        Ok(db) => {
            tracing::info!("Database initialized successfully");
            db
        }
        Err(e) => {
            tracing::error!("Failed to initialize database: {}", e);
            return Err(e);
        }
    };

    // Perform database health check
    match db.health_check().await {
        Ok(true) => tracing::info!("Database health check passed"),
        Ok(false) => tracing::warn!("Database health check failed"),
        Err(e) => tracing::error!("Database health check error: {}", e),
    }

    // Get schema version
    if let Ok(Some(version)) = db.get_schema_version().await {
        tracing::info!("Database schema version: {}", version);
    }

    // Initialize event bus first
    let event_receiver = crate::services::events::init_event_bus();
    tracing::info!("Event bus initialized");

    // Initialize xray service
    let xray_service = XrayService::new();
    
    // Initialize and start task scheduler with dependencies
    let mut task_scheduler = TaskScheduler::new().await?;
    task_scheduler.start(db.clone(), xray_service).await?;
    tracing::info!("Task scheduler started with xray sync");

    // Start event-driven sync handler with the receiver
    TaskScheduler::start_event_handler(db.clone(), event_receiver).await;
    tracing::info!("Event-driven sync handler started");

    // Start web server with task scheduler
    tracing::info!("Starting web server on {}:{}", config.web.host, config.web.port);
    
    tokio::select! {
        result = web::start_server(db, config.web.clone()) => {
            match result {
                Ok(_) => tracing::info!("Web server stopped gracefully"),
                Err(e) => tracing::error!("Web server error: {}", e),
            }
        }
        _ = tokio::signal::ctrl_c() => {
            tracing::info!("Shutdown signal received, stopping services...");
            if let Err(e) = task_scheduler.shutdown().await {
                tracing::error!("Error shutting down task scheduler: {}", e);
            }
        }
    }

    Ok(())
}

fn init_logging(level: &str) -> Result<()> {
    let filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(level));

    tracing_subscriber::registry()
        .with(filter)
        .with(
            tracing_subscriber::fmt::layer()
                .with_target(true)  // Show module names
                .with_thread_ids(false)
                .with_thread_names(false)
                .with_file(false)
                .with_line_number(false)
                .compact()
        )
        .try_init()?;

    Ok(())
}

fn print_default_config() -> Result<()> {
    let default_config = AppConfig::default();
    let toml_content = toml::to_string_pretty(&default_config)?;
    
    println!("# Default configuration for Xray Admin Panel");
    println!("# Save this to config.toml and modify as needed\n");
    println!("{}", toml_content);
    
    Ok(())
}

#[allow(dead_code)]
fn mask_url(url: &str) -> String {
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
    fn test_mask_url() {
        let url = "postgresql://user:password@localhost/db";
        let masked = mask_url(url);
        assert!(masked.contains("***"));
        assert!(!masked.contains("password"));
    }

    #[test]
    fn test_mask_url_no_password() {
        let url = "postgresql://user@localhost/db";
        let masked = mask_url(url);
        assert_eq!(masked, url);
    }
}