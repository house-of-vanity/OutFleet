use sea_orm::entity::prelude::*;
use sea_orm::{ActiveModelTrait, Set};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "inbound_users")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,

    /// Reference to the actual user
    pub user_id: Uuid,

    pub server_inbound_id: Uuid,

    /// Generated xray user ID (UUID for protocols like vmess/vless)
    pub xray_user_id: String,

    /// Generated password for protocols like trojan/shadowsocks  
    pub password: Option<String>,

    pub level: i32,

    pub is_active: bool,

    pub created_at: DateTimeUtc,

    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(
        belongs_to = "super::user::Entity",
        from = "Column::UserId",
        to = "super::user::Column::Id"
    )]
    User,
    #[sea_orm(
        belongs_to = "super::server_inbound::Entity",
        from = "Column::ServerInboundId",
        to = "super::server_inbound::Column::Id"
    )]
    ServerInbound,
}

impl Related<super::user::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::User.def()
    }
}

impl Related<super::server_inbound::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::ServerInbound.def()
    }
}

impl ActiveModelBehavior for ActiveModel {
    fn new() -> Self {
        Self {
            id: Set(Uuid::new_v4()),
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

/// Inbound user creation data transfer object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateInboundUserDto {
    pub user_id: Uuid,
    pub server_inbound_id: Uuid,
    pub level: Option<i32>,
}

impl CreateInboundUserDto {
    /// Generate UUID for xray user (for vmess/vless)
    pub fn generate_xray_user_id(&self) -> String {
        Uuid::new_v4().to_string()
    }

    /// Generate random password (for trojan/shadowsocks)
    pub fn generate_password(&self) -> String {
        use rand::distributions::Alphanumeric;
        use rand::prelude::*;

        thread_rng()
            .sample_iter(&Alphanumeric)
            .take(24)
            .map(char::from)
            .collect()
    }
}

/// Inbound user update data transfer object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateInboundUserDto {
    pub level: Option<i32>,
    pub is_active: Option<bool>,
}

impl From<CreateInboundUserDto> for ActiveModel {
    fn from(dto: CreateInboundUserDto) -> Self {
        let xray_user_id = dto.generate_xray_user_id();

        Self {
            user_id: Set(dto.user_id),
            server_inbound_id: Set(dto.server_inbound_id),
            xray_user_id: Set(xray_user_id),
            password: Set(Some(dto.generate_password())), // Generate password for all protocols
            level: Set(dto.level.unwrap_or(0)),
            is_active: Set(true),
            ..Self::new()
        }
    }
}

impl Model {
    /// Update this model with data from UpdateInboundUserDto
    pub fn apply_update(self, dto: UpdateInboundUserDto) -> ActiveModel {
        let mut active_model: ActiveModel = self.into();

        if let Some(level) = dto.level {
            active_model.level = Set(level);
        }
        if let Some(is_active) = dto.is_active {
            active_model.is_active = Set(is_active);
        }

        active_model
    }

    /// Generate email for xray client based on user information
    pub fn generate_client_email(&self, username: &str) -> String {
        format!("{}@OutFleet", username)
    }
}

/// Response model for inbound user
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InboundUserResponse {
    pub id: Uuid,
    pub user_id: Uuid,
    pub server_inbound_id: Uuid,
    pub xray_user_id: String,
    pub password: Option<String>,
    pub level: i32,
    pub is_active: bool,
    pub created_at: String,
    pub updated_at: String,
}

impl From<Model> for InboundUserResponse {
    fn from(model: Model) -> Self {
        Self {
            id: model.id,
            user_id: model.user_id,
            server_inbound_id: model.server_inbound_id,
            xray_user_id: model.xray_user_id,
            password: model.password,
            level: model.level,
            is_active: model.is_active,
            created_at: model.created_at.to_rfc3339(),
            updated_at: model.updated_at.to_rfc3339(),
        }
    }
}
