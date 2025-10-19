use anyhow::Result;
use sea_orm::{ActiveModelTrait, DatabaseConnection, EntityTrait, ColumnTrait, QueryFilter, Set};
use uuid::Uuid;

use crate::database::entities::inbound_users::{
    Entity, Model, ActiveModel, CreateInboundUserDto, UpdateInboundUserDto, Column
};
use crate::services::uri_generator::ClientConfigData;

pub struct InboundUsersRepository {
    db: DatabaseConnection,
}

impl InboundUsersRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    pub async fn find_all(&self) -> Result<Vec<Model>> {
        let users = Entity::find().all(&self.db).await?;
        Ok(users)
    }

    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<Model>> {
        let user = Entity::find_by_id(id).one(&self.db).await?;
        Ok(user)
    }

    /// Find all users for a specific inbound
    pub async fn find_by_inbound_id(&self, inbound_id: Uuid) -> Result<Vec<Model>> {
        let users = Entity::find()
            .filter(Column::ServerInboundId.eq(inbound_id))
            .all(&self.db)
            .await?;
        Ok(users)
    }

    /// Find active users for a specific inbound
    pub async fn find_active_by_inbound_id(&self, inbound_id: Uuid) -> Result<Vec<Model>> {
        let users = Entity::find()
            .filter(Column::ServerInboundId.eq(inbound_id))
            .filter(Column::IsActive.eq(true))
            .all(&self.db)
            .await?;
        Ok(users)
    }

    /// Find user by user_id and inbound (for uniqueness check - one user per inbound)
    pub async fn find_by_user_and_inbound(&self, user_id: Uuid, inbound_id: Uuid) -> Result<Option<Model>> {
        let user = Entity::find()
            .filter(Column::UserId.eq(user_id))
            .filter(Column::ServerInboundId.eq(inbound_id))
            .one(&self.db)
            .await?;
        Ok(user)
    }

    /// Find all inbound access for a specific user
    pub async fn find_by_user_id(&self, user_id: Uuid) -> Result<Vec<Model>> {
        let users = Entity::find()
            .filter(Column::UserId.eq(user_id))
            .all(&self.db)
            .await?;
        Ok(users)
    }

    pub async fn create(&self, dto: CreateInboundUserDto) -> Result<Model> {
        let active_model: ActiveModel = dto.into();
        let user = active_model.insert(&self.db).await?;
        Ok(user)
    }

    pub async fn update(&self, id: Uuid, dto: UpdateInboundUserDto) -> Result<Option<Model>> {
        let user = match self.find_by_id(id).await? {
            Some(user) => user,
            None => return Ok(None),
        };

        let updated_model = user.apply_update(dto);
        let updated_user = updated_model.update(&self.db).await?;
        Ok(Some(updated_user))
    }

    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = Entity::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }

    /// Enable user (set is_active = true)
    pub async fn enable(&self, id: Uuid) -> Result<Option<Model>> {
        let user = match self.find_by_id(id).await? {
            Some(user) => user,
            None => return Ok(None),
        };

        let mut active_model: ActiveModel = user.into();
        active_model.is_active = Set(true);
        active_model.updated_at = Set(chrono::Utc::now());
        
        let updated_user = active_model.update(&self.db).await?;
        Ok(Some(updated_user))
    }

    /// Disable user (set is_active = false)
    pub async fn disable(&self, id: Uuid) -> Result<Option<Model>> {
        let user = match self.find_by_id(id).await? {
            Some(user) => user,
            None => return Ok(None),
        };

        let mut active_model: ActiveModel = user.into();
        active_model.is_active = Set(false);
        active_model.updated_at = Set(chrono::Utc::now());
        
        let updated_user = active_model.update(&self.db).await?;
        Ok(Some(updated_user))
    }

    /// Remove all users for a specific inbound (when inbound is deleted)
    pub async fn remove_all_for_inbound(&self, inbound_id: Uuid) -> Result<u64> {
        let result = Entity::delete_many()
            .filter(Column::ServerInboundId.eq(inbound_id))
            .exec(&self.db)
            .await?;
        Ok(result.rows_affected)
    }

    /// Check if user already has access to this inbound
    pub async fn user_has_access_to_inbound(&self, user_id: Uuid, inbound_id: Uuid) -> Result<bool> {
        let exists = self.find_by_user_and_inbound(user_id, inbound_id).await?;
        Ok(exists.is_some())
    }

    /// Get complete client configuration data for URI generation
    pub async fn get_client_config_data(&self, user_id: Uuid, server_inbound_id: Uuid) -> Result<Option<ClientConfigData>> {
        use crate::database::entities::{
            user, server, server_inbound, inbound_template, certificate
        };
        
        // Get the inbound_user record first
        let inbound_user = Entity::find()
            .filter(Column::UserId.eq(user_id))
            .filter(Column::ServerInboundId.eq(server_inbound_id))
            .filter(Column::IsActive.eq(true))
            .one(&self.db)
            .await?;
            
        if let Some(inbound_user) = inbound_user {
            // Get user info
            let user_entity = user::Entity::find_by_id(inbound_user.user_id)
                .one(&self.db)
                .await?
                .ok_or_else(|| anyhow::anyhow!("User not found"))?;
                
            // Get server inbound info
            let server_inbound_entity = server_inbound::Entity::find_by_id(inbound_user.server_inbound_id)
                .one(&self.db)
                .await?
                .ok_or_else(|| anyhow::anyhow!("Server inbound not found"))?;
                
            // Get server info
            let server_entity = server::Entity::find_by_id(server_inbound_entity.server_id)
                .one(&self.db)
                .await?
                .ok_or_else(|| anyhow::anyhow!("Server not found"))?;
                
            // Get template info
            let template_entity = inbound_template::Entity::find_by_id(server_inbound_entity.template_id)
                .one(&self.db)
                .await?
                .ok_or_else(|| anyhow::anyhow!("Template not found"))?;
                
            // Get certificate info (optional)
            let certificate_domain = if let Some(cert_id) = server_inbound_entity.certificate_id {
                certificate::Entity::find_by_id(cert_id)
                    .one(&self.db)
                    .await?
                    .map(|cert| cert.domain)
            } else {
                None
            };
            
            let config = ClientConfigData {
                user_name: user_entity.name,
                xray_user_id: inbound_user.xray_user_id,
                password: inbound_user.password,
                level: inbound_user.level,
                hostname: server_entity.hostname,
                port: server_inbound_entity.port_override.unwrap_or(template_entity.default_port),
                protocol: template_entity.protocol,
                stream_settings: template_entity.stream_settings,
                base_settings: template_entity.base_settings,
                certificate_domain,
                requires_tls: template_entity.requires_tls,
                variable_values: server_inbound_entity.variable_values,
                server_name: server_entity.name,
                inbound_tag: server_inbound_entity.tag,
                template_name: template_entity.name,
            };
            
            Ok(Some(config))
        } else {
            Ok(None)
        }
    }

    /// Get all client configuration data for a user
    pub async fn get_all_client_configs_for_user(&self, user_id: Uuid) -> Result<Vec<ClientConfigData>> {
        // Get all active inbound users for this user
        let inbound_users = Entity::find()
            .filter(Column::UserId.eq(user_id))
            .filter(Column::IsActive.eq(true))
            .all(&self.db)
            .await?;
            
        let mut configs = Vec::new();
        
        for inbound_user in inbound_users {
            // Get the client config data for each inbound
            if let Ok(Some(config)) = self.get_client_config_data(user_id, inbound_user.server_inbound_id).await {
                configs.push(config);
            }
        }
        
        Ok(configs)
    }
}