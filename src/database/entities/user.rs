use sea_orm::entity::prelude::*;
use sea_orm::{ActiveModelTrait, Set};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "users")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,

    /// User display name
    pub name: String,

    /// Optional comment/description about the user
    #[sea_orm(column_type = "Text")]
    pub comment: Option<String>,

    /// Optional Telegram user ID for bot integration
    pub telegram_id: Option<i64>,

    /// Whether the user is a Telegram admin
    pub is_telegram_admin: bool,

    /// When the user was registered/created
    pub created_at: DateTimeUtc,

    /// Last time user record was updated
    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {}

impl ActiveModelBehavior for ActiveModel {
    /// Called before insert and update
    fn new() -> Self {
        Self {
            id: Set(Uuid::new_v4()),
            is_telegram_admin: Set(false),
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
            }
            Ok(self)
        })
    }
}

/// User creation data transfer object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateUserDto {
    pub name: String,
    pub comment: Option<String>,
    pub telegram_id: Option<i64>,
    #[serde(default)]
    pub is_telegram_admin: bool,
}

/// User update data transfer object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateUserDto {
    pub name: Option<String>,
    pub comment: Option<String>,
    pub telegram_id: Option<i64>,
    pub is_telegram_admin: Option<bool>,
}

impl From<CreateUserDto> for ActiveModel {
    fn from(dto: CreateUserDto) -> Self {
        Self {
            name: Set(dto.name),
            comment: Set(dto.comment),
            telegram_id: Set(dto.telegram_id),
            is_telegram_admin: Set(dto.is_telegram_admin),
            ..Self::new()
        }
    }
}

impl Model {
    /// Update this model with data from UpdateUserDto
    pub fn apply_update(self, dto: UpdateUserDto) -> ActiveModel {
        let mut active_model: ActiveModel = self.into();

        if let Some(name) = dto.name {
            active_model.name = Set(name);
        }
        if let Some(comment) = dto.comment {
            active_model.comment = Set(Some(comment));
        } else if dto.comment.is_some() {
            // Explicitly set to None if Some(None) was passed
            active_model.comment = Set(None);
        }
        if dto.telegram_id.is_some() {
            active_model.telegram_id = Set(dto.telegram_id);
        }
        if let Some(is_admin) = dto.is_telegram_admin {
            active_model.is_telegram_admin = Set(is_admin);
        }

        active_model
    }

    /// Check if user has Telegram integration
    #[allow(dead_code)]
    pub fn has_telegram(&self) -> bool {
        self.telegram_id.is_some()
    }

    /// Get display name with optional comment
    #[allow(dead_code)]
    pub fn display_name(&self) -> String {
        match &self.comment {
            Some(comment) if !comment.is_empty() => format!("{} ({})", self.name, comment),
            _ => self.name.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_user_dto_conversion() {
        let dto = CreateUserDto {
            name: "Test User".to_string(),
            comment: Some("Test comment".to_string()),
            telegram_id: Some(123456789),
        };

        let active_model: ActiveModel = dto.into();

        assert_eq!(active_model.name.unwrap(), "Test User");
        assert_eq!(
            active_model.comment.unwrap(),
            Some("Test comment".to_string())
        );
        assert_eq!(active_model.telegram_id.unwrap(), Some(123456789));
    }

    #[test]
    fn test_user_display_name() {
        let user = Model {
            id: Uuid::new_v4(),
            name: "John Doe".to_string(),
            comment: Some("Admin user".to_string()),
            telegram_id: None,
            created_at: chrono::Utc::now(),
            updated_at: chrono::Utc::now(),
        };

        assert_eq!(user.display_name(), "John Doe (Admin user)");

        let user_no_comment = Model {
            comment: None,
            ..user
        };

        assert_eq!(user_no_comment.display_name(), "John Doe");
    }

    #[test]
    fn test_has_telegram() {
        let user_with_telegram = Model {
            id: Uuid::new_v4(),
            name: "User".to_string(),
            comment: None,
            telegram_id: Some(123456789),
            created_at: chrono::Utc::now(),
            updated_at: chrono::Utc::now(),
        };

        let user_without_telegram = Model {
            telegram_id: None,
            ..user_with_telegram.clone()
        };

        assert!(user_with_telegram.has_telegram());
        assert!(!user_without_telegram.has_telegram());
    }
}
