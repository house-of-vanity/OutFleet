use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Drop existing indexes that reference columns we're removing
        manager
            .drop_index(
                Index::drop()
                    .name("idx_inbound_users_unique_user_per_inbound")
                    .table(InboundUsers::Table)
                    .to_owned(),
            )
            .await
            .ok(); // Ignore error if index doesn't exist

        manager
            .drop_index(
                Index::drop()
                    .name("idx_inbound_users_email")
                    .table(InboundUsers::Table)
                    .to_owned(),
            )
            .await
            .ok(); // Ignore error if index doesn't exist

        // Add user_id column
        manager
            .alter_table(
                Table::alter()
                    .table(InboundUsers::Table)
                    .add_column(
                        ColumnDef::new(InboundUsers::UserId)
                            .uuid()
                            .not_null()
                            .default(Expr::val("00000000-0000-0000-0000-000000000000"))
                    )
                    .to_owned(),
            )
            .await?;

        // Add password column  
        manager
            .alter_table(
                Table::alter()
                    .table(InboundUsers::Table)
                    .add_column(
                        ColumnDef::new(InboundUsers::Password)
                            .string()
                            .null()
                    )
                    .to_owned(),
            )
            .await?;

        // Drop old columns (username and email)
        manager
            .alter_table(
                Table::alter()
                    .table(InboundUsers::Table)
                    .drop_column(InboundUsers::Username)
                    .to_owned(),
            )
            .await?;

        manager
            .alter_table(
                Table::alter()
                    .table(InboundUsers::Table)
                    .drop_column(InboundUsers::Email)
                    .to_owned(),
            )
            .await?;

        // Add foreign key to users table
        manager
            .create_foreign_key(
                ForeignKey::create()
                    .name("fk_inbound_users_user")
                    .from(InboundUsers::Table, InboundUsers::UserId)
                    .to(Users::Table, Users::Id)
                    .on_delete(ForeignKeyAction::Cascade)
                    .to_owned()
            )
            .await?;

        // Create new unique constraint: one user per inbound
        manager
            .create_index(
                Index::create()
                    .name("idx_inbound_users_unique_user_per_inbound")
                    .table(InboundUsers::Table)
                    .col(InboundUsers::UserId)
                    .col(InboundUsers::ServerInboundId)
                    .unique()
                    .to_owned(),
            )
            .await?;

        // Create index on user_id for faster lookups
        manager
            .create_index(
                Index::create()
                    .name("idx_inbound_users_user_id")
                    .table(InboundUsers::Table)
                    .col(InboundUsers::UserId)
                    .to_owned(),
            )
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Drop new indexes
        manager
            .drop_index(
                Index::drop()
                    .name("idx_inbound_users_unique_user_per_inbound")
                    .table(InboundUsers::Table)
                    .to_owned(),
            )
            .await?;

        manager
            .drop_index(
                Index::drop()
                    .name("idx_inbound_users_user_id")
                    .table(InboundUsers::Table)
                    .to_owned(),
            )
            .await?;

        // Drop foreign key
        manager
            .drop_foreign_key(
                ForeignKey::drop()
                    .name("fk_inbound_users_user")
                    .table(InboundUsers::Table)
                    .to_owned(),
            )
            .await?;

        // Add back old columns
        manager
            .alter_table(
                Table::alter()
                    .table(InboundUsers::Table)
                    .add_column(
                        ColumnDef::new(InboundUsers::Username)
                            .string()
                            .not_null()
                            .default("")
                    )
                    .to_owned(),
            )
            .await?;

        manager
            .alter_table(
                Table::alter()
                    .table(InboundUsers::Table)
                    .add_column(
                        ColumnDef::new(InboundUsers::Email)
                            .string()
                            .not_null()
                            .default("")
                    )
                    .to_owned(),
            )
            .await?;

        // Drop new columns
        manager
            .alter_table(
                Table::alter()
                    .table(InboundUsers::Table)
                    .drop_column(InboundUsers::UserId)
                    .to_owned(),
            )
            .await?;

        manager
            .alter_table(
                Table::alter()
                    .table(InboundUsers::Table)
                    .drop_column(InboundUsers::Password)
                    .to_owned(),
            )
            .await?;

        // Recreate old indexes
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
}

#[derive(DeriveIden)]
enum InboundUsers {
    Table,
    Id,
    UserId,
    ServerInboundId,
    Username,
    Email,
    XrayUserId,
    Password,
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