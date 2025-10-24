use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Add language column to user_requests table
        manager
            .alter_table(
                Table::alter()
                    .table(UserRequests::Table)
                    .add_column(
                        ColumnDef::new(UserRequests::Language)
                            .string()
                            .default("en"), // Default to English
                    )
                    .to_owned(),
            )
            .await
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Remove language column from user_requests table
        manager
            .alter_table(
                Table::alter()
                    .table(UserRequests::Table)
                    .drop_column(UserRequests::Language)
                    .to_owned(),
            )
            .await
    }
}

#[derive(Iden)]
enum UserRequests {
    Table,
    Language,
}
