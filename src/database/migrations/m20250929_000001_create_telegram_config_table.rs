use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .create_table(
                Table::create()
                    .table(TelegramConfig::Table)
                    .if_not_exists()
                    .col(ColumnDef::new(TelegramConfig::Id)
                        .uuid()
                        .not_null()
                        .primary_key())
                    .col(ColumnDef::new(TelegramConfig::BotToken)
                        .string()
                        .not_null())
                    .col(ColumnDef::new(TelegramConfig::IsActive)
                        .boolean()
                        .not_null()
                        .default(false))
                    .col(ColumnDef::new(TelegramConfig::CreatedAt)
                        .timestamp_with_time_zone()
                        .not_null())
                    .col(ColumnDef::new(TelegramConfig::UpdatedAt)
                        .timestamp_with_time_zone()
                        .not_null())
                    .to_owned(),
            )
            .await
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .drop_table(Table::drop().table(TelegramConfig::Table).to_owned())
            .await
    }
}

#[derive(Iden)]
pub enum TelegramConfig {
    Table,
    Id,
    BotToken,
    IsActive,
    CreatedAt,
    UpdatedAt,
}