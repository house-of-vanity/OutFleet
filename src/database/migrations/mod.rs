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
mod m20250923_000001_create_dns_providers_table;
mod m20250929_000001_create_telegram_config_table;
mod m20250929_000002_add_telegram_admin_to_users;
mod m20251018_000001_create_user_requests_table;
mod m20251018_000002_remove_unique_telegram_id;
mod m20251018_000003_add_language_to_user_requests;

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
            Box::new(m20250923_000001_create_dns_providers_table::Migration),
            Box::new(m20250929_000001_create_telegram_config_table::Migration),
            Box::new(m20250929_000002_add_telegram_admin_to_users::Migration),
            Box::new(m20251018_000001_create_user_requests_table::Migration),
            Box::new(m20251018_000002_remove_unique_telegram_id::Migration),
            Box::new(m20251018_000003_add_language_to_user_requests::Migration),
        ]
    }
}
