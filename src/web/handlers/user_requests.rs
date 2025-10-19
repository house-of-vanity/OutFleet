use axum::{
    extract::{Path, Query, State},
    Json,
    http::StatusCode,
};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::{
    database::entities::user_request::{CreateUserRequestDto, UpdateUserRequestDto, RequestStatus},
    database::repository::UserRequestRepository,
    web::AppState,
};

#[derive(Debug, Deserialize)]
pub struct RequestsQuery {
    #[serde(default = "default_page")]
    page: u64,
    #[serde(default = "default_per_page")]
    per_page: u64,
    #[serde(default)]
    status: Option<String>,
}

fn default_page() -> u64 { 1 }
fn default_per_page() -> u64 { 20 }

#[derive(Debug, Serialize)]
pub struct RequestsResponse {
    items: Vec<UserRequestResponse>,
    total: u64,
    page: u64,
    per_page: u64,
}

#[derive(Debug, Serialize)]
pub struct UserRequestResponse {
    id: Uuid,
    user_id: Option<Uuid>,
    telegram_id: i64,
    telegram_username: Option<String>,
    telegram_first_name: Option<String>,
    telegram_last_name: Option<String>,
    full_name: String,
    telegram_link: String,
    status: String,
    request_message: Option<String>,
    response_message: Option<String>,
    processed_by_user_id: Option<Uuid>,
    processed_at: Option<chrono::DateTime<chrono::Utc>>,
    created_at: chrono::DateTime<chrono::Utc>,
    updated_at: chrono::DateTime<chrono::Utc>,
}

impl From<crate::database::entities::user_request::Model> for UserRequestResponse {
    fn from(model: crate::database::entities::user_request::Model) -> Self {
        Self {
            id: model.id,
            user_id: model.user_id,
            telegram_id: model.telegram_id,
            telegram_username: model.telegram_username.clone(),
            telegram_first_name: model.telegram_first_name.clone(),
            telegram_last_name: model.telegram_last_name.clone(),
            full_name: model.get_full_name(),
            telegram_link: model.get_telegram_link(),
            status: model.status,
            request_message: model.request_message,
            response_message: model.response_message,
            processed_by_user_id: model.processed_by_user_id,
            processed_at: model.processed_at.map(|dt| dt.into()),
            created_at: model.created_at.into(),
            updated_at: model.updated_at.into(),
        }
    }
}

/// Get user requests with pagination
pub async fn get_requests(
    State(state): State<AppState>,
    Query(query): Query<RequestsQuery>,
) -> Result<Json<RequestsResponse>, StatusCode> {
    let request_repo = UserRequestRepository::new(state.db.connection());

    let (items, total) = if let Some(status) = query.status {
        // Filter by status
        match status.as_str() {
            "pending" => request_repo.find_pending(query.page, query.per_page).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
            _ => request_repo.find_all(query.page, query.per_page).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
        }
    } else {
        request_repo.find_all(query.page, query.per_page).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
    };

    let items: Vec<UserRequestResponse> = items.into_iter().map(Into::into).collect();

    Ok(Json(RequestsResponse {
        items,
        total,
        page: query.page,
        per_page: query.per_page,
    }))
}

/// Get a single user request
pub async fn get_request(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<UserRequestResponse>, StatusCode> {
    let request_repo = UserRequestRepository::new(state.db.connection());
    
    match request_repo.find_by_id(id).await {
        Ok(Some(request)) => Ok(Json(UserRequestResponse::from(request))),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

#[derive(Debug, Deserialize)]
pub struct ApproveRequestDto {
    response_message: Option<String>,
}

/// Approve a user request
pub async fn approve_request(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(dto): Json<ApproveRequestDto>,
) -> Result<Json<UserRequestResponse>, StatusCode> {
    let request_repo = UserRequestRepository::new(state.db.connection());
    let user_repo = crate::database::repository::UserRepository::new(state.db.connection());
    
    // Get the request
    let request = match request_repo.find_by_id(id).await {
        Ok(Some(request)) => request,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Check if already processed
    if request.status != "pending" {
        return Err(StatusCode::BAD_REQUEST);
    }
    
    // Create user account
    let username = request.telegram_username.as_deref().unwrap_or("Unknown");
    let user_dto = crate::database::entities::user::CreateUserDto {
        name: request.get_full_name(),
        comment: Some(format!("Telegram user: @{}", username)),
        telegram_id: Some(request.telegram_id),
        is_telegram_admin: false,
    };
    
    match user_repo.create(user_dto).await {
        Ok(new_user) => {
            // Approve the request
            let approved = match request_repo.approve(id, dto.response_message, new_user.id).await {
                Ok(Some(approved)) => approved,
                Ok(None) => return Err(StatusCode::NOT_FOUND),
                Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
            };
            
            // TODO: Send Telegram notification to user
            
            Ok(Json(UserRequestResponse::from(approved)))
        }
        Err(_) => {
            Err(StatusCode::BAD_REQUEST)
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct DeclineRequestDto {
    response_message: Option<String>,
}

/// Decline a user request
pub async fn decline_request(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(dto): Json<DeclineRequestDto>,
) -> Result<Json<UserRequestResponse>, StatusCode> {
    let request_repo = UserRequestRepository::new(state.db.connection());
    
    // Get the request
    let request = match request_repo.find_by_id(id).await {
        Ok(Some(request)) => request,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Check if already processed
    if request.status != "pending" {
        return Err(StatusCode::BAD_REQUEST);
    }
    
    // Use a default user ID for declined requests (we can set it to the first admin user)
    let dummy_user_id = Uuid::new_v4();
    
    // Decline the request
    let declined = match request_repo.decline(id, dto.response_message, dummy_user_id).await {
        Ok(Some(declined)) => declined,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // TODO: Send Telegram notification to user
    
    Ok(Json(UserRequestResponse::from(declined)))
}

/// Delete a user request
pub async fn delete_request(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    let request_repo = UserRequestRepository::new(state.db.connection());
    
    match request_repo.delete(id).await {
        Ok(true) => Ok(Json(serde_json::json!({ "message": "User request deleted" }))),
        Ok(false) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}