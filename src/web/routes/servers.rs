use axum::{
    routing::{get, post},
    Router,
};
use crate::{
    web::{AppState, handlers},
};

pub fn server_routes() -> Router<AppState> {
    Router::new()
        // Server management
        .route("/", get(handlers::list_servers).post(handlers::create_server))
        .route("/:id", get(handlers::get_server).put(handlers::update_server).delete(handlers::delete_server))
        .route("/:id/test", post(handlers::test_server_connection))
        .route("/:id/stats", get(handlers::get_server_stats))
        
        // Server inbounds
        .route("/:server_id/inbounds", get(handlers::list_server_inbounds).post(handlers::create_server_inbound))
        .route("/:server_id/inbounds/:inbound_id", get(handlers::get_server_inbound).put(handlers::update_server_inbound).delete(handlers::delete_server_inbound))
        
        // User management for inbounds
        .route("/:server_id/inbounds/:inbound_id/users", post(handlers::add_user_to_inbound))
        .route("/:server_id/inbounds/:inbound_id/users/:email", axum::routing::delete(handlers::remove_user_from_inbound))
        
        // Client configurations for inbounds
        .route("/:server_id/inbounds/:inbound_id/configs", get(handlers::get_inbound_configs))
}

pub fn certificate_routes() -> Router<AppState> {
    Router::new()
        .route("/", get(handlers::list_certificates).post(handlers::create_certificate))
        .route("/:id", get(handlers::get_certificate).put(handlers::update_certificate).delete(handlers::delete_certificate))
        .route("/:id/details", get(handlers::get_certificate_details))
        .route("/expiring", get(handlers::get_expiring_certificates))
}

pub fn template_routes() -> Router<AppState> {
    Router::new()
        .route("/", get(handlers::list_templates).post(handlers::create_template))
        .route("/:id", get(handlers::get_template).put(handlers::update_template).delete(handlers::delete_template))
}