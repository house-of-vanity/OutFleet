use sea_orm::*;
use crate::database::entities::{inbound_template, prelude::*};
use anyhow::Result;
use uuid::Uuid;

#[derive(Clone)]
pub struct InboundTemplateRepository {
    db: DatabaseConnection,
}

#[allow(dead_code)]
impl InboundTemplateRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    pub async fn create(&self, template_data: inbound_template::CreateInboundTemplateDto) -> Result<inbound_template::Model> {
        let template = inbound_template::ActiveModel::from(template_data);

        let result = InboundTemplate::insert(template).exec(&self.db).await?;
        
        InboundTemplate::find_by_id(result.last_insert_id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Failed to retrieve created template"))
    }

    pub async fn find_all(&self) -> Result<Vec<inbound_template::Model>> {
        Ok(InboundTemplate::find().all(&self.db).await?)
    }

    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<inbound_template::Model>> {
        Ok(InboundTemplate::find_by_id(id).one(&self.db).await?)
    }

    pub async fn find_by_name(&self, name: &str) -> Result<Option<inbound_template::Model>> {
        Ok(InboundTemplate::find()
            .filter(inbound_template::Column::Name.eq(name))
            .one(&self.db)
            .await?)
    }

    pub async fn find_by_protocol(&self, protocol: &str) -> Result<Vec<inbound_template::Model>> {
        Ok(InboundTemplate::find()
            .filter(inbound_template::Column::Protocol.eq(protocol))
            .all(&self.db)
            .await?)
    }

    pub async fn update(&self, id: Uuid, template_data: inbound_template::UpdateInboundTemplateDto) -> Result<inbound_template::Model> {
        let template = InboundTemplate::find_by_id(id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Template not found"))?;

        let updated_template = template.apply_update(template_data);

        Ok(updated_template.update(&self.db).await?)
    }

    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = InboundTemplate::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }
}