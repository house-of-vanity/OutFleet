use sea_orm::entity::prelude::*;
use sea_orm::{Set, ActiveModelTrait};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "inbound_users")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,
    
    pub server_inbound_id: Uuid,
    
    pub username: String,
    
    pub email: String,
    
    pub xray_user_id: String,
    
    pub level: i32,
    
    pub is_active: bool,
    
    pub created_at: DateTimeUtc,
    
    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(
        belongs_to = "super::server_inbound::Entity",
        from = "Column::ServerInboundId",
        to = "super::server_inbound::Column::Id"
    )]
    ServerInbound,
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
    ) -> core::pin::Pin<Box<dyn core::future::Future<Output = Result<Self, DbErr>> + Send + 'async_trait>>
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
    pub server_inbound_id: Uuid,
    pub username: String,
    pub level: Option<i32>,
}

impl CreateInboundUserDto {
    /// Generate email in format: username@OutFleet
    pub fn generate_email(&self) -> String {
        format!("{}@OutFleet", self.username)
    }
    
    /// Generate UUID for xray user
    pub fn generate_xray_user_id(&self) -> String {
        Uuid::new_v4().to_string()
    }
}

/// Inbound user update data transfer object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateInboundUserDto {
    pub username: Option<String>,
    pub level: Option<i32>,
    pub is_active: Option<bool>,
}

impl From<CreateInboundUserDto> for ActiveModel {
    fn from(dto: CreateInboundUserDto) -> Self {
        let email = dto.generate_email();
        let xray_user_id = dto.generate_xray_user_id();
        
        Self {
            server_inbound_id: Set(dto.server_inbound_id),
            username: Set(dto.username),
            email: Set(email),
            xray_user_id: Set(xray_user_id),
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
        
        if let Some(username) = dto.username {
            let new_email = format!("{}@OutFleet", username);
            active_model.username = Set(username);
            active_model.email = Set(new_email);
        }
        if let Some(level) = dto.level {
            active_model.level = Set(level);
        }
        if let Some(is_active) = dto.is_active {
            active_model.is_active = Set(is_active);
        }
        
        active_model
    }
}

/// Response model for inbound user
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InboundUserResponse {
    pub id: Uuid,
    pub server_inbound_id: Uuid,
    pub username: String,
    pub email: String,
    pub xray_user_id: String,
    pub level: i32,
    pub is_active: bool,
    pub created_at: String,
    pub updated_at: String,
}

impl From<Model> for InboundUserResponse {
    fn from(model: Model) -> Self {
        Self {
            id: model.id,
            server_inbound_id: model.server_inbound_id,
            username: model.username,
            email: model.email,
            xray_user_id: model.xray_user_id,
            level: model.level,
            is_active: model.is_active,
            created_at: model.created_at.to_rfc3339(),
            updated_at: model.updated_at.to_rfc3339(),
        }
    }
}