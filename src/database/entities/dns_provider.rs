use sea_orm::entity::prelude::*;
use sea_orm::{Set, ActiveModelTrait};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "dns_providers")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,
    
    pub name: String,
    
    pub provider_type: String, // "cloudflare", "route53", etc.
    
    #[serde(skip_serializing)]
    pub api_token: String, // Encrypted storage in production
    
    pub is_active: bool,
    
    pub created_at: DateTimeUtc,
    
    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {}

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

// DTOs for API requests/responses
#[derive(Debug, Serialize, Deserialize)]
pub struct CreateDnsProviderDto {
    pub name: String,
    pub provider_type: String,
    pub api_token: String,
    pub is_active: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UpdateDnsProviderDto {
    pub name: Option<String>,
    pub api_token: Option<String>,
    pub is_active: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DnsProviderResponseDto {
    pub id: Uuid,
    pub name: String,
    pub provider_type: String,
    pub is_active: bool,
    pub created_at: DateTimeUtc,
    pub updated_at: DateTimeUtc,
    pub has_token: bool, // Don't expose actual token
}

impl From<CreateDnsProviderDto> for ActiveModel {
    fn from(dto: CreateDnsProviderDto) -> Self {
        ActiveModel {
            id: Set(Uuid::new_v4()),
            name: Set(dto.name),
            provider_type: Set(dto.provider_type),
            api_token: Set(dto.api_token),
            is_active: Set(dto.is_active.unwrap_or(true)),
            created_at: Set(chrono::Utc::now()),
            updated_at: Set(chrono::Utc::now()),
        }
    }
}

impl Model {
    /// Update this model with data from UpdateDnsProviderDto
    pub fn apply_update(self, dto: UpdateDnsProviderDto) -> ActiveModel {
        let mut active_model: ActiveModel = self.into();
        
        if let Some(name) = dto.name {
            active_model.name = Set(name);
        }
        if let Some(api_token) = dto.api_token {
            active_model.api_token = Set(api_token);
        }
        if let Some(is_active) = dto.is_active {
            active_model.is_active = Set(is_active);
        }
        
        active_model.updated_at = Set(chrono::Utc::now());
        active_model
    }
    
    /// Convert to response DTO (without exposing API token)
    pub fn to_response_dto(&self) -> DnsProviderResponseDto {
        DnsProviderResponseDto {
            id: self.id,
            name: self.name.clone(),
            provider_type: self.provider_type.clone(),
            is_active: self.is_active,
            created_at: self.created_at,
            updated_at: self.updated_at,
            has_token: !self.api_token.is_empty(),
        }
    }
}

/// Supported DNS provider types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DnsProviderType {
    #[serde(rename = "cloudflare")]
    Cloudflare,
}

impl DnsProviderType {
    pub fn as_str(&self) -> &'static str {
        match self {
            DnsProviderType::Cloudflare => "cloudflare",
        }
    }
    
    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "cloudflare" => Some(DnsProviderType::Cloudflare),
            _ => None,
        }
    }
    
    pub fn all() -> Vec<Self> {
        vec![DnsProviderType::Cloudflare]
    }
}