pub mod user;
pub mod certificate;
pub mod inbound_template;
pub mod server;
pub mod server_inbound;
pub mod user_access;
pub mod inbound_users;

pub mod prelude {
    pub use super::certificate::Entity as Certificate;
    pub use super::inbound_template::Entity as InboundTemplate;
    pub use super::server::Entity as Server;
    pub use super::server_inbound::Entity as ServerInbound;
    pub use super::user_access::Entity as UserAccess;
    pub use super::inbound_users::Entity as InboundUsers;
}