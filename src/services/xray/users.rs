use anyhow::{anyhow, Result};
use prost::Message;
use serde_json::Value;
use xray_core::{
    app::proxyman::command::{AddUserOperation, AlterInboundRequest, RemoveUserOperation},
    common::protocol::User,
    common::serial::TypedMessage,
    proxy::trojan::Account as TrojanAccount,
    proxy::vless::Account as VlessAccount,
    proxy::vmess::Account as VmessAccount,
    tonic::Request,
    Client,
};

pub struct UserClient<'a> {
    client: &'a Client,
}

impl<'a> UserClient<'a> {
    pub fn new(_endpoint: String, client: &'a Client) -> Self {
        Self { client }
    }

    /// Add user to inbound (simple version that works)
    pub async fn add_user(&self, inbound_tag: &str, user: &Value) -> Result<()> {
        let email = user["email"].as_str().unwrap_or("").to_string();
        let user_id = user["id"].as_str().unwrap_or("").to_string();
        let level = user["level"].as_u64().unwrap_or(0) as u32;
        let protocol = user["protocol"].as_str().unwrap_or("vless");

        if email.is_empty() || user_id.is_empty() {
            return Err(anyhow!("User email and id are required"));
        }

        // Create user account based on protocol
        let account_message = match protocol {
            "vless" => {
                let account = VlessAccount {
                    id: user_id.clone(),
                    encryption: "none".to_string(),
                    flow: "".to_string(), // Empty flow for basic VLESS
                };
                TypedMessage {
                    r#type: "xray.proxy.vless.Account".to_string(),
                    value: account.encode_to_vec(),
                }
            }
            "vmess" => {
                let account = VmessAccount {
                    id: user_id,
                    security_settings: None,
                    tests_enabled: "".to_string(),
                };
                TypedMessage {
                    r#type: "xray.proxy.vmess.Account".to_string(),
                    value: account.encode_to_vec(),
                }
            }
            "trojan" => {
                let account = TrojanAccount {
                    password: user_id, // For trojan, use password instead of UUID
                };
                TypedMessage {
                    r#type: "xray.proxy.trojan.Account".to_string(),
                    value: account.encode_to_vec(),
                }
            }
            _ => {
                return Err(anyhow!("Unsupported protocol for user: {}", protocol));
            }
        };

        // Create user protobuf message
        let user_proto = User {
            level: level,
            email: email.clone(),
            account: Some(account_message),
        };

        // Build the AddUserOperation
        let add_user_op = AddUserOperation {
            user: Some(user_proto),
        };

        let typed_message = TypedMessage {
            r#type: "xray.app.proxyman.command.AddUserOperation".to_string(),
            value: add_user_op.encode_to_vec(),
        };

        // Build the AlterInboundRequest
        let request = Request::new(AlterInboundRequest {
            tag: inbound_tag.to_string(),
            operation: Some(typed_message),
        });

        let mut handler_client = self.client.handler();
        match handler_client.alter_inbound(request).await {
            Ok(response) => {
                let _response_inner = response.into_inner();
                Ok(())
            }
            Err(e) => {
                tracing::error!(
                    "gRPC error adding user '{}' to inbound '{}': status={}, message={}",
                    email,
                    inbound_tag,
                    e.code(),
                    e.message()
                );
                Err(anyhow!(
                    "Failed to add user '{}' to inbound '{}': {}",
                    email,
                    inbound_tag,
                    e
                ))
            }
        }
    }

    /// Remove user from inbound
    pub async fn remove_user(&self, inbound_tag: &str, email: &str) -> Result<()> {
        // Build the RemoveUserOperation
        let remove_user_op = RemoveUserOperation {
            email: email.to_string(),
        };

        let typed_message = TypedMessage {
            r#type: "xray.app.proxyman.command.RemoveUserOperation".to_string(),
            value: remove_user_op.encode_to_vec(),
        };

        let request = Request::new(AlterInboundRequest {
            tag: inbound_tag.to_string(),
            operation: Some(typed_message),
        });

        let mut handler_client = self.client.handler();
        match handler_client.alter_inbound(request).await {
            Ok(_) => Ok(()),
            Err(e) => {
                tracing::error!(
                    "Failed to remove user '{}' from inbound '{}': {}",
                    email,
                    inbound_tag,
                    e
                );
                Err(anyhow!(
                    "Failed to remove user '{}' from inbound '{}': {}",
                    email,
                    inbound_tag,
                    e
                ))
            }
        }
    }
}
