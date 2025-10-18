use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    Json as JsonExtractor,
};
use uuid::Uuid;
use crate::{
    database::{
        entities::{server, server_inbound},
        repository::{ServerRepository, ServerInboundRepository, InboundTemplateRepository, CertificateRepository, InboundUsersRepository, UserRepository},
    },
    web::AppState,
};

/// List all servers
pub async fn list_servers(
    State(app_state): State<AppState>,
) -> Result<Json<Vec<server::ServerResponse>>, StatusCode> {
    let repo = ServerRepository::new(app_state.db.connection().clone());
    
    match repo.find_all().await {
        Ok(servers) => {
            let responses: Vec<server::ServerResponse> = servers
                .into_iter()
                .map(|s| s.into())
                .collect();
            Ok(Json(responses))
        }
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Get server by ID
pub async fn get_server(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<server::ServerResponse>, StatusCode> {
    let repo = ServerRepository::new(app_state.db.connection().clone());
    
    match repo.find_by_id(id).await {
        Ok(Some(server)) => Ok(Json(server.into())),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Create new server
pub async fn create_server(
    State(app_state): State<AppState>,
    Json(server_data): Json<server::CreateServerDto>,
) -> Result<Json<server::ServerResponse>, StatusCode> {
    let repo = ServerRepository::new(app_state.db.connection().clone());
    
    match repo.create(server_data).await {
        Ok(server) => Ok(Json(server.into())),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Update server
pub async fn update_server(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(server_data): Json<server::UpdateServerDto>,
) -> Result<Json<server::ServerResponse>, StatusCode> {
    let repo = ServerRepository::new(app_state.db.connection().clone());
    
    match repo.update(id, server_data).await {
        Ok(server) => Ok(Json(server.into())),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Delete server
pub async fn delete_server(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, StatusCode> {
    let repo = ServerRepository::new(app_state.db.connection().clone());
    
    match repo.delete(id).await {
        Ok(true) => Ok(StatusCode::NO_CONTENT),
        Ok(false) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Test server connection
pub async fn test_server_connection(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    let repo = ServerRepository::new(app_state.db.connection().clone());
    
    let server = match repo.find_by_id(id).await {
        Ok(Some(server)) => server,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };

    let endpoint = server.get_grpc_endpoint();
    
    match app_state.xray_service.test_connection(id, &endpoint).await {
        Ok(connected) => {
            // Update server status based on connection test
            let new_status = if connected { "online" } else { "offline" };
            let update_dto = server::UpdateServerDto {
                name: None,
                hostname: None,
                grpc_hostname: None,
                grpc_port: None,
                api_credentials: None,
                default_certificate_id: None,
                status: Some(new_status.to_string()),
            };
            
            let _ = repo.update(id, update_dto).await; // Ignore update errors for now
            
            Ok(Json(serde_json::json!({
                "connected": connected,
                "endpoint": endpoint
            })))
        },
        Err(e) => {
            // Update status to error
            let update_dto = server::UpdateServerDto {
                name: None,
                hostname: None,
                grpc_hostname: None,
                grpc_port: None,
                api_credentials: None,
                default_certificate_id: None,
                status: Some("error".to_string()),
            };
            
            let _ = repo.update(id, update_dto).await; // Ignore update errors for now
            
            Ok(Json(serde_json::json!({
                "connected": false,
                "endpoint": endpoint,
                "error": e.to_string()
            })))
        },
    }
}

/// Get server statistics
pub async fn get_server_stats(
    State(app_state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    let repo = ServerRepository::new(app_state.db.connection().clone());
    
    let server = match repo.find_by_id(id).await {
        Ok(Some(server)) => server,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };

    let endpoint = server.get_grpc_endpoint();
    
    match app_state.xray_service.get_stats(id, &endpoint).await {
        Ok(stats) => Ok(Json(stats)),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// List server inbounds
pub async fn list_server_inbounds(
    State(app_state): State<AppState>,
    Path(server_id): Path<Uuid>,
) -> Result<Json<Vec<server_inbound::ServerInboundResponse>>, StatusCode> {
    let repo = ServerInboundRepository::new(app_state.db.connection().clone());
    
    match repo.find_by_server_id_with_template(server_id).await {
        Ok(responses) => Ok(Json(responses)),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Create server inbound
pub async fn create_server_inbound(
    State(app_state): State<AppState>,
    Path(server_id): Path<Uuid>,
    JsonExtractor(inbound_data): JsonExtractor<server_inbound::CreateServerInboundDto>,
) -> Result<Json<server_inbound::ServerInboundResponse>, StatusCode> {
    tracing::debug!("Creating server inbound for server {}", server_id);
    
    let server_repo = ServerRepository::new(app_state.db.connection().clone());
    let inbound_repo = ServerInboundRepository::new(app_state.db.connection().clone());
    let template_repo = InboundTemplateRepository::new(app_state.db.connection().clone());
    let cert_repo = CertificateRepository::new(app_state.db.connection().clone());
    
    // Get server info
    let server = match server_repo.find_by_id(server_id).await {
        Ok(Some(server)) => server,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Get template info
    let template = match template_repo.find_by_id(inbound_data.template_id).await {
        Ok(Some(template)) => template,
        Ok(None) => return Err(StatusCode::BAD_REQUEST),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Create inbound in database first with protocol-aware tag
    let inbound = match inbound_repo.create_with_protocol(server_id, inbound_data, &template.protocol).await {
        Ok(inbound) => {
            // Send sync event for immediate synchronization
            crate::services::events::send_sync_event(
                crate::services::events::SyncEvent::InboundChanged(server_id)
            );
            inbound
        },
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Try to create inbound on xray server only if it's active
    let endpoint = server.get_grpc_endpoint();
    if inbound.is_active {
        // Get certificate data if certificate is specified
        let (cert_pem, key_pem) = if let Some(cert_id) = inbound.certificate_id {
            match cert_repo.find_by_id(cert_id).await {
                Ok(Some(cert)) => {
                    (Some(cert.certificate_pem()), Some(cert.private_key_pem()))
                },
                Ok(None) => {
                    tracing::warn!("Certificate {} not found", cert_id);
                    (None, None)
                },
                Err(e) => {
                    tracing::error!("Error fetching certificate {}: {}", cert_id, e);
                    (None, None)
                }
            }
        } else {
            (None, None)
        };

        match app_state.xray_service.create_inbound_with_certificate(
            server_id,
            &endpoint,
            &inbound.tag,
            inbound.port_override.unwrap_or(template.default_port),
            &template.protocol,
            template.base_settings.clone(),
            template.stream_settings.clone(),
            cert_pem.as_deref(),
            key_pem.as_deref(),
        ).await {
            Ok(_) => {
                tracing::info!("Created inbound '{}' on {}", inbound.tag, endpoint);
            },
            Err(e) => {
                tracing::error!("Failed to create inbound '{}' on {}: {}", inbound.tag, endpoint, e);
                // Note: We don't fail the request since the inbound is already in DB
                // The user can manually sync or retry later
            }
        }
    } else {
        tracing::debug!("Inbound '{}' created as inactive", inbound.tag);
    }
    
    Ok(Json(inbound.into()))
}

/// Update server inbound
pub async fn update_server_inbound(
    State(app_state): State<AppState>,
    Path((server_id, inbound_id)): Path<(Uuid, Uuid)>,
    JsonExtractor(inbound_data): JsonExtractor<server_inbound::UpdateServerInboundDto>,
) -> Result<Json<server_inbound::ServerInboundResponse>, StatusCode> {
    tracing::debug!("Updating server inbound {} for server {}", inbound_id, server_id);
    
    let server_repo = ServerRepository::new(app_state.db.connection().clone());
    let inbound_repo = ServerInboundRepository::new(app_state.db.connection().clone());
    let template_repo = InboundTemplateRepository::new(app_state.db.connection().clone());
    let cert_repo = CertificateRepository::new(app_state.db.connection().clone());
    
    // Get server info
    let server = match server_repo.find_by_id(server_id).await {
        Ok(Some(server)) => server,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Get current inbound state
    let current_inbound = match inbound_repo.find_by_id(inbound_id).await {
        Ok(Some(inbound)) if inbound.server_id == server_id => inbound,
        Ok(Some(_)) => return Err(StatusCode::BAD_REQUEST),
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Check if is_active status is changing
    let old_is_active = current_inbound.is_active;
    let new_is_active = inbound_data.is_active.unwrap_or(old_is_active);
    let endpoint = server.get_grpc_endpoint();
    
    // Handle xray server changes based on active status change
    if old_is_active && !new_is_active {
        // Becoming inactive - remove from xray server
        match app_state.xray_service.remove_inbound(server_id, &endpoint, &current_inbound.tag).await {
            Ok(_) => {
                tracing::info!("Deactivated inbound '{}' on {}", current_inbound.tag, endpoint);
            },
            Err(e) => {
                tracing::error!("Failed to deactivate inbound '{}': {}", current_inbound.tag, e);
                // Continue with database update even if xray removal fails
            }
        }
    } else if !old_is_active && new_is_active {
        // Becoming active - add to xray server
        
        // Get template info for recreation
        let template = match template_repo.find_by_id(current_inbound.template_id).await {
            Ok(Some(template)) => template,
            Ok(None) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
            Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
        };
        
        // Use updated port if provided, otherwise keep current
        let port = inbound_data.port_override.unwrap_or(current_inbound.port_override.unwrap_or(template.default_port));
        
        // Get certificate data if certificate is specified (could be updated)
        let certificate_id = inbound_data.certificate_id.or(current_inbound.certificate_id);
        let (cert_pem, key_pem) = if let Some(cert_id) = certificate_id {
            match cert_repo.find_by_id(cert_id).await {
                Ok(Some(cert)) => {
                    (Some(cert.certificate_pem()), Some(cert.private_key_pem()))
                },
                Ok(None) => {
                    tracing::warn!("Certificate {} not found", cert_id);
                    (None, None)
                },
                Err(e) => {
                    tracing::error!("Error fetching certificate {}: {}", cert_id, e);
                    (None, None)
                }
            }
        } else {
            (None, None)
        };
        
        match app_state.xray_service.create_inbound_with_certificate(
            server_id,
            &endpoint,
            &current_inbound.tag,
            port,
            &template.protocol,
            template.base_settings.clone(),
            template.stream_settings.clone(),
            cert_pem.as_deref(),
            key_pem.as_deref(),
        ).await {
            Ok(_) => {
                tracing::info!("Activated inbound '{}' on {}", current_inbound.tag, endpoint);
            },
            Err(e) => {
                tracing::error!("Failed to activate inbound '{}': {}", current_inbound.tag, e);
                // Continue with database update even if xray creation fails
            }
        }
    }
    
    // Update database
    match inbound_repo.update(inbound_id, inbound_data).await {
        Ok(updated_inbound) => {
            // Send sync event for immediate synchronization
            crate::services::events::send_sync_event(
                crate::services::events::SyncEvent::InboundChanged(server_id)
            );
            Ok(Json(updated_inbound.into()))
        },
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Get server inbound by ID
pub async fn get_server_inbound(
    State(app_state): State<AppState>,
    Path((server_id, inbound_id)): Path<(Uuid, Uuid)>,
) -> Result<Json<server_inbound::ServerInboundResponse>, StatusCode> {
    let repo = ServerInboundRepository::new(app_state.db.connection().clone());
    
    // Verify the inbound belongs to the server
    match repo.find_by_id(inbound_id).await {
        Ok(Some(inbound)) if inbound.server_id == server_id => {
            Ok(Json(inbound.into()))
        }
        Ok(Some(_)) => Err(StatusCode::BAD_REQUEST),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Delete server inbound
pub async fn delete_server_inbound(
    State(app_state): State<AppState>,
    Path((server_id, inbound_id)): Path<(Uuid, Uuid)>,
) -> Result<StatusCode, StatusCode> {
    let server_repo = ServerRepository::new(app_state.db.connection().clone());
    let inbound_repo = ServerInboundRepository::new(app_state.db.connection().clone());
    
    // Get server and inbound info
    let server = match server_repo.find_by_id(server_id).await {
        Ok(Some(server)) => server,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Verify the inbound belongs to the server
    let inbound = match inbound_repo.find_by_id(inbound_id).await {
        Ok(Some(inbound)) if inbound.server_id == server_id => inbound,
        Ok(Some(_)) => return Err(StatusCode::BAD_REQUEST),
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Try to remove inbound from xray server first
    let endpoint = server.get_grpc_endpoint();
    match app_state.xray_service.remove_inbound(server_id, &endpoint, &inbound.tag).await {
        Ok(_) => {
            tracing::info!("Removed inbound '{}' from {}", inbound.tag, endpoint);
        },
        Err(e) => {
            tracing::error!("Failed to remove inbound '{}' from {}: {}", inbound.tag, endpoint, e);
            // Continue with database deletion even if xray removal fails
        }
    }
    
    // Delete from database
    match inbound_repo.delete(inbound_id).await {
        Ok(true) => {
            // Send sync event for immediate synchronization
            crate::services::events::send_sync_event(
                crate::services::events::SyncEvent::InboundChanged(server_id)
            );
            Ok(StatusCode::NO_CONTENT)
        },
        Ok(false) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

/// Give user access to server inbound (database only - sync will apply changes)
pub async fn add_user_to_inbound(
    State(app_state): State<AppState>,
    Path((server_id, inbound_id)): Path<(Uuid, Uuid)>,
    JsonExtractor(user_data): JsonExtractor<serde_json::Value>,
) -> Result<StatusCode, StatusCode> {
    use crate::database::entities::inbound_users::CreateInboundUserDto;
    use crate::database::entities::user::CreateUserDto;
    
    let server_repo = ServerRepository::new(app_state.db.connection().clone());
    let inbound_repo = ServerInboundRepository::new(app_state.db.connection().clone());
    let user_repo = UserRepository::new(app_state.db.connection().clone());
    
    // Get server and inbound to validate they exist
    let _server = match server_repo.find_by_id(server_id).await {
        Ok(Some(server)) => server,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    let inbound = match inbound_repo.find_by_id(inbound_id).await {
        Ok(Some(inbound)) => inbound,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Verify inbound belongs to server
    if inbound.server_id != server_id {
        return Err(StatusCode::BAD_REQUEST);
    }
    
    // Extract user data
    
    let user_name = user_data["name"].as_str()
        .or_else(|| user_data["username"].as_str())
        .or_else(|| user_data["email"].as_str())
        .map(|s| s.to_string())
        .unwrap_or_else(|| {
            format!("user_{}", Uuid::new_v4().to_string()[..8].to_string())
        });
    
    let level = user_data["level"].as_u64().unwrap_or(0) as i32;
    let user_id = user_data["user_id"].as_str().and_then(|s| Uuid::parse_str(s).ok());
    
    // Get or create user
    let user = if let Some(uid) = user_id {
        // Use existing user
        match user_repo.find_by_id(uid).await {
            Ok(Some(user)) => user,
            Ok(None) => return Err(StatusCode::NOT_FOUND), // User not found
            Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
        }
    } else {
        // Create new user
        let create_user_dto = CreateUserDto {
            name: user_name.clone(),
            comment: user_data["comment"].as_str().map(|s| s.to_string()),
            telegram_id: user_data["telegram_id"].as_i64(),
            is_telegram_admin: false,
        };
        
        match user_repo.create(create_user_dto).await {
            Ok(user) => user,
            Err(e) => {
                tracing::error!("Failed to create user '{}': {}", user_name, e);
                return Err(StatusCode::INTERNAL_SERVER_ERROR);
            }
        }
    };
    
    // Create inbound user repository
    let inbound_users_repo = InboundUsersRepository::new(app_state.db.connection().clone());
    
    // Check if user already has access to this inbound
    if inbound_users_repo.user_has_access_to_inbound(user.id, inbound_id).await.unwrap_or(false) {
        tracing::warn!("User '{}' already has access to inbound", user.name);
        return Err(StatusCode::CONFLICT);
    }
    
    // Create inbound access for user
    let inbound_user_dto = CreateInboundUserDto {
        user_id: user.id,
        server_inbound_id: inbound_id,
        level: Some(level),
    };
    
    // Grant access in database
    match inbound_users_repo.create(inbound_user_dto).await {
        Ok(created_access) => {
            tracing::info!("Granted user '{}' access to inbound (xray_id={})", 
                user.name, created_access.xray_user_id);
            
            // Send sync event for immediate synchronization
            crate::services::events::send_sync_event(
                crate::services::events::SyncEvent::UserAccessChanged(server_id)
            );
            
            Ok(StatusCode::CREATED)
        },
        Err(e) => {
            tracing::error!("Failed to grant user '{}' access: {}", user.name, e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// Remove user from server inbound
pub async fn remove_user_from_inbound(
    State(app_state): State<AppState>,
    Path((server_id, inbound_id, email)): Path<(Uuid, Uuid, String)>,
) -> Result<StatusCode, StatusCode> {
    let server_repo = ServerRepository::new(app_state.db.connection().clone());
    let inbound_repo = ServerInboundRepository::new(app_state.db.connection().clone());
    
    // Get server and inbound
    let server = match server_repo.find_by_id(server_id).await {
        Ok(Some(server)) => server,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    let inbound = match inbound_repo.find_by_id(inbound_id).await {
        Ok(Some(inbound)) => inbound,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    // Verify inbound belongs to server
    if inbound.server_id != server_id {
        return Err(StatusCode::BAD_REQUEST);
    }
    
    // Get inbound tag
    let template_repo = InboundTemplateRepository::new(app_state.db.connection().clone());
    let template = match template_repo.find_by_id(inbound.template_id).await {
        Ok(Some(template)) => template,
        Ok(None) => return Err(StatusCode::NOT_FOUND),
        Err(_) => return Err(StatusCode::INTERNAL_SERVER_ERROR),
    };
    
    let inbound_tag = &inbound.tag;
    
    // Remove user from xray server
    match app_state.xray_service.remove_user(server_id, &server.get_grpc_endpoint(), &inbound_tag, &email).await {
        Ok(_) => {
            tracing::info!("Removed user '{}' from inbound", email);
            Ok(StatusCode::NO_CONTENT)
        },
        Err(e) => {
            tracing::error!("Failed to remove user '{}' from inbound: {}", email, e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}