use sea_orm::entity::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, DeriveEntityModel, Serialize, Deserialize)]
#[sea_orm(table_name = "user_requests")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,
    pub user_id: Option<Uuid>,
    pub telegram_id: i64,
    pub telegram_username: Option<String>,
    pub telegram_first_name: Option<String>,
    pub telegram_last_name: Option<String>,
    pub status: String, // pending, approved, declined
    pub request_message: Option<String>,
    pub response_message: Option<String>,
    pub processed_by_user_id: Option<Uuid>,
    pub processed_at: Option<DateTimeWithTimeZone>,
    pub language: String, // User's language preference (en, ru)
    pub created_at: DateTimeWithTimeZone,
    pub updated_at: DateTimeWithTimeZone,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(
        belongs_to = "super::user::Entity",
        from = "Column::UserId",
        to = "super::user::Column::Id",
        on_update = "Cascade",
        on_delete = "SetNull"
    )]
    User,
    #[sea_orm(
        belongs_to = "super::user::Entity",
        from = "Column::ProcessedByUserId",
        to = "super::user::Column::Id",
        on_update = "Cascade",
        on_delete = "SetNull"
    )]
    ProcessedByUser,
}

impl Related<super::user::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::User.def()
    }
}

impl ActiveModelBehavior for ActiveModel {}

// Request status enum
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RequestStatus {
    Pending,
    Approved,
    Declined,
}

impl RequestStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            RequestStatus::Pending => "pending",
            RequestStatus::Approved => "approved",
            RequestStatus::Declined => "declined",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "pending" => Some(RequestStatus::Pending),
            "approved" => Some(RequestStatus::Approved),
            "declined" => Some(RequestStatus::Declined),
            _ => None,
        }
    }
}

impl Model {
    pub fn get_status(&self) -> RequestStatus {
        RequestStatus::from_str(&self.status).unwrap_or(RequestStatus::Pending)
    }

    pub fn get_full_name(&self) -> String {
        let mut parts = vec![];
        if let Some(first) = &self.telegram_first_name {
            parts.push(first.clone());
        }
        if let Some(last) = &self.telegram_last_name {
            parts.push(last.clone());
        }
        if parts.is_empty() {
            self.telegram_username
                .clone()
                .unwrap_or_else(|| format!("User {}", self.telegram_id))
        } else {
            parts.join(" ")
        }
    }

    pub fn get_telegram_link(&self) -> String {
        if let Some(username) = &self.telegram_username {
            format!("@{}", username)
        } else {
            format!("tg://user?id={}", self.telegram_id)
        }
    }

    pub fn get_language(&self) -> String {
        self.language.clone()
    }
}

// DTOs for creating and updating user requests
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateUserRequestDto {
    pub telegram_id: i64,
    pub telegram_username: Option<String>,
    pub telegram_first_name: Option<String>,
    pub telegram_last_name: Option<String>,
    pub request_message: Option<String>,
    pub language: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateUserRequestDto {
    pub status: Option<String>,
    pub response_message: Option<String>,
    pub processed_by_user_id: Option<Uuid>,
}

impl From<CreateUserRequestDto> for ActiveModel {
    fn from(dto: CreateUserRequestDto) -> Self {
        use sea_orm::ActiveValue::*;

        ActiveModel {
            id: Set(Uuid::new_v4()),
            user_id: Set(None),
            telegram_id: Set(dto.telegram_id),
            telegram_username: Set(dto.telegram_username),
            telegram_first_name: Set(dto.telegram_first_name),
            telegram_last_name: Set(dto.telegram_last_name),
            status: Set("pending".to_string()),
            request_message: Set(dto.request_message),
            response_message: Set(None),
            processed_by_user_id: Set(None),
            processed_at: Set(None),
            language: Set(dto.language),
            created_at: Set(chrono::Utc::now().into()),
            updated_at: Set(chrono::Utc::now().into()),
        }
    }
}

impl Model {
    pub fn apply_update(self, dto: UpdateUserRequestDto, processed_by: Uuid) -> ActiveModel {
        use sea_orm::ActiveValue::*;

        let mut active: ActiveModel = self.into();

        if let Some(status) = dto.status {
            active.status = Set(status);
            active.processed_by_user_id = Set(Some(processed_by));
            active.processed_at = Set(Some(chrono::Utc::now().into()));
        }

        if let Some(response) = dto.response_message {
            active.response_message = Set(Some(response));
        }

        active.updated_at = Set(chrono::Utc::now().into());
        active
    }
}
