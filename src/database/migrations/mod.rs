use sea_orm_migration::prelude::*;

mod m20241201_000001_create_users_table;
mod m20241201_000002_create_certificates_table;
mod m20241201_000003_create_inbound_templates_table;
mod m20241201_000004_create_servers_table;
mod m20241201_000005_create_server_inbounds_table;
mod m20241201_000006_create_user_access_table;
mod m20241201_000007_create_inbound_users_table;
mod m20250919_000001_update_inbound_users_schema;
mod m20250922_000001_add_grpc_hostname_to_servers;

pub struct Migrator;

#[async_trait::async_trait]
impl MigratorTrait for Migrator {
    fn migrations() -> Vec<Box<dyn MigrationTrait>> {
        vec![
            Box::new(m20241201_000001_create_users_table::Migration),
            Box::new(m20241201_000002_create_certificates_table::Migration),
            Box::new(m20241201_000003_create_inbound_templates_table::Migration),
            Box::new(m20241201_000004_create_servers_table::Migration),
            Box::new(m20241201_000005_create_server_inbounds_table::Migration),
            Box::new(m20241201_000006_create_user_access_table::Migration),
            Box::new(m20241201_000007_create_inbound_users_table::Migration),
            Box::new(m20250919_000001_update_inbound_users_schema::Migration),
            Box::new(m20250922_000001_add_grpc_hostname_to_servers::Migration),
        ]
    }
}