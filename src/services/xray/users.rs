use anyhow::{Result, anyhow};
use serde_json::Value;
use xray_core::{
    tonic::Request,
    app::proxyman::command::{AlterInboundRequest, AddUserOperation, RemoveUserOperation},
    common::serial::TypedMessage,
    common::protocol::User,
    proxy::vless::Account as VlessAccount,
    proxy::vmess::Account as VmessAccount,
    proxy::trojan::Account as TrojanAccount,
    Client,
};
use prost::Message;

pub struct UserClient<'a> {
    endpoint: String,
    client: &'a Client,
}

impl<'a> UserClient<'a> {
    pub fn new(endpoint: String, client: &'a Client) -> Self {
        Self { endpoint, client }
    }

    /// Add user to inbound (simple version that works)
    pub async fn add_user(&self, inbound_tag: &str, user: &Value) -> Result<()> {
        tracing::info!("Adding user to inbound '{}' on Xray server at {}", inbound_tag, self.endpoint);
        tracing::debug!("User config: {}", serde_json::to_string_pretty(user)?);
        
        let email = user["email"].as_str().unwrap_or("").to_string();
        let user_id = user["id"].as_str().unwrap_or("").to_string();
        let level = user["level"].as_u64().unwrap_or(0) as u32;
        let protocol = user["protocol"].as_str().unwrap_or("vless");
        
        tracing::info!("Parsed user data: email={}, id={}, level={}, protocol={}", email, user_id, level, protocol);
        
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
            },
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
            },
            "trojan" => {
                let account = TrojanAccount {
                    password: user_id, // For trojan, use password instead of UUID
                };
                TypedMessage {
                    r#type: "xray.proxy.trojan.Account".to_string(),
                    value: account.encode_to_vec(),
                }
            },
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
        
        tracing::info!("Sending AlterInboundRequest to add user '{}' to inbound '{}'", email, inbound_tag);
        
        let mut handler_client = self.client.handler();
        match handler_client.alter_inbound(request).await {
            Ok(response) => {
                let _response_inner = response.into_inner();
                tracing::info!("Successfully added user '{}' to inbound '{}'", email, inbound_tag);
                Ok(())
            }
            Err(e) => {
                tracing::error!("gRPC error adding user '{}' to inbound '{}': status={}, message={}", 
                    email, inbound_tag, e.code(), e.message());
                Err(anyhow!("Failed to add user '{}' to inbound '{}': {}", email, inbound_tag, e))
            }
        }
    }

    /// Remove user from inbound
    pub async fn remove_user(&self, inbound_tag: &str, email: &str) -> Result<()> {
        tracing::info!("Removing user '{}' from inbound '{}' on Xray server at {}", email, inbound_tag, self.endpoint);
        
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
            Ok(_) => {
                tracing::info!("Successfully removed user '{}' from inbound '{}'", email, inbound_tag);
                Ok(())
            }
            Err(e) => {
                tracing::error!("Failed to remove user '{}' from inbound '{}': {}", email, inbound_tag, e);
                Err(anyhow!("Failed to remove user '{}' from inbound '{}': {}", email, inbound_tag, e))
            }
        }
    }
}