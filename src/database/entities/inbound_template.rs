use sea_orm::entity::prelude::*;
use sea_orm::{ActiveModelTrait, Set};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "inbound_templates")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: Uuid,

    pub name: String,

    pub description: Option<String>,

    pub protocol: String,

    pub default_port: i32,

    pub base_settings: Value,

    pub stream_settings: Value,

    pub requires_tls: bool,

    pub requires_domain: bool,

    pub variables: Value,

    pub is_active: bool,

    pub created_at: DateTimeUtc,

    pub updated_at: DateTimeUtc,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(has_many = "super::server_inbound::Entity")]
    ServerInbounds,
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Protocol {
    Vless,
    Vmess,
    Trojan,
    Shadowsocks,
}

impl From<Protocol> for String {
    fn from(protocol: Protocol) -> Self {
        match protocol {
            Protocol::Vless => "vless".to_string(),
            Protocol::Vmess => "vmess".to_string(),
            Protocol::Trojan => "trojan".to_string(),
            Protocol::Shadowsocks => "shadowsocks".to_string(),
        }
    }
}

impl From<String> for Protocol {
    fn from(s: String) -> Self {
        match s.as_str() {
            "vless" => Protocol::Vless,
            "vmess" => Protocol::Vmess,
            "trojan" => Protocol::Trojan,
            "shadowsocks" => Protocol::Shadowsocks,
            _ => Protocol::Vless,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateVariable {
    pub key: String,
    pub var_type: VariableType,
    pub required: bool,
    pub default_value: Option<String>,
    pub description: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VariableType {
    String,
    Number,
    Path,
    Domain,
    Port,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateInboundTemplateDto {
    pub name: String,
    pub protocol: String,
    pub default_port: i32,
    pub requires_tls: bool,
    pub config_template: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateInboundTemplateDto {
    pub name: Option<String>,
    pub description: Option<String>,
    pub default_port: Option<i32>,
    pub base_settings: Option<Value>,
    pub stream_settings: Option<Value>,
    pub requires_tls: Option<bool>,
    pub requires_domain: Option<bool>,
    pub variables: Option<Vec<TemplateVariable>>,
    pub is_active: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InboundTemplateResponse {
    pub id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub protocol: String,
    pub default_port: i32,
    pub base_settings: Value,
    pub stream_settings: Value,
    pub requires_tls: bool,
    pub requires_domain: bool,
    pub variables: Vec<TemplateVariable>,
    pub is_active: bool,
    pub created_at: DateTimeUtc,
    pub updated_at: DateTimeUtc,
}

impl From<Model> for InboundTemplateResponse {
    fn from(template: Model) -> Self {
        let variables = template.get_variables();
        Self {
            id: template.id,
            name: template.name,
            description: template.description,
            protocol: template.protocol,
            default_port: template.default_port,
            base_settings: template.base_settings,
            stream_settings: template.stream_settings,
            requires_tls: template.requires_tls,
            requires_domain: template.requires_domain,
            variables,
            is_active: template.is_active,
            created_at: template.created_at,
            updated_at: template.updated_at,
        }
    }
}

impl From<CreateInboundTemplateDto> for ActiveModel {
    fn from(dto: CreateInboundTemplateDto) -> Self {
        // Parse config_template as JSON or use default
        let config_json: Value =
            serde_json::from_str(&dto.config_template).unwrap_or_else(|_| serde_json::json!({}));

        Self {
            name: Set(dto.name),
            description: Set(None),
            protocol: Set(dto.protocol),
            default_port: Set(dto.default_port),
            base_settings: Set(config_json.clone()),
            stream_settings: Set(serde_json::json!({})),
            requires_tls: Set(dto.requires_tls),
            requires_domain: Set(false),
            variables: Set(Value::Array(vec![])),
            is_active: Set(true),
            ..Self::new()
        }
    }
}

impl Model {
    pub fn get_variables(&self) -> Vec<TemplateVariable> {
        serde_json::from_value(self.variables.clone()).unwrap_or_default()
    }

    #[allow(dead_code)]
    pub fn apply_variables(
        &self,
        values: &serde_json::Map<String, Value>,
    ) -> Result<(Value, Value), String> {
        let base_settings = self.base_settings.clone();
        let stream_settings = self.stream_settings.clone();

        // Replace variables in JSON using simple string replacement
        let base_str = base_settings.to_string();
        let stream_str = stream_settings.to_string();

        let mut result_base = base_str;
        let mut result_stream = stream_str;

        for (key, value) in values {
            let placeholder = format!("${{{}}}", key);
            let replacement = match value {
                Value::String(s) => s.clone(),
                Value::Number(n) => n.to_string(),
                _ => value.to_string(),
            };
            result_base = result_base.replace(&placeholder, &replacement);
            result_stream = result_stream.replace(&placeholder, &replacement);
        }

        let final_base: Value = serde_json::from_str(&result_base)
            .map_err(|e| format!("Invalid base settings after variable substitution: {}", e))?;
        let final_stream: Value = serde_json::from_str(&result_stream)
            .map_err(|e| format!("Invalid stream settings after variable substitution: {}", e))?;

        Ok((final_base, final_stream))
    }

    pub fn apply_update(self, dto: UpdateInboundTemplateDto) -> ActiveModel {
        let mut active_model: ActiveModel = self.into();

        if let Some(name) = dto.name {
            active_model.name = Set(name);
        }
        if let Some(description) = dto.description {
            active_model.description = Set(Some(description));
        }
        if let Some(default_port) = dto.default_port {
            active_model.default_port = Set(default_port);
        }
        if let Some(base_settings) = dto.base_settings {
            active_model.base_settings = Set(base_settings);
        }
        if let Some(stream_settings) = dto.stream_settings {
            active_model.stream_settings = Set(stream_settings);
        }
        if let Some(requires_tls) = dto.requires_tls {
            active_model.requires_tls = Set(requires_tls);
        }
        if let Some(requires_domain) = dto.requires_domain {
            active_model.requires_domain = Set(requires_domain);
        }
        if let Some(variables) = dto.variables {
            active_model.variables =
                Set(serde_json::to_value(variables).unwrap_or(Value::Array(vec![])));
        }
        if let Some(is_active) = dto.is_active {
            active_model.is_active = Set(is_active);
        }

        active_model
    }
}
