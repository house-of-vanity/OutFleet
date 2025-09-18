use anyhow::{Result, anyhow};
use serde_json::Value;
use xray_core::{
    tonic::Request,
    app::proxyman::command::{AddInboundRequest, RemoveInboundRequest},
    core::InboundHandlerConfig,
    common::serial::TypedMessage,
    common::protocol::User,
    app::proxyman::ReceiverConfig,
    common::net::{PortList, PortRange, IpOrDomain},
    transport::internet::StreamConfig,
    transport::internet::tls::{Config as TlsConfig, Certificate as TlsCertificate},
    proxy::vless::inbound::Config as VlessInboundConfig,
    proxy::vless::Account as VlessAccount,
    proxy::vmess::inbound::Config as VmessInboundConfig,
    proxy::vmess::Account as VmessAccount,
    proxy::trojan::ServerConfig as TrojanServerConfig,
    proxy::trojan::Account as TrojanAccount,
    proxy::shadowsocks::ServerConfig as ShadowsocksServerConfig,
    proxy::shadowsocks::Account as ShadowsocksAccount,
    Client,
    prost_types,
};
use prost::Message;

/// Convert PEM format to DER (x509) format
fn pem_to_der(pem_data: &str) -> Result<Vec<u8>> {
    // Remove PEM headers and whitespace, then decode base64
    let base64_data: String = pem_data.lines()
        .filter(|line| !line.starts_with("-----") && !line.trim().is_empty())
        .map(|line| line.trim())
        .collect::<Vec<&str>>()
        .join("");
    
    tracing::debug!("Base64 data length: {}", base64_data.len());
    tracing::debug!("Base64 data: {}", &base64_data[..std::cmp::min(100, base64_data.len())]);
    
    use base64::{Engine as _, engine::general_purpose};
    general_purpose::STANDARD.decode(&base64_data)
        .map_err(|e| anyhow!("Failed to decode base64 PEM data: {}", e))
}

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
        self.add_inbound_with_certificate(inbound, None, None, None).await
    }

    /// Add inbound configuration with TLS certificate and users
    pub async fn add_inbound_with_certificate(&self, inbound: &Value, users: Option<&[Value]>, cert_pem: Option<&str>, key_pem: Option<&str>) -> Result<()> {
        tracing::info!("Adding inbound to Xray server at {}", self.endpoint);
        tracing::debug!("Inbound config: {}", serde_json::to_string_pretty(inbound)?);
        
        let tag = inbound["tag"].as_str().unwrap_or("").to_string();
        let port = inbound["port"].as_u64().unwrap_or(8080) as u32;
        let protocol = inbound["protocol"].as_str().unwrap_or("vless");
        
        tracing::debug!("Creating inbound: tag={}, port={}, protocol={}", tag, port, protocol);
        
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
            
            tracing::info!("Creating StreamConfig with TLS like working example");
            
            // Create TLS certificate with empty content but paths (even though we don't use files)
            let tls_cert = TlsCertificate {
                certificate: vec![], // Empty - try using content in different way
                key: vec![], // Empty - try using content in different way
                usage: 0,
                ocsp_stapling: 3600, // From Marzban examples
                one_time_loading: true,
                build_chain: false,
                certificate_path: cert_pem.to_string(), // Try putting PEM content here
                key_path: key_pem.to_string(), // Try putting PEM content here
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
            
            tracing::info!("Created TLS config with server_name: {}, next_protocol: {:?}", 
                tls_config.server_name, tls_config.next_protocol);
            
            // Create StreamConfig like working example
            Some(StreamConfig {
                address: Some(IpOrDomain { address: None }), 
                port: 0, // No port in working example streamSettings
                protocol_name: "tcp".to_string(),
                transport_settings: vec![],
                security_type: "xray.transport.internet.tls.Config".to_string(), // Full type like working example
                security_settings: vec![tls_message],
                socket_settings: None,
            })
        } else {
            tracing::info!("No certificates provided, creating inbound without TLS");
            None
        };

        let receiver_config = ReceiverConfig {
            port_list: Some(port_list),
            listen: Some(IpOrDomain { address: None }), // Use proper IpOrDomain for listen
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
            },
            "vmess" => {
                let mut vmess_users = vec![];
                if let Some(users) = users {
                    for user in users {
                        let user_id = user["id"].as_str().unwrap_or("").to_string();
                        let email = user["email"].as_str().unwrap_or("").to_string();
                        let level = user["level"].as_u64().unwrap_or(0) as u32;
                        
                        if !user_id.is_empty() && !email.is_empty() {
                            let account = VmessAccount {
                                id: user_id,
                                security_settings: None,
                                tests_enabled: "".to_string(),
                            };
                            vmess_users.push(User {
                                email,
                                level,
                                account: Some(TypedMessage {
                                    r#type: "xray.proxy.vmess.Account".to_string(),
                                    value: account.encode_to_vec(),
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
            },
            "trojan" => {
                let mut trojan_users = vec![];
                if let Some(users) = users {
                    for user in users {
                        let password = user["password"].as_str().or_else(|| user["id"].as_str()).unwrap_or("").to_string();
                        let email = user["email"].as_str().unwrap_or("").to_string();
                        let level = user["level"].as_u64().unwrap_or(0) as u32;
                        
                        if !password.is_empty() && !email.is_empty() {
                            let account = TrojanAccount {
                                password,
                            };
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
            },
            "shadowsocks" => {
                let mut ss_users = vec![];
                if let Some(users) = users {
                    for user in users {
                        let password = user["password"].as_str().or_else(|| user["id"].as_str()).unwrap_or("").to_string();
                        let email = user["email"].as_str().unwrap_or("").to_string();
                        let level = user["level"].as_u64().unwrap_or(0) as u32;
                        
                        if !password.is_empty() && !email.is_empty() {
                            let account = ShadowsocksAccount {
                                password,
                                cipher_type: 0, // Default cipher
                                iv_check: false, // Default IV check
                            };
                            ss_users.push(User {
                                email,
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
                    network: vec![], // Support all networks by default
                };
                TypedMessage {
                    r#type: "xray.proxy.shadowsocks.ServerConfig".to_string(),
                    value: shadowsocks_config.encode_to_vec(),
                }
            },
            _ => {
                return Err(anyhow!("Unsupported protocol: {}", protocol));
            }
        };

        let inbound_config = InboundHandlerConfig {
            tag: tag.clone(),
            receiver_settings: Some(receiver_message),
            proxy_settings: Some(proxy_message),
        };

        tracing::info!("Sending AddInboundRequest for '{}'", tag);
        tracing::debug!("InboundConfig: {:?}", inbound_config);
        
        let request = Request::new(AddInboundRequest {
            inbound: Some(inbound_config),
        });
        let mut handler_client = self.client.handler();
        match handler_client.add_inbound(request).await {
            Ok(response) => {
                let _response_inner = response.into_inner();
                tracing::info!("Successfully added inbound {}", tag);
                Ok(())
            }
            Err(e) => {
                tracing::error!("Failed to add inbound {}: {}", tag, e);
                Err(anyhow!("Failed to add inbound {}: {}", tag, e))
            }
        }
    }

    /// Remove inbound by tag
    pub async fn remove_inbound(&self, tag: &str) -> Result<()> {
        tracing::info!("Removing inbound '{}' from Xray server at {}", tag, self.endpoint);
        
        let mut handler_client = self.client.handler();
        let request = Request::new(RemoveInboundRequest {
            tag: tag.to_string(),
        });
        
        match handler_client.remove_inbound(request).await {
            Ok(_) => {
                tracing::info!("Successfully removed inbound");
                Ok(())
            },
            Err(e) => {
                tracing::error!("Failed to remove inbound: {}", e);
                Err(anyhow!("Failed to remove inbound: {}", e))
            }
        }
    }

    /// Restart Xray with new configuration
    pub async fn restart_with_config(&self, config: &crate::services::xray::XrayConfig) -> Result<()> {
        tracing::info!("Restarting Xray server at {} with new config", self.endpoint);
        tracing::debug!("Config: {}", serde_json::to_string_pretty(&config.to_json())?);
        
        // TODO: Implement restart with config using xray-core
        // For now just return success
        Ok(())
    }
}