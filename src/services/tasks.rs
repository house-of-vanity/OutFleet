use anyhow::Result;
use tokio_cron_scheduler::{JobScheduler, Job};
use tracing::{info, error, warn};
use crate::database::DatabaseManager;
use crate::database::repository::{ServerRepository, ServerInboundRepository, InboundTemplateRepository, InboundUsersRepository, CertificateRepository};
use crate::database::entities::inbound_users;
use crate::services::XrayService;
use crate::services::events::SyncEvent;
use sea_orm::{EntityTrait, ColumnTrait, QueryFilter, RelationTrait, JoinType};
use uuid::Uuid;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use chrono::{DateTime, Utc};
use serde::{Serialize, Deserialize};

pub struct TaskScheduler {
    scheduler: JobScheduler,
    task_status: Arc<RwLock<HashMap<String, TaskStatus>>>,
}

/// Status of a background task
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskStatus {
    pub name: String,
    pub description: String,
    pub schedule: String,
    pub status: TaskState,
    pub last_run: Option<DateTime<Utc>>,
    pub next_run: Option<DateTime<Utc>>,
    pub total_runs: u64,
    pub success_count: u64,
    pub error_count: u64,
    pub last_error: Option<String>,
    pub last_duration_ms: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TaskState {
    Idle,
    Running,
    Success,
    Error,
}

impl TaskScheduler {
    pub async fn new() -> Result<Self> {
        let scheduler = JobScheduler::new().await?;
        let task_status = Arc::new(RwLock::new(HashMap::new()));
        Ok(Self { scheduler, task_status })
    }

    /// Get current status of all tasks
    pub fn get_task_status(&self) -> HashMap<String, TaskStatus> {
        self.task_status.read().unwrap().clone()
    }

    /// Start event-driven sync handler
    pub async fn start_event_handler(db: DatabaseManager, mut event_receiver: tokio::sync::broadcast::Receiver<SyncEvent>) {
        let xray_service = XrayService::new();
        
        tokio::spawn(async move {
            info!("Starting event-driven sync handler");
            
            while let Ok(event) = event_receiver.recv().await {
                match event {
                    SyncEvent::InboundChanged(server_id) | SyncEvent::UserAccessChanged(server_id) => {
                        info!("Received sync event for server {}", server_id);
                        
                        if let Err(e) = sync_single_server_by_id(&xray_service, &db, server_id).await {
                            error!("Failed to sync server {} from event: {}", server_id, e);
                        } else {
                            info!("Successfully synced server {} from event", server_id);
                        }
                    }
                }
            }
        });
    }

    pub async fn start(&mut self, db: DatabaseManager, xray_service: XrayService) -> Result<()> {
        info!("Starting task scheduler with database synchronization");
        
        // Initialize task status
        {
            let mut status = self.task_status.write().unwrap();
            status.insert("xray_sync".to_string(), TaskStatus {
                name: "Xray Synchronization".to_string(),
                description: "Synchronizes database state with xray servers".to_string(),
                schedule: "0 * * * * * (every minute)".to_string(),
                status: TaskState::Idle,
                last_run: None,
                next_run: Some(Utc::now() + chrono::Duration::minutes(1)),
                total_runs: 0,
                success_count: 0,
                error_count: 0,
                last_error: None,
                last_duration_ms: None,
            });
        }
        
        // Run initial sync on startup
        info!("Running initial xray synchronization on startup");
        let start_time = Utc::now();
        self.update_task_status("xray_sync", TaskState::Running, None);
        
        match sync_xray_state(db.clone(), xray_service.clone()).await {
            Ok(_) => {
                let duration = (Utc::now() - start_time).num_milliseconds() as u64;
                self.update_task_status("xray_sync", TaskState::Success, Some(duration));
                info!("Initial xray sync completed successfully");
            },
            Err(e) => {
                let duration = (Utc::now() - start_time).num_milliseconds() as u64;
                self.update_task_status_with_error("xray_sync", e.to_string(), Some(duration));
                error!("Initial xray sync failed: {}", e);
            }
        }
        
        // Add synchronization task that runs every minute
        let db_clone = db.clone();
        let xray_service_clone = xray_service.clone();
        let task_status_clone = self.task_status.clone();
        
        let sync_job = Job::new_async("0 */5 * * * *", move |_uuid, _l| {
            let db = db_clone.clone();
            let xray_service = xray_service_clone.clone();
            let task_status = task_status_clone.clone();
            
            Box::pin(async move {
                info!("Running scheduled xray synchronization");
                let start_time = Utc::now();
                
                // Update status to running
                {
                    let mut status = task_status.write().unwrap();
                    if let Some(task) = status.get_mut("xray_sync") {
                        task.status = TaskState::Running;
                        task.last_run = Some(start_time);
                        task.total_runs += 1;
                        task.next_run = Some(start_time + chrono::Duration::minutes(1));
                    }
                }
                
                match sync_xray_state(db, xray_service).await {
                    Ok(_) => {
                        let duration = (Utc::now() - start_time).num_milliseconds() as u64;
                        let mut status = task_status.write().unwrap();
                        if let Some(task) = status.get_mut("xray_sync") {
                            task.status = TaskState::Success;
                            task.success_count += 1;
                            task.last_duration_ms = Some(duration);
                            task.last_error = None;
                        }
                        info!("Scheduled xray sync completed successfully in {}ms", duration);
                    },
                    Err(e) => {
                        let duration = (Utc::now() - start_time).num_milliseconds() as u64;
                        let mut status = task_status.write().unwrap();
                        if let Some(task) = status.get_mut("xray_sync") {
                            task.status = TaskState::Error;
                            task.error_count += 1;
                            task.last_duration_ms = Some(duration);
                            task.last_error = Some(e.to_string());
                        }
                        error!("Scheduled xray sync failed: {}", e);
                    }
                }
            })
        })?;
        
        self.scheduler.add(sync_job).await?;
        
        info!("Task scheduler started with sync job running every minute");
        
        self.scheduler.start().await?;
        Ok(())
    }

    fn update_task_status(&self, task_id: &str, state: TaskState, duration_ms: Option<u64>) {
        let mut status = self.task_status.write().unwrap();
        if let Some(task) = status.get_mut(task_id) {
            task.status = state;
            task.last_run = Some(Utc::now());
            task.total_runs += 1;
            task.success_count += 1;
            task.last_duration_ms = duration_ms;
            task.last_error = None;
        }
    }

    fn update_task_status_with_error(&self, task_id: &str, error: String, duration_ms: Option<u64>) {
        let mut status = self.task_status.write().unwrap();
        if let Some(task) = status.get_mut(task_id) {
            task.status = TaskState::Error;
            task.last_run = Some(Utc::now());
            task.total_runs += 1;
            task.error_count += 1;
            task.last_duration_ms = duration_ms;
            task.last_error = Some(error);
        }
    }

    pub async fn shutdown(&mut self) -> Result<()> {
        info!("Shutting down task scheduler");
        self.scheduler.shutdown().await?;
        Ok(())
    }
}

/// Synchronize xray server state with database state
async fn sync_xray_state(db: DatabaseManager, xray_service: XrayService) -> Result<()> {
    info!("Starting xray state synchronization");
    
    let server_repo = ServerRepository::new(db.connection().clone());
    let inbound_repo = ServerInboundRepository::new(db.connection().clone());
    let template_repo = InboundTemplateRepository::new(db.connection().clone());
    
    // Get all servers from database
    let servers = match server_repo.find_all().await {
        Ok(servers) => servers,
        Err(e) => {
            error!("Failed to fetch servers: {}", e);
            return Err(e.into());
        }
    };
    
    info!("Found {} servers to synchronize", servers.len());
    
    for server in servers {
        info!("Synchronizing server: {} ({}:{})", server.name, server.hostname, server.grpc_port);
        
        let endpoint = format!("{}:{}", server.hostname, server.grpc_port);
        
        // Test connection first
        match xray_service.test_connection(server.id, &endpoint).await {
            Ok(true) => {
                info!("Connection to server {} successful", server.name);
            },
            Ok(false) => {
                warn!("Cannot connect to server {} at {}, skipping", server.name, endpoint);
                continue;
            },
            Err(e) => {
                error!("Error testing connection to server {}: {}", server.name, e);
                continue;
            }
        }
        
        // Get desired inbounds from database
        let desired_inbounds = match get_desired_inbounds_from_db(&db, &server, &inbound_repo, &template_repo).await {
            Ok(inbounds) => inbounds,
            Err(e) => {
                error!("Failed to get desired inbounds for server {}: {}", server.name, e);
                continue;
            }
        };
        
        info!("Server {}: desired={} inbounds", server.name, desired_inbounds.len());
        
        // Synchronize inbounds
        if let Err(e) = sync_server_inbounds(
            &xray_service, 
            server.id, 
            &endpoint, 
            &desired_inbounds
        ).await {
            error!("Failed to sync inbounds for server {}: {}", server.name, e);
        } else {
            info!("Successfully synchronized server {}", server.name);
        }
    }
    
    info!("Xray state synchronization completed");
    Ok(())
}


/// Get desired inbounds configuration from database
async fn get_desired_inbounds_from_db(
    db: &DatabaseManager,
    server: &crate::database::entities::server::Model,
    inbound_repo: &ServerInboundRepository,
    template_repo: &InboundTemplateRepository,
) -> Result<HashMap<String, DesiredInbound>> {
    info!("Getting desired inbounds for server {} from database", server.name);
    
    // Get all inbounds for this server
    let inbounds = inbound_repo.find_by_server_id(server.id).await?;
    let mut desired_inbounds = HashMap::new();
    
    for inbound in inbounds {
        // Get template for this inbound
        let template = match template_repo.find_by_id(inbound.template_id).await? {
            Some(template) => template,
            None => {
                warn!("Template {} not found for inbound {}, skipping", inbound.template_id, inbound.tag);
                continue;
            }
        };
        
        // Get users for this inbound
        let users = get_users_for_inbound(db, inbound.id).await?;
        
        info!("Inbound {}: {} users found", inbound.tag, users.len());
        
        // Get port from template or override
        let port = inbound.port_override.unwrap_or(template.default_port);
        
        // Get certificate if specified
        let (cert_pem, key_pem) = if let Some(_cert_id) = inbound.certificate_id {
            match load_certificate_from_db(db, inbound.certificate_id).await {
                Ok((cert, key)) => (cert, key),
                Err(e) => {
                    warn!("Failed to load certificate for inbound {}: {}", inbound.tag, e);
                    (None, None)
                }
            }
        } else {
            (None, None)
        };
        
        let desired_inbound = DesiredInbound {
            tag: inbound.tag.clone(),
            port,
            protocol: template.protocol.clone(),
            settings: template.base_settings.clone(),
            stream_settings: template.stream_settings.clone(),
            users,
            cert_pem,
            key_pem,
        };
        
        desired_inbounds.insert(inbound.tag.clone(), desired_inbound);
    }
    
    info!("Found {} desired inbounds for server {}", desired_inbounds.len(), server.name);
    Ok(desired_inbounds)
}

/// Get users for specific inbound from database
async fn get_users_for_inbound(db: &DatabaseManager, inbound_id: Uuid) -> Result<Vec<XrayUser>> {
    let inbound_users_repo = InboundUsersRepository::new(db.connection().clone());
    
    let inbound_users = inbound_users_repo.find_active_by_inbound_id(inbound_id).await?;
    
    let users: Vec<XrayUser> = inbound_users.into_iter().map(|user| {
        XrayUser {
            id: user.xray_user_id,
            email: user.email,
            level: user.level,
        }
    }).collect();
    
    Ok(users)
}

/// Load certificate from database
async fn load_certificate_from_db(db: &DatabaseManager, cert_id: Option<Uuid>) -> Result<(Option<String>, Option<String>)> {
    let cert_id = match cert_id {
        Some(id) => id,
        None => return Ok((None, None)),
    };
    
    let cert_repo = CertificateRepository::new(db.connection().clone());
    
    match cert_repo.find_by_id(cert_id).await? {
        Some(cert) => {
            info!("Loaded certificate: {}", cert.domain);
            Ok((Some(cert.certificate_pem()), Some(cert.private_key_pem())))
        },
        None => {
            warn!("Certificate {} not found", cert_id);
            Ok((None, None))
        }
    }
}

/// Synchronize inbounds for a single server
async fn sync_server_inbounds(
    xray_service: &XrayService,
    server_id: Uuid,
    endpoint: &str,
    desired_inbounds: &HashMap<String, DesiredInbound>,
) -> Result<()> {
    
    // Create or update inbounds
    // Since xray has no API to list inbounds, we always recreate them
    for (tag, desired) in desired_inbounds {
        info!("Creating/updating inbound: {} with {} users", tag, desired.users.len());
        
        // Always try to remove inbound first (ignore errors if it doesn't exist)
        if let Err(e) = xray_service.remove_inbound(server_id, endpoint, tag).await {
            // Log but don't fail - inbound might not exist
            info!("Inbound {} removal result: {} (this is normal if inbound didn't exist)", tag, e);
        }
        
        // Create inbound with users
        let users_json: Vec<Value> = desired.users.iter().map(|user| {
            serde_json::json!({
                "id": user.id,
                "email": user.email,
                "level": user.level
            })
        }).collect();
        
        match xray_service.create_inbound_with_users(
            server_id,
            endpoint,
            &desired.tag,
            desired.port,
            &desired.protocol,
            desired.settings.clone(),
            desired.stream_settings.clone(),
            &users_json,
            desired.cert_pem.as_deref(),
            desired.key_pem.as_deref(),
        ).await {
            Ok(_) => {
                info!("Successfully created inbound {} with {} users", tag, desired.users.len());
            },
            Err(e) => {
                error!("Failed to create inbound {}: {}", tag, e);
            }
        }
    }
    
    Ok(())
}

/// Sync a single server by ID (for event-driven sync)
async fn sync_single_server_by_id(
    xray_service: &XrayService,
    db: &DatabaseManager,
    server_id: Uuid,
) -> Result<()> {
    let server_repo = ServerRepository::new(db.connection().clone());
    let inbound_repo = ServerInboundRepository::new(db.connection().clone());
    let template_repo = InboundTemplateRepository::new(db.connection().clone());
    
    // Get server
    let server = match server_repo.find_by_id(server_id).await? {
        Some(server) => server,
        None => {
            warn!("Server {} not found for sync", server_id);
            return Ok(());
        }
    };
    
    // For now, sync all servers (can add active/inactive flag later)
    
    // Get desired inbounds from database
    let desired_inbounds = get_desired_inbounds_from_db(db, &server, &inbound_repo, &template_repo).await?;
    
    // Build endpoint
    let endpoint = format!("{}:{}", server.hostname, server.grpc_port);
    
    // Sync server
    sync_server_inbounds(xray_service, server_id, &endpoint, &desired_inbounds).await?;
    
    Ok(())
}


/// Represents desired inbound configuration from database
#[derive(Debug, Clone)]
struct DesiredInbound {
    tag: String,
    port: i32,
    protocol: String,
    settings: Value,
    stream_settings: Value,
    users: Vec<XrayUser>,
    cert_pem: Option<String>,
    key_pem: Option<String>,
}

/// Represents xray user configuration
#[derive(Debug, Clone)]
struct XrayUser {
    id: String,
    email: String,
    level: i32,
}