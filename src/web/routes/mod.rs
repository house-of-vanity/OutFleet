use axum::{
    routing::{get, post},
    Router,
};

use crate::web::{handlers, AppState};

pub mod servers;

/// Create API routes
pub fn api_routes() -> Router<AppState> {
    Router::new()
        .nest("/users", user_routes())
        .nest("/servers", servers::server_routes())
        .nest("/certificates", servers::certificate_routes())
        .nest("/templates", servers::template_routes())
        .nest("/dns-providers", dns_provider_routes())
        .nest("/tasks", task_routes())
        .nest("/telegram", telegram_routes())
        .nest("/user-requests", user_request_routes())
}

/// User management routes
fn user_routes() -> Router<AppState> {
    Router::new()
        .route("/", get(handlers::get_users).post(handlers::create_user))
        .route("/search", get(handlers::search_users))
        .route(
            "/:id",
            get(handlers::get_user)
                .put(handlers::update_user)
                .delete(handlers::delete_user),
        )
        .route("/:id/access", get(handlers::get_user_access))
        .route("/:user_id/configs", get(handlers::get_user_configs))
        .route(
            "/:user_id/access/:inbound_id/config",
            get(handlers::get_user_inbound_config),
        )
}

/// DNS Provider management routes
fn dns_provider_routes() -> Router<AppState> {
    Router::new()
        .route(
            "/",
            get(handlers::list_dns_providers).post(handlers::create_dns_provider),
        )
        .route(
            "/:id",
            get(handlers::get_dns_provider)
                .put(handlers::update_dns_provider)
                .delete(handlers::delete_dns_provider),
        )
        .route(
            "/cloudflare/active",
            get(handlers::list_active_cloudflare_providers),
        )
}

/// Task management routes
fn task_routes() -> Router<AppState> {
    Router::new()
        .route("/", get(handlers::get_tasks_status))
        .route("/:id/trigger", post(handlers::trigger_task))
}

/// Telegram bot management routes
fn telegram_routes() -> Router<AppState> {
    Router::new()
        .route(
            "/config",
            get(handlers::get_telegram_config).post(handlers::create_telegram_config),
        )
        .route(
            "/config/:id",
            get(handlers::get_telegram_config)
                .put(handlers::update_telegram_config)
                .delete(handlers::delete_telegram_config),
        )
        .route("/status", get(handlers::get_telegram_status))
        .route("/admins", get(handlers::get_telegram_admins))
        .route(
            "/admins/:user_id",
            post(handlers::add_telegram_admin).delete(handlers::remove_telegram_admin),
        )
        .route("/send", post(handlers::send_test_message))
}

/// User request management routes
fn user_request_routes() -> Router<AppState> {
    Router::new()
        .route("/", get(handlers::get_requests))
        .route(
            "/:id",
            get(handlers::get_request).delete(handlers::delete_request),
        )
        .route("/:id/approve", post(handlers::approve_request))
        .route("/:id/decline", post(handlers::decline_request))
}
