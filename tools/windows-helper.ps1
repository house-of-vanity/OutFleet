$url = Read-Host "Please enter the URL for the JSON configuration"
$comment = Read-Host "Comment [server, country, etc]"
$port = Read-Host "Please enter the port to use for sslocal"

$version = "1.21.0"
$archiveUrl = "https://github.com/shadowsocks/shadowsocks-rust/releases/download/v${version}/shadowsocks-v${version}.x86_64-pc-windows-gnu.zip"
$downloadPath = "$HOME\shadowsocks-rust\shadowsocks.zip"
$extractPath = "$HOME\shadowsocks-rust"
$scriptUrl = "https://raw.githubusercontent.com/house-of-vanity/OutFleet/refs/heads/master/tools/windows_task.ps1"
$cmdFilePath = "$extractPath\run_${comment}.cmd"
$taskName = "Shadowsocks_Task_${comment}"
$logFile = "$extractPath\Log_${comment}.log"


if ($url -notmatch "^[a-z]+://") {
    $url = "https://$url"
} elseif ($url -like "ssconf://*") {
    $url = $url -replace "^ssconf://", "https://"
}

function Test-Admin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-Not (Test-Admin)) {
    Write-Host "Error: This script requires administrator privileges. Please run PowerShell as administrator." -ForegroundColor Red
    exit 1
}

# Ensure the extraction directory exists
if (-Not (Test-Path -Path $extractPath)) {
    New-Item -ItemType Directory -Path $extractPath
}

# Download the archive
Invoke-WebRequest -Uri $archiveUrl -OutFile $downloadPath

# Extract the archive
Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force

# Check if sslocal.exe exists
if (-Not (Test-Path -Path "$extractPath\sslocal.exe")) {
    Write-Host "Error: sslocal.exe not found in $extractPath" -ForegroundColor Red
    exit 1
}

# Download the windows_task.ps1 script
Invoke-WebRequest -Uri $scriptUrl -OutFile "$extractPath\windows_task.ps1"

# Build Batch file content
$batchContent = @"
@echo off
set scriptPath=""$extractPath\windows_task.ps1""
powershell.exe -ExecutionPolicy Bypass -File %scriptPath% ""$url"" ""$extractPath\sslocal.exe"" ""$port""
"@


$batchContent | Set-Content -Path $cmdFilePath

# Create or update Task Scheduler
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmdFilePath > $logFile"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Check if the task already exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Task $taskName already exists. Updating the task..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Register the new or updated task
Register-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -TaskName $taskName

Write-Host "Task $taskName has been created/updated successfully."

# Optionally, start the task immediately
Start-ScheduledTask -TaskName $taskName
Write-Host "Task $taskName has been started."
