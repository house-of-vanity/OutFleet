use sea_orm_migration::prelude::*;

#[derive(DeriveMigrationName)]
pub struct Migration;

#[async_trait::async_trait]
impl MigrationTrait for Migration {
    async fn up(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .create_table(
                Table::create()
                    .table(ServerInbounds::Table)
                    .if_not_exists()
                    .col(
                        ColumnDef::new(ServerInbounds::Id)
                            .uuid()
                            .not_null()
                            .primary_key(),
                    )
                    .col(ColumnDef::new(ServerInbounds::ServerId).uuid().not_null())
                    .col(ColumnDef::new(ServerInbounds::TemplateId).uuid().not_null())
                    .col(
                        ColumnDef::new(ServerInbounds::Tag)
                            .string_len(255)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(ServerInbounds::PortOverride)
                            .integer()
                            .null(),
                    )
                    .col(ColumnDef::new(ServerInbounds::CertificateId).uuid().null())
                    .col(
                        ColumnDef::new(ServerInbounds::VariableValues)
                            .json()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(ServerInbounds::IsActive)
                            .boolean()
                            .default(true)
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(ServerInbounds::CreatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .col(
                        ColumnDef::new(ServerInbounds::UpdatedAt)
                            .timestamp_with_time_zone()
                            .not_null(),
                    )
                    .to_owned(),
            )
            .await?;

        // Foreign keys
        manager
            .create_foreign_key(
                ForeignKey::create()
                    .name("fk_server_inbounds_server")
                    .from(ServerInbounds::Table, ServerInbounds::ServerId)
                    .to(Servers::Table, Servers::Id)
                    .on_delete(ForeignKeyAction::Cascade)
                    .to_owned(),
            )
            .await?;

        manager
            .create_foreign_key(
                ForeignKey::create()
                    .name("fk_server_inbounds_template")
                    .from(ServerInbounds::Table, ServerInbounds::TemplateId)
                    .to(InboundTemplates::Table, InboundTemplates::Id)
                    .on_delete(ForeignKeyAction::Restrict)
                    .to_owned(),
            )
            .await?;

        manager
            .create_foreign_key(
                ForeignKey::create()
                    .name("fk_server_inbounds_certificate")
                    .from(ServerInbounds::Table, ServerInbounds::CertificateId)
                    .to(Certificates::Table, Certificates::Id)
                    .on_delete(ForeignKeyAction::SetNull)
                    .to_owned(),
            )
            .await?;

        // Unique constraint on server_id + tag
        manager
            .create_index(
                Index::create()
                    .if_not_exists()
                    .name("idx_server_inbounds_server_tag")
                    .table(ServerInbounds::Table)
                    .col(ServerInbounds::ServerId)
                    .col(ServerInbounds::Tag)
                    .unique()
                    .to_owned(),
            )
            .await?;

        Ok(())
    }

    async fn down(&self, manager: &SchemaManager) -> Result<(), DbErr> {
        manager
            .drop_foreign_key(
                ForeignKey::drop()
                    .name("fk_server_inbounds_certificate")
                    .table(ServerInbounds::Table)
                    .to_owned(),
            )
            .await?;

        manager
            .drop_foreign_key(
                ForeignKey::drop()
                    .name("fk_server_inbounds_template")
                    .table(ServerInbounds::Table)
                    .to_owned(),
            )
            .await?;

        manager
            .drop_foreign_key(
                ForeignKey::drop()
                    .name("fk_server_inbounds_server")
                    .table(ServerInbounds::Table)
                    .to_owned(),
            )
            .await?;

        manager
            .drop_index(
                Index::drop()
                    .if_exists()
                    .name("idx_server_inbounds_server_tag")
                    .to_owned(),
            )
            .await?;

        manager
            .drop_table(Table::drop().table(ServerInbounds::Table).to_owned())
            .await
    }
}

#[derive(DeriveIden)]
enum ServerInbounds {
    Table,
    Id,
    ServerId,
    TemplateId,
    Tag,
    PortOverride,
    CertificateId,
    VariableValues,
    IsActive,
    CreatedAt,
    UpdatedAt,
}

#[derive(DeriveIden)]
enum Servers {
    Table,
    Id,
}

#[derive(DeriveIden)]
enum InboundTemplates {
    Table,
    Id,
}

#[derive(DeriveIden)]
enum Certificates {
    Table,
    Id,
}
