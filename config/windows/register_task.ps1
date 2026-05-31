param(
    [string]$TaskName = "App Store Monitor Daily",
    [string]$ProjectDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectDir) {
    $ProjectDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
}
$ProjectDir = (Resolve-Path $ProjectDir).Path

$ScriptPath = Join-Path $ProjectDir "scripts\run_daily.ps1"
if (-not (Test-Path $ScriptPath)) {
    throw "run_daily.ps1 not found: $ScriptPath"
}

$ExistingTasks = @(Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
foreach ($Task in $ExistingTasks) {
    Unregister-ScheduledTask -TaskName $Task.TaskName -TaskPath $Task.TaskPath -Confirm:$false
}

$SimilarTasks = @(
    Get-ScheduledTask -ErrorAction SilentlyContinue |
        Where-Object {
            $_.TaskName -ne $TaskName -and (
                $_.TaskName -like "*App Store*" -or
                $_.TaskName -like "*AppStore*"
            )
        }
)

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Daily -At 8:30AM
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Run app-store-monitor daily at 8:30" `
    -Force | Out-Null

Write-Output "Registered scheduled task: $TaskName"
if ($ExistingTasks.Count -gt 0) {
    Write-Output "Replaced existing scheduled task entries: $($ExistingTasks.Count)"
}
if ($SimilarTasks.Count -gt 0) {
    Write-Output "Similar scheduled tasks found; review manually if duplicate notifications continue:"
    foreach ($Task in $SimilarTasks) {
        Write-Output "- $($Task.TaskPath)$($Task.TaskName)"
    }
}
Write-Output "ProjectDir: $ProjectDir"
Write-Output "ScriptPath: $ScriptPath"
Write-Output "Schedule: daily 08:30"
