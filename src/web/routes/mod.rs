use axum::{
    Router,
    routing::get,
};

use crate::web::{AppState, handlers};

pub mod servers;

/// Create API routes
pub fn api_routes() -> Router<AppState> {
    Router::new()
        .nest("/users", user_routes())
        .nest("/servers", servers::server_routes())
        .nest("/certificates", servers::certificate_routes())
        .nest("/templates", servers::template_routes())
}

/// User management routes
fn user_routes() -> Router<AppState> {
    Router::new()
        .route("/", get(handlers::get_users).post(handlers::create_user))
        .route("/search", get(handlers::search_users))
        .route("/:id", get(handlers::get_user)
            .put(handlers::update_user)
            .delete(handlers::delete_user))
}