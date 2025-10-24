use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::database::repository::InboundUsersRepository;
use crate::services::UriGeneratorService;
use crate::web::AppState;

#[derive(Debug, Deserialize)]
pub struct IncludeUrisQuery {
    #[serde(default)]
    pub include_uris: bool,
}

#[derive(Debug, Serialize)]
pub struct ClientConfigResponse {
    pub user_id: Uuid,
    pub server_name: String,
    pub inbound_tag: String,
    pub protocol: String,
    pub uri: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub qr_code: Option<String>,
}

/// Generate URI for specific user and inbound
pub async fn get_user_inbound_config(
    State(app_state): State<AppState>,
    Path((user_id, inbound_id)): Path<(Uuid, Uuid)>,
) -> Result<Json<ClientConfigResponse>, StatusCode> {
    let repo = InboundUsersRepository::new(app_state.db.connection().clone());
    let uri_service = UriGeneratorService::new();

    // Get client configuration data
    let config_data = repo
        .get_client_config_data(user_id, inbound_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let config_data = config_data.ok_or(StatusCode::NOT_FOUND)?;

    // Generate URI
    let client_config = uri_service
        .generate_client_config(user_id, &config_data)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let response = ClientConfigResponse {
        user_id: client_config.user_id,
        server_name: client_config.server_name,
        inbound_tag: client_config.inbound_tag,
        protocol: client_config.protocol,
        uri: client_config.uri,
        qr_code: client_config.qr_code,
    };

    Ok(Json(response))
}

/// Generate all URIs for a user
pub async fn get_user_configs(
    State(app_state): State<AppState>,
    Path(user_id): Path<Uuid>,
) -> Result<Json<Vec<ClientConfigResponse>>, StatusCode> {
    let repo = InboundUsersRepository::new(app_state.db.connection().clone());
    let uri_service = UriGeneratorService::new();

    // Get all client configuration data for user
    let configs_data = repo
        .get_all_client_configs_for_user(user_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut responses = Vec::new();

    for config_data in configs_data {
        match uri_service.generate_client_config(user_id, &config_data) {
            Ok(client_config) => {
                responses.push(ClientConfigResponse {
                    user_id: client_config.user_id,
                    server_name: client_config.server_name,
                    inbound_tag: client_config.inbound_tag,
                    protocol: client_config.protocol,
                    uri: client_config.uri,
                    qr_code: client_config.qr_code,
                });
            }
            Err(_) => {
                // Log error but continue with other configs
                continue;
            }
        }
    }

    Ok(Json(responses))
}

/// Get all URIs for all users of a specific inbound
pub async fn get_inbound_configs(
    State(app_state): State<AppState>,
    Path((_server_id, inbound_id)): Path<(Uuid, Uuid)>,
) -> Result<Json<Vec<ClientConfigResponse>>, StatusCode> {
    let repo = InboundUsersRepository::new(app_state.db.connection().clone());
    let uri_service = UriGeneratorService::new();

    // Get all users for this inbound
    let inbound_users = repo
        .find_active_by_inbound_id(inbound_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut responses = Vec::new();

    for inbound_user in inbound_users {
        // Get client configuration data for each user
        if let Ok(Some(config_data)) = repo
            .get_client_config_data(inbound_user.user_id, inbound_id)
            .await
        {
            match uri_service.generate_client_config(inbound_user.user_id, &config_data) {
                Ok(client_config) => {
                    responses.push(ClientConfigResponse {
                        user_id: client_config.user_id,
                        server_name: client_config.server_name,
                        inbound_tag: client_config.inbound_tag,
                        protocol: client_config.protocol,
                        uri: client_config.uri,
                        qr_code: client_config.qr_code,
                    });
                }
                Err(_) => {
                    // Log error but continue with other configs
                    continue;
                }
            }
        }
    }

    Ok(Json(responses))
}
