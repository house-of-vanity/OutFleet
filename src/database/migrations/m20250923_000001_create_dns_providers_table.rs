use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .create_table(
                Table::create()
                    .table(DnsProviders::Table)
                    .if_not_exists()
                    .col(
                        ColumnDef::new(DnsProviders::Id)
                            .uuid()
                            .not_null()
                            .primary_key(),
                    )
                    .col(
                        ColumnDef::new(DnsProviders::Name)
                            .string_len(255)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(DnsProviders::ProviderType)
                            .string_len(50)
                            .not_null(),
                    )
                    .col(ColumnDef::new(DnsProviders::ApiToken).text().not_null())
                    .col(
                        ColumnDef::new(DnsProviders::IsActive)
                            .boolean()
                            .default(true)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(DnsProviders::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(DnsProviders::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .to_owned(),
            )
            .await?;

        // Index on name for faster lookups
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_dns_providers_name")
                    .table(DnsProviders::Table)
                    .col(DnsProviders::Name)
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
                    .name("idx_dns_providers_name")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_table(Table::drop().table(DnsProviders::Table).to_owned())
            .await
    }
}

#[derive(DeriveIden)]
enum DnsProviders {
    Table,
    Id,
    Name,
    ProviderType,
    ApiToken,
    IsActive,
    CreatedAt,
    UpdatedAt,
}
