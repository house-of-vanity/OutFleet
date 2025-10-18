use axum::{
    extract::{State, Path, Json},
    http::StatusCode,
    response::IntoResponse,
};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::web::AppState;
use crate::database::repository::{UserRepository, TelegramConfigRepository};
use crate::database::entities::telegram_config::{CreateTelegramConfigDto, UpdateTelegramConfigDto};

/// Response for Telegram config
#[derive(Debug, Serialize)]
pub struct TelegramConfigResponse {
    pub id: Uuid,
    pub is_active: bool,
    pub bot_info: Option<BotInfo>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Serialize)]
pub struct BotInfo {
    pub username: String,
    pub first_name: String,
}

/// Get current Telegram configuration
pub async fn get_telegram_config(
    State(state): State<AppState>,
) -> impl IntoResponse {
    let repo = TelegramConfigRepository::new(state.db.connection());
    
    match repo.get_latest().await {
        Ok(Some(config)) => {
            let mut response = TelegramConfigResponse {
                id: config.id,
                is_active: config.is_active,
                bot_info: None,
                created_at: config.created_at.to_rfc3339(),
                updated_at: config.updated_at.to_rfc3339(),
            };

            // Get bot info if active
            if config.is_active {
                if let Ok(status) = get_bot_status(&state).await {
                    response.bot_info = status.bot_info;
                }
            }

            Json(response).into_response()
        }
        Ok(None) => {
            StatusCode::NOT_FOUND.into_response()
        }
        Err(e) => {
            tracing::error!("Failed to get telegram config: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// Create new Telegram configuration
pub async fn create_telegram_config(
    State(state): State<AppState>,
    Json(dto): Json<CreateTelegramConfigDto>,
) -> impl IntoResponse {
    let repo = TelegramConfigRepository::new(state.db.connection());
    
    match repo.create(dto).await {
        Ok(config) => {
            // Initialize telegram service with new config if active
            if config.is_active {
                if let Some(telegram_service) = &state.telegram_service {
                    let _ = telegram_service.update_config(config.id).await;
                }
            }
            
            (StatusCode::CREATED, Json(config)).into_response()
        }
        Err(e) => {
            tracing::error!("Failed to create telegram config: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// Update Telegram configuration
pub async fn update_telegram_config(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(dto): Json<UpdateTelegramConfigDto>,
) -> impl IntoResponse {
    let repo = TelegramConfigRepository::new(state.db.connection());
    
    match repo.update(id, dto).await {
        Ok(Some(config)) => {
            // Update telegram service
            if let Some(telegram_service) = &state.telegram_service {
                let _ = telegram_service.update_config(config.id).await;
            }
            
            Json(config).into_response()
        }
        Ok(None) => {
            StatusCode::NOT_FOUND.into_response()
        }
        Err(e) => {
            tracing::error!("Failed to update telegram config: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// Delete Telegram configuration
pub async fn delete_telegram_config(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> impl IntoResponse {
    let repo = TelegramConfigRepository::new(state.db.connection());
    
    // Stop bot if this config is active
    if let Ok(Some(config)) = repo.find_by_id(id).await {
        if config.is_active {
            if let Some(telegram_service) = &state.telegram_service {
                let _ = telegram_service.stop().await;
            }
        }
    }
    
    match repo.delete(id).await {
        Ok(true) => StatusCode::NO_CONTENT.into_response(),
        Ok(false) => StatusCode::NOT_FOUND.into_response(),
        Err(e) => {
            tracing::error!("Failed to delete telegram config: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// Get Telegram bot status
#[derive(Debug, Serialize)]
pub struct BotStatusResponse {
    pub is_running: bool,
    pub bot_info: Option<BotInfo>,
}

async fn get_bot_status(state: &AppState) -> Result<BotStatusResponse, String> {
    if let Some(telegram_service) = &state.telegram_service {
        let status = telegram_service.get_status().await;
        
        let bot_info = if status.is_running {
            // In production, you would get this from the bot API
            Some(BotInfo {
                username: "bot".to_string(),
                first_name: "Bot".to_string(),
            })
        } else {
            None
        };
        
        Ok(BotStatusResponse {
            is_running: status.is_running,
            bot_info,
        })
    } else {
        Ok(BotStatusResponse {
            is_running: false,
            bot_info: None,
        })
    }
}

pub async fn get_telegram_status(
    State(state): State<AppState>,
) -> impl IntoResponse {
    match get_bot_status(&state).await {
        Ok(status) => Json(status).into_response(),
        Err(e) => {
            tracing::error!("Failed to get bot status: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// Get list of Telegram admins
#[derive(Debug, Serialize)]
pub struct TelegramAdmin {
    pub user_id: Uuid,
    pub name: String,
    pub telegram_id: Option<i64>,
}

pub async fn get_telegram_admins(
    State(state): State<AppState>,
) -> impl IntoResponse {
    let repo = UserRepository::new(state.db.connection());
    
    match repo.get_telegram_admins().await {
        Ok(admins) => {
            let response: Vec<TelegramAdmin> = admins
                .into_iter()
                .map(|u| TelegramAdmin {
                    user_id: u.id,
                    name: u.name,
                    telegram_id: u.telegram_id,
                })
                .collect();
            
            Json(response).into_response()
        }
        Err(e) => {
            tracing::error!("Failed to get telegram admins: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// Add Telegram admin
pub async fn add_telegram_admin(
    State(state): State<AppState>,
    Path(user_id): Path<Uuid>,
) -> impl IntoResponse {
    let repo = UserRepository::new(state.db.connection());
    
    match repo.set_telegram_admin(user_id, true).await {
        Ok(Some(user)) => {
            // Notify via Telegram if bot is running
            if let Some(telegram_service) = &state.telegram_service {
                if let Some(telegram_id) = user.telegram_id {
                    let _ = telegram_service.send_message(
                        telegram_id,
                        "✅ You have been granted admin privileges!".to_string()
                    ).await;
                }
            }
            
            Json(user).into_response()
        }
        Ok(None) => {
            StatusCode::NOT_FOUND.into_response()
        }
        Err(e) => {
            tracing::error!("Failed to add telegram admin: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// Remove Telegram admin
pub async fn remove_telegram_admin(
    State(state): State<AppState>,
    Path(user_id): Path<Uuid>,
) -> impl IntoResponse {
    let repo = UserRepository::new(state.db.connection());
    
    match repo.set_telegram_admin(user_id, false).await {
        Ok(Some(user)) => {
            // Notify via Telegram if bot is running
            if let Some(telegram_service) = &state.telegram_service {
                if let Some(telegram_id) = user.telegram_id {
                    let _ = telegram_service.send_message(
                        telegram_id,
                        "❌ Your admin privileges have been revoked.".to_string()
                    ).await;
                }
            }
            
            Json(user).into_response()
        }
        Ok(None) => {
            StatusCode::NOT_FOUND.into_response()
        }
        Err(e) => {
            tracing::error!("Failed to remove telegram admin: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// Send test message
#[derive(Debug, Deserialize)]
pub struct SendMessageRequest {
    pub chat_id: i64,
    pub text: String,
}

pub async fn send_test_message(
    State(state): State<AppState>,
    Json(req): Json<SendMessageRequest>,
) -> impl IntoResponse {
    if let Some(telegram_service) = &state.telegram_service {
        match telegram_service.send_message(req.chat_id, req.text).await {
            Ok(_) => StatusCode::OK.into_response(),
            Err(e) => {
                tracing::error!("Failed to send test message: {}", e);
                (StatusCode::BAD_REQUEST, e.to_string()).into_response()
            }
        }
    } else {
        StatusCode::SERVICE_UNAVAILABLE.into_response()
    }
}