use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
};
use uuid::Uuid;

use crate::{
    database::{
        entities::dns_provider::{
            CreateDnsProviderDto, UpdateDnsProviderDto, DnsProviderResponseDto,
        },
        repository::DnsProviderRepository,
    },
    web::AppState,
};

pub async fn create_dns_provider(
    State(state): State<AppState>,
    Json(dto): Json<CreateDnsProviderDto>,
) -> Result<Json<DnsProviderResponseDto>, StatusCode> {
    let repo = DnsProviderRepository::new(state.db.connection().clone());
    
    match repo.create(dto).await {
        Ok(provider) => Ok(Json(provider.to_response_dto())),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

pub async fn list_dns_providers(
    State(state): State<AppState>,
) -> Result<Json<Vec<DnsProviderResponseDto>>, StatusCode> {
    let repo = DnsProviderRepository::new(state.db.connection().clone());
    
    match repo.find_all().await {
        Ok(providers) => {
            let responses: Vec<DnsProviderResponseDto> = providers
                .into_iter()
                .map(|p| p.to_response_dto())
                .collect();
            Ok(Json(responses))
        }
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

pub async fn get_dns_provider(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<DnsProviderResponseDto>, StatusCode> {
    let repo = DnsProviderRepository::new(state.db.connection().clone());
    
    match repo.find_by_id(id).await {
        Ok(Some(provider)) => Ok(Json(provider.to_response_dto())),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

pub async fn update_dns_provider(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(dto): Json<UpdateDnsProviderDto>,
) -> Result<Json<DnsProviderResponseDto>, StatusCode> {
    let repo = DnsProviderRepository::new(state.db.connection().clone());
    
    match repo.update(id, dto).await {
        Ok(Some(updated_provider)) => Ok(Json(updated_provider.to_response_dto())),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

pub async fn delete_dns_provider(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, StatusCode> {
    let repo = DnsProviderRepository::new(state.db.connection().clone());
    
    match repo.delete(id).await {
        Ok(true) => Ok(StatusCode::NO_CONTENT),
        Ok(false) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

pub async fn list_active_cloudflare_providers(
    State(state): State<AppState>,
) -> Result<Json<Vec<DnsProviderResponseDto>>, StatusCode> {
    let repo = DnsProviderRepository::new(state.db.connection().clone());
    
    match repo.find_active_by_type("cloudflare").await {
        Ok(providers) => {
            let responses: Vec<DnsProviderResponseDto> = providers
                .into_iter()
                .map(|p| p.to_response_dto())
                .collect();
            Ok(Json(responses))
        }
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}