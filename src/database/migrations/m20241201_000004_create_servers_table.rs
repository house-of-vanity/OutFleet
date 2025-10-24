use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .create_table(
                Table::create()
                    .table(Servers::Table)
                    .if_not_exists()
                    .col(ColumnDef::new(Servers::Id).uuid().not_null().primary_key())
                    .col(ColumnDef::new(Servers::Name).string_len(255).not_null())
                    .col(ColumnDef::new(Servers::Hostname).string_len(255).not_null())
                    .col(
                        ColumnDef::new(Servers::GrpcPort)
                            .integer()
                            .default(2053)
                            .not_null(),
                    )
                    .col(ColumnDef::new(Servers::ApiCredentials).text().null())
                    .col(
                        ColumnDef::new(Servers::Status)
                            .string_len(50)
                            .default("unknown")
                            .not_null(),
                    )
                    .col(ColumnDef::new(Servers::DefaultCertificateId).uuid().null())
                    .col(
                        ColumnDef::new(Servers::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(Servers::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .to_owned(),
            )
            .await?;

        // Foreign key to certificates
        manager
            .create_foreign_key(
                ForeignKey::create()
                    .name("fk_servers_default_certificate")
                    .from(Servers::Table, Servers::DefaultCertificateId)
                    .to(Certificates::Table, Certificates::Id)
                    .on_delete(ForeignKeyAction::SetNull)
                    .to_owned(),
            )
            .await?;

        // Index on hostname
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_servers_hostname")
                    .table(Servers::Table)
                    .col(Servers::Hostname)
                    .to_owned(),
            )
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .drop_foreign_key(
                ForeignKey::drop()
                    .name("fk_servers_default_certificate")
                    .table(Servers::Table)
                    .to_owned(),
            )
            .await?;

        manager
            .drop_index(
                Index::drop()
                    .if_exists()
                    .name("idx_servers_hostname")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_table(Table::drop().table(Servers::Table).to_owned())
            .await
    }
}

#[derive(DeriveIden)]
enum Servers {
    Table,
    Id,
    Name,
    Hostname,
    GrpcPort,
    ApiCredentials,
    Status,
    DefaultCertificateId,
    CreatedAt,
    UpdatedAt,
}

#[derive(DeriveIden)]
enum Certificates {
    Table,
    Id,
}
