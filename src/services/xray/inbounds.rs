use anyhow::{anyhow, Result};
use prost::Message;
use serde_json::Value;
use uuid;
use xray_core::{
    app::proxyman::command::{AddInboundRequest, RemoveInboundRequest},
    app::proxyman::ReceiverConfig,
    common::net::{ip_or_domain::Address, IpOrDomain, Network, PortList, PortRange},
    common::protocol::User,
    common::serial::TypedMessage,
    core::InboundHandlerConfig,
    proxy::shadowsocks::ServerConfig as ShadowsocksServerConfig,
    proxy::shadowsocks::{Account as ShadowsocksAccount, CipherType},
    proxy::trojan::Account as TrojanAccount,
    proxy::trojan::ServerConfig as TrojanServerConfig,
    proxy::vless::inbound::Config as VlessInboundConfig,
    proxy::vless::Account as VlessAccount,
    proxy::vmess::inbound::Config as VmessInboundConfig,
    proxy::vmess::Account as VmessAccount,
    tonic::Request,
    transport::internet::tls::{Certificate as TlsCertificate, Config as TlsConfig},
    transport::internet::StreamConfig,
    Client,
};


pub struct InboundClient<'a> {
    endpoint: String,
    client: &'a Client,
}

impl<'a> InboundClient<'a> {
    pub fn new(endpoint: String, client: &'a Client) -> Self {
        Self { endpoint, client }
    }

    /// Add inbound configuration
    pub async fn add_inbound(&self, inbound: &Value) -> Result<()> {
        self.add_inbound_with_certificate(inbound, None, None, None)
            .await
    }

    /// Add inbound configuration with TLS certificate and users
    pub async fn add_inbound_with_certificate(
        &self,
        inbound: &Value,
        users: Option<&[Value]>,
        cert_pem: Option<&str>,
        key_pem: Option<&str>,
    ) -> Result<()> {
        let tag = inbound["tag"].as_str().unwrap_or("").to_string();
        let port = inbound["port"].as_u64().unwrap_or(8080) as u32;
        let protocol = inbound["protocol"].as_str().unwrap_or("vless");
        let _user_count = users.map_or(0, |u| u.len());

        tracing::info!(
            "Adding inbound '{}' with protocol={}, port={}, has_cert={}, has_key={}",
            tag,
            protocol,
            port,
            cert_pem.is_some(),
            key_pem.is_some()
        );

        // Create receiver configuration (port binding) - use simple port number
        let port_list = PortList {
            range: vec![PortRange {
                from: port,
                to: port,
            }],
        };

        // Create StreamConfig with proper structure and TLS like working example
        let stream_settings = if cert_pem.is_some() && key_pem.is_some() {
            let cert_pem = cert_pem.unwrap();
            let key_pem = key_pem.unwrap();

            // Create TLS certificate exactly like working example - PEM content as bytes
            let tls_cert = TlsCertificate {
                certificate: cert_pem.as_bytes().to_vec(), // PEM content as bytes like working example
                key: key_pem.as_bytes().to_vec(), // PEM content as bytes like working example
                usage: 0,
                ocsp_stapling: 3600,    // From working example
                one_time_loading: true, // From working example
                build_chain: false,
                certificate_path: "".to_string(), // Empty paths since we use content
                key_path: "".to_string(),         // Empty paths since we use content
            };

            // Create TLS config with proper fields like working example
            let mut tls_config = TlsConfig::default();
            tls_config.certificate = vec![tls_cert];
            tls_config.next_protocol = vec!["h2".to_string(), "http/1.1".to_string()]; // From working example
            tls_config.server_name = "localhost".to_string(); // From working example
            tls_config.min_version = "1.2".to_string(); // From Marzban examples

            // Create TypedMessage for TLS config
            let tls_message = TypedMessage {
                r#type: "xray.transport.internet.tls.Config".to_string(),
                value: tls_config.encode_to_vec(),
            };

            tracing::debug!(
                "TLS config: server_name={}, protocols={:?}",
                tls_config.server_name,
                tls_config.next_protocol
            );

            // Create StreamConfig like working example
            Some(StreamConfig {
                address: None, // No address in streamSettings according to working example
                port: 0,       // No port in working example streamSettings
                protocol_name: "tcp".to_string(),
                transport_settings: vec![],
                security_type: "xray.transport.internet.tls.Config".to_string(), // Full type like working example
                security_settings: vec![tls_message],
                socket_settings: None,
            })
        } else {
            None
        };

        let receiver_config = ReceiverConfig {
            port_list: Some(port_list),
            listen: Some(IpOrDomain {
                address: Some(Address::Ip(vec![0, 0, 0, 0])), // "0.0.0.0" as IPv4 bytes
            }),
            allocation_strategy: None,
            stream_settings: stream_settings,
            receive_original_destination: false,
            sniffing_settings: None, // TODO: add sniffing settings if needed
        };

        let receiver_message = TypedMessage {
            r#type: "xray.app.proxyman.ReceiverConfig".to_string(),
            value: receiver_config.encode_to_vec(),
        };

        // Create proxy configuration based on protocol with users
        let proxy_message = match protocol {
            "vless" => {
                let mut clients = vec![];
                if let Some(users) = users {
                    for user in users {
                        let user_id = user["id"].as_str().unwrap_or("").to_string();
                        let email = user["email"].as_str().unwrap_or("").to_string();
                        let level = user["level"].as_u64().unwrap_or(0) as u32;

                        if !user_id.is_empty() && !email.is_empty() {
                            let account = VlessAccount {
                                id: user_id,
                                encryption: "none".to_string(),
                                flow: "".to_string(),
                            };
                            clients.push(User {
                                email,
                                level,
                                account: Some(TypedMessage {
                                    r#type: "xray.proxy.vless.Account".to_string(),
                                    value: account.encode_to_vec(),
                                }),
                            });
                        }
                    }
                }

                let vless_config = VlessInboundConfig {
                    clients,
                    decryption: "none".to_string(),
                    fallbacks: vec![],
                };
                TypedMessage {
                    r#type: "xray.proxy.vless.inbound.Config".to_string(),
                    value: vless_config.encode_to_vec(),
                }
            }
            "vmess" => {
                let mut vmess_users = vec![];
                if let Some(users) = users {
                    for user in users {
                        let user_id = user["id"].as_str().unwrap_or("").to_string();
                        let email = user["email"].as_str().unwrap_or("").to_string();
                        let level = user["level"].as_u64().unwrap_or(0) as u32;

                        // Validate required fields
                        if user_id.is_empty() || email.is_empty() {
                            tracing::warn!("Skipping VMess user: missing id or email");
                            continue;
                        }

                        // Validate UUID format
                        if uuid::Uuid::parse_str(&user_id).is_err() {
                            tracing::warn!("VMess user '{}' has invalid UUID format", user_id);
                        }

                        if !user_id.is_empty() && !email.is_empty() {
                            let account = VmessAccount {
                                id: user_id.clone(),
                                security_settings: None,
                                tests_enabled: "".to_string(), // Keep empty as in examples
                            };
                            let account_bytes = account.encode_to_vec();

                            vmess_users.push(User {
                                email: email.clone(),
                                level,
                                account: Some(TypedMessage {
                                    r#type: "xray.proxy.vmess.Account".to_string(),
                                    value: account_bytes,
                                }),
                            });
                        }
                    }
                }

                let vmess_config = VmessInboundConfig {
                    user: vmess_users,
                    default: None,
                    detour: None,
                };
                TypedMessage {
                    r#type: "xray.proxy.vmess.inbound.Config".to_string(),
                    value: vmess_config.encode_to_vec(),
                }
            }
            "trojan" => {
                let mut trojan_users = vec![];
                if let Some(users) = users {
                    for user in users {
                        let password = user["password"]
                            .as_str()
                            .or_else(|| user["id"].as_str())
                            .unwrap_or("")
                            .to_string();
                        let email = user["email"].as_str().unwrap_or("").to_string();
                        let level = user["level"].as_u64().unwrap_or(0) as u32;

                        if !password.is_empty() && !email.is_empty() {
                            let account = TrojanAccount { password };
                            trojan_users.push(User {
                                email,
                                level,
                                account: Some(TypedMessage {
                                    r#type: "xray.proxy.trojan.Account".to_string(),
                                    value: account.encode_to_vec(),
                                }),
                            });
                        }
                    }
                }

                let trojan_config = TrojanServerConfig {
                    users: trojan_users,
                    fallbacks: vec![],
                };
                TypedMessage {
                    r#type: "xray.proxy.trojan.ServerConfig".to_string(),
                    value: trojan_config.encode_to_vec(),
                }
            }
            "shadowsocks" => {
                let mut ss_users = vec![];
                if let Some(users) = users {
                    for user in users {
                        let password = user["password"]
                            .as_str()
                            .or_else(|| user["id"].as_str())
                            .unwrap_or("")
                            .to_string();
                        let email = user["email"].as_str().unwrap_or("").to_string();
                        let level = user["level"].as_u64().unwrap_or(0) as u32;

                        if !password.is_empty() && !email.is_empty() {
                            let account = ShadowsocksAccount {
                                password,
                                cipher_type: CipherType::Aes256Gcm as i32, // Use AES-256-GCM cipher
                                iv_check: false,                           // Default IV check
                            };
                            ss_users.push(User {
                                email: email.clone(),
                                level,
                                account: Some(TypedMessage {
                                    r#type: "xray.proxy.shadowsocks.Account".to_string(),
                                    value: account.encode_to_vec(),
                                }),
                            });
                        }
                    }
                }

                let shadowsocks_config = ShadowsocksServerConfig {
                    users: ss_users,
                    network: vec![Network::Tcp as i32, Network::Udp as i32], // Support TCP and UDP
                };
                TypedMessage {
                    r#type: "xray.proxy.shadowsocks.ServerConfig".to_string(),
                    value: shadowsocks_config.encode_to_vec(),
                }
            }
            _ => {
                return Err(anyhow!("Unsupported protocol: {}", protocol));
            }
        };

        let inbound_config = InboundHandlerConfig {
            tag: tag.clone(),
            receiver_settings: Some(receiver_message),
            proxy_settings: Some(proxy_message),
        };

        let request = Request::new(AddInboundRequest {
            inbound: Some(inbound_config),
        });
        let mut handler_client = self.client.handler();
        match handler_client.add_inbound(request).await {
            Ok(_) => {
                tracing::info!("Added {} inbound '{}' successfully", protocol, tag);
                Ok(())
            }
            Err(e) => {
                tracing::error!("Failed to add {} inbound '{}': {}", protocol, tag, e);
                Err(anyhow!("Failed to add inbound {}: {}", tag, e))
            }
        }
    }

    /// Remove inbound by tag
    pub async fn remove_inbound(&self, tag: &str) -> Result<()> {
        let mut handler_client = self.client.handler();
        let request = Request::new(RemoveInboundRequest {
            tag: tag.to_string(),
        });

        match handler_client.remove_inbound(request).await {
            Ok(_) => {
                tracing::info!("Removed inbound '{}' from {}", tag, self.endpoint);
                Ok(())
            }
            Err(e) => {
                tracing::error!("Failed to remove inbound '{}': {}", tag, e);
                Err(anyhow!("Failed to remove inbound: {}", e))
            }
        }
    }

    /// Restart Xray with new configuration
    pub async fn restart_with_config(
        &self,
        _config: &crate::services::xray::XrayConfig,
    ) -> Result<()> {
        tracing::debug!(
            "Restarting Xray server at {} with new config",
            self.endpoint
        );

        // TODO: Implement restart with config using xray-core
        // For now just return success
        Ok(())
    }
}
