use sea_orm::entity::prelude::*;
use sea_orm::{Set, ActiveModelTrait};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "server_inbounds")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,
    
    pub server_id: Uuid,
    
    pub template_id: Uuid,
    
    pub tag: String,
    
    pub port_override: Option<i32>,
    
    pub certificate_id: Option<Uuid>,
    
    pub variable_values: Value,
    
    pub is_active: bool,
    
    pub created_at: DateTimeUtc,
    
    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(
        belongs_to = "super::server::Entity",
        from = "Column::ServerId",
        to = "super::server::Column::Id"
    )]
    Server,
    #[sea_orm(
        belongs_to = "super::inbound_template::Entity",
        from = "Column::TemplateId",
        to = "super::inbound_template::Column::Id"
    )]
    Template,
    #[sea_orm(
        belongs_to = "super::certificate::Entity",
        from = "Column::CertificateId",
        to = "super::certificate::Column::Id"
    )]
    Certificate,
}

impl Related<super::server::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Server.def()
    }
}

impl Related<super::inbound_template::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Template.def()
    }
}

impl Related<super::certificate::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Certificate.def()
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
pub struct CreateServerInboundDto {
    pub template_id: Uuid,
    pub port: i32,
    pub certificate_id: Option<Uuid>,
    pub is_active: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateServerInboundDto {
    pub tag: Option<String>,
    pub port_override: Option<i32>,
    pub certificate_id: Option<Uuid>,
    pub variable_values: Option<serde_json::Map<String, Value>>,
    pub is_active: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerInboundResponse {
    pub id: Uuid,
    pub server_id: Uuid,
    pub template_id: Uuid,
    pub tag: String,
    pub port: i32,
    pub certificate_id: Option<Uuid>,
    pub variable_values: Value,
    pub is_active: bool,
    pub created_at: DateTimeUtc,
    pub updated_at: DateTimeUtc,
    // Populated by joins (simplified for now)
    pub template_name: Option<String>,
    pub certificate_name: Option<String>,
}

impl From<Model> for ServerInboundResponse {
    fn from(inbound: Model) -> Self {
        Self {
            id: inbound.id,
            server_id: inbound.server_id,
            template_id: inbound.template_id,
            tag: inbound.tag,
            port: inbound.port_override.unwrap_or(443), // Default port if not set
            certificate_id: inbound.certificate_id,
            variable_values: inbound.variable_values,
            is_active: inbound.is_active,
            created_at: inbound.created_at,
            updated_at: inbound.updated_at,
            template_name: None, // Will be filled by repository if needed
            certificate_name: None, // Will be filled by repository if needed
        }
    }
}

impl Model {
    pub fn apply_update(self, dto: UpdateServerInboundDto) -> ActiveModel {
        let mut active_model: ActiveModel = self.into();
        
        if let Some(tag) = dto.tag {
            active_model.tag = Set(tag);
        }
        if let Some(port_override) = dto.port_override {
            active_model.port_override = Set(Some(port_override));
        }
        if let Some(certificate_id) = dto.certificate_id {
            active_model.certificate_id = Set(Some(certificate_id));
        }
        if let Some(variable_values) = dto.variable_values {
            active_model.variable_values = Set(Value::Object(variable_values));
        }
        if let Some(is_active) = dto.is_active {
            active_model.is_active = Set(is_active);
        }
        
        active_model
    }

    #[allow(dead_code)]
    pub fn get_variable_values(&self) -> serde_json::Map<String, Value> {
        if let Value::Object(map) = &self.variable_values {
            map.clone()
        } else {
            serde_json::Map::new()
        }
    }

    #[allow(dead_code)]
    pub fn get_effective_port(&self, template_default_port: i32) -> i32 {
        self.port_override.unwrap_or(template_default_port)
    }
}

impl From<CreateServerInboundDto> for ActiveModel {
    fn from(dto: CreateServerInboundDto) -> Self {
        Self {
            template_id: Set(dto.template_id),
            tag: Set(format!("inbound-{}", Uuid::new_v4())), // Generate unique tag
            port_override: Set(Some(dto.port)),
            certificate_id: Set(dto.certificate_id),
            variable_values: Set(Value::Object(serde_json::Map::new())),
            is_active: Set(dto.is_active),
            ..Self::new()
        }
    }
}