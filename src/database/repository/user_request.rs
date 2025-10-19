use anyhow::Result;
use sea_orm::{EntityTrait, QueryFilter, ColumnTrait, DatabaseConnection, QueryOrder, PaginatorTrait, QuerySelect};
use uuid::Uuid;
use crate::database::entities::user_request::{
    self, Model, ActiveModel, CreateUserRequestDto, UpdateUserRequestDto, RequestStatus
};

pub struct UserRequestRepository {
    db: DatabaseConnection,
}

impl UserRequestRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    pub async fn find_all(&self, page: u64, per_page: u64) -> Result<(Vec<Model>, u64)> {
        let paginator = user_request::Entity::find()
            .order_by_desc(user_request::Column::CreatedAt)
            .paginate(&self.db, per_page);
        
        let total = paginator.num_items().await?;
        let items = paginator.fetch_page(page - 1).await?;
        
        Ok((items, total))
    }

    pub async fn find_pending(&self, page: u64, per_page: u64) -> Result<(Vec<Model>, u64)> {
        let paginator = user_request::Entity::find()
            .filter(user_request::Column::Status.eq("pending"))
            .order_by_desc(user_request::Column::CreatedAt)
            .paginate(&self.db, per_page);
        
        let total = paginator.num_items().await?;
        let items = paginator.fetch_page(page - 1).await?;
        
        Ok((items, total))
    }

    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<Model>> {
        let request = user_request::Entity::find_by_id(id)
            .one(&self.db)
            .await?;
        Ok(request)
    }

    pub async fn find_by_telegram_id(&self, telegram_id: i64) -> Result<Vec<Model>> {
        let requests = user_request::Entity::find()
            .filter(user_request::Column::TelegramId.eq(telegram_id))
            .order_by_desc(user_request::Column::CreatedAt)
            .all(&self.db)
            .await?;
        Ok(requests)
    }

    /// Find recent user requests (ordered by creation date)
    pub async fn find_recent(&self, limit: u64) -> Result<Vec<Model>> {
        let requests = user_request::Entity::find()
            .order_by_desc(user_request::Column::CreatedAt)
            .limit(limit)
            .all(&self.db)
            .await?;
        Ok(requests)
    }

    pub async fn find_pending_by_telegram_id(&self, telegram_id: i64) -> Result<Option<Model>> {
        let request = user_request::Entity::find()
            .filter(user_request::Column::TelegramId.eq(telegram_id))
            .filter(user_request::Column::Status.eq("pending"))
            .order_by_desc(user_request::Column::CreatedAt)
            .one(&self.db)
            .await?;
        Ok(request)
    }

    pub async fn create(&self, dto: CreateUserRequestDto) -> Result<Model> {
        use sea_orm::ActiveModelTrait;
        let active_model: ActiveModel = dto.into();
        let request = active_model.insert(&self.db).await?;
        Ok(request)
    }

    pub async fn update(&self, id: Uuid, dto: UpdateUserRequestDto, processed_by: Uuid) -> Result<Option<Model>> {
        let model = user_request::Entity::find_by_id(id)
            .one(&self.db)
            .await?;
        
        match model {
            Some(model) => {
                use sea_orm::ActiveModelTrait;
                let active_model = model.apply_update(dto, processed_by);
                let updated = active_model.update(&self.db).await?;
                Ok(Some(updated))
            }
            None => Ok(None),
        }
    }

    pub async fn approve(&self, id: Uuid, response_message: Option<String>, processed_by: Uuid) -> Result<Option<Model>> {
        let dto = UpdateUserRequestDto {
            status: Some(RequestStatus::Approved.as_str().to_string()),
            response_message,
            processed_by_user_id: None,
        };
        self.update(id, dto, processed_by).await
    }

    pub async fn decline(&self, id: Uuid, response_message: Option<String>, processed_by: Uuid) -> Result<Option<Model>> {
        let dto = UpdateUserRequestDto {
            status: Some(RequestStatus::Declined.as_str().to_string()),
            response_message,
            processed_by_user_id: None,
        };
        self.update(id, dto, processed_by).await
    }

    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = user_request::Entity::delete_by_id(id)
            .exec(&self.db)
            .await?;
        Ok(result.rows_affected > 0)
    }

    pub async fn count_by_status(&self, status: RequestStatus) -> Result<u64> {
        let count = user_request::Entity::find()
            .filter(user_request::Column::Status.eq(status.as_str()))
            .count(&self.db)
            .await?;
        Ok(count)
    }
}