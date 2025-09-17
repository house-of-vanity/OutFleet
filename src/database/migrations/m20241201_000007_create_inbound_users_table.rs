use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .create_table(
                Table::create()
                    .table(InboundUsers::Table)
                    .if_not_exists()
                    .col(
                        ColumnDef::new(InboundUsers::Id)
                            .uuid()
                            .not_null()
                            .primary_key(),
                    )
                    .col(
                        ColumnDef::new(InboundUsers::ServerInboundId)
                            .uuid()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundUsers::Username)
                            .string()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundUsers::Email)
                            .string()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundUsers::XrayUserId)
                            .string()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundUsers::Level)
                            .integer()
                            .not_null()
                            .default(0),
                    )
                    .col(
                        ColumnDef::new(InboundUsers::IsActive)
                            .boolean()
                            .not_null()
                            .default(true),
                    )
                    .col(
                        ColumnDef::new(InboundUsers::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundUsers::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .foreign_key(
                        ForeignKey::create()
                            .name("fk_inbound_users_server_inbound")
                            .from(InboundUsers::Table, InboundUsers::ServerInboundId)
                            .to(ServerInbounds::Table, ServerInbounds::Id)
                            .on_delete(ForeignKeyAction::Cascade),
                    )
                    .to_owned(),
            )
            .await?;

        // Create unique constraint: one user per inbound
        manager
            .create_index(
                Index::create()
                    .name("idx_inbound_users_unique_user_per_inbound")
                    .table(InboundUsers::Table)
                    .col(InboundUsers::ServerInboundId)
                    .col(InboundUsers::Username)
                    .unique()
                    .to_owned(),
            )
            .await?;

        // Create index on email for faster lookups
        manager
            .create_index(
                Index::create()
                    .name("idx_inbound_users_email")
                    .table(InboundUsers::Table)
                    .col(InboundUsers::Email)
                    .to_owned(),
            )
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .drop_table(Table::drop().table(InboundUsers::Table).to_owned())
            .await
    }
}

#[derive(DeriveIden)]
enum InboundUsers {
    Table,
    Id,
    ServerInboundId,
    Username,
    Email,
    XrayUserId,
    Level,
    IsActive,
    CreatedAt,
    UpdatedAt,
}

#[derive(DeriveIden)]
enum ServerInbounds {
    Table,
    Id,
}