use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .create_table(
                Table::create()
                    .table(InboundTemplates::Table)
                    .if_not_exists()
                    .col(
                        ColumnDef::new(InboundTemplates::Id)
                            .uuid()
                            .not_null()
                            .primary_key(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::Name)
                            .string_len(255)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::Description)
                            .text()
                            .null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::Protocol)
                            .string_len(50)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::DefaultPort)
                            .integer()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::BaseSettings)
                            .json()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::StreamSettings)
                            .json()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::RequiresTls)
                            .boolean()
                            .default(false)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::RequiresDomain)
                            .boolean()
                            .default(false)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::Variables)
                            .json()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::IsActive)
                            .boolean()
                            .default(true)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(InboundTemplates::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .to_owned(),
            )
            .await?;

        // Index on name for searches
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_inbound_templates_name")
                    .table(InboundTemplates::Table)
                    .col(InboundTemplates::Name)
                    .to_owned(),
            )
            .await?;

        // Index on protocol
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_inbound_templates_protocol")
                    .table(InboundTemplates::Table)
                    .col(InboundTemplates::Protocol)
                    .to_owned(),
            )
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .drop_index(
                Index::drop()
                    .if_exists()
                    .name("idx_inbound_templates_protocol")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_index(
                Index::drop()
                    .if_exists()
                    .name("idx_inbound_templates_name")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_table(Table::drop().table(InboundTemplates::Table).to_owned())
            .await
    }
}

#[derive(DeriveIden)]
enum InboundTemplates {
    Table,
    Id,
    Name,
    Description,
    Protocol,
    DefaultPort,
    BaseSettings,
    StreamSettings,
    RequiresTls,
    RequiresDomain,
    Variables,
    IsActive,
    CreatedAt,
    UpdatedAt,
}