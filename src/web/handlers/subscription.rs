use axum::{
    extract::{Path, State},
    http::{StatusCode, HeaderMap, HeaderValue},
    response::{IntoResponse, Response},
};
use base64::{Engine, engine::general_purpose};
use uuid::Uuid;

use crate::{
    database::repository::{UserRepository, InboundUsersRepository},
    services::uri_generator::UriGeneratorService,
    web::AppState,
};

/// Get subscription links for a user by their ID
/// Returns all configuration links for the user, one per line
/// Based on Django implementation for compatibility
pub async fn get_user_subscription(
    State(state): State<AppState>,
    Path(user_id): Path<Uuid>,
) -> Result<Response, StatusCode> {
    let user_repo = UserRepository::new(state.db.connection());
    let inbound_users_repo = InboundUsersRepository::new(state.db.connection().clone());
    
    // Check if user exists
    let user = match user_repo.get_by_id(user_id).await {
        Ok(Some(user)) => user,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Get all client config data for the user (this gets all active inbound accesses)
    let all_configs = match inbound_users_repo.get_all_client_configs_for_user(user_id).await {
        Ok(configs) => configs,
        Err(e) => {
            tracing::error!("Failed to get client configs for user {}: {}", user_id, e);
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };
    
    if all_configs.is_empty() {
        let response_text = "# No configurations available\n".to_string();
        let response_base64 = general_purpose::STANDARD.encode(response_text);
        return Ok((
            StatusCode::OK,
            [("content-type", "text/plain; charset=utf-8")],
            response_base64,
        ).into_response());
    }
    
    let mut config_lines = Vec::new();
    
    // Generate connection strings for each config using existing UriGeneratorService
    let uri_generator = UriGeneratorService::new();
    
    for config_data in all_configs {
        match uri_generator.generate_client_config(user_id, &config_data) {
            Ok(client_config) => {
                config_lines.push(client_config.uri);
                tracing::debug!("Generated {} config for user {}: {}", 
                    config_data.protocol.to_uppercase(), user.name, config_data.template_name);
            }
            Err(e) => {
                tracing::warn!("Failed to generate connection string for user {} template {}: {}", 
                    user.name, config_data.template_name, e);
                continue;
            }
        }
    }
    
    if config_lines.is_empty() {
        let response_text = "# No valid configurations available\n".to_string();
        let response_base64 = general_purpose::STANDARD.encode(response_text);
        return Ok((
            StatusCode::OK,
            [("content-type", "text/plain; charset=utf-8")],
            response_base64,
        ).into_response());
    }
    
    // Join all URIs with newlines (like Django implementation)
    let response_text = config_lines.join("\n") + "\n";
    
    // Encode the entire response in base64 (like Django implementation)
    let response_base64 = general_purpose::STANDARD.encode(response_text);
    
    // Build response with subscription headers (like Django)
    let mut headers = HeaderMap::new();
    
    // Add headers required by VPN clients
    headers.insert("content-type", HeaderValue::from_static("text/plain; charset=utf-8"));
    headers.insert("content-disposition", HeaderValue::from_str(&format!("attachment; filename=\"{}\"", user.name)).unwrap());
    headers.insert("cache-control", HeaderValue::from_static("no-cache"));
    
    // Profile information
    let profile_title = general_purpose::STANDARD.encode("OutFleet VPN");
    headers.insert("profile-title", HeaderValue::from_str(&format!("base64:{}", profile_title)).unwrap());
    headers.insert("profile-update-interval", HeaderValue::from_static("24"));
    headers.insert("profile-web-page-url", HeaderValue::from_str(&format!("{}/u/{}", state.config.web.base_url, user_id)).unwrap());
    headers.insert("support-url", HeaderValue::from_str(&format!("{}/admin/", state.config.web.base_url)).unwrap());
    
    // Subscription info (unlimited service)
    let expire_timestamp = chrono::Utc::now().timestamp() + (365 * 24 * 60 * 60); // 1 year from now
    headers.insert("subscription-userinfo", 
        HeaderValue::from_str(&format!("upload=0; download=0; total=1099511627776; expire={}", expire_timestamp)).unwrap());
    
    Ok((StatusCode::OK, headers, response_base64).into_response())
}

