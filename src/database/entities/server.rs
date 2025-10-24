use sea_orm::entity::prelude::*;
use sea_orm::{ActiveModelTrait, Set};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "servers")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,

    pub name: String,

    pub hostname: String,

    pub grpc_hostname: String,

    pub grpc_port: i32,

    #[serde(skip_serializing)]
    pub api_credentials: Option<String>,

    pub status: String,

    pub default_certificate_id: Option<Uuid>,

    pub created_at: DateTimeUtc,

    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(
        belongs_to = "super::certificate::Entity",
        from = "Column::DefaultCertificateId",
        to = "super::certificate::Column::Id"
    )]
    DefaultCertificate,
    #[sea_orm(has_many = "super::server_inbound::Entity")]
    ServerInbounds,
}

impl Related<super::certificate::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::DefaultCertificate.def()
    }
}

impl Related<super::server_inbound::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::ServerInbounds.def()
    }
}

impl ActiveModelBehavior for ActiveModel {
    fn new() -> Self {
        Self {
            id: Set(Uuid::new_v4()),
            status: Set(ServerStatus::Unknown.into()),
            created_at: Set(chrono::Utc::now()),
            updated_at: Set(chrono::Utc::now()),
            ..ActiveModelTrait::default()
        }
    }

    fn before_save<'life0, 'async_trait, C>(
        mut self,
        _db: &'life0 C,
        insert: bool,
    ) -> core::pin::Pin<
        Box<dyn core::future::Future<Output = Result<Self, DbErr>> + Send + 'async_trait>,
    >
    where
        'life0: 'async_trait,
        C: 'async_trait + ConnectionTrait,
        Self: 'async_trait,
    {
        Box::pin(async move {
            if !insert {
                self.updated_at = Set(chrono::Utc::now());
            }
            Ok(self)
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ServerStatus {
    Unknown,
    Online,
    Offline,
    Error,
    Connecting,
}

impl From<ServerStatus> for String {
    fn from(status: ServerStatus) -> Self {
        match status {
            ServerStatus::Unknown => "unknown".to_string(),
            ServerStatus::Online => "online".to_string(),
            ServerStatus::Offline => "offline".to_string(),
            ServerStatus::Error => "error".to_string(),
            ServerStatus::Connecting => "connecting".to_string(),
        }
    }
}

impl From<String> for ServerStatus {
    fn from(s: String) -> Self {
        match s.as_str() {
            "online" => ServerStatus::Online,
            "offline" => ServerStatus::Offline,
            "error" => ServerStatus::Error,
            "connecting" => ServerStatus::Connecting,
            _ => ServerStatus::Unknown,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateServerDto {
    pub name: String,
    pub hostname: String,
    pub grpc_hostname: Option<String>, // Optional, defaults to hostname if not provided
    pub grpc_port: Option<i32>,
    pub api_credentials: Option<String>,
    pub default_certificate_id: Option<Uuid>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateServerDto {
    pub name: Option<String>,
    pub hostname: Option<String>,
    pub grpc_hostname: Option<String>,
    pub grpc_port: Option<i32>,
    pub api_credentials: Option<String>,
    pub status: Option<String>,
    pub default_certificate_id: Option<Uuid>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerResponse {
    pub id: Uuid,
    pub name: String,
    pub hostname: String,
    pub grpc_hostname: String,
    pub grpc_port: i32,
    pub status: String,
    pub default_certificate_id: Option<Uuid>,
    pub created_at: DateTimeUtc,
    pub updated_at: DateTimeUtc,
    pub has_credentials: bool,
}

impl From<CreateServerDto> for ActiveModel {
    fn from(dto: CreateServerDto) -> Self {
        Self {
            name: Set(dto.name.clone()),
            hostname: Set(dto.hostname.clone()),
            grpc_hostname: Set(dto.grpc_hostname.unwrap_or(dto.hostname)), // Default to hostname if not provided
            grpc_port: Set(dto.grpc_port.unwrap_or(2053)),
            api_credentials: Set(dto.api_credentials),
            status: Set("unknown".to_string()),
            default_certificate_id: Set(dto.default_certificate_id),
            ..Self::new()
        }
    }
}

impl From<Model> for ServerResponse {
    fn from(server: Model) -> Self {
        Self {
            id: server.id,
            name: server.name,
            hostname: server.hostname,
            grpc_hostname: server.grpc_hostname,
            grpc_port: server.grpc_port,
            status: server.status,
            default_certificate_id: server.default_certificate_id,
            created_at: server.created_at,
            updated_at: server.updated_at,
            has_credentials: server.api_credentials.is_some(),
        }
    }
}

impl Model {
    pub fn apply_update(self, dto: UpdateServerDto) -> ActiveModel {
        let mut active_model: ActiveModel = self.into();

        if let Some(name) = dto.name {
            active_model.name = Set(name);
        }
        if let Some(hostname) = dto.hostname {
            active_model.hostname = Set(hostname);
        }
        if let Some(grpc_hostname) = dto.grpc_hostname {
            active_model.grpc_hostname = Set(grpc_hostname);
        }
        if let Some(grpc_port) = dto.grpc_port {
            active_model.grpc_port = Set(grpc_port);
        }
        if let Some(api_credentials) = dto.api_credentials {
            active_model.api_credentials = Set(Some(api_credentials));
        }
        if let Some(status) = dto.status {
            active_model.status = Set(status);
        }
        if let Some(default_certificate_id) = dto.default_certificate_id {
            active_model.default_certificate_id = Set(Some(default_certificate_id));
        }

        active_model
    }

    pub fn get_grpc_endpoint(&self) -> String {
        let hostname = if self.grpc_hostname.is_empty() {
            tracing::debug!(
                "Using public hostname '{}' for gRPC (grpc_hostname is empty)",
                self.hostname
            );
            &self.hostname
        } else {
            tracing::debug!(
                "Using dedicated gRPC hostname '{}' (different from public hostname '{}')",
                self.grpc_hostname,
                self.hostname
            );
            &self.grpc_hostname
        };
        let endpoint = format!("{}:{}", hostname, self.grpc_port);
        tracing::info!("gRPC endpoint for server '{}': {}", self.name, endpoint);
        endpoint
    }

    #[allow(dead_code)]
    pub fn get_status(&self) -> ServerStatus {
        self.status.clone().into()
    }
}
