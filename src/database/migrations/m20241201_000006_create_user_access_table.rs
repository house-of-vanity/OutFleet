use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .create_table(
                Table::create()
                    .table(UserAccess::Table)
                    .if_not_exists()
                    .col(
                        ColumnDef::new(UserAccess::Id)
                            .uuid()
                            .not_null()
                            .primary_key(),
                    )
                    .col(ColumnDef::new(UserAccess::UserId).uuid().not_null())
                    .col(ColumnDef::new(UserAccess::ServerId).uuid().not_null())
                    .col(
                        ColumnDef::new(UserAccess::ServerInboundId)
                            .uuid()
                            .not_null(),
                    )
                    .col(ColumnDef::new(UserAccess::XrayUserId).string().not_null())
                    .col(ColumnDef::new(UserAccess::XrayEmail).string().not_null())
                    .col(ColumnDef::new(UserAccess::Level).integer().not_null())
                    .col(ColumnDef::new(UserAccess::IsActive).boolean().not_null())
                    .col(
                        ColumnDef::new(UserAccess::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(UserAccess::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .foreign_key(
                        ForeignKey::create()
                            .name("fk_user_access_user_id")
                            .from(UserAccess::Table, UserAccess::UserId)
                            .to(Users::Table, Users::Id)
                            .on_delete(ForeignKeyAction::Cascade),
                    )
                    .foreign_key(
                        ForeignKey::create()
                            .name("fk_user_access_server_id")
                            .from(UserAccess::Table, UserAccess::ServerId)
                            .to(Servers::Table, Servers::Id)
                            .on_delete(ForeignKeyAction::Cascade),
                    )
                    .foreign_key(
                        ForeignKey::create()
                            .name("fk_user_access_server_inbound_id")
                            .from(UserAccess::Table, UserAccess::ServerInboundId)
                            .to(ServerInbounds::Table, ServerInbounds::Id)
                            .on_delete(ForeignKeyAction::Cascade),
                    )
                    .to_owned(),
            )
            .await?;

        // Create indexes separately
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_user_access_server_inbound")
                    .table(UserAccess::Table)
                    .col(UserAccess::ServerId)
                    .col(UserAccess::ServerInboundId)
                    .to_owned(),
            )
            .await?;

        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_user_access_user_server")
                    .table(UserAccess::Table)
                    .col(UserAccess::UserId)
                    .col(UserAccess::ServerId)
                    .to_owned(),
            )
            .await?;

        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_user_access_xray_email")
                    .table(UserAccess::Table)
                    .col(UserAccess::XrayEmail)
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
                    .name("idx_user_access_xray_email")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_index(
                Index::drop()
                    .if_exists()
                    .name("idx_user_access_user_server")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_index(
                Index::drop()
                    .if_exists()
                    .name("idx_user_access_server_inbound")
                    .to_owned(),
            )
            .await?;

        // Drop table
        manager
            .drop_table(Table::drop().table(UserAccess::Table).to_owned())
            .await
    }
}

#[derive(DeriveIden)]
enum UserAccess {
    Table,
    Id,
    UserId,
    ServerId,
    ServerInboundId,
    XrayUserId,
    XrayEmail,
    Level,
    IsActive,
    CreatedAt,
    UpdatedAt,
}

#[derive(DeriveIden)]
enum Users {
    Table,
    Id,
}

#[derive(DeriveIden)]
enum Servers {
    Table,
    Id,
}

#[derive(DeriveIden)]
enum ServerInbounds {
    Table,
    Id,
}
