use sea_orm::entity::prelude::*;
use sea_orm::{Set, ActiveModelTrait};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "certificates")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,
    
    pub name: String,
    
    #[sea_orm(column_name = "cert_type")]
    pub cert_type: String,
    
    pub domain: String,
    
    #[serde(skip_serializing)]
    pub cert_data: Vec<u8>,
    
    #[serde(skip_serializing)]
    pub key_data: Vec<u8>,
    
    #[serde(skip_serializing)]
    pub chain_data: Option<Vec<u8>>,
    
    pub expires_at: DateTimeUtc,
    
    pub auto_renew: bool,
    
    pub created_at: DateTimeUtc,
    
    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(has_many = "super::server::Entity")]
    Servers,
    #[sea_orm(has_many = "super::server_inbound::Entity")]
    ServerInbounds,
}

impl Related<super::server::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Servers.def()
    }
}

impl Related<super::server_inbound::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::ServerInbounds.def()
    }
}

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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CertificateType {
    SelfSigned,
    Imported,
}

impl From<CertificateType> for String {
    fn from(cert_type: CertificateType) -> Self {
        match cert_type {
            CertificateType::SelfSigned => "self_signed".to_string(),
            CertificateType::Imported => "imported".to_string(),
        }
    }
}

impl From<String> for CertificateType {
    fn from(s: String) -> Self {
        match s.as_str() {
            "self_signed" => CertificateType::SelfSigned,
            "imported" => CertificateType::Imported,
            _ => CertificateType::SelfSigned,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateCertificateDto {
    pub name: String,
    pub cert_type: String,
    pub domain: String,
    pub auto_renew: bool,
    #[serde(default)]
    pub certificate_pem: String,
    #[serde(default)]
    pub private_key: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateCertificateDto {
    pub name: Option<String>,
    pub auto_renew: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CertificateResponse {
    pub id: Uuid,
    pub name: String,
    pub cert_type: String,
    pub domain: String,
    pub expires_at: DateTimeUtc,
    pub auto_renew: bool,
    pub created_at: DateTimeUtc,
    pub updated_at: DateTimeUtc,
    pub has_cert_data: bool,
    pub has_key_data: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CertificateDetailsResponse {
    pub id: Uuid,
    pub name: String,
    pub cert_type: String,
    pub domain: String,
    pub expires_at: DateTimeUtc,
    pub auto_renew: bool,
    pub created_at: DateTimeUtc,
    pub updated_at: DateTimeUtc,
    pub certificate_pem: String,
    pub has_private_key: bool,
}

impl From<Model> for CertificateResponse {
    fn from(cert: Model) -> Self {
        Self {
            id: cert.id,
            name: cert.name,
            cert_type: cert.cert_type,
            domain: cert.domain,
            expires_at: cert.expires_at,
            auto_renew: cert.auto_renew,
            created_at: cert.created_at,
            updated_at: cert.updated_at,
            has_cert_data: !cert.cert_data.is_empty(),
            has_key_data: !cert.key_data.is_empty(),
        }
    }
}

impl From<Model> for CertificateDetailsResponse {
    fn from(cert: Model) -> Self {
        let certificate_pem = cert.certificate_pem();
        let has_private_key = !cert.key_data.is_empty();
        
        Self {
            id: cert.id,
            name: cert.name,
            cert_type: cert.cert_type,
            domain: cert.domain,
            expires_at: cert.expires_at,
            auto_renew: cert.auto_renew,
            created_at: cert.created_at,
            updated_at: cert.updated_at,
            certificate_pem,
            has_private_key,
        }
    }
}

impl Model {
    #[allow(dead_code)]
    pub fn is_expired(&self) -> bool {
        self.expires_at < chrono::Utc::now()
    }

    #[allow(dead_code)]
    pub fn expires_soon(&self, days: i64) -> bool {
        let threshold = chrono::Utc::now() + chrono::Duration::days(days);
        self.expires_at < threshold
    }

    /// Get certificate data as PEM string
    pub fn certificate_pem(&self) -> String {
        String::from_utf8_lossy(&self.cert_data).to_string()
    }

    /// Get private key data as PEM string
    pub fn private_key_pem(&self) -> String {
        String::from_utf8_lossy(&self.key_data).to_string()
    }

    pub fn apply_update(self, dto: UpdateCertificateDto) -> ActiveModel {
        let mut active_model: ActiveModel = self.into();
        
        if let Some(name) = dto.name {
            active_model.name = Set(name);
        }
        if let Some(auto_renew) = dto.auto_renew {
            active_model.auto_renew = Set(auto_renew);
        }
        
        active_model
    }
}

impl From<CreateCertificateDto> for ActiveModel {
    fn from(dto: CreateCertificateDto) -> Self {
        Self {
            name: Set(dto.name),
            cert_type: Set(dto.cert_type),
            domain: Set(dto.domain),
            cert_data: Set(dto.certificate_pem.into_bytes()),
            key_data: Set(dto.private_key.into_bytes()),
            chain_data: Set(None),
            expires_at: Set(chrono::Utc::now() + chrono::Duration::days(90)), // Default 90 days
            auto_renew: Set(dto.auto_renew),
            ..Self::new()
        }
    }
}