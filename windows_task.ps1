if ($args.Count -lt 2) {
    Write-Host "Usage: windows_task.ps1 <url> <sslocal_path> <comment>"
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
    Write-Host "Starting sslocal with method: $method, server: $server, port: $serverPort"

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
        Write-Host "Checking server: $server, port: $serverPort"

        # Check if the password has changed
        if ($password -ne $previousPassword) {
            # Start/restart sslocal
            Start-SSLocal -method $method -password $password -server $server -serverPort $serverPort
            $previousPassword = $password
            Write-Host "Password changed, restarting sslocal."
        } else {
            Write-Host "Password has not changed."
        }

    } catch {
        Write-Host "Error occurred: $_"
    }

    # Wait for the next check
    Start-Sleep -Seconds $checkInterval
}
