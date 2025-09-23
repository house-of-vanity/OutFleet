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
    // Initialize default crypto provider for rustls
    rustls::crypto::aws_lc_rs::default_provider()
        .install_default()
        .expect("Failed to install rustls crypto provider");

    // Parse command line arguments first
    let args = parse_args();

    // Initialize logging early with basic configuration
    init_logging(&args.log_level.as_deref().unwrap_or("info"))?;


    // Handle special flags
    if args.print_default_config {
        print_default_config()?;
        return Ok(());
    }

    // Load configuration
    let config = match AppConfig::load() {
        Ok(config) => {
            config
        }
        Err(e) => {
            tracing::error!("Failed to load configuration: {}", e);
            if args.validate_config {
                std::process::exit(1);
            }
            AppConfig::default()
        }
    };

    // Validate configuration if requested
    if args.validate_config {
        return Ok(());
    }

    // Display configuration summary
    config.display_summary();

    // Print environment info in debug mode
    if tracing::level_enabled!(tracing::Level::DEBUG) {
        config::env::EnvVars::print_env_info();
    }


    // Initialize database connection
    let db = match DatabaseManager::new(&config.database).await {
        Ok(db) => {
            db
        }
        Err(e) => {
            tracing::error!("Failed to initialize database: {}", e);
            return Err(e);
        }
    };

    // Perform database health check
    match db.health_check().await {
        Ok(false) => tracing::warn!("Database health check failed"),
        Err(e) => tracing::error!("Database health check error: {}", e),
        _ => {}
    }

    // Initialize event bus first
    let event_receiver = crate::services::events::init_event_bus();

    // Initialize xray service
    let xray_service = XrayService::new();
    
    // Initialize and start task scheduler with dependencies
    let mut task_scheduler = TaskScheduler::new().await?;
    task_scheduler.start(db.clone(), xray_service).await?;

    // Start event-driven sync handler with the receiver
    TaskScheduler::start_event_handler(db.clone(), event_receiver).await;

    // Start web server with task scheduler
    
    tokio::select! {
        result = web::start_server(db, config.web.clone()) => {
            match result {
                Err(e) => tracing::error!("Web server error: {}", e),
                _ => {}
            }
        }
        _ = tokio::signal::ctrl_c() => {
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