// Server status check functionality for admin
document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners to all check status buttons
    document.querySelectorAll('.check-status-btn').forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const serverId = this.dataset.serverId;
            const serverName = this.dataset.serverName;
            const serverType = this.dataset.serverType;
            const originalText = this.textContent;
            const originalColor = this.style.background;
            
            // Show loading state
            this.textContent = '⏳ Checking...';
            this.style.background = '#6c757d';
            this.disabled = true;
            
            try {
                // Try AJAX request first
                const response = await fetch(`/admin/vpn/server/${serverId}/check-status/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    // Update button based on status
                    if (data.status === 'online') {
                        this.textContent = '✅ Online';
                        this.style.background = '#28a745';
                    } else if (data.status === 'offline') {
                        this.textContent = '❌ Offline';
                        this.style.background = '#dc3545';
                    } else if (data.status === 'error') {
                        this.textContent = '⚠️ Error';
                        this.style.background = '#fd7e14';
                    } else {
                        this.textContent = '❓ Unknown';
                        this.style.background = '#6c757d';
                    }
                    
                    // Show additional info if available
                    if (data.message) {
                        this.title = data.message;
                    }
                    
                } else {
                    throw new Error(data.error || 'Failed to check status');
                }
                
            } catch (error) {
                console.error('Error checking server status:', error);
                
                // Fallback: show basic server info
                this.textContent = `📊 ${serverType}`;
                this.style.background = '#17a2b8';
                this.title = `Server: ${serverName} (${serverType}) - Status check failed: ${error.message}`;
            }
            
            // Reset after 5 seconds in all cases
            setTimeout(() => {
                this.textContent = originalText;
                this.style.background = originalColor;
                this.title = '';
                this.disabled = false;
            }, 5000);
        });
    });
});

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
