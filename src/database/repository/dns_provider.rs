use anyhow::Result;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    Set,
};
use uuid::Uuid;

use crate::database::entities::dns_provider::{
    ActiveModel, Column, CreateDnsProviderDto, DnsProviderType, Entity, Model, UpdateDnsProviderDto,
};

pub struct DnsProviderRepository {
    db: DatabaseConnection,
}

impl DnsProviderRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    pub async fn find_all(&self) -> Result<Vec<Model>> {
        let providers = Entity::find().all(&self.db).await?;
        Ok(providers)
    }

    pub async fn find_active(&self) -> Result<Vec<Model>> {
        let providers = Entity::find()
            .filter(Column::IsActive.eq(true))
            .all(&self.db)
            .await?;
        Ok(providers)
    }

    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<Model>> {
        let provider = Entity::find_by_id(id).one(&self.db).await?;
        Ok(provider)
    }

    pub async fn find_by_name(&self, name: &str) -> Result<Option<Model>> {
        let provider = Entity::find()
            .filter(Column::Name.eq(name))
            .one(&self.db)
            .await?;
        Ok(provider)
    }

    pub async fn find_by_type(&self, provider_type: &str) -> Result<Vec<Model>> {
        let providers = Entity::find()
            .filter(Column::ProviderType.eq(provider_type))
            .all(&self.db)
            .await?;
        Ok(providers)
    }

    pub async fn find_active_by_type(&self, provider_type: &str) -> Result<Vec<Model>> {
        let providers = Entity::find()
            .filter(Column::ProviderType.eq(provider_type))
            .filter(Column::IsActive.eq(true))
            .all(&self.db)
            .await?;
        Ok(providers)
    }

    pub async fn create(&self, dto: CreateDnsProviderDto) -> Result<Model> {
        let active_model: ActiveModel = dto.into();
        let provider = active_model.insert(&self.db).await?;
        Ok(provider)
    }

    pub async fn update(&self, id: Uuid, dto: UpdateDnsProviderDto) -> Result<Option<Model>> {
        let provider = match self.find_by_id(id).await? {
            Some(provider) => provider,
            None => return Ok(None),
        };

        let updated_model = provider.apply_update(dto);
        let updated_provider = updated_model.update(&self.db).await?;
        Ok(Some(updated_provider))
    }

    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = Entity::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }

    pub async fn enable(&self, id: Uuid) -> Result<Option<Model>> {
        let provider = match self.find_by_id(id).await? {
            Some(provider) => provider,
            None => return Ok(None),
        };

        let mut active_model: ActiveModel = provider.into();
        active_model.is_active = Set(true);
        active_model.updated_at = Set(chrono::Utc::now());

        let updated_provider = active_model.update(&self.db).await?;
        Ok(Some(updated_provider))
    }

    pub async fn disable(&self, id: Uuid) -> Result<Option<Model>> {
        let provider = match self.find_by_id(id).await? {
            Some(provider) => provider,
            None => return Ok(None),
        };

        let mut active_model: ActiveModel = provider.into();
        active_model.is_active = Set(false);
        active_model.updated_at = Set(chrono::Utc::now());

        let updated_provider = active_model.update(&self.db).await?;
        Ok(Some(updated_provider))
    }

    /// Check if a provider name already exists
    pub async fn name_exists(&self, name: &str, exclude_id: Option<Uuid>) -> Result<bool> {
        let mut query = Entity::find().filter(Column::Name.eq(name));

        if let Some(id) = exclude_id {
            query = query.filter(Column::Id.ne(id));
        }

        let count = query.count(&self.db).await?;
        Ok(count > 0)
    }

    /// Get the first active provider of a specific type
    pub async fn get_active_provider_by_type(
        &self,
        provider_type: DnsProviderType,
    ) -> Result<Option<Model>> {
        let provider = Entity::find()
            .filter(Column::ProviderType.eq(provider_type.as_str()))
            .filter(Column::IsActive.eq(true))
            .one(&self.db)
            .await?;
        Ok(provider)
    }
}
