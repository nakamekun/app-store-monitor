param(
    [string]$TaskName = "App Store Monitor Daily"
)

$ErrorActionPreference = "Stop"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Output "Unregistered scheduled task: $TaskName"
