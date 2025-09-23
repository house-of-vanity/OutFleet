use sea_orm::*;
use crate::database::entities::{certificate, prelude::*};
use anyhow::Result;
use uuid::Uuid;

#[derive(Clone)]
pub struct CertificateRepository {
    db: DatabaseConnection,
}

impl CertificateRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    pub async fn create(&self, cert_data: certificate::CreateCertificateDto) -> Result<certificate::Model> {
        let cert = certificate::ActiveModel::from(cert_data);

        let result = Certificate::insert(cert).exec(&self.db).await?;
        
        Certificate::find_by_id(result.last_insert_id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Failed to retrieve created certificate"))
    }

    pub async fn find_all(&self) -> Result<Vec<certificate::Model>> {
        Ok(Certificate::find().all(&self.db).await?)
    }

    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<certificate::Model>> {
        Ok(Certificate::find_by_id(id).one(&self.db).await?)
    }

    #[allow(dead_code)]
    pub async fn find_by_domain(&self, domain: &str) -> Result<Vec<certificate::Model>> {
        Ok(Certificate::find()
            .filter(certificate::Column::Domain.eq(domain))
            .all(&self.db)
            .await?)
    }

    #[allow(dead_code)]
    pub async fn find_by_type(&self, cert_type: &str) -> Result<Vec<certificate::Model>> {
        Ok(Certificate::find()
            .filter(certificate::Column::CertType.eq(cert_type))
            .all(&self.db)
            .await?)
    }

    pub async fn update(&self, id: Uuid, cert_data: certificate::UpdateCertificateDto) -> Result<certificate::Model> {
        let cert = Certificate::find_by_id(id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Certificate not found"))?;

        let updated_cert = cert.apply_update(cert_data);

        Ok(updated_cert.update(&self.db).await?)
    }

    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = Certificate::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }

    pub async fn find_expiring_soon(&self, days: i64) -> Result<Vec<certificate::Model>> {
        let threshold = chrono::Utc::now() + chrono::Duration::days(days);
        
        Ok(Certificate::find()
            .filter(certificate::Column::ExpiresAt.lt(threshold))
            .all(&self.db)
            .await?)
    }

    /// Update certificate data (cert and key) and expiration date
    pub async fn update_certificate_data(
        &self, 
        id: Uuid, 
        cert_pem: &str, 
        key_pem: &str,
        expires_at: chrono::DateTime<chrono::Utc>
    ) -> Result<certificate::Model> {
        let mut cert: certificate::ActiveModel = Certificate::find_by_id(id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Certificate not found"))?
            .into();

        cert.cert_data = Set(cert_pem.as_bytes().to_vec());
        cert.key_data = Set(key_pem.as_bytes().to_vec());
        cert.expires_at = Set(expires_at);
        cert.updated_at = Set(chrono::Utc::now());

        Ok(cert.update(&self.db).await?)
    }
}