pub mod user;
pub mod certificate;
pub mod dns_provider;
pub mod inbound_template;
pub mod server;
pub mod server_inbound;
pub mod user_access;
pub mod inbound_users;
pub mod telegram_config;
pub mod user_request;

pub mod prelude {
    pub use super::user::Entity as User;
    pub use super::certificate::Entity as Certificate;
    pub use super::dns_provider::Entity as DnsProvider;
    pub use super::inbound_template::Entity as InboundTemplate;
    pub use super::server::Entity as Server;
    pub use super::server_inbound::Entity as ServerInbound;
    pub use super::user_access::Entity as UserAccess;
    pub use super::inbound_users::Entity as InboundUsers;
    pub use super::telegram_config::Entity as TelegramConfig;
    pub use super::user_request::Entity as UserRequest;
}