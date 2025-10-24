use anyhow::Result;
use axum::{http::StatusCode, response::Json, routing::get, serve, Router};
use serde_json::{json, Value};
use std::net::SocketAddr;
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;
use tower_http::services::ServeDir;
use tracing::info;

use crate::config::{AppConfig, WebConfig};
use crate::database::DatabaseManager;
use crate::services::{TelegramService, XrayService};
use std::sync::Arc;

pub mod handlers;
pub mod routes;

use routes::api_routes;

/// Application state shared across handlers
#[derive(Clone)]
pub struct AppState {
    pub db: DatabaseManager,
    pub config: AppConfig,
    pub xray_service: XrayService,
    pub telegram_service: Option<Arc<TelegramService>>,
}

/// Start the web server
pub async fn start_server(
    db: DatabaseManager,
    config: AppConfig,
    telegram_service: Option<Arc<TelegramService>>,
) -> Result<()> {
    let xray_service = XrayService::new();

    let app_state = AppState {
        db,
        config: config.clone(),
        xray_service,
        telegram_service,
    };

    // Serve static files
    let serve_dir = ServeDir::new("static");

    let app = Router::new()
        .route("/health", get(health_check))
        .route("/sub/:user_id", get(handlers::get_user_subscription))
        .nest("/api", api_routes())
        .nest_service("/", serve_dir)
        .layer(CorsLayer::permissive())
        .with_state(app_state);

    let addr: SocketAddr = format!("{}:{}", config.web.host, config.web.port).parse()?;
    info!("Starting web server on {}", addr);

    let listener = TcpListener::bind(&addr).await?;
    serve(listener, app).await?;

    Ok(())
}

/// Health check endpoint
async fn health_check() -> Result<Json<Value>, StatusCode> {
    Ok(Json(json!({
        "status": "ok",
        "service": "xray-admin",
        "version": env!("CARGO_PKG_VERSION")
    })))
}
