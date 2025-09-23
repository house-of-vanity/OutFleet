use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    Json as JsonExtractor,
};
use serde_json::json;
use uuid::Uuid;
use crate::{
    database::{
        entities::certificate,
        repository::CertificateRepository,
    },
    services::certificates::CertificateService,
    web::AppState,
};

/// List all certificates
pub async fn list_certificates(
    State(app_state): State<AppState>,
) -> Result<Json<Vec<certificate::CertificateResponse>>, StatusCode> {
    let repo = CertificateRepository::new(app_state.db.connection().clone());
    
    match repo.find_all().await {
        Ok(certificates) => {
            let responses: Vec<certificate::CertificateResponse> = certificates
                .into_iter()
                .map(|c| c.into())
                .collect();
            Ok(Json(responses))
        }
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Get certificate by ID
pub async fn get_certificate(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<certificate::CertificateResponse>, StatusCode> {
    let repo = CertificateRepository::new(app_state.db.connection().clone());
    
    match repo.find_by_id(id).await {
        Ok(Some(certificate)) => Ok(Json(certificate.into())),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Get certificate details with PEM data by ID
pub async fn get_certificate_details(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<certificate::CertificateDetailsResponse>, StatusCode> {
    let repo = CertificateRepository::new(app_state.db.connection().clone());
    
    match repo.find_by_id(id).await {
        Ok(Some(certificate)) => Ok(Json(certificate.into())),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Create new certificate
pub async fn create_certificate(
    State(app_state): State<AppState>,
    JsonExtractor(cert_data): JsonExtractor<certificate::CreateCertificateDto>,
) -> Result<Json<certificate::CertificateResponse>, (StatusCode, Json<serde_json::Value>)> {
    tracing::info!("Creating certificate: {:?}", cert_data);
    let repo = CertificateRepository::new(app_state.db.connection().clone());
    let cert_service = CertificateService::new();
    
    // Generate certificate based on type
    let (cert_pem, private_key) = match cert_data.cert_type.as_str() {
        "self_signed" => {
            cert_service.generate_self_signed(&cert_data.domain).await
                .map_err(|e| {
                    tracing::error!("Failed to generate self-signed certificate: {:?}", e);
                    (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
                        "error": "Failed to generate self-signed certificate",
                        "details": format!("{:?}", e)
                    })))
                })?
        }
        "letsencrypt" => {
            // Validate required fields for Let's Encrypt
            let dns_provider_id = cert_data.dns_provider_id
                .ok_or((StatusCode::BAD_REQUEST, Json(json!({
                    "error": "DNS provider ID is required for Let's Encrypt certificates"
                }))))?;
            let acme_email = cert_data.acme_email
                .as_ref()
                .ok_or((StatusCode::BAD_REQUEST, Json(json!({
                    "error": "ACME email is required for Let's Encrypt certificates"
                }))))?;
            
            let cert_service = CertificateService::with_db(app_state.db.connection().clone());
            cert_service.generate_letsencrypt_certificate(
                &cert_data.domain,
                dns_provider_id,
                acme_email,
                false // production by default
            ).await
                .map_err(|e| {
                    tracing::error!("Failed to generate Let's Encrypt certificate: {:?}", e);
                    // Return a more detailed error response
                    (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
                        "error": "Failed to generate Let's Encrypt certificate",
                        "details": format!("{:?}", e)
                    })))
                })?
        }
        "imported" => {
            // For imported certificates, use provided PEM data
            if cert_data.certificate_pem.is_empty() || cert_data.private_key.is_empty() {
                return Err((StatusCode::BAD_REQUEST, Json(json!({
                    "error": "Certificate PEM and private key are required for imported certificates"
                }))));
            }
            (cert_data.certificate_pem.clone(), cert_data.private_key.clone())
        }
        _ => return Err((StatusCode::BAD_REQUEST, Json(json!({
            "error": "Invalid certificate type. Supported types: self_signed, letsencrypt, imported"
        })))),
    };
    
    // Create certificate with generated data
    let mut create_dto = cert_data;
    create_dto.certificate_pem = cert_pem;
    create_dto.private_key = private_key;
    
    match repo.create(create_dto).await {
        Ok(certificate) => Ok(Json(certificate.into())),
        Err(e) => {
            tracing::error!("Failed to save certificate to database: {:?}", e);
            Err((StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
                "error": "Failed to save certificate to database",
                "details": format!("{:?}", e)
            }))))
        }
    }
}

/// Update certificate
pub async fn update_certificate(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
    JsonExtractor(cert_data): JsonExtractor<certificate::UpdateCertificateDto>,
) -> Result<Json<certificate::CertificateResponse>, StatusCode> {
    let repo = CertificateRepository::new(app_state.db.connection().clone());
    
    match repo.update(id, cert_data).await {
        Ok(certificate) => Ok(Json(certificate.into())),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Delete certificate
pub async fn delete_certificate(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, StatusCode> {
    let repo = CertificateRepository::new(app_state.db.connection().clone());
    
    match repo.delete(id).await {
        Ok(true) => Ok(StatusCode::NO_CONTENT),
        Ok(false) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Get certificates expiring soon
pub async fn get_expiring_certificates(
    State(app_state): State<AppState>,
) -> Result<Json<Vec<certificate::CertificateResponse>>, StatusCode> {
    let repo = CertificateRepository::new(app_state.db.connection().clone());
    
    // Get certificates expiring in next 30 days
    match repo.find_expiring_soon(30).await {
        Ok(certificates) => {
            let responses: Vec<certificate::CertificateResponse> = certificates
                .into_iter()
                .map(|c| c.into())
                .collect();
            Ok(Json(responses))
        }
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}