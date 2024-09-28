# Path to log file
$logFile = $args[3]

# Function to log messages
function Log-Message {
    param (
        [string]$message
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $message" | Out-File -Append -FilePath $logFile
}

if ($args.Count -lt 2) {
    Log-Message "Usage: windows_task.ps1 <url> <sslocal_path> <comment> <log_file>"
    exit 1
}

$url = $args[0]
$sslocalPath = $args[1]
$localPort = $args[2]

$localAddr = "localhost"
$checkInterval = 60
$previousPassword = ""

# Function to start sslocal
function Start-SSLocal {
    param (
        [string]$method,
        [string]$password,
        [string]$server,
        [int]$serverPort
    )
    
    # Form the Shadowsocks connection string
    $credentials = "${method}:${password}@${server}:${serverPort}"
    $encodedCredentials = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($credentials))
    $ssUrl = "ss://$encodedCredentials"

    # Kill any existing sslocal process
    Get-Process sslocal -ErrorAction SilentlyContinue | Stop-Process -Force

    # Log the sslocal restart
    Log-Message "Starting sslocal with method: $method, server: $server, port: $serverPort"

    # Start sslocal with the provided arguments
    Start-Process -NoNewWindow -FilePath $sslocalPath -ArgumentList "--local-addr ${localAddr}:${localPort} --server-url $ssUrl"
}

# Main loop
while ($true) {
    try {
        # Download and parse the JSON
        $jsonContent = Invoke-WebRequest -Uri $url -UseBasicParsing | Select-Object -ExpandProperty Content
        $json = $jsonContent | ConvertFrom-Json

        # Extract the necessary fields
        $method = $json.method
        $password = $json.password
        $server = $json.server
        $serverPort = $json.server_port

        # Log current password and server information
        Log-Message "Checking server: $server, port: $serverPort"

        # Check if the password has changed
        if ($password -ne $previousPassword) {
            # Start/restart sslocal
            Start-SSLocal -method $method -password $password -server $server -serverPort $serverPort
            $previousPassword = $password
            Log-Message "Password changed, restarting sslocal."
        } else {
            Log-Message "Password has not changed."
        }

    } catch {
        Log-Message "Error occurred: $_"
    }

    # Wait for the next check
    Start-Sleep -Seconds $checkInterval
}
