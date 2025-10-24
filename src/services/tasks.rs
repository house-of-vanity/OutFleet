use crate::database::entities::inbound_users;
use crate::database::repository::{
    CertificateRepository, InboundTemplateRepository, InboundUsersRepository,
    ServerInboundRepository, ServerRepository, UserRepository,
};
use crate::database::DatabaseManager;
use crate::services::events::SyncEvent;
use crate::services::XrayService;
use anyhow::Result;
use chrono::{DateTime, Utc};
use sea_orm::{ColumnTrait, EntityTrait, JoinType, QueryFilter, RelationTrait};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use tokio_cron_scheduler::{Job, JobScheduler};
use tracing::{debug, error, info, warn};
use uuid::Uuid;

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
        Ok(Self {
            scheduler,
            task_status,
        })
    }

    /// Get current status of all tasks
    pub fn get_task_status(&self) -> HashMap<String, TaskStatus> {
        self.task_status.read().unwrap().clone()
    }

    /// Start event-driven sync handler
    pub async fn start_event_handler(
        db: DatabaseManager,
        mut event_receiver: tokio::sync::broadcast::Receiver<SyncEvent>,
    ) {
        let xray_service = XrayService::new();

        tokio::spawn(async move {
            while let Ok(event) = event_receiver.recv().await {
                match event {
                    SyncEvent::InboundChanged(server_id)
                    | SyncEvent::UserAccessChanged(server_id) => {
                        if let Err(e) =
                            sync_single_server_by_id(&xray_service, &db, server_id).await
                        {
                            // Get server name for better logging
                            let server_repo = ServerRepository::new(db.connection().clone());
                            let server_name = match server_repo.find_by_id(server_id).await {
                                Ok(Some(server)) => server.name,
                                _ => server_id.to_string(),
                            };
                            error!(
                                "Failed to sync server '{}' ({}) from event: {}",
                                server_name, server_id, e
                            );
                        }
                    }
                }
            }
        });
    }

    pub async fn start(&mut self, db: DatabaseManager, xray_service: XrayService) -> Result<()> {
        // Initialize task status
        {
            let mut status = self.task_status.write().unwrap();
            status.insert(
                "xray_sync".to_string(),
                TaskStatus {
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
                },
            );
        }

        // Run initial sync in background to avoid blocking startup
        let db_initial = db.clone();
        let xray_service_initial = xray_service.clone();
        let task_status_initial = self.task_status.clone();

        tokio::spawn(async move {
            info!("Starting initial xray sync in background...");
            let start_time = Utc::now();

            // Update status to running
            {
                let mut status = task_status_initial.write().unwrap();
                if let Some(task) = status.get_mut("xray_sync") {
                    task.status = TaskState::Running;
                    task.last_run = Some(start_time);
                    task.total_runs += 1;
                }
            }

            match sync_xray_state(db_initial, xray_service_initial).await {
                Ok(_) => {
                    let duration = (Utc::now() - start_time).num_milliseconds() as u64;
                    let mut status = task_status_initial.write().unwrap();
                    if let Some(task) = status.get_mut("xray_sync") {
                        task.status = TaskState::Success;
                        task.success_count += 1;
                        task.last_duration_ms = Some(duration);
                        task.last_error = None;
                    }
                    info!("Initial xray sync completed successfully in {}ms", duration);
                }
                Err(e) => {
                    let duration = (Utc::now() - start_time).num_milliseconds() as u64;
                    let mut status = task_status_initial.write().unwrap();
                    if let Some(task) = status.get_mut("xray_sync") {
                        task.status = TaskState::Error;
                        task.error_count += 1;
                        task.last_duration_ms = Some(duration);
                        task.last_error = Some(e.to_string());
                    }
                    error!("Initial xray sync failed: {}", e);
                }
            }
        });

        // Add synchronization task that runs every minute
        let db_clone = db.clone();
        let xray_service_clone = xray_service.clone();
        let task_status_clone = self.task_status.clone();

        let sync_job = Job::new_async("0 */5 * * * *", move |_uuid, _l| {
            let db = db_clone.clone();
            let xray_service = xray_service_clone.clone();
            let task_status = task_status_clone.clone();

            Box::pin(async move {
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
                    }
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

        // Add certificate renewal task that runs once a day at 2 AM
        let db_clone_cert = db.clone();
        let task_status_cert = self.task_status.clone();

        // Initialize certificate renewal task status
        {
            let mut status = self.task_status.write().unwrap();
            status.insert(
                "cert_renewal".to_string(),
                TaskStatus {
                    name: "Certificate Renewal".to_string(),
                    description: "Renews Let's Encrypt certificates that expire within 15 days"
                        .to_string(),
                    schedule: "0 0 2 * * * (daily at 2 AM)".to_string(),
                    status: TaskState::Idle,
                    last_run: None,
                    next_run: Some(Utc::now() + chrono::Duration::days(1)),
                    total_runs: 0,
                    success_count: 0,
                    error_count: 0,
                    last_error: None,
                    last_duration_ms: None,
                },
            );
        }

        let cert_renewal_job = Job::new_async("0 0 2 * * *", move |_uuid, _l| {
            let db = db_clone_cert.clone();
            let task_status = task_status_cert.clone();

            Box::pin(async move {
                let start_time = Utc::now();

                // Update task status to running
                {
                    let mut status = task_status.write().unwrap();
                    if let Some(task) = status.get_mut("cert_renewal") {
                        task.status = TaskState::Running;
                        task.last_run = Some(Utc::now());
                        task.total_runs += 1;
                    }
                }

                match check_and_renew_certificates(&db).await {
                    Ok(_) => {
                        let duration = (Utc::now() - start_time).num_milliseconds() as u64;
                        let mut status = task_status.write().unwrap();
                        if let Some(task) = status.get_mut("cert_renewal") {
                            task.status = TaskState::Success;
                            task.success_count += 1;
                            task.last_duration_ms = Some(duration);
                            task.last_error = None;
                        }
                    }
                    Err(e) => {
                        let duration = (Utc::now() - start_time).num_milliseconds() as u64;
                        let mut status = task_status.write().unwrap();
                        if let Some(task) = status.get_mut("cert_renewal") {
                            task.status = TaskState::Error;
                            task.error_count += 1;
                            task.last_duration_ms = Some(duration);
                            task.last_error = Some(e.to_string());
                        }
                        error!("Certificate renewal task failed: {}", e);
                    }
                }
            })
        })?;

        self.scheduler.add(cert_renewal_job).await?;

        // Also run certificate check on startup
        info!("Running initial certificate renewal check...");
        tokio::spawn(async move {
            if let Err(e) = check_and_renew_certificates(&db).await {
                error!("Initial certificate renewal check failed: {}", e);
            }
        });

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

    fn update_task_status_with_error(
        &self,
        task_id: &str,
        error: String,
        duration_ms: Option<u64>,
    ) {
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
        self.scheduler.shutdown().await?;
        Ok(())
    }
}

/// Synchronize xray server state with database state
async fn sync_xray_state(db: DatabaseManager, xray_service: XrayService) -> Result<()> {
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

    for server in servers {
        let endpoint = server.get_grpc_endpoint();

        // Test connection first
        match xray_service.test_connection(server.id, &endpoint).await {
            Ok(false) => {
                warn!(
                    "Cannot connect to server {} at {}, skipping",
                    server.name, endpoint
                );
                continue;
            }
            Err(e) => {
                error!("Error testing connection to server {}: {}", server.name, e);
                continue;
            }
            _ => {}
        }

        // Get desired inbounds from database
        let desired_inbounds =
            match get_desired_inbounds_from_db(&db, &server, &inbound_repo, &template_repo).await {
                Ok(inbounds) => inbounds,
                Err(e) => {
                    error!(
                        "Failed to get desired inbounds for server {}: {}",
                        server.name, e
                    );
                    continue;
                }
            };

        // Synchronize inbounds
        if let Err(e) =
            sync_server_inbounds(&xray_service, server.id, &endpoint, &desired_inbounds).await
        {
            error!("Failed to sync inbounds for server {}: {}", server.name, e);
        }
    }

    Ok(())
}

/// Get desired inbounds configuration from database
async fn get_desired_inbounds_from_db(
    db: &DatabaseManager,
    server: &crate::database::entities::server::Model,
    inbound_repo: &ServerInboundRepository,
    template_repo: &InboundTemplateRepository,
) -> Result<HashMap<String, DesiredInbound>> {
    // Get all inbounds for this server
    let inbounds = inbound_repo.find_by_server_id(server.id).await?;
    let mut desired_inbounds = HashMap::new();

    for inbound in inbounds {
        // Get template for this inbound
        let template = match template_repo.find_by_id(inbound.template_id).await? {
            Some(template) => template,
            None => {
                warn!(
                    "Template {} not found for inbound {}, skipping",
                    inbound.template_id, inbound.tag
                );
                continue;
            }
        };

        // Get users for this inbound
        let users = get_users_for_inbound(db, inbound.id).await?;

        // Get port from template or override
        let port = inbound.port_override.unwrap_or(template.default_port);

        // Get certificate if specified
        let (cert_pem, key_pem) = if let Some(cert_id) = inbound.certificate_id {
            match load_certificate_from_db(db, inbound.certificate_id).await {
                Ok((cert, key)) => {
                    // Get certificate name for better logging
                    let cert_repo = CertificateRepository::new(db.connection().clone());
                    let cert_name = match cert_repo.find_by_id(cert_id).await {
                        Ok(Some(cert)) => cert.name,
                        _ => cert_id.to_string(),
                    };
                    info!(
                        "Loaded certificate '{}' ({}) for inbound '{}' on server '{}', has_cert={}, has_key={}",
                        cert_name,
                        cert_id,
                        inbound.tag,
                        server.name,
                        cert.is_some(),
                        key.is_some()
                    );
                    (cert, key)
                }
                Err(e) => {
                    // Get certificate name for better logging
                    let cert_repo = CertificateRepository::new(db.connection().clone());
                    let cert_name = match cert_repo.find_by_id(cert_id).await {
                        Ok(Some(cert)) => cert.name,
                        _ => cert_id.to_string(),
                    };
                    warn!(
                        "Failed to load certificate '{}' ({}) for inbound '{}' on server '{}': {}",
                        cert_name, cert_id, inbound.tag, server.name, e
                    );
                    (None, None)
                }
            }
        } else {
            debug!(
                "No certificate configured for inbound '{}' on server '{}'",
                inbound.tag, server.name
            );
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

    Ok(desired_inbounds)
}

/// Get users for specific inbound from database
async fn get_users_for_inbound(db: &DatabaseManager, inbound_id: Uuid) -> Result<Vec<XrayUser>> {
    let inbound_users_repo = InboundUsersRepository::new(db.connection().clone());

    let inbound_users = inbound_users_repo
        .find_active_by_inbound_id(inbound_id)
        .await?;

    // Get user details to generate emails
    let user_repo = UserRepository::new(db.connection().clone());

    let mut users: Vec<XrayUser> = Vec::new();
    for inbound_user in inbound_users {
        if let Some(user) = user_repo.find_by_id(inbound_user.user_id).await? {
            let email = inbound_user.generate_client_email(&user.name);
            users.push(XrayUser {
                id: inbound_user.xray_user_id,
                email,
                level: inbound_user.level,
            });
        }
    }

    Ok(users)
}

/// Load certificate from database
async fn load_certificate_from_db(
    db: &DatabaseManager,
    cert_id: Option<Uuid>,
) -> Result<(Option<String>, Option<String>)> {
    let cert_id = match cert_id {
        Some(id) => id,
        None => return Ok((None, None)),
    };

    let cert_repo = CertificateRepository::new(db.connection().clone());

    match cert_repo.find_by_id(cert_id).await? {
        Some(cert) => {
            debug!(
                "Loaded certificate '{}' ({}) successfully",
                cert.name, cert.id
            );
            Ok((Some(cert.certificate_pem()), Some(cert.private_key_pem())))
        }
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
    // Use optimized batch sync with single client
    xray_service
        .sync_server_inbounds_optimized(server_id, endpoint, desired_inbounds)
        .await
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
    let desired_inbounds =
        get_desired_inbounds_from_db(db, &server, &inbound_repo, &template_repo).await?;

    // Build endpoint
    let endpoint = server.get_grpc_endpoint();

    // Sync server
    sync_server_inbounds(xray_service, server_id, &endpoint, &desired_inbounds).await?;

    Ok(())
}

/// Represents desired inbound configuration from database
#[derive(Debug, Clone)]
pub struct DesiredInbound {
    pub tag: String,
    pub port: i32,
    pub protocol: String,
    pub settings: Value,
    pub stream_settings: Value,
    pub users: Vec<XrayUser>,
    pub cert_pem: Option<String>,
    pub key_pem: Option<String>,
}

/// Represents xray user configuration
#[derive(Debug, Clone)]
pub struct XrayUser {
    pub id: String,
    pub email: String,
    pub level: i32,
}

/// Check and renew certificates that expire within 15 days
async fn check_and_renew_certificates(db: &DatabaseManager) -> Result<()> {
    use crate::database::repository::DnsProviderRepository;
    use crate::services::certificates::CertificateService;

    info!("Starting certificate renewal check...");

    let cert_repo = CertificateRepository::new(db.connection().clone());
    let dns_repo = DnsProviderRepository::new(db.connection().clone());
    let cert_service = CertificateService::with_db(db.connection().clone());

    // Get all certificates
    let certificates = cert_repo.find_all().await?;
    let mut renewed_count = 0;
    let mut checked_count = 0;

    for cert in certificates {
        // Only check Let's Encrypt certificates with auto_renew enabled
        if cert.cert_type != "letsencrypt" || !cert.auto_renew {
            continue;
        }

        checked_count += 1;

        // Check if certificate expires within 15 days
        if cert.expires_soon(15) {
            info!(
                "Certificate '{}' (ID: {}) expires at {} - renewing...",
                cert.name, cert.id, cert.expires_at
            );

            // Find the DNS provider used for this certificate
            // For now, we'll use the first active Cloudflare provider
            // In production, you might want to store the provider ID with the certificate
            let providers = dns_repo.find_active_by_type("cloudflare").await?;

            if providers.is_empty() {
                error!(
                    "Cannot renew certificate '{}': No active Cloudflare DNS provider found",
                    cert.name
                );
                continue;
            }

            let dns_provider = &providers[0];

            // Need to get the ACME email - for now using a default
            // In production, this should be stored with the certificate
            let acme_email = "admin@example.com"; // TODO: Store this with certificate

            // Attempt to renew the certificate
            match cert_service
                .generate_letsencrypt_certificate(
                    &cert.domain,
                    dns_provider.id,
                    acme_email,
                    false, // Use production Let's Encrypt
                )
                .await
            {
                Ok((new_cert_pem, new_key_pem)) => {
                    // Update the certificate in database
                    match cert_repo
                        .update_certificate_data(
                            cert.id,
                            &new_cert_pem,
                            &new_key_pem,
                            chrono::Utc::now() + chrono::Duration::days(90), // Let's Encrypt certs are valid for 90 days
                        )
                        .await
                    {
                        Ok(_) => {
                            info!("Successfully renewed certificate '{}'", cert.name);
                            renewed_count += 1;

                            // Trigger sync for all servers using this certificate
                            // This will be done via the event system
                            if let Err(e) = trigger_cert_renewal_sync(db, cert.id).await {
                                error!("Failed to trigger sync after certificate renewal: {}", e);
                            }
                        }
                        Err(e) => {
                            error!(
                                "Failed to save renewed certificate '{}' to database: {}",
                                cert.name, e
                            );
                        }
                    }
                }
                Err(e) => {
                    error!("Failed to renew certificate '{}': {:?}", cert.name, e);
                }
            }
        } else {
            debug!(
                "Certificate '{}' expires at {} - no renewal needed yet",
                cert.name, cert.expires_at
            );
        }
    }

    info!(
        "Certificate renewal check completed: checked {}, renewed {}",
        checked_count, renewed_count
    );

    Ok(())
}

/// Trigger sync for all servers that use a specific certificate
async fn trigger_cert_renewal_sync(db: &DatabaseManager, cert_id: Uuid) -> Result<()> {
    use crate::services::events::send_sync_event;
    use crate::services::events::SyncEvent;

    let inbound_repo = ServerInboundRepository::new(db.connection().clone());

    // Find all server inbounds that use this certificate
    let inbounds = inbound_repo.find_by_certificate_id(cert_id).await?;

    // Collect unique server IDs
    let mut server_ids = std::collections::HashSet::new();
    for inbound in inbounds {
        server_ids.insert(inbound.server_id);
    }

    // Trigger sync for each server
    for server_id in server_ids {
        // Get server name for better logging
        let server_repo = ServerRepository::new(db.connection().clone());
        let server_name = match server_repo.find_by_id(server_id).await {
            Ok(Some(server)) => server.name,
            _ => server_id.to_string(),
        };
        info!(
            "Triggering sync for server '{}' ({}) after certificate renewal",
            server_name, server_id
        );
        send_sync_event(SyncEvent::InboundChanged(server_id));
    }

    Ok(())
}
