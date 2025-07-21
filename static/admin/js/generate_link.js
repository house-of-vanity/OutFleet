// static/admin/js/generate_uuid.js

function generateLink(button) {
    let row = button.closest('tr');
    let inputField = row.querySelector('input[name$="link"]');

    if (inputField) {
        inputField.value = generateRandomString(16);
    }
}

function generateRandomString(length) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

// OutlineServer JSON Configuration Functionality
document.addEventListener('DOMContentLoaded', function() {
    
    // JSON Import functionality
    const importJsonBtn = document.getElementById('import-json-btn');
    const importJsonTextarea = document.getElementById('import-json-config');
    
    if (importJsonBtn && importJsonTextarea) {
        // Auto-fill on paste event
        importJsonTextarea.addEventListener('paste', function(e) {
            // Small delay to let paste complete
            setTimeout(() => {
                tryAutoFillFromJson();
            }, 100);
        });
        
        // Manual import button
        importJsonBtn.addEventListener('click', function() {
            tryAutoFillFromJson();
        });
        
        function tryAutoFillFromJson() {
            try {
                const jsonText = importJsonTextarea.value.trim();
                if (!jsonText) {
                    alert('Please enter JSON configuration');
                    return;
                }
                
                const config = JSON.parse(jsonText);
                
                // Validate required fields
                if (!config.apiUrl || !config.certSha256) {
                    alert('Invalid JSON format. Required fields: apiUrl, certSha256');
                    return;
                }
                
                // Parse apiUrl to extract components
                const url = new URL(config.apiUrl);
                
                // Fill form fields
                const adminUrlField = document.getElementById('id_admin_url');
                const adminCertField = document.getElementById('id_admin_access_cert');
                const clientHostnameField = document.getElementById('id_client_hostname');
                const clientPortField = document.getElementById('id_client_port');
                const nameField = document.getElementById('id_name');
                const commentField = document.getElementById('id_comment');
                
                if (adminUrlField) adminUrlField.value = config.apiUrl;
                if (adminCertField) adminCertField.value = config.certSha256;
                
                // Use provided hostname or extract from URL
                const hostname = config.clientHostname || config.hostnameForAccessKeys || url.hostname;
                if (clientHostnameField) clientHostnameField.value = hostname;
                
                // Use provided port or extract from various sources
                const clientPort = config.clientPort || config.portForNewAccessKeys || url.port || '1257';
                if (clientPortField) clientPortField.value = clientPort;
                
                // Generate server name if not provided and field is empty
                if (nameField && !nameField.value) {
                    const serverName = config.serverName || config.name || `Outline-${hostname}`;
                    nameField.value = serverName;
                }
                
                // Fill comment if provided and field exists
                if (commentField && config.comment) {
                    commentField.value = config.comment;
                }
                
                // Clear the JSON input
                importJsonTextarea.value = '';
                
                // Show success message
                showSuccessMessage('✅ Configuration imported successfully!');
                
            } catch (error) {
                alert('Invalid JSON format: ' + error.message);
            }
        }
    }
    
    // Copy to clipboard functionality
    window.copyToClipboard = function(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            const text = element.textContent || element.innerText;
            
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(() => {
                    showCopySuccess();
                }).catch(err => {
                    fallbackCopyTextToClipboard(text);
                });
            } else {
                fallbackCopyTextToClipboard(text);
            }
        }
    };
    
    function fallbackCopyTextToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            showCopySuccess();
        } catch (err) {
            console.error('Failed to copy text: ', err);
        }
        
        document.body.removeChild(textArea);
    }
    
    function showCopySuccess() {
        showSuccessMessage('📋 Copied to clipboard!');
    }
    
    function showSuccessMessage(message) {
        const alertHtml = `
            <div class="alert alert-success alert-dismissible" style="margin: 1rem 0;">
                ${message}
                <button type="button" class="close" aria-label="Close" onclick="this.parentElement.remove()">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `;
        
        // Try to find a container for the message
        const container = document.querySelector('.card-body') || document.querySelector('#content-main');
        if (container) {
            container.insertAdjacentHTML('afterbegin', alertHtml);
        }
        
        setTimeout(() => {
            const alert = document.querySelector('.alert-success');
            if (alert) alert.remove();
        }, 5000);
    }
    
    // Sync server button - handle both static and dynamic buttons
    document.addEventListener('click', async function(e) {
        if (e.target && (e.target.id === 'sync-server-btn' || e.target.matches('[id="sync-server-btn"]'))) {
            const syncBtn = e.target;
            const serverId = syncBtn.dataset.serverId;
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
            const originalText = syncBtn.textContent;
            syncBtn.textContent = '⏳ Syncing...';
            syncBtn.disabled = true;
            
            try {
                const response = await fetch(`/admin/vpn/outlineserver/${serverId}/sync/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': csrfToken
                    }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccessMessage(`✅ ${data.message}`);
                    setTimeout(() => window.location.reload(), 2000);
                } else {
                    alert('Sync failed: ' + data.error);
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            } finally {
                syncBtn.textContent = originalText;
                syncBtn.disabled = false;
            }
        }
    });
});
