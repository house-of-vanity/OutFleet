use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::Json,
    Json as JsonExtractor,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use uuid::Uuid;

use crate::database::entities::user::{CreateUserDto, Model as UserModel, UpdateUserDto};
use crate::database::repository::UserRepository;
use crate::web::AppState;

use super::client_configs::IncludeUrisQuery;

#[derive(Debug, Deserialize)]
pub struct PaginationQuery {
    #[serde(default = "default_page")]
    pub page: u64,
    #[serde(default = "default_per_page")]
    pub per_page: u64,
}

#[derive(Debug, Deserialize)]
pub struct SearchQuery {
    pub q: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct UsersResponse {
    pub users: Vec<UserResponse>,
    pub total: u64,
    pub page: u64,
    pub per_page: u64,
}

#[derive(Debug, Serialize)]
pub struct UserResponse {
    pub id: Uuid,
    pub name: String,
    pub comment: Option<String>,
    pub telegram_id: Option<i64>,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: chrono::DateTime<chrono::Utc>,
}

fn default_page() -> u64 {
    1
}
fn default_per_page() -> u64 {
    20
}

impl From<UserModel> for UserResponse {
    fn from(user: UserModel) -> Self {
        Self {
            id: user.id,
            name: user.name,
            comment: user.comment,
            telegram_id: user.telegram_id,
            created_at: user.created_at,
            updated_at: user.updated_at,
        }
    }
}

/// Get all users with pagination
pub async fn get_users(
    State(app_state): State<AppState>,
    Query(query): Query<PaginationQuery>,
) -> Result<Json<UsersResponse>, StatusCode> {
    let repo = UserRepository::new(app_state.db.connection().clone());

    let users = repo
        .get_all(query.page, query.per_page)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let total = repo
        .count()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let response = UsersResponse {
        users: users.into_iter().map(UserResponse::from).collect(),
        total,
        page: query.page,
        per_page: query.per_page,
    };

    Ok(Json(response))
}

/// Search users by name, telegram_id or user_id
pub async fn search_users(
    State(app_state): State<AppState>,
    Query(query): Query<SearchQuery>,
) -> Result<Json<Vec<UserResponse>>, StatusCode> {
    let repo = UserRepository::new(app_state.db.connection().clone());

    let users = if let Some(search_query) = query.q {
        // Search by name, telegram_id, or UUID
        repo.search(&search_query)
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
    } else {
        // If no query, return empty array
        Vec::new()
    };

    let response: Vec<UserResponse> = users.into_iter().map(UserResponse::from).collect();
    Ok(Json(response))
}

/// Get user by ID
pub async fn get_user(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<UserResponse>, StatusCode> {
    let repo = UserRepository::new(app_state.db.connection().clone());

    let user = repo
        .get_by_id(id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    match user {
        Some(user) => Ok(Json(UserResponse::from(user))),
        None => Err(StatusCode::NOT_FOUND),
    }
}

/// Create a new user
pub async fn create_user(
    State(app_state): State<AppState>,
    JsonExtractor(dto): JsonExtractor<CreateUserDto>,
) -> Result<Json<UserResponse>, StatusCode> {
    let repo = UserRepository::new(app_state.db.connection().clone());

    // Check if telegram ID is already in use
    if let Some(telegram_id) = dto.telegram_id {
        let exists = repo
            .telegram_id_exists(telegram_id)
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        if exists {
            return Err(StatusCode::CONFLICT);
        }
    }

    let user = repo
        .create(dto)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(UserResponse::from(user)))
}

/// Update user by ID
pub async fn update_user(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
    JsonExtractor(dto): JsonExtractor<UpdateUserDto>,
) -> Result<Json<UserResponse>, StatusCode> {
    let repo = UserRepository::new(app_state.db.connection().clone());

    // Check if telegram ID is already in use by another user
    if let Some(telegram_id) = dto.telegram_id {
        if let Some(existing_user) = repo
            .get_by_telegram_id(telegram_id)
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        {
            if existing_user.id != id {
                return Err(StatusCode::CONFLICT);
            }
        }
    }

    let user = repo
        .update(id, dto)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    match user {
        Some(user) => Ok(Json(UserResponse::from(user))),
        None => Err(StatusCode::NOT_FOUND),
    }
}

/// Delete user by ID
pub async fn delete_user(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, StatusCode> {
    let repo = UserRepository::new(app_state.db.connection().clone());

    let deleted = repo
        .delete(id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if deleted {
        Ok(Json(json!({ "message": "User deleted successfully" })))
    } else {
        Err(StatusCode::NOT_FOUND)
    }
}

/// Get user access (inbound associations)
pub async fn get_user_access(
    State(app_state): State<AppState>,
    Path(user_id): Path<Uuid>,
    Query(query): Query<IncludeUrisQuery>,
) -> Result<Json<Vec<serde_json::Value>>, StatusCode> {
    use crate::database::repository::InboundUsersRepository;
    use crate::services::UriGeneratorService;

    let inbound_users_repo = InboundUsersRepository::new(app_state.db.connection().clone());

    let access_list = inbound_users_repo
        .find_by_user_id(user_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut response: Vec<serde_json::Value> = Vec::new();

    if query.include_uris {
        let uri_service = UriGeneratorService::new();

        for access in access_list {
            let mut access_json = serde_json::json!({
                "id": access.id,
                "user_id": access.user_id,
                "server_inbound_id": access.server_inbound_id,
                "xray_user_id": access.xray_user_id,
                "level": access.level,
                "is_active": access.is_active,
            });

            // Try to get client config and generate URI
            if access.is_active {
                if let Ok(Some(config_data)) = inbound_users_repo
                    .get_client_config_data(user_id, access.server_inbound_id)
                    .await
                {
                    if let Ok(client_config) =
                        uri_service.generate_client_config(user_id, &config_data)
                    {
                        access_json["uri"] = serde_json::Value::String(client_config.uri);
                        access_json["protocol"] = serde_json::Value::String(client_config.protocol);
                        access_json["server_name"] =
                            serde_json::Value::String(client_config.server_name);
                        access_json["inbound_tag"] =
                            serde_json::Value::String(client_config.inbound_tag);
                    }
                }
            }

            response.push(access_json);
        }
    } else {
        response = access_list
            .into_iter()
            .map(|access| {
                serde_json::json!({
                    "id": access.id,
                    "user_id": access.user_id,
                    "server_inbound_id": access.server_inbound_id,
                    "xray_user_id": access.xray_user_id,
                    "level": access.level,
                    "is_active": access.is_active,
                })
            })
            .collect();
    }

    Ok(Json(response))
}
