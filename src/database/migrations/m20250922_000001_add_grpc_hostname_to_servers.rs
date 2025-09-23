use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .alter_table(
                Table::alter()
                    .table(Servers::Table)
                    .add_column(
                        ColumnDef::new(Servers::GrpcHostname)
                            .string()
                            .not_null()
                            .default(""),
                    )
                    .to_owned(),
            )
            .await?;

        // Update existing servers: set grpc_hostname to hostname value
        let db = manager.get_connection();
        
        // Use raw SQL to copy hostname to grpc_hostname for existing records
        // Handle both empty strings and default empty values
        db.execute_unprepared("UPDATE servers SET grpc_hostname = hostname WHERE grpc_hostname = '' OR grpc_hostname IS NULL")
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .alter_table(
                Table::alter()
                    .table(Servers::Table)
                    .drop_column(Servers::GrpcHostname)
                    .to_owned(),
            )
            .await
    }
}

#[derive(Iden)]
enum Servers {
    Table,
    GrpcHostname,
}