use anyhow::Result;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, QueryOrder, Set,
};
use uuid::Uuid;

use crate::database::entities::telegram_config::{
    self, CreateTelegramConfigDto, Model, UpdateTelegramConfigDto,
};

pub struct TelegramConfigRepository {
    db: DatabaseConnection,
}

impl TelegramConfigRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    /// Get the current active configuration (should be only one)
    pub async fn get_active(&self) -> Result<Option<Model>> {
        Ok(telegram_config::Entity::find()
            .filter(telegram_config::Column::IsActive.eq(true))
            .one(&self.db)
            .await?)
    }

    /// Get configuration by ID
    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<Model>> {
        Ok(telegram_config::Entity::find_by_id(id)
            .one(&self.db)
            .await?)
    }

    /// Get the latest configuration (active or not)
    pub async fn get_latest(&self) -> Result<Option<Model>> {
        Ok(telegram_config::Entity::find()
            .order_by_desc(telegram_config::Column::CreatedAt)
            .one(&self.db)
            .await?)
    }

    /// Create new configuration (deactivates previous if exists)
    pub async fn create(&self, dto: CreateTelegramConfigDto) -> Result<Model> {
        // If is_active is true, deactivate all other configs
        if dto.is_active {
            self.deactivate_all().await?;
        }

        let model = telegram_config::ActiveModel {
            id: Set(Uuid::new_v4()),
            bot_token: Set(dto.bot_token),
            is_active: Set(dto.is_active),
            created_at: Set(chrono::Utc::now()),
            updated_at: Set(chrono::Utc::now()),
        };

        Ok(model.insert(&self.db).await?)
    }

    /// Update configuration
    pub async fn update(&self, id: Uuid, dto: UpdateTelegramConfigDto) -> Result<Option<Model>> {
        let model = telegram_config::Entity::find_by_id(id)
            .one(&self.db)
            .await?;

        let Some(model) = model else {
            return Ok(None);
        };

        // If activating this config, deactivate others
        if dto.is_active == Some(true) {
            self.deactivate_all_except(id).await?;
        }

        let mut active_model = model.into_active_model();

        if let Some(bot_token) = dto.bot_token {
            active_model.bot_token = Set(bot_token);
        }
        if let Some(is_active) = dto.is_active {
            active_model.is_active = Set(is_active);
        }

        active_model.updated_at = Set(chrono::Utc::now());

        Ok(Some(active_model.update(&self.db).await?))
    }

    /// Activate a configuration (deactivates all others)
    pub async fn activate(&self, id: Uuid) -> Result<Option<Model>> {
        self.deactivate_all_except(id).await?;

        let model = telegram_config::Entity::find_by_id(id)
            .one(&self.db)
            .await?;

        let Some(model) = model else {
            return Ok(None);
        };

        let mut active_model = model.into_active_model();
        active_model.is_active = Set(true);
        active_model.updated_at = Set(chrono::Utc::now());

        Ok(Some(active_model.update(&self.db).await?))
    }

    /// Deactivate a configuration
    pub async fn deactivate(&self, id: Uuid) -> Result<Option<Model>> {
        let model = telegram_config::Entity::find_by_id(id)
            .one(&self.db)
            .await?;

        let Some(model) = model else {
            return Ok(None);
        };

        let mut active_model = model.into_active_model();
        active_model.is_active = Set(false);
        active_model.updated_at = Set(chrono::Utc::now());

        Ok(Some(active_model.update(&self.db).await?))
    }

    /// Delete configuration
    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = telegram_config::Entity::delete_by_id(id)
            .exec(&self.db)
            .await?;

        Ok(result.rows_affected > 0)
    }

    /// Deactivate all configurations
    async fn deactivate_all(&self) -> Result<()> {
        let configs = telegram_config::Entity::find()
            .filter(telegram_config::Column::IsActive.eq(true))
            .all(&self.db)
            .await?;

        for config in configs {
            let mut active_model = config.into_active_model();
            active_model.is_active = Set(false);
            active_model.updated_at = Set(chrono::Utc::now());
            active_model.update(&self.db).await?;
        }

        Ok(())
    }

    /// Deactivate all configurations except one
    async fn deactivate_all_except(&self, except_id: Uuid) -> Result<()> {
        let configs = telegram_config::Entity::find()
            .filter(telegram_config::Column::IsActive.eq(true))
            .filter(telegram_config::Column::Id.ne(except_id))
            .all(&self.db)
            .await?;

        for config in configs {
            let mut active_model = config.into_active_model();
            active_model.is_active = Set(false);
            active_model.updated_at = Set(chrono::Utc::now());
            active_model.update(&self.db).await?;
        }

        Ok(())
    }
}
