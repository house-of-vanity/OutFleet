// Xray Inbound Auto-Fill Helper
console.log('Xray inbound helper script loaded');

// Protocol configurations based on Xray documentation
const protocolConfigs = {
    'vless': {
        port: 443,
        network: 'tcp',
        security: 'tls',
        description: 'VLESS - Lightweight protocol with UUID authentication'
    },
    'vmess': {
        port: 443,
        network: 'ws',
        security: 'tls',
        description: 'VMess - V2Ray protocol with encryption and authentication'
    },
    'trojan': {
        port: 443,
        network: 'tcp',
        security: 'tls',
        description: 'Trojan - TLS-based protocol mimicking HTTPS traffic'
    },
    'shadowsocks': {
        port: 8388,
        network: 'tcp',
        security: 'none',
        ss_method: 'aes-256-gcm',
        description: 'Shadowsocks - SOCKS5 proxy with encryption'
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM ready, initializing Xray helper');
    
    // Add help text and generate buttons
    addHelpText();
    addGenerateButtons();
    
    // Watch for protocol field changes
    const protocolField = document.getElementById('id_protocol');
    if (protocolField) {
        protocolField.addEventListener('change', function() {
            handleProtocolChange(this.value);
        });
        
        // Auto-fill on initial load if new inbound
        if (protocolField.value && isNewInbound()) {
            handleProtocolChange(protocolField.value);
        }
    }
});

function isNewInbound() {
    // Check if this is a new inbound (no port value set)
    const portField = document.getElementById('id_port');
    return !portField || !portField.value;
}

function handleProtocolChange(protocol) {
    if (!protocol || !protocolConfigs[protocol]) {
        return;
    }
    
    const config = protocolConfigs[protocol];
    
    // Only auto-fill for new inbounds to avoid overwriting user data
    if (isNewInbound()) {
        console.log('Auto-filling fields for new', protocol, 'inbound');
        autoFillFields(protocol, config);
        showMessage(`Auto-filled ${protocol.toUpperCase()} configuration`, 'info');
    }
}

function autoFillFields(protocol, config) {
    // Fill basic fields only if they're empty
    fillIfEmpty('id_port', config.port);
    fillIfEmpty('id_network', config.network);
    fillIfEmpty('id_security', config.security);
    
    // Protocol-specific fields
    if (config.ss_method && protocol === 'shadowsocks') {
        fillIfEmpty('id_ss_method', config.ss_method);
    }
    
    // Generate helpful JSON configs
    generateJsonConfigs(protocol, config);
}

function fillIfEmpty(fieldId, value) {
    const field = document.getElementById(fieldId);
    if (field && !field.value && value !== undefined) {
        field.value = value;
        field.dispatchEvent(new Event('change', { bubbles: true }));
    }
}

function generateJsonConfigs(protocol, config) {
    // Generate stream settings
    const streamField = document.getElementById('id_stream_settings');
    if (streamField && !streamField.value) {
        const streamSettings = getStreamSettings(protocol, config.network);
        if (streamSettings) {
            streamField.value = JSON.stringify(streamSettings, null, 2);
        }
    }
    
    // Generate sniffing settings
    const sniffingField = document.getElementById('id_sniffing_settings');
    if (sniffingField && !sniffingField.value) {
        const sniffingSettings = {
            enabled: true,
            destOverride: ['http', 'tls'],
            metadataOnly: false
        };
        sniffingField.value = JSON.stringify(sniffingSettings, null, 2);
    }
}

function getStreamSettings(protocol, network) {
    const settings = {};
    
    switch (network) {
        case 'ws':
            settings.wsSettings = {
                path: '/ws',
                headers: {
                    Host: 'example.com'
                }
            };
            break;
        case 'grpc':
            settings.grpcSettings = {
                serviceName: 'GunService'
            };
            break;
        case 'h2':
            settings.httpSettings = {
                host: ['example.com'],
                path: '/path'
            };
            break;
        case 'tcp':
            settings.tcpSettings = {
                header: {
                    type: 'none'
                }
            };
            break;
        case 'kcp':
            settings.kcpSettings = {
                mtu: 1350,
                tti: 50,
                uplinkCapacity: 5,
                downlinkCapacity: 20,
                congestion: false,
                readBufferSize: 2,
                writeBufferSize: 2,
                header: {
                    type: 'none'
                }
            };
            break;
    }
    
    return Object.keys(settings).length > 0 ? settings : null;
}

function addHelpText() {
    // Add help text to complex fields
    addFieldHelp('id_stream_settings', 
        'Transport settings: TCP (none), WebSocket (path/host), gRPC (serviceName), etc. Format: JSON');
    
    addFieldHelp('id_sniffing_settings', 
        'Traffic sniffing for routing: enabled, destOverride ["http","tls"], metadataOnly');
    
    addFieldHelp('id_tls_cert_file', 
        'TLS certificate file path (required for TLS security). Example: /path/to/cert.pem');
    
    addFieldHelp('id_tls_key_file', 
        'TLS private key file path (required for TLS security). Example: /path/to/key.pem');
    
    addFieldHelp('id_protocol', 
        'VLESS: lightweight + UUID | VMess: V2Ray encrypted | Trojan: HTTPS-like | Shadowsocks: SOCKS5');
    
    addFieldHelp('id_network', 
        'Transport: tcp (direct), ws (WebSocket), grpc (HTTP/2), h2 (HTTP/2), kcp (mKCP)');
    
    addFieldHelp('id_security', 
        'Encryption: none (no TLS), tls (standard TLS), reality (advanced steganography)');
}

function addFieldHelp(fieldId, helpText) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    
    const helpDiv = document.createElement('div');
    helpDiv.className = 'help';
    helpDiv.style.cssText = 'font-size: 11px; color: #666; margin-top: 2px; line-height: 1.3;';
    helpDiv.textContent = helpText;
    
    field.parentNode.appendChild(helpDiv);
}

function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `alert alert-${type}`;
    messageDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        padding: 12px 20px;
        border-radius: 4px;
        background: ${type === 'success' ? '#d4edda' : '#cce7ff'};
        border: 1px solid ${type === 'success' ? '#c3e6cb' : '#b8daff'};
        color: ${type === 'success' ? '#155724' : '#004085'};
        font-weight: 500;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    `;
    messageDiv.textContent = message;
    
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.remove();
    }, 3000);
}

// Helper functions for generating values
function generateRandomString(length = 8) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

function generateShortId() {
    return Math.random().toString(16).substr(2, 8);
}

function suggestPort(protocol) {
    const ports = {
        'vless': [443, 8443, 2053, 2083],
        'vmess': [443, 80, 8080, 8443],
        'trojan': [443, 8443, 2087],
        'shadowsocks': [8388, 1080, 8080]
    };
    const protocolPorts = ports[protocol] || [443];
    return protocolPorts[Math.floor(Math.random() * protocolPorts.length)];
}

// Add generate buttons to fields
function addGenerateButtons() {
    console.log('Adding generate buttons');
    
    // Add tag generator
    addGenerateButton('id_tag', '🎲', () => `inbound-${generateShortId()}`);
    
    // Add port suggestion based on protocol
    addGenerateButton('id_port', '🎯', () => {
        const protocol = document.getElementById('id_protocol')?.value;
        return suggestPort(protocol);
    });
}

function addGenerateButton(fieldId, icon, generator) {
    const field = document.getElementById(fieldId);
    if (!field || field.nextElementSibling?.classList.contains('generate-btn')) return;
    
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'generate-btn btn btn-sm btn-secondary';
    button.innerHTML = icon;
    button.title = 'Generate value';
    button.style.cssText = 'margin-left: 5px; padding: 2px 6px; font-size: 12px;';
    
    button.addEventListener('click', () => {
        const value = generator();
        field.value = value;
        showMessage(`Generated: ${value}`, 'success');
        field.dispatchEvent(new Event('change', { bubbles: true }));
    });
    
    field.parentNode.insertBefore(button, field.nextSibling);
}