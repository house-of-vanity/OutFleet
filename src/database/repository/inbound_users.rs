use anyhow::Result;
use sea_orm::{ActiveModelTrait, DatabaseConnection, EntityTrait, ColumnTrait, QueryFilter, Set};
use uuid::Uuid;

use crate::database::entities::inbound_users::{
    Entity, Model, ActiveModel, CreateInboundUserDto, UpdateInboundUserDto, Column
};

pub struct InboundUsersRepository {
    db: DatabaseConnection,
}

impl InboundUsersRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    pub async fn find_all(&self) -> Result<Vec<Model>> {
        let users = Entity::find().all(&self.db).await?;
        Ok(users)
    }

    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<Model>> {
        let user = Entity::find_by_id(id).one(&self.db).await?;
        Ok(user)
    }

    /// Find all users for a specific inbound
    pub async fn find_by_inbound_id(&self, inbound_id: Uuid) -> Result<Vec<Model>> {
        let users = Entity::find()
            .filter(Column::ServerInboundId.eq(inbound_id))
            .all(&self.db)
            .await?;
        Ok(users)
    }

    /// Find active users for a specific inbound
    pub async fn find_active_by_inbound_id(&self, inbound_id: Uuid) -> Result<Vec<Model>> {
        let users = Entity::find()
            .filter(Column::ServerInboundId.eq(inbound_id))
            .filter(Column::IsActive.eq(true))
            .all(&self.db)
            .await?;
        Ok(users)
    }

    /// Find user by user_id and inbound (for uniqueness check - one user per inbound)
    pub async fn find_by_user_and_inbound(&self, user_id: Uuid, inbound_id: Uuid) -> Result<Option<Model>> {
        let user = Entity::find()
            .filter(Column::UserId.eq(user_id))
            .filter(Column::ServerInboundId.eq(inbound_id))
            .one(&self.db)
            .await?;
        Ok(user)
    }

    /// Find all inbound access for a specific user
    pub async fn find_by_user_id(&self, user_id: Uuid) -> Result<Vec<Model>> {
        let users = Entity::find()
            .filter(Column::UserId.eq(user_id))
            .all(&self.db)
            .await?;
        Ok(users)
    }

    pub async fn create(&self, dto: CreateInboundUserDto) -> Result<Model> {
        let active_model: ActiveModel = dto.into();
        let user = active_model.insert(&self.db).await?;
        Ok(user)
    }

    pub async fn update(&self, id: Uuid, dto: UpdateInboundUserDto) -> Result<Option<Model>> {
        let user = match self.find_by_id(id).await? {
            Some(user) => user,
            None => return Ok(None),
        };

        let updated_model = user.apply_update(dto);
        let updated_user = updated_model.update(&self.db).await?;
        Ok(Some(updated_user))
    }

    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = Entity::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }

    /// Enable user (set is_active = true)
    pub async fn enable(&self, id: Uuid) -> Result<Option<Model>> {
        let user = match self.find_by_id(id).await? {
            Some(user) => user,
            None => return Ok(None),
        };

        let mut active_model: ActiveModel = user.into();
        active_model.is_active = Set(true);
        active_model.updated_at = Set(chrono::Utc::now());
        
        let updated_user = active_model.update(&self.db).await?;
        Ok(Some(updated_user))
    }

    /// Disable user (set is_active = false)
    pub async fn disable(&self, id: Uuid) -> Result<Option<Model>> {
        let user = match self.find_by_id(id).await? {
            Some(user) => user,
            None => return Ok(None),
        };

        let mut active_model: ActiveModel = user.into();
        active_model.is_active = Set(false);
        active_model.updated_at = Set(chrono::Utc::now());
        
        let updated_user = active_model.update(&self.db).await?;
        Ok(Some(updated_user))
    }

    /// Remove all users for a specific inbound (when inbound is deleted)
    pub async fn remove_all_for_inbound(&self, inbound_id: Uuid) -> Result<u64> {
        let result = Entity::delete_many()
            .filter(Column::ServerInboundId.eq(inbound_id))
            .exec(&self.db)
            .await?;
        Ok(result.rows_affected)
    }

    /// Check if user already has access to this inbound
    pub async fn user_has_access_to_inbound(&self, user_id: Uuid, inbound_id: Uuid) -> Result<bool> {
        let exists = self.find_by_user_and_inbound(user_id, inbound_id).await?;
        Ok(exists.is_some())
    }
}