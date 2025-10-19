use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::{IntoResponse, Response},
};
use uuid::Uuid;

use crate::{
    database::repository::{UserRepository, InboundUsersRepository},
    services::uri_generator::UriGeneratorService,
    web::AppState,
};

/// Get subscription links for a user by their ID
/// Returns all configuration links for the user, one per line
pub async fn get_user_subscription(
    State(state): State<AppState>,
    Path(user_id): Path<Uuid>,
) -> Result<Response, StatusCode> {
    let user_repo = UserRepository::new(state.db.connection());
    let inbound_users_repo = InboundUsersRepository::new(state.db.connection().clone());
    let uri_generator = UriGeneratorService::new();
    
    // Check if user exists
    let user = match user_repo.get_by_id(user_id).await {
        Ok(Some(user)) => user,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Get all inbound accesses for this user
    let user_inbounds = match inbound_users_repo.find_by_user_id(user_id).await {
        Ok(inbounds) => inbounds,
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    if user_inbounds.is_empty() {
        let response = "# No configurations available\n".to_string();
        return Ok((
            StatusCode::OK,
            [("content-type", "text/plain; charset=utf-8")],
            response,
        ).into_response());
    }
    
    let mut config_lines = Vec::new();
    
    // Generate URI for each inbound access
    for user_inbound in user_inbounds {
        // Get client configuration data using the existing repository method
        match inbound_users_repo.get_client_config_data(user_id, user_inbound.server_inbound_id).await {
            Ok(Some(config_data)) => {
                // Generate URI
                match uri_generator.generate_client_config(user_id, &config_data) {
                    Ok(client_config) => {
                        config_lines.push(client_config.uri);
                    }
                    Err(e) => {
                        tracing::warn!("Failed to generate URI for user {} inbound {}: {}", user_id, user_inbound.server_inbound_id, e);
                        continue;
                    }
                }
            }
            Ok(None) => {
                tracing::debug!("No config data found for user {} inbound {}", user_id, user_inbound.server_inbound_id);
                continue;
            }
            Err(e) => {
                tracing::warn!("Failed to get config data for user {} inbound {}: {}", user_id, user_inbound.server_inbound_id, e);
                continue;
            }
        }
    }
    
    if config_lines.is_empty() {
        let response = "# No valid configurations available\n".to_string();
        return Ok((
            StatusCode::OK,
            [("content-type", "text/plain; charset=utf-8")],
            response,
        ).into_response());
    }
    
    // Join all URIs with newlines
    let response = config_lines.join("\n") + "\n";
    
    Ok((
        StatusCode::OK,
        [("content-type", "text/plain; charset=utf-8")],
        response,
    ).into_response())
}