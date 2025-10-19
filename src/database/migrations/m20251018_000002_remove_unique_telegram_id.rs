use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Drop the unique constraint on telegram_id
        // This allows users to have multiple requests (e.g., if one was declined)
        manager
            .get_connection()
            .execute_unprepared(
                r#"
                ALTER TABLE user_requests 
                DROP CONSTRAINT IF EXISTS user_requests_telegram_id_key;
                "#,
            )
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        // Re-add the unique constraint
        manager
            .get_connection()
            .execute_unprepared(
                r#"
                ALTER TABLE user_requests 
                ADD CONSTRAINT user_requests_telegram_id_key UNIQUE (telegram_id);
                "#,
            )
            .await?;

        Ok(())
    }
}