use sea_orm::*;
use crate::database::entities::{server_inbound, prelude::*};
use anyhow::Result;
use uuid::Uuid;

#[derive(Clone)]
pub struct ServerInboundRepository {
    db: DatabaseConnection,
}

#[allow(dead_code)]
impl ServerInboundRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    pub async fn create(&self, server_id: Uuid, inbound_data: server_inbound::CreateServerInboundDto) -> Result<server_inbound::Model> {
        let mut inbound: server_inbound::ActiveModel = inbound_data.into();
        inbound.id = Set(Uuid::new_v4());
        inbound.server_id = Set(server_id);
        inbound.created_at = Set(chrono::Utc::now());
        inbound.updated_at = Set(chrono::Utc::now());

        let result = ServerInbound::insert(inbound).exec(&self.db).await?;
        
        ServerInbound::find_by_id(result.last_insert_id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Failed to retrieve created server inbound"))
    }

    pub async fn create_with_protocol(&self, server_id: Uuid, inbound_data: server_inbound::CreateServerInboundDto, protocol: &str) -> Result<server_inbound::Model> {
        let mut inbound: server_inbound::ActiveModel = inbound_data.into();
        inbound.id = Set(Uuid::new_v4());
        inbound.server_id = Set(server_id);
        inbound.created_at = Set(chrono::Utc::now());
        inbound.updated_at = Set(chrono::Utc::now());
        
        // Override tag with protocol prefix
        let id = inbound.id.as_ref();
        inbound.tag = Set(format!("{}-inbound-{}", protocol, id));

        let result = ServerInbound::insert(inbound).exec(&self.db).await?;
        
        ServerInbound::find_by_id(result.last_insert_id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Failed to retrieve created server inbound"))
    }

    pub async fn find_all(&self) -> Result<Vec<server_inbound::Model>> {
        Ok(ServerInbound::find().all(&self.db).await?)
    }

    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<server_inbound::Model>> {
        Ok(ServerInbound::find_by_id(id).one(&self.db).await?)
    }

    pub async fn find_by_server_id(&self, server_id: Uuid) -> Result<Vec<server_inbound::Model>> {
        Ok(ServerInbound::find()
            .filter(server_inbound::Column::ServerId.eq(server_id))
            .all(&self.db)
            .await?)
    }

    pub async fn find_by_server_id_with_template(&self, server_id: Uuid) -> Result<Vec<server_inbound::ServerInboundResponse>> {
        use crate::database::entities::{inbound_template, certificate};
        
        let inbounds = ServerInbound::find()
            .filter(server_inbound::Column::ServerId.eq(server_id))
            .all(&self.db)
            .await?;

        let mut responses = Vec::new();
        for inbound in inbounds {
            let mut response = server_inbound::ServerInboundResponse::from(inbound.clone());
            
            // Load template information
            if let Ok(Some(template)) = InboundTemplate::find_by_id(inbound.template_id).one(&self.db).await {
                response.template_name = Some(template.name);
            }
            
            // Load certificate information
            if let Some(cert_id) = inbound.certificate_id {
                if let Ok(Some(certificate)) = Certificate::find_by_id(cert_id).one(&self.db).await {
                    response.certificate_name = Some(certificate.domain);
                }
            }
            
            responses.push(response);
        }

        Ok(responses)
    }

    pub async fn find_by_template_id(&self, template_id: Uuid) -> Result<Vec<server_inbound::Model>> {
        Ok(ServerInbound::find()
            .filter(server_inbound::Column::TemplateId.eq(template_id))
            .all(&self.db)
            .await?)
    }

    pub async fn find_by_tag(&self, tag: &str) -> Result<Option<server_inbound::Model>> {
        Ok(ServerInbound::find()
            .filter(server_inbound::Column::Tag.eq(tag))
            .one(&self.db)
            .await?)
    }

    pub async fn find_by_certificate_id(&self, certificate_id: Uuid) -> Result<Vec<server_inbound::Model>> {
        Ok(ServerInbound::find()
            .filter(server_inbound::Column::CertificateId.eq(certificate_id))
            .all(&self.db)
            .await?)
    }

    pub async fn find_active_by_server(&self, server_id: Uuid) -> Result<Vec<server_inbound::Model>> {
        Ok(ServerInbound::find()
            .filter(server_inbound::Column::ServerId.eq(server_id))
            .filter(server_inbound::Column::IsActive.eq(true))
            .all(&self.db)
            .await?)
    }

    pub async fn update(&self, id: Uuid, inbound_data: server_inbound::UpdateServerInboundDto) -> Result<server_inbound::Model> {
        let inbound = ServerInbound::find_by_id(id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Server inbound not found"))?;

        let updated_inbound = inbound.apply_update(inbound_data);

        Ok(updated_inbound.update(&self.db).await?)
    }

    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = ServerInbound::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }

    pub async fn activate(&self, id: Uuid) -> Result<server_inbound::Model> {
        let inbound = ServerInbound::find_by_id(id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Server inbound not found"))?;

        let mut inbound: server_inbound::ActiveModel = inbound.into();
        inbound.is_active = Set(true);
        inbound.updated_at = Set(chrono::Utc::now());

        Ok(inbound.update(&self.db).await?)
    }

    pub async fn deactivate(&self, id: Uuid) -> Result<server_inbound::Model> {
        let inbound = ServerInbound::find_by_id(id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Server inbound not found"))?;

        let mut inbound: server_inbound::ActiveModel = inbound.into();
        inbound.is_active = Set(false);
        inbound.updated_at = Set(chrono::Utc::now());

        Ok(inbound.update(&self.db).await?)
    }

    pub async fn find_by_user_id(&self, user_id: Uuid) -> Result<Vec<server_inbound::Model>> {
        // This would need a join with user_access table
        // For now, returning empty vec as placeholder
        // TODO: Implement proper join query
        Ok(vec![])
    }

    pub async fn count(&self) -> Result<u64> {
        let count = ServerInbound::find().count(&self.db).await?;
        Ok(count)
    }
}