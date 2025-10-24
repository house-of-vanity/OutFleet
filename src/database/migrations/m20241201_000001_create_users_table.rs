use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Create users table
        manager
            .create_table(
                Table::create()
                    .table(Users::Table)
                    .if_not_exists()
                    .col(ColumnDef::new(Users::Id).uuid().not_null().primary_key())
                    .col(ColumnDef::new(Users::Name).string_len(255).not_null())
                    .col(ColumnDef::new(Users::Comment).text().null())
                    .col(ColumnDef::new(Users::TelegramId).big_integer().null())
                    .col(
                        ColumnDef::new(Users::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(Users::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .to_owned(),
            )
            .await?;

        // Create index on name for faster searches
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_users_name")
                    .table(Users::Table)
                    .col(Users::Name)
                    .to_owned(),
            )
            .await?;

        // Create unique index on telegram_id (if not null)
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_users_telegram_id")
                    .table(Users::Table)
                    .col(Users::TelegramId)
                    .unique()
                    .to_owned(),
            )
            .await?;

        // Create index on created_at for sorting
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_users_created_at")
                    .table(Users::Table)
                    .col(Users::CreatedAt)
                    .to_owned(),
            )
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Drop indexes first
        manager
            .drop_index(
                Index::drop()
                    .if_exists()
                    .name("idx_users_created_at")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_index(
                Index::drop()
                    .if_exists()
                    .name("idx_users_telegram_id")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_index(Index::drop().if_exists().name("idx_users_name").to_owned())
            .await?;

        // Drop table
        manager
            .drop_table(Table::drop().table(Users::Table).to_owned())
            .await
    }
}

#[derive(DeriveIden)]
enum Users {
    Table,
    Id,
    Name,
    Comment,
    TelegramId,
    CreatedAt,
    UpdatedAt,
}
