use crate::{
    database::{entities::inbound_template, repository::InboundTemplateRepository},
    web::AppState,
};
use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    Json as JsonExtractor,
};
use uuid::Uuid;

/// List all inbound templates
pub async fn list_templates(
    State(app_state): State<AppState>,
) -> Result<Json<Vec<inbound_template::InboundTemplateResponse>>, StatusCode> {
    let repo = InboundTemplateRepository::new(app_state.db.connection().clone());

    match repo.find_all().await {
        Ok(templates) => {
            let responses: Vec<inbound_template::InboundTemplateResponse> =
                templates.into_iter().map(|t| t.into()).collect();
            Ok(Json(responses))
        }
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Get template by ID
pub async fn get_template(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<inbound_template::InboundTemplateResponse>, StatusCode> {
    let repo = InboundTemplateRepository::new(app_state.db.connection().clone());

    match repo.find_by_id(id).await {
        Ok(Some(template)) => Ok(Json(template.into())),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Create new template
pub async fn create_template(
    State(app_state): State<AppState>,
    JsonExtractor(template_data): JsonExtractor<inbound_template::CreateInboundTemplateDto>,
) -> Result<Json<inbound_template::InboundTemplateResponse>, StatusCode> {
    tracing::info!("Creating template: {:?}", template_data);
    let repo = InboundTemplateRepository::new(app_state.db.connection().clone());

    match repo.create(template_data).await {
        Ok(template) => Ok(Json(template.into())),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Update template
pub async fn update_template(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
    JsonExtractor(template_data): JsonExtractor<inbound_template::UpdateInboundTemplateDto>,
) -> Result<Json<inbound_template::InboundTemplateResponse>, StatusCode> {
    let repo = InboundTemplateRepository::new(app_state.db.connection().clone());

    match repo.update(id, template_data).await {
        Ok(template) => Ok(Json(template.into())),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Delete template
pub async fn delete_template(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, StatusCode> {
    let repo = InboundTemplateRepository::new(app_state.db.connection().clone());

    match repo.delete(id).await {
        Ok(true) => Ok(StatusCode::NO_CONTENT),
        Ok(false) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}
