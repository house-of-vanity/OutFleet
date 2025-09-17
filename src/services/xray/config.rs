use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// Xray configuration structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct XrayConfig {
    pub log: LogConfig,
    pub api: ApiConfig,
    pub dns: Option<DnsConfig>,
    pub routing: Option<RoutingConfig>,
    pub policy: Option<PolicyConfig>,
    pub inbounds: Vec<InboundConfig>,
    pub outbounds: Vec<OutboundConfig>,
    pub transport: Option<TransportConfig>,
    pub stats: Option<StatsConfig>,
    pub reverse: Option<ReverseConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogConfig {
    pub access: Option<String>,
    pub error: Option<String>,
    #[serde(rename = "loglevel")]
    pub log_level: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiConfig {
    pub tag: String,
    pub listen: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DnsConfig {
    pub servers: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingConfig {
    #[serde(rename = "domainStrategy")]
    pub domain_strategy: Option<String>,
    pub rules: Vec<RoutingRule>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingRule {
    #[serde(rename = "type")]
    pub rule_type: String,
    pub domain: Option<Vec<String>>,
    pub ip: Option<Vec<String>>,
    pub port: Option<String>,
    #[serde(rename = "outboundTag")]
    pub outbound_tag: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyConfig {
    pub levels: HashMap<String, PolicyLevel>,
    pub system: Option<SystemPolicy>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyLevel {
    #[serde(rename = "handshakeTimeout")]
    pub handshake_timeout: Option<u32>,
    #[serde(rename = "connIdle")]
    pub conn_idle: Option<u32>,
    #[serde(rename = "uplinkOnly")]
    pub uplink_only: Option<u32>,
    #[serde(rename = "downlinkOnly")]
    pub downlink_only: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemPolicy {
    #[serde(rename = "statsInboundUplink")]
    pub stats_inbound_uplink: Option<bool>,
    #[serde(rename = "statsInboundDownlink")]
    pub stats_inbound_downlink: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InboundConfig {
    pub tag: String,
    pub port: u16,
    pub listen: Option<String>,
    pub protocol: String,
    pub settings: Value,
    #[serde(rename = "streamSettings")]
    pub stream_settings: Option<Value>,
    pub sniffing: Option<SniffingConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutboundConfig {
    pub tag: String,
    pub protocol: String,
    pub settings: Value,
    #[serde(rename = "streamSettings")]
    pub stream_settings: Option<Value>,
    pub mux: Option<MuxConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SniffingConfig {
    pub enabled: bool,
    #[serde(rename = "destOverride")]
    pub dest_override: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MuxConfig {
    pub enabled: bool,
    pub concurrency: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransportConfig {
    #[serde(rename = "tcpSettings")]
    pub tcp_settings: Option<Value>,
    #[serde(rename = "kcpSettings")]
    pub kcp_settings: Option<Value>,
    #[serde(rename = "wsSettings")]
    pub ws_settings: Option<Value>,
    #[serde(rename = "httpSettings")]
    pub http_settings: Option<Value>,
    #[serde(rename = "dsSettings")]
    pub ds_settings: Option<Value>,
    #[serde(rename = "quicSettings")]
    pub quic_settings: Option<Value>,
    #[serde(rename = "grpcSettings")]
    pub grpc_settings: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatsConfig {}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReverseConfig {
    pub bridges: Option<Vec<BridgeConfig>>,
    pub portals: Option<Vec<PortalConfig>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeConfig {
    pub tag: String,
    pub domain: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortalConfig {
    pub tag: String,
    pub domain: String,
}

#[allow(dead_code)]
impl XrayConfig {
    /// Create a new basic Xray configuration
    pub fn new() -> Self {
        Self {
            log: LogConfig {
                access: Some("/var/log/xray/access.log".to_string()),
                error: Some("/var/log/xray/error.log".to_string()),
                log_level: "warning".to_string(),
            },
            api: ApiConfig {
                tag: "api".to_string(),
                listen: "127.0.0.1:2053".to_string(),
            },
            dns: None,
            routing: Some(RoutingConfig {
                domain_strategy: Some("IPIfNonMatch".to_string()),
                rules: vec![
                    RoutingRule {
                        rule_type: "field".to_string(),
                        domain: None,
                        ip: Some(vec!["geoip:private".to_string()]),
                        port: None,
                        outbound_tag: "direct".to_string(),
                    }
                ],
            }),
            policy: Some(PolicyConfig {
                levels: {
                    let mut levels = HashMap::new();
                    levels.insert("0".to_string(), PolicyLevel {
                        handshake_timeout: Some(4),
                        conn_idle: Some(300),
                        uplink_only: Some(2),
                        downlink_only: Some(5),
                    });
                    levels
                },
                system: Some(SystemPolicy {
                    stats_inbound_uplink: Some(true),
                    stats_inbound_downlink: Some(true),
                }),
            }),
            inbounds: vec![],
            outbounds: vec![
                OutboundConfig {
                    tag: "direct".to_string(),
                    protocol: "freedom".to_string(),
                    settings: serde_json::json!({}),
                    stream_settings: None,
                    mux: None,
                },
                OutboundConfig {
                    tag: "blocked".to_string(),
                    protocol: "blackhole".to_string(),
                    settings: serde_json::json!({
                        "response": {
                            "type": "http"
                        }
                    }),
                    stream_settings: None,
                    mux: None,
                },
            ],
            transport: None,
            stats: Some(StatsConfig {}),
            reverse: None,
        }
    }

    /// Add inbound to configuration
    pub fn add_inbound(&mut self, inbound: InboundConfig) {
        self.inbounds.push(inbound);
    }

    /// Remove inbound by tag
    pub fn remove_inbound(&mut self, tag: &str) -> bool {
        let initial_len = self.inbounds.len();
        self.inbounds.retain(|inbound| inbound.tag != tag);
        self.inbounds.len() != initial_len
    }

    /// Find inbound by tag
    pub fn find_inbound(&self, tag: &str) -> Option<&InboundConfig> {
        self.inbounds.iter().find(|inbound| inbound.tag == tag)
    }

    /// Find inbound by tag (mutable)
    pub fn find_inbound_mut(&mut self, tag: &str) -> Option<&mut InboundConfig> {
        self.inbounds.iter_mut().find(|inbound| inbound.tag == tag)
    }

    /// Convert to JSON Value
    pub fn to_json(&self) -> Value {
        serde_json::to_value(self).unwrap_or(Value::Null)
    }

    /// Create from JSON Value
    pub fn from_json(value: &Value) -> Result<Self, serde_json::Error> {
        serde_json::from_value(value.clone())
    }

    /// Validate configuration
    pub fn validate(&self) -> Result<(), String> {
        // Check for duplicate inbound tags
        let mut tags = std::collections::HashSet::new();
        for inbound in &self.inbounds {
            if !tags.insert(&inbound.tag) {
                return Err(format!("Duplicate inbound tag: {}", inbound.tag));
            }
        }

        // Check for duplicate outbound tags
        tags.clear();
        for outbound in &self.outbounds {
            if !tags.insert(&outbound.tag) {
                return Err(format!("Duplicate outbound tag: {}", outbound.tag));
            }
        }

        Ok(())
    }
}

impl Default for XrayConfig {
    fn default() -> Self {
        Self::new()
    }
}