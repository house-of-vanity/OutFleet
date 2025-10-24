use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .create_table(
                Table::create()
                    .table(Certificates::Table)
                    .if_not_exists()
                    .col(
                        ColumnDef::new(Certificates::Id)
                            .uuid()
                            .not_null()
                            .primary_key(),
                    )
                    .col(
                        ColumnDef::new(Certificates::Name)
                            .string_len(255)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(Certificates::CertType)
                            .string_len(50)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(Certificates::Domain)
                            .string_len(255)
                            .not_null(),
                    )
                    .col(ColumnDef::new(Certificates::CertData).blob().not_null())
                    .col(ColumnDef::new(Certificates::KeyData).blob().not_null())
                    .col(ColumnDef::new(Certificates::ChainData).blob().null())
                    .col(
                        ColumnDef::new(Certificates::ExpiresAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(Certificates::AutoRenew)
                            .boolean()
                            .default(false)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(Certificates::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(Certificates::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .to_owned(),
            )
            .await?;

        // Index on domain for faster lookups
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_certificates_domain")
                    .table(Certificates::Table)
                    .col(Certificates::Domain)
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
                    .name("idx_certificates_domain")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_table(Table::drop().table(Certificates::Table).to_owned())
            .await
    }
}

#[derive(DeriveIden)]
enum Certificates {
    Table,
    Id,
    Name,
    CertType,
    Domain,
    CertData,
    KeyData,
    ChainData,
    ExpiresAt,
    AutoRenew,
    CreatedAt,
    UpdatedAt,
}
