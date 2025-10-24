use anyhow::Result;
use sea_orm::{
    ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter, QueryOrder,
    QuerySelect,
};
use uuid::Uuid;

use crate::database::entities::user::{
    ActiveModel, Column, CreateUserDto, Entity as User, Model, UpdateUserDto,
};
use sea_orm::{ActiveModelTrait, Set};

pub struct UserRepository {
    db: DatabaseConnection,
}

impl UserRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    /// Get all users with pagination
    pub async fn get_all(&self, page: u64, per_page: u64) -> Result<Vec<Model>> {
        let users = User::find()
            .order_by_desc(Column::CreatedAt)
            .paginate(&self.db, per_page)
            .fetch_page(page.saturating_sub(1))
            .await?;

        Ok(users)
    }

    /// Get user by ID
    pub async fn get_by_id(&self, id: Uuid) -> Result<Option<Model>> {
        let user = User::find_by_id(id).one(&self.db).await?;
        Ok(user)
    }

    /// Find user by ID (alias for get_by_id)
    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<Model>> {
        self.get_by_id(id).await
    }

    /// Get user by telegram ID
    pub async fn get_by_telegram_id(&self, telegram_id: i64) -> Result<Option<Model>> {
        let user = User::find()
            .filter(Column::TelegramId.eq(telegram_id))
            .one(&self.db)
            .await?;
        Ok(user)
    }

    /// Search users by name (with pagination for backward compatibility)
    pub async fn search_by_name(
        &self,
        query: &str,
        page: u64,
        per_page: u64,
    ) -> Result<Vec<Model>> {
        let users = User::find()
            .filter(Column::Name.contains(query))
            .order_by_desc(Column::CreatedAt)
            .paginate(&self.db, per_page)
            .fetch_page(page.saturating_sub(1))
            .await?;

        Ok(users)
    }

    /// Universal search - searches by name, telegram_id, or user_id
    pub async fn search(&self, query: &str) -> Result<Vec<Model>> {
        use sea_orm::Condition;

        let mut condition = Condition::any();

        // Search by name (case-insensitive partial match)
        condition = condition.add(Column::Name.contains(query));

        // Try to parse as telegram_id (i64)
        if let Ok(telegram_id) = query.parse::<i64>() {
            condition = condition.add(Column::TelegramId.eq(telegram_id));
        }

        // Try to parse as UUID (user_id)
        if let Ok(user_id) = Uuid::parse_str(query) {
            condition = condition.add(Column::Id.eq(user_id));
        }

        let users = User::find()
            .filter(condition)
            .order_by_desc(Column::CreatedAt)
            .limit(100) // Reasonable limit to prevent huge results
            .all(&self.db)
            .await?;

        Ok(users)
    }

    /// Create a new user
    pub async fn create(&self, dto: CreateUserDto) -> Result<Model> {
        let active_model: ActiveModel = dto.into();
        let user = User::insert(active_model)
            .exec_with_returning(&self.db)
            .await?;
        Ok(user)
    }

    /// Update user by ID
    pub async fn update(&self, id: Uuid, dto: UpdateUserDto) -> Result<Option<Model>> {
        if let Some(user) = self.get_by_id(id).await? {
            let active_model = user.apply_update(dto);
            User::update(active_model).exec(&self.db).await?;
            // Fetch the updated user
            self.get_by_id(id).await
        } else {
            Ok(None)
        }
    }

    /// Delete user by ID
    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = User::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }

    /// Get total count of users
    pub async fn count(&self) -> Result<u64> {
        let count = User::find().count(&self.db).await?;
        Ok(count)
    }

    /// Check if telegram ID is already used
    pub async fn telegram_id_exists(&self, telegram_id: i64) -> Result<bool> {
        let count = User::find()
            .filter(Column::TelegramId.eq(telegram_id))
            .count(&self.db)
            .await?;
        Ok(count > 0)
    }

    /// Set user as Telegram admin
    pub async fn set_telegram_admin(&self, user_id: Uuid, is_admin: bool) -> Result<Option<Model>> {
        if let Some(user) = self.get_by_id(user_id).await? {
            let mut active_model: ActiveModel = user.into();
            active_model.is_telegram_admin = Set(is_admin);
            active_model.updated_at = Set(chrono::Utc::now());

            let updated = active_model.update(&self.db).await?;
            Ok(Some(updated))
        } else {
            Ok(None)
        }
    }

    /// Check if user is Telegram admin
    pub async fn is_telegram_admin(&self, user_id: Uuid) -> Result<bool> {
        if let Some(user) = self.get_by_id(user_id).await? {
            Ok(user.is_telegram_admin)
        } else {
            Ok(false)
        }
    }

    /// Check if telegram_id is admin
    pub async fn is_telegram_id_admin(&self, telegram_id: i64) -> Result<bool> {
        if let Some(user) = self.get_by_telegram_id(telegram_id).await? {
            Ok(user.is_telegram_admin)
        } else {
            Ok(false)
        }
    }

    /// Get all Telegram admins
    pub async fn get_telegram_admins(&self) -> Result<Vec<Model>> {
        let admins = User::find()
            .filter(Column::IsTelegramAdmin.eq(true))
            .filter(Column::TelegramId.is_not_null())
            .all(&self.db)
            .await?;
        Ok(admins)
    }

    /// Get the first admin user (for system operations)
    pub async fn get_first_admin(&self) -> Result<Option<Model>> {
        let admin = User::find()
            .filter(Column::IsTelegramAdmin.eq(true))
            .one(&self.db)
            .await?;

        Ok(admin)
    }

    /// Count total users
    pub async fn count_all(&self) -> Result<i64> {
        let count = User::find().count(&self.db).await?;

        Ok(count as i64)
    }

    /// Find users with pagination
    pub async fn find_paginated(&self, offset: u64, limit: u64) -> Result<Vec<Model>> {
        let users = User::find()
            .order_by_desc(Column::CreatedAt)
            .offset(offset)
            .limit(limit)
            .all(&self.db)
            .await?;

        Ok(users)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::DatabaseConfig;
    use crate::database::DatabaseManager;

    async fn setup_test_db() -> Result<UserRepository> {
        let config = DatabaseConfig {
            url: std::env::var("DATABASE_URL").unwrap_or_else(|_| "sqlite::memory:".to_string()),
            max_connections: 5,
            connection_timeout: 30,
            auto_migrate: true,
        };

        let db_manager = DatabaseManager::new(&config).await?;
        Ok(UserRepository::new(db_manager.connection().clone()))
    }

    #[tokio::test]
    async fn test_user_crud() {
        let repo = match setup_test_db().await {
            Ok(repo) => repo,
            Err(_) => return, // Skip test if no database available
        };

        // Create user
        let create_dto = CreateUserDto {
            name: "Test User".to_string(),
            comment: Some("Test comment".to_string()),
            telegram_id: Some(123456789),
            is_telegram_admin: false,
        };

        let created_user = repo.create(create_dto).await.unwrap();
        assert_eq!(created_user.name, "Test User");
        assert_eq!(created_user.telegram_id, Some(123456789));

        // Get by ID
        let fetched_user = repo.get_by_id(created_user.id).await.unwrap();
        assert!(fetched_user.is_some());
        assert_eq!(fetched_user.unwrap().name, "Test User");

        // Update user
        let update_dto = UpdateUserDto {
            name: Some("Updated User".to_string()),
            comment: None,
            telegram_id: None,
            is_telegram_admin: None,
        };

        let updated_user = repo.update(created_user.id, update_dto).await.unwrap();
        assert!(updated_user.is_some());
        assert_eq!(updated_user.unwrap().name, "Updated User");

        // Delete user
        let deleted = repo.delete(created_user.id).await.unwrap();
        assert!(deleted);

        // Verify deletion
        let deleted_user = repo.get_by_id(created_user.id).await.unwrap();
        assert!(deleted_user.is_none());
    }
}
