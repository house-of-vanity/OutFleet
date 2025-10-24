use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Create user_requests table
        manager
            .create_table(
                Table::create()
                    .table(UserRequests::Table)
                    .if_not_exists()
                    .col(
                        ColumnDef::new(UserRequests::Id)
                            .uuid()
                            .not_null()
                            .primary_key()
                            .default(Expr::cust("gen_random_uuid()")),
                    )
                    .col(
                        ColumnDef::new(UserRequests::UserId).uuid().null(), // Can be null if user doesn't exist yet
                    )
                    .col(
                        ColumnDef::new(UserRequests::TelegramId)
                            .big_integer()
                            .not_null()
                            .unique_key(),
                    )
                    .col(
                        ColumnDef::new(UserRequests::TelegramUsername)
                            .string()
                            .null(),
                    )
                    .col(
                        ColumnDef::new(UserRequests::TelegramFirstName)
                            .string()
                            .null(),
                    )
                    .col(
                        ColumnDef::new(UserRequests::TelegramLastName)
                            .string()
                            .null(),
                    )
                    .col(
                        ColumnDef::new(UserRequests::Status)
                            .string()
                            .not_null()
                            .default("pending"), // pending, approved, declined
                    )
                    .col(ColumnDef::new(UserRequests::RequestMessage).text().null())
                    .col(ColumnDef::new(UserRequests::ResponseMessage).text().null())
                    .col(
                        ColumnDef::new(UserRequests::ProcessedByUserId)
                            .uuid()
                            .null(),
                    )
                    .col(
                        ColumnDef::new(UserRequests::ProcessedAt)
                            .timestamp_with_time_zone()
                            .null(),
                    )
                    .col(
                        ColumnDef::new(UserRequests::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null()
                            .default(Expr::current_timestamp()),
                    )
                    .col(
                        ColumnDef::new(UserRequests::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null()
                            .default(Expr::current_timestamp()),
                    )
                    .foreign_key(
                        ForeignKey::create()
                            .name("fk_user_requests_user")
                            .from(UserRequests::Table, UserRequests::UserId)
                            .to(Users::Table, Users::Id)
                            .on_delete(ForeignKeyAction::SetNull)
                            .on_update(ForeignKeyAction::Cascade),
                    )
                    .foreign_key(
                        ForeignKey::create()
                            .name("fk_user_requests_processed_by")
                            .from(UserRequests::Table, UserRequests::ProcessedByUserId)
                            .to(Users::Table, Users::Id)
                            .on_delete(ForeignKeyAction::SetNull)
                            .on_update(ForeignKeyAction::Cascade),
                    )
                    .to_owned(),
            )
            .await?;

        // Create index on telegram_id for faster lookups
        manager
            .create_index(
                Index::create()
                    .name("idx_user_requests_telegram_id")
                    .table(UserRequests::Table)
                    .col(UserRequests::TelegramId)
                    .to_owned(),
            )
            .await?;

        // Create index on status for filtering
        manager
            .create_index(
                Index::create()
                    .name("idx_user_requests_status")
                    .table(UserRequests::Table)
                    .col(UserRequests::Status)
                    .to_owned(),
            )
            .await?;

        // Create trigger to update updated_at timestamp
        manager
            .get_connection()
            .execute_unprepared(
                r#"
                CREATE OR REPLACE FUNCTION update_user_requests_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER user_requests_updated_at
                BEFORE UPDATE ON user_requests
                FOR EACH ROW
                EXECUTE FUNCTION update_user_requests_updated_at();
                "#,
            )
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Drop trigger and function
        manager
            .get_connection()
            .execute_unprepared(
                r#"
                DROP TRIGGER IF EXISTS user_requests_updated_at ON user_requests;
                DROP FUNCTION IF EXISTS update_user_requests_updated_at();
                "#,
            )
            .await?;

        // Drop table
        manager
            .drop_table(Table::drop().table(UserRequests::Table).to_owned())
            .await
    }
}

#[derive(Iden)]
enum UserRequests {
    Table,
    Id,
    UserId,
    TelegramId,
    TelegramUsername,
    TelegramFirstName,
    TelegramLastName,
    Status,
    RequestMessage,
    ResponseMessage,
    ProcessedByUserId,
    ProcessedAt,
    CreatedAt,
    UpdatedAt,
}

#[derive(Iden)]
enum Users {
    Table,
    Id,
}
