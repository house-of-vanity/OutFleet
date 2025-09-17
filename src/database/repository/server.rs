use sea_orm::*;
use crate::database::entities::{server, prelude::*};
use anyhow::Result;
use uuid::Uuid;

#[derive(Clone)]
pub struct ServerRepository {
    db: DatabaseConnection,
}

#[allow(dead_code)]
impl ServerRepository {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    pub async fn create(&self, server_data: server::CreateServerDto) -> Result<server::Model> {
        let server = server::ActiveModel::from(server_data);

        let result = Server::insert(server).exec(&self.db).await?;
        
        Server::find_by_id(result.last_insert_id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Failed to retrieve created server"))
    }

    pub async fn find_all(&self) -> Result<Vec<server::Model>> {
        Ok(Server::find().all(&self.db).await?)
    }

    pub async fn find_by_id(&self, id: Uuid) -> Result<Option<server::Model>> {
        Ok(Server::find_by_id(id).one(&self.db).await?)
    }

    pub async fn find_by_name(&self, name: &str) -> Result<Option<server::Model>> {
        Ok(Server::find()
            .filter(server::Column::Name.eq(name))
            .one(&self.db)
            .await?)
    }

    pub async fn find_by_hostname(&self, hostname: &str) -> Result<Option<server::Model>> {
        Ok(Server::find()
            .filter(server::Column::Hostname.eq(hostname))
            .one(&self.db)
            .await?)
    }

    pub async fn find_by_status(&self, status: &str) -> Result<Vec<server::Model>> {
        Ok(Server::find()
            .filter(server::Column::Status.eq(status))
            .all(&self.db)
            .await?)
    }

    pub async fn update(&self, id: Uuid, server_data: server::UpdateServerDto) -> Result<server::Model> {
        let server = Server::find_by_id(id)
            .one(&self.db)
            .await?
            .ok_or_else(|| anyhow::anyhow!("Server not found"))?;

        let updated_server = server.apply_update(server_data);

        Ok(updated_server.update(&self.db).await?)
    }

    pub async fn delete(&self, id: Uuid) -> Result<bool> {
        let result = Server::delete_by_id(id).exec(&self.db).await?;
        Ok(result.rows_affected > 0)
    }

    pub async fn get_grpc_endpoint(&self, id: Uuid) -> Result<String> {
        let server = self.find_by_id(id).await?
            .ok_or_else(|| anyhow::anyhow!("Server not found"))?;
        
        Ok(format!("{}:{}", server.hostname, server.grpc_port))
    }
}