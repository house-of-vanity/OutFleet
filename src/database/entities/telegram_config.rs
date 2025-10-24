use sea_orm::entity::prelude::*;
use sea_orm::{ActiveModelTrait, Set};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "telegram_config")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,

    /// Telegram bot token (encrypted in production)
    pub bot_token: String,

    /// Whether the bot is active
    pub is_active: bool,

    /// When the config was created
    pub created_at: DateTimeUtc,

    /// Last time config was updated
    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {}

impl ActiveModelBehavior for ActiveModel {
    /// Called before insert and update
    fn new() -> Self {
        Self {
            id: Set(Uuid::new_v4()),
            created_at: Set(chrono::Utc::now()),
            updated_at: Set(chrono::Utc::now()),
            ..ActiveModelTrait::default()
        }
    }

    /// Called before update
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
            } else if self.id.is_not_set() {
                self.id = Set(Uuid::new_v4());
            }

            if self.created_at.is_not_set() {
                self.created_at = Set(chrono::Utc::now());
            }

            if self.updated_at.is_not_set() {
                self.updated_at = Set(chrono::Utc::now());
            }

            Ok(self)
        })
    }
}

/// DTO for creating a new Telegram configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct CreateTelegramConfigDto {
    pub bot_token: String,
    pub is_active: bool,
}

/// DTO for updating Telegram configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct UpdateTelegramConfigDto {
    pub bot_token: Option<String>,
    pub is_active: Option<bool>,
}

impl Model {
    /// Convert to ActiveModel for updates
    pub fn into_active_model(self) -> ActiveModel {
        ActiveModel {
            id: Set(self.id),
            bot_token: Set(self.bot_token),
            is_active: Set(self.is_active),
            created_at: Set(self.created_at),
            updated_at: Set(self.updated_at),
        }
    }
}
