pub mod certificate;
pub mod dns_provider;
pub mod inbound_template;
pub mod inbound_users;
pub mod server;
pub mod server_inbound;
pub mod telegram_config;
pub mod user;
pub mod user_access;
pub mod user_request;

pub mod prelude {
    pub use super::certificate::Entity as Certificate;
    pub use super::inbound_template::Entity as InboundTemplate;
    pub use super::server::Entity as Server;
    pub use super::server_inbound::Entity as ServerInbound;
}
