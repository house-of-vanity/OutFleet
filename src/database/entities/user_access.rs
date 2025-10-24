use sea_orm::entity::prelude::*;
use sea_orm::{ActiveModelTrait, Set};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "user_access")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,

    /// User ID this access is for
    pub user_id: Uuid,

    /// Server ID this access applies to
    pub server_id: Uuid,

    /// Server inbound ID this access applies to
    pub server_inbound_id: Uuid,

    /// User's unique identifier in xray (UUID for VLESS/VMess, password for Trojan)
    pub xray_user_id: String,

    /// User's email in xray
    pub xray_email: String,

    /// User level in xray (0-255)
    pub level: i32,

    /// Whether this access is currently active
    pub is_active: bool,

    /// When this access was created
    pub created_at: DateTimeUtc,

    /// Last time this access was updated
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
        belongs_to = "super::server::Entity",
        from = "Column::ServerId",
        to = "super::server::Column::Id"
    )]
    Server,
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

impl Related<super::server::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Server.def()
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

/// User access creation data transfer object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateUserAccessDto {
    pub user_id: Uuid,
    pub server_id: Uuid,
    pub server_inbound_id: Uuid,
    pub xray_user_id: String,
    pub xray_email: String,
    pub level: Option<i32>,
}

/// User access update data transfer object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateUserAccessDto {
    pub is_active: Option<bool>,
    pub level: Option<i32>,
}

impl From<CreateUserAccessDto> for ActiveModel {
    fn from(dto: CreateUserAccessDto) -> Self {
        Self {
            user_id: Set(dto.user_id),
            server_id: Set(dto.server_id),
            server_inbound_id: Set(dto.server_inbound_id),
            xray_user_id: Set(dto.xray_user_id),
            xray_email: Set(dto.xray_email),
            level: Set(dto.level.unwrap_or(0)),
            is_active: Set(true),
            ..Self::new()
        }
    }
}

impl Model {
    /// Update this model with data from UpdateUserAccessDto
    pub fn apply_update(self, dto: UpdateUserAccessDto) -> ActiveModel {
        let mut active_model: ActiveModel = self.into();

        if let Some(is_active) = dto.is_active {
            active_model.is_active = Set(is_active);
        }
        if let Some(level) = dto.level {
            active_model.level = Set(level);
        }

        active_model
    }
}

/// Response model for user access
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserAccessResponse {
    pub id: Uuid,
    pub user_id: Uuid,
    pub server_id: Uuid,
    pub server_inbound_id: Uuid,
    pub xray_user_id: String,
    pub xray_email: String,
    pub level: i32,
    pub is_active: bool,
    pub created_at: String,
    pub updated_at: String,
}

impl From<Model> for UserAccessResponse {
    fn from(model: Model) -> Self {
        Self {
            id: model.id,
            user_id: model.user_id,
            server_id: model.server_id,
            server_inbound_id: model.server_inbound_id,
            xray_user_id: model.xray_user_id,
            xray_email: model.xray_email,
            level: model.level,
            is_active: model.is_active,
            created_at: model.created_at.to_rfc3339(),
            updated_at: model.updated_at.to_rfc3339(),
        }
    }
}
