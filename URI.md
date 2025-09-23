# Xray Client URI Generation

## VMess URI Format

VMess URIs use two formats:

### 1. Query Parameter Format
```
vmess://uuid@hostname:port?parameters#alias
```

**Parameters:**
- `encryption=auto` - Encryption method
- `security=tls|none` - Security layer (TLS or none)
- `sni=domain` - Server Name Indication for TLS
- `fp=chrome|firefox|safari` - TLS fingerprint
- `type=ws|tcp|grpc|http` - Transport type
- `path=/path` - WebSocket/HTTP path
- `host=domain` - Host header for WebSocket

**Example:**
```
vmess://2c981164-9b93-4bca-94ff-b78d3f8498d7@v2ray.codefyinc.com:443?encryption=auto&security=tls&sni=example.com&fp=chrome&type=ws&path=/ws&host=v2ray.codefyinc.com#MyServer
```

### 2. Base64 JSON Format
```
vmess://base64(json_config)#alias
```

**JSON Structure:**
```json
{
  "v": "2",
  "ps": "Server Name",
  "add": "hostname",
  "port": "443",
  "id": "uuid",
  "aid": "0",
  "scy": "auto",
  "net": "ws",
  "type": "none",
  "host": "domain",
  "path": "/path",
  "tls": "tls",
  "sni": "domain",
  "alpn": "",
  "fp": "chrome"
}
```

## VLESS URI Format

```
vless://uuid@hostname:port?parameters#alias
```

**Key Parameters:**
- `encryption=none` - VLESS uses no encryption
- `security=tls|reality|none` - Security layer
- `type=ws|tcp|grpc|http|httpupgrade|xhttp` - Transport type
- `flow=xtls-rprx-vision` - Flow control (for XTLS)
- `headerType=none|http` - Header type for TCP
- `mode=auto|gun|stream-one` - Transport mode
- `serviceName=name` - gRPC service name
- `authority=domain` - gRPC authority
- `spx=/path` - Split HTTP path (for xhttp)

**REALITY Parameters:**
- `pbk=public_key` - Public key
- `sid=short_id` - Short ID
- `fp=chrome|firefox|safari` - TLS fingerprint
- `sni=domain` - Server Name Indication

**Examples:**
```
vless://uuid@server.com:443?type=tcp&security=none&headerType=none#Basic
vless://uuid@server.com:443?type=ws&security=tls&path=/ws&host=example.com#WebSocket
vless://uuid@server.com:443?type=grpc&security=reality&serviceName=grpcService&pbk=key&sid=id#gRPC-Reality
```

## Generation Algorithm

1. **UUID**: Use `inbound_users.xray_user_id`
2. **Hostname**: From `servers.hostname`
3. **Port**: From `server_inbounds.port_override` or template default
4. **Transport**: From inbound template `stream_settings`
5. **Security**: Based on certificate configuration
6. **Path**: From WebSocket stream settings
7. **Alias**: User name + server name

## Shadowsocks URI Format

```
ss://password@hostname:port?parameters#alias
```

**Parameters:**
- `encryption=none` - Usually none for modern configs
- `security=tls|reality|none` - Security layer
- `type=ws|tcp|grpc|xhttp` - Transport type
- `path=/path` - WebSocket/HTTP path
- `host=domain` - Host header
- `mode=auto|gun|stream-one` - Transport mode
- `headerType=none|http` - Header type for TCP
- `flow=xtls-rprx-vision` - Flow control (for REALITY)
- `pbk=key` - Public key (for REALITY)
- `sid=id` - Short ID (for REALITY)

**Example:**
```
ss://my-password@server.com:443?type=ws&security=tls&path=/ws&host=example.com#MyServer
```

## Trojan URI Format

```
trojan://password@hostname:port?parameters#alias
```

**Parameters:**
- `security=tls|reality|none` - Security layer
- `type=ws|tcp|grpc` - Transport type
- `sni=domain` - Server Name Indication
- `fp=chrome|firefox|randomized` - TLS fingerprint
- `flow=xtls-rprx-vision` - Flow control
- `allowInsecure=1` - Allow insecure connections
- `headerType=http|none` - Header type for TCP
- `mode=gun` - gRPC mode
- `serviceName=name` - gRPC service name

**WebSocket Parameters:**
- `path=/path` - WebSocket path
- `host=domain` - Host header
- `alpn=http/1.1|h2` - ALPN protocols

**Examples:**
```
trojan://password@server.com:443?type=tcp&security=tls&sni=example.com#Basic
trojan://password@server.com:443?type=ws&security=tls&path=/ws&host=example.com&sni=example.com#WebSocket
trojan://password@server.com:443?type=grpc&security=tls&serviceName=grpcService&mode=gun&sni=example.com#gRPC
```

## Implementation Notes

- VMess requires `aid=0` for modern clients
- VLESS doesn't use `aid` parameter
- Shadowsocks uses password instead of UUID
- Base64 encoding required for VMess JSON format
- URL encoding needed for special characters in parameters
- REALITY parameters: `pbk`, `sid`, `fp`, `sni`