# LLM Project Context - Xray Admin Panel

## Project Overview
Rust-based administration panel for managing xray-core VPN proxy servers. Uses real gRPC integration with xray-core library for server communication.

## Current Architecture

### Core Technologies
- **Language**: Rust (edition 2021)
- **Web Framework**: Axum with tower-http
- **Database**: PostgreSQL with Sea-ORM
- **Xray Integration**: xray-core 0.2.1 library with real gRPC communication
- **Frontend**: Vanilla HTML/CSS/JS with toast notifications

### Module Structure
```
src/
├── config/          # Configuration management (args, env, file)
├── database/        # Sea-ORM entities, repositories, migrations
├── services/        # Business logic (xray gRPC client, certificates)
├── web/             # Axum handlers and routes
└── main.rs          # Application entry point
```

## Key Features Implemented

### 1. Database Entities
- **Users**: Basic user management
- **Servers**: Xray server definitions with gRPC endpoints
- **Certificates**: TLS certificates with PEM storage (binary format)
- **InboundTemplates**: Reusable inbound configurations
- **ServerInbounds**: Template bindings to servers with ports/certificates

### 2. Xray gRPC Integration
**Location**: `src/services/xray/client.rs`
- Real xray-core library integration (NOT mock/CLI)
- Methods: `add_inbound_with_certificate()`, `remove_inbound()`, `get_stats()`
- **CRITICAL**: TLS certificate configuration via streamSettings with proper protobuf messages
- Supports VLESS, VMess, Trojan, Shadowsocks protocols

### 3. Certificate Management
**Location**: `src/database/entities/certificate.rs`
- Self-signed certificate generation using rcgen
- Binary storage (cert_data, key_data as Vec<u8>)
- PEM conversion methods: `certificate_pem()`, `private_key_pem()`
- Separate endpoints: `/certificates/{id}` (basic) and `/certificates/{id}/details` (with PEM)

### 4. Template-Based Architecture
Templates define reusable inbound configurations that can be bound to servers with:
- Port overrides
- Certificate assignments
- Active/inactive states

## Current Status & Issues

### ✅ Working Features
- Complete CRUD for all entities
- Real xray gRPC communication with TLS certificate support
- Toast notification system (absolute positioning)
- Modal-based editing interface
- Password masking in database URL logging
- Certificate details display with PEM content

### 🔧 Recent Fixes
- **StreamConfig Integration**: Fixed TLS certificate configuration in xray gRPC calls
- **Certificate Display**: Added `/certificates/{id}/details` endpoint for PEM viewing
- **Active/Inactive Management**: Inbounds automatically added/removed from xray when toggled

### ⚠️ Current Issue
User reported certificate details still showing "Not available" - this was just fixed with the new `/certificates/{id}/details` endpoint.

## API Structure

### Endpoints
```
/api/users/*           # User management
/api/servers/*         # Server management
/api/servers/{id}/inbounds/*  # Server inbound management
/api/certificates/*    # Certificate management (basic)
/api/certificates/{id}/details  # Certificate details with PEM
/api/templates/*       # Template management
```

## Configuration
- **Default port**: 8080 (user tested on 8082)
- **Database**: PostgreSQL with auto-migration
- **Environment variables**: XRAY_ADMIN__* prefix
- **Config file**: config.toml support

## Testing Commands
```bash
# Run application
cargo run -- --host 0.0.0.0 --port 8082

# Test xray integration
xray api lsi --server 100.91.97.36:10085

# Check compilation
cargo check
```

## Key Implementation Details

### Xray TLS Configuration
**Location**: `src/services/xray/client.rs:185-194`
```rust
let stream_config = StreamConfig {
    protocol_name: "tcp".to_string(),
    security_type: "tls".to_string(),
    security_settings: vec![tls_message],
    // ... other fields
};
```

### Certificate Data Flow
1. User creates certificate via web interface
2. PEM data stored as binary in database (cert_data, key_data)
3. When creating inbound, certificate fetched and converted back to PEM
4. PEM passed to xray gRPC client for TLS configuration

### Database Migrations
Auto-migration enabled by default. All entities use UUID primary keys with timestamps.

## Development Notes
- **User prefers English in code/comments**
- **No emoji usage unless explicitly requested**
- **Prefer editing existing files over creating new ones**
- **Real xray-core integration required** (user specifically asked not to abandon it)
- **Application tested with actual xray server at 100.91.97.36:10085**

## Last Working State
All features implemented and compiling. StreamConfig properly configured for TLS certificate transmission to xray servers. Certificate viewing endpoint fixed for PEM display.