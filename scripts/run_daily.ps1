$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Split-Path -Parent $ScriptDir
Set-Location $AppDir

New-Item -ItemType Directory -Force -Path "logs", "reports", "data" | Out-Null

$RunDate = Get-Date -Format "yyyy-MM-dd"
$LogPath = Join-Path $AppDir "logs\daily_$RunDate.log"
$LockPath = Join-Path $AppDir "data\run_daily.lock"
$LockStream = $null

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $LogPath -Value $line
    Write-Output $line
}

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Log "warning: .env not found"
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($key) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Log ".env loaded"
}

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    Write-Log "-- $Name --"
    & $PythonBin @Arguments 2>&1 | ForEach-Object { Add-Content -Path $LogPath -Value $_; Write-Output $_ }
    $status = $LASTEXITCODE
    if ($status -ne 0) {
        Write-Log "$Name failed with status $status; continuing"
    }
    return $status
}

try {
    $LockStream = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $LockStream.SetLength(0)
    $LockWriter = New-Object System.IO.StreamWriter($LockStream)
    $LockWriter.WriteLine("pid=$PID")
    $LockWriter.WriteLine("started_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    $LockWriter.Flush()
    $LockStream.Flush()
} catch {
    Write-Log "another app-store-monitor daily run is already active; skipping"
    exit 0
}

try {
    Write-Log "== app-store-monitor daily start =="
    Write-Log "working_directory=$AppDir"

    Import-DotEnv -Path (Join-Path $AppDir ".env")

    $PythonBin = if ($env:PYTHON) { $env:PYTHON } else { "python" }
    Write-Log "date_strategy=latest_fetchable_daily_segment"

    Invoke-Step -Name "check-config" -Arguments @("-m", "src.cli", "check-config") | Out-Null
    Invoke-Step -Name "sync-apps" -Arguments @("-m", "src.cli", "sync-apps") | Out-Null
    Invoke-Step -Name "create-report-request" -Arguments @("-m", "src.cli", "create-report-request", "--all") | Out-Null
    Invoke-Step -Name "fetch" -Arguments @("-m", "src.cli", "fetch", "--latest", "--all") | Out-Null

    $reportArgs = @("-m", "src.cli", "report", "--latest", "--print")
    if ($env:DISCORD_ENABLED -eq "true") {
        $reportArgs += "--notify"
        $reportArgs += "--notify-once"
        Write-Log "discord notification enabled with once-per-metric-date guard"
    } else {
        Write-Log "discord notification disabled"
    }
    Invoke-Step -Name "report" -Arguments $reportArgs | Out-Null

    Write-Log "== app-store-monitor daily end =="
} finally {
    if ($LockStream) {
        $LockStream.Close()
        Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue
    }
}

# Keep Task Scheduler green while fetch/report availability stabilizes. Failures are logged above.
exit 0
