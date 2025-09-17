use sea_orm::*;
use uuid::Uuid;
use anyhow::Result;

use crate::database::entities::user_access::{self, Entity as UserAccess, Model, ActiveModel, CreateUserAccessDto, UpdateUserAccessDto};

pub struct UserAccessRepository {
    db: DatabaseConnection,
}

impl UserAccessRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    /// Find all user access records
    pub async fn find_all(&self) -> Result<Vec<Model>> {
        let records = UserAccess::find().all(&self.db).await?;
        Ok(records)
    }

    /// Find user access by ID
    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<Model>> {
        let record = UserAccess::find_by_id(id).one(&self.db).await?;
        Ok(record)
    }

    /// Find user access by user ID
    pub async fn find_by_user_id(&self, user_id: Uuid) -> Result<Vec<Model>> {
        let records = UserAccess::find()
            .filter(user_access::Column::UserId.eq(user_id))
            .all(&self.db)
            .await?;
        Ok(records)
    }

    /// Find user access by server and inbound
    pub async fn find_by_server_inbound(&self, server_id: Uuid, server_inbound_id: Uuid) -> Result<Vec<Model>> {
        let records = UserAccess::find()
            .filter(user_access::Column::ServerId.eq(server_id))
            .filter(user_access::Column::ServerInboundId.eq(server_inbound_id))
            .all(&self.db)
            .await?;
        Ok(records)
    }

    /// Find active user access for specific user, server and inbound
    pub async fn find_active_access(&self, user_id: Uuid, server_id: Uuid, server_inbound_id: Uuid) -> Result<Option<Model>> {
        let record = UserAccess::find()
            .filter(user_access::Column::UserId.eq(user_id))
            .filter(user_access::Column::ServerId.eq(server_id))
            .filter(user_access::Column::ServerInboundId.eq(server_inbound_id))
            .filter(user_access::Column::IsActive.eq(true))
            .one(&self.db)
            .await?;
        Ok(record)
    }

    /// Create new user access
    pub async fn create(&self, dto: CreateUserAccessDto) -> Result<Model> {
        let active_model: ActiveModel = dto.into();
        let model = active_model.insert(&self.db).await?;
        Ok(model)
    }

    /// Update user access
    pub async fn update(&self, id: Uuid, dto: UpdateUserAccessDto) -> Result<Option<Model>> {
        let existing = match self.find_by_id(id).await? {
            Some(model) => model,
            None => return Ok(None),
        };

        let active_model = existing.apply_update(dto);
        let updated = active_model.update(&self.db).await?;
        Ok(Some(updated))
    }

    /// Delete user access
    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = UserAccess::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }

    /// Enable user access (set is_active = true)
    pub async fn enable(&self, id: Uuid) -> Result<Option<Model>> {
        self.update(id, UpdateUserAccessDto {
            is_active: Some(true),
            level: None,
        }).await
    }

    /// Disable user access (set is_active = false)
    pub async fn disable(&self, id: Uuid) -> Result<Option<Model>> {
        self.update(id, UpdateUserAccessDto {
            is_active: Some(false),
            level: None,
        }).await
    }

    /// Get all active access for a user
    pub async fn find_active_for_user(&self, user_id: Uuid) -> Result<Vec<Model>> {
        let records = UserAccess::find()
            .filter(user_access::Column::UserId.eq(user_id))
            .filter(user_access::Column::IsActive.eq(true))
            .all(&self.db)
            .await?;
        Ok(records)
    }

    /// Remove all access for a specific server inbound
    pub async fn remove_all_for_inbound(&self, server_inbound_id: Uuid) -> Result<u64> {
        let result = UserAccess::delete_many()
            .filter(user_access::Column::ServerInboundId.eq(server_inbound_id))
            .exec(&self.db)
            .await?;
        Ok(result.rows_affected)
    }
}