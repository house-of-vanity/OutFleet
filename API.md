# OutFleet Xray Admin API

Base URL: `http://localhost:8080`

## Overview
Complete API documentation for OutFleet - a web admin panel for managing xray-core VPN proxy servers.

## Base Endpoints

### Health Check
- `GET /health` - Service health check

**Response:**
```json
{
  "status": "ok",
  "service": "xray-admin", 
  "version": "0.1.0"
}
```

### User Subscription
- `GET /sub/{user_id}` - Get all user configuration links (subscription endpoint)

**Description:** Returns all VPN configuration links for a specific user, one per line. This endpoint is designed for VPN clients that support subscription URLs for automatic configuration updates.

**Path Parameters:**
- `user_id` (UUID) - The user's unique identifier

**Response:**
- **Content-Type:** `text/plain; charset=utf-8`
- **Success (200):** Base64 encoded string containing configuration URIs (one per line when decoded)
- **Not Found (404):** User doesn't exist
- **No Content:** Returns base64 encoded comment if no configurations available

**Example Response:**
```
dm1lc3M6Ly9leUoySWpvaU1pSXNJbkJ6SWpvaVUyVnlkbVZ5TVNJc0ltRmtaQ0k2SWpFeU55NHdMakF1TVM0eElpd2ljRzl5ZENJNklqUTBNeUlzSWxsa0lqb2lNVEl6TkRVMk56Z3RNVEl6TkMwMU5qYzRMVGxoWW1NdE1USXpORFUyTnpnNVlXSmpJaXdpWVdsa0lqb2lNQ0lzSW5Oamj0SWpvaVlYVjBieUlzSW01bGRDSTZJblJqY0NJc0luUjVjR1VpT2lKdWIyNWxJaXdpYUc5emRDSTZJaUlzSW5CaGRHZ2lPaUlpTEhKMGJITWlPaUowYkhNaUxGTnVhU0k2SWlKOQ0Kdmxlc3M6Ly91dWlkQGhvc3RuYW1lOnBvcnQ/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZ0eXBlPXRjcCZoZWFkZXJUeXBlPW5vbmUjU2VydmVyTmFtZQ0Kc3M6Ly9ZV1Z6TFRJMk5TMW5ZMjFBY0dGemMzZHZjbVE2TVRJNExqQXVNQzR5T2pnd09EQT0jU2VydmVyMg0K
```

**Decoded Example:**
```
vmess://eyJ2IjoiMiIsInBzIjoiU2VydmVyMSIsImFkZCI6IjEyNy4wLjAuMSIsInBvcnQiOiI0NDMiLCJpZCI6IjEyMzQ1Njc4LTEyMzQtNTY3OC05YWJjLTEyMzQ1Njc4OWFiYyIsImFpZCI6IjAiLCJzY3kiOiJhdXRvIiwibmV0IjoidGNwIiwidHlwZSI6Im5vbmUiLCJob3N0IjoiIiwicGF0aCI6IiIsInRscyI6InRscyIsInNuaSI6IiJ9
vless://uuid@hostname:port?encryption=none&security=tls&type=tcp&headerType=none#ServerName
ss://YWVzLTI1Ni1nY21AcGFzc3dvcmQ6MTI3LjAuMC4xOjgwODA=#Server2
```

**Usage:** This endpoint is intended for VPN client applications that support subscription URLs. Users can add this URL to their VPN client to automatically receive all their configurations and get updates when configurations change.

## API Endpoints

All API endpoints are prefixed with `/api`.

### Users

#### List Users
- `GET /users?page=1&per_page=20` - Get paginated list of users

#### Search Users
- `GET /users/search?q=john` - Universal search for users
  
**Search capabilities:**
- By name (partial match, case-insensitive): `?q=john`
- By telegram_id: `?q=123456789`
- By user UUID: `?q=550e8400-e29b-41d4-a716-446655440000`

**Response:** Array of user objects (limited to 100 results)
```json
[
  {
    "id": "uuid",
    "name": "string",
    "comment": "string|null",
    "telegram_id": "number|null",
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
]
```

#### Get User
- `GET /users/{id}` - Get user by ID

#### Create User
- `POST /users` - Create new user
```json
{
  "name": "John Doe",
  "comment": "Admin user",
  "telegram_id": 123456789
}
```

#### Update User  
- `PUT /users/{id}` - Update user by ID
```json
{
  "name": "Jane Doe",
  "comment": null,
  "telegram_id": 987654321
}
```

#### Delete User
- `DELETE /users/{id}` - Delete user by ID

#### Get User Access
- `GET /users/{id}/access?include_uris=true` - Get user access to inbounds (optionally with client URIs)

**Query Parameters:**
- `include_uris`: boolean (optional) - Include client configuration URIs in response

**Response (without URIs):**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "server_inbound_id": "uuid", 
    "xray_user_id": "string",
    "level": 0,
    "is_active": true
  }
]
```

**Response (with URIs):**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "server_inbound_id": "uuid", 
    "xray_user_id": "string",
    "level": 0,
    "is_active": true,
    "uri": "vless://uuid@hostname:port?parameters#alias",
    "protocol": "vless",
    "server_name": "Server Name",
    "inbound_tag": "inbound-tag"
  }
]
```

#### Generate Client Configurations
- `GET /users/{user_id}/configs` - Get all client configuration URIs for a user
- `GET /users/{user_id}/access/{inbound_id}/config` - Get specific client configuration URI

**Response:**
```json
{
  "user_id": "uuid",
  "server_name": "string",
  "inbound_tag": "string", 
  "protocol": "vmess|vless|trojan|shadowsocks",
  "uri": "protocol://uri_string",
  "qr_code": null
}
```

### Servers

#### List Servers
- `GET /servers` - Get all servers

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "string",
    "hostname": "string",
    "grpc_hostname": "string", 
    "grpc_port": 2053,
    "status": "online|offline|error|unknown",
    "default_certificate_id": "uuid|null",
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "has_credentials": true
  }
]
```

#### Get Server
- `GET /servers/{id}` - Get server by ID

#### Create Server
- `POST /servers` - Create new server

**Request:**
```json
{
  "name": "Server Name",
  "hostname": "server.example.com",
  "grpc_hostname": "192.168.1.100", // optional, defaults to hostname
  "grpc_port": 2053, // optional, defaults to 2053
  "api_credentials": "optional credentials",
  "default_certificate_id": "uuid" // optional
}
```

#### Update Server
- `PUT /servers/{id}` - Update server

**Request:** (all fields optional)
```json
{
  "name": "New Server Name",
  "hostname": "new.server.com",
  "grpc_hostname": "192.168.1.200",
  "grpc_port": 2054,
  "api_credentials": "new credentials", 
  "status": "online",
  "default_certificate_id": "uuid"
}
```

#### Delete Server
- `DELETE /servers/{id}` - Delete server

#### Test Server Connection
- `POST /servers/{id}/test` - Test connection to server

**Response:**
```json
{
  "connected": true,
  "endpoint": "192.168.1.100:2053"
}
```

#### Get Server Statistics
- `GET /servers/{id}/stats` - Get server statistics

### Server Inbounds

#### List Server Inbounds
- `GET /servers/{server_id}/inbounds` - Get all inbounds for a server

**Response:**
```json
[
  {
    "id": "uuid",
    "server_id": "uuid", 
    "template_id": "uuid",
    "template_name": "string",
    "tag": "string",
    "port_override": 8080,
    "certificate_id": "uuid|null",
    "variable_values": {},
    "is_active": true,
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
]
```

#### Get Server Inbound
- `GET /servers/{server_id}/inbounds/{inbound_id}` - Get specific inbound

#### Create Server Inbound
- `POST /servers/{server_id}/inbounds` - Create new inbound for server

**Request:**
```json
{
  "template_id": "uuid",
  "port": 8080,
  "certificate_id": "uuid", // optional
  "is_active": true
}
```

#### Update Server Inbound
- `PUT /servers/{server_id}/inbounds/{inbound_id}` - Update inbound

**Request:** (all fields optional)
```json
{
  "tag": "new-tag",
  "port_override": 8081,
  "certificate_id": "uuid",
  "variable_values": {"domain": "example.com"},
  "is_active": false
}
```

#### Delete Server Inbound
- `DELETE /servers/{server_id}/inbounds/{inbound_id}` - Delete inbound

### User-Inbound Management

#### Add User to Inbound
- `POST /servers/{server_id}/inbounds/{inbound_id}/users` - Grant user access to inbound

**Request:**
```json
{
  "user_id": "uuid", // optional, will create new user if not provided
  "name": "username",
  "comment": "User description", // optional
  "telegram_id": 123456789, // optional
  "level": 0 // optional, defaults to 0
}
```

#### Remove User from Inbound
- `DELETE /servers/{server_id}/inbounds/{inbound_id}/users/{email}` - Remove user access

#### Get Inbound Client Configurations  
- `GET /servers/{server_id}/inbounds/{inbound_id}/configs` - Get all client configuration URIs for an inbound

**Response:**
```json
[
  {
    "user_id": "uuid",
    "server_name": "string",
    "inbound_tag": "string",
    "protocol": "vmess|vless|trojan|shadowsocks", 
    "uri": "protocol://uri_string",
    "qr_code": null
  }
]
```

### Certificates

#### List Certificates
- `GET /certificates` - Get all certificates

#### Get Certificate
- `GET /certificates/{id}` - Get certificate by ID

#### Create Certificate
- `POST /certificates` - Create new certificate

**Request:**
```json
{
  "name": "Certificate Name",
  "cert_type": "self_signed|letsencrypt",
  "domain": "example.com", 
  "auto_renew": true,
  "certificate_pem": "-----BEGIN CERTIFICATE-----...",
  "private_key": "-----BEGIN PRIVATE KEY-----..."
}
```

#### Update Certificate
- `PUT /certificates/{id}` - Update certificate

**Request:** (all fields optional)
```json
{
  "name": "New Certificate Name",
  "auto_renew": false
}
```

#### Delete Certificate
- `DELETE /certificates/{id}` - Delete certificate

#### Get Certificate Details
- `GET /certificates/{id}/details` - Get detailed certificate information

#### Get Expiring Certificates
- `GET /certificates/expiring` - Get certificates that are expiring soon

### Templates

#### List Templates
- `GET /templates` - Get all inbound templates

#### Get Template
- `GET /templates/{id}` - Get template by ID

#### Create Template
- `POST /templates` - Create new inbound template

**Request:**
```json
{
  "name": "Template Name",
  "protocol": "vmess|vless|trojan|shadowsocks",
  "default_port": 8080,
  "requires_tls": true,
  "config_template": "JSON template string"
}
```

#### Update Template
- `PUT /templates/{id}` - Update template

**Request:** (all fields optional)
```json
{
  "name": "New Template Name",
  "description": "Template description", 
  "default_port": 8081,
  "base_settings": {},
  "stream_settings": {},
  "requires_tls": false,
  "requires_domain": true,
  "variables": [],
  "is_active": true
}
```

#### Delete Template
- `DELETE /templates/{id}` - Delete template

## Response Format

### User Object
```json
{
  "id": "uuid",
  "name": "string",
  "comment": "string|null", 
  "telegram_id": "number|null",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Users List Response
```json
{
  "users": [UserObject],
  "total": 100,
  "page": 1,
  "per_page": 20
}
```

### Server Object
```json
{
  "id": "uuid",
  "name": "string", 
  "hostname": "string",
  "grpc_hostname": "string",
  "grpc_port": 2053,
  "status": "online|offline|error|unknown",
  "default_certificate_id": "uuid|null",
  "created_at": "timestamp",
  "updated_at": "timestamp", 
  "has_credentials": true
}
```

### Server Inbound Object
```json
{
  "id": "uuid",
  "server_id": "uuid",
  "template_id": "uuid", 
  "template_name": "string",
  "tag": "string",
  "port_override": 8080,
  "certificate_id": "uuid|null",
  "variable_values": {},
  "is_active": true,
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Certificate Object
```json
{
  "id": "uuid",
  "name": "string",
  "cert_type": "self_signed|letsencrypt", 
  "domain": "string",
  "auto_renew": true,
  "expires_at": "timestamp|null",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Template Object  
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string|null",
  "protocol": "vmess|vless|trojan|shadowsocks",
  "default_port": 8080,
  "base_settings": {},
  "stream_settings": {},
  "requires_tls": true,
  "requires_domain": false,
  "variables": [],
  "is_active": true,
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Inbound User Object
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "server_inbound_id": "uuid",
  "xray_user_id": "string",
  "password": "string|null",
  "level": 0,
  "is_active": true,
  "created_at": "timestamp", 
  "updated_at": "timestamp"
}
```

## Status Codes
- `200` - Success
- `201` - Created  
- `204` - No Content (successful deletion)
- `400` - Bad Request (invalid data)
- `404` - Not Found
- `409` - Conflict (duplicate data, e.g. telegram_id)
- `500` - Internal Server Error

## Error Response Format
```json
{
  "error": "Error message description",
  "code": "ERROR_CODE",
  "details": "Additional error details"
}
```

## Telegram Bot Integration

OutFleet includes a Telegram bot for user management and configuration access.

### User Management Endpoints

#### List User Requests
- `GET /api/user-requests` - Get all user access requests
- `GET /api/user-requests?status=pending` - Get pending requests only

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid|null", 
      "telegram_id": 123456789,
      "telegram_username": "username",
      "telegram_first_name": "John",
      "telegram_last_name": "Doe",
      "full_name": "John Doe",
      "telegram_link": "@username",
      "status": "pending|approved|declined",
      "request_message": "Access request message",
      "response_message": "Admin response",
      "processed_by_user_id": "uuid|null",
      "processed_at": "timestamp|null",
      "created_at": "timestamp",
      "updated_at": "timestamp"
    }
  ],
  "total": 50,
  "page": 1,
  "per_page": 20
}
```

#### Get User Request
- `GET /api/user-requests/{id}` - Get specific user request

#### Approve User Request
- `POST /api/user-requests/{id}/approve` - Approve user access request

**Request:**
```json
{
  "response_message": "Welcome! Your access has been approved."
}
```

**Response:** Updated user request object

**Side Effects:**
- Creates a new user account
- Sends Telegram notification with main menu to the user

#### Decline User Request  
- `POST /api/user-requests/{id}/decline` - Decline user access request

**Request:**
```json
{
  "response_message": "Sorry, your request has been declined."
}
```

**Response:** Updated user request object

**Side Effects:**
- Sends Telegram notification to the user

#### Delete User Request
- `DELETE /api/user-requests/{id}` - Delete user request

### Telegram Bot Configuration

#### Get Telegram Status
- `GET /api/telegram/status` - Get bot status and configuration

**Response:**
```json
{
  "is_running": true,
  "config": {
    "id": "uuid",
    "name": "Bot Name",
    "bot_token": "masked",
    "is_active": true,
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
}
```

#### Create/Update Telegram Config
- `POST /api/telegram/config` - Create new bot configuration
- `PUT /api/telegram/config/{id}` - Update bot configuration

**Request:**
```json
{
  "name": "OutFleet Bot",
  "bot_token": "bot_token_from_botfather",
  "is_active": true
}
```

#### Telegram Admin Management
- `GET /api/telegram/admins` - Get all Telegram admins
- `POST /api/telegram/admins/{user_id}` - Add user as Telegram admin
- `DELETE /api/telegram/admins/{user_id}` - Remove user from Telegram admins

### Telegram Bot Features

#### User Flow
1. **Request Access**: Users send `/start` to the bot and request VPN access
2. **Admin Approval**: Admins receive notifications and can approve/decline via Telegram or web interface
3. **Configuration Access**: Approved users get access to:
   - **🔗 Subscription Link**: Personal subscription URL (`/sub/{user_id}`)
   - **⚙️ My Configs**: Individual configuration management  
   - **💬 Support**: Contact support

#### Admin Features
- **📋 User Requests**: View and manage pending access requests
- **📊 Statistics**: View system statistics
- **📢 Broadcast**: Send messages to all users
- **Approval Workflow**: Approve/decline requests with server selection

#### Subscription Link Integration
When users click "🔗 Subscription Link" in the Telegram bot, they receive:
- Personal subscription URL: `{BASE_URL}/sub/{user_id}`
- Instructions in their preferred language (Russian/English)
- Automatic updates when configurations change

**Environment Variables:**
- `BASE_URL` - Base URL for subscription links (default: `http://localhost:8080`)

### Bot Commands
- `/start` - Start bot and show main menu
- `/requests` - [Admin] View pending user requests  
- `/stats` - [Admin] Show system statistics
- `/broadcast <message>` - [Admin] Send message to all users