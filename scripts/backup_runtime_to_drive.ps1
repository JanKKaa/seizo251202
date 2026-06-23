param(
    [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$BackupDir = "backup_db\daily",
    [string]$RcloneRemote = "gdrive:seizo0-backups",
    [string]$DriveFolder = "",
    [int]$KeepLocalDays = 14,
    [int]$KeepBackupCount = 2,
    [switch]$SkipUpload,
    [switch]$NoMedia,
    [switch]$FullRuntime,
    [switch]$MinimalRuntime,
    [switch]$IncludeEnv
)

$ErrorActionPreference = "Stop"

Set-Location $ProjectDir

$fullBackupDir = Join-Path $ProjectDir $BackupDir
New-Item -ItemType Directory -Force -Path $fullBackupDir | Out-Null

$logDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "daily_backup.log"

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $logFile -Value $line
    Write-Host $line
}

function Resolve-DriveBackupFolder {
    param([string]$ConfiguredFolder)

    if ($ConfiguredFolder) {
        $parent = Split-Path -Parent $ConfiguredFolder
        if ($parent -and (Test-Path -LiteralPath $parent)) {
            return $ConfiguredFolder
        }
    }

    $japaneseMyDrive = -join ([char[]](0x30DE, 0x30A4, 0x30C9, 0x30E9, 0x30A4, 0x30D6))
    $myDriveNames = @($japaneseMyDrive, "My Drive", "Google Drive")
    $driveRoots = Get-PSDrive -PSProvider FileSystem |
        Where-Object { $_.Root -match '^[A-Z]:\\$' } |
        ForEach-Object { $_.Root }

    foreach ($root in $driveRoots) {
        foreach ($name in $myDriveNames) {
            $candidateRoot = Join-Path $root $name
            if (Test-Path -LiteralPath $candidateRoot) {
                return (Join-Path $candidateRoot "seizo0-backups")
            }
        }
    }

    return $ConfiguredFolder
}

$DriveFolder = Resolve-DriveBackupFolder -ConfiguredFolder $DriveFolder

Write-Log "Backup start"

function Invoke-NativeAndLog {
    param(
        [string]$Exe,
        [string[]]$ArgList
    )
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Exe @ArgList 2>&1 | ForEach-Object { Write-Log $_ }
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

$dockerArgs = @(
    "run", "--rm",
    "--network", "trang_chu_default",
    "-v", "${ProjectDir}:/app",
    "-w", "/app",
    "-e", "DJANGO_SETTINGS_MODULE=trang_chu.settings"
)

$envFile = Join-Path $ProjectDir ".env"
if (Test-Path $envFile) {
    $dockerArgs += @("--env-file", $envFile)
}

$dockerArgs += @(
    "seizo0-django:latest",
    "python", "manage.py", "backup_runtime_data",
    "--output-dir", "/app/backup_db/daily",
    "--keep-local-days", "$KeepLocalDays",
    "--keep-local-count", "$KeepBackupCount"
)

if ($IncludeEnv) {
    $dockerArgs += "--include-env"
}

if ($NoMedia) {
    $dockerArgs += "--no-media"
}

if ($FullRuntime -or -not $MinimalRuntime) {
    $dockerArgs += "--full-runtime"
}

$exitCode = Invoke-NativeAndLog -Exe "docker" -ArgList $dockerArgs
if ($exitCode -ne 0) {
    throw "Django backup command failed with exit code $exitCode"
}

$latest = Get-ChildItem -Path $fullBackupDir -Filter "seizo0_runtime_backup_*.zip" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $latest) {
    throw "Backup zip was not created"
}

Write-Log "Latest backup: $($latest.FullName)"

if ($SkipUpload) {
    Write-Log "Upload skipped"
    exit 0
}

function Copy-ToDriveFolder {
    if (-not $DriveFolder) {
        Write-Log "DriveFolder is empty and Google Drive Desktop folder was not found; upload skipped"
        exit 2
    }

    New-Item -ItemType Directory -Force -Path $DriveFolder | Out-Null
    Copy-Item -LiteralPath $latest.FullName -Destination $DriveFolder -Force
    Write-Log "Copied backup to Google Drive folder: $DriveFolder"

    if ($KeepBackupCount -gt 0) {
        Get-ChildItem -LiteralPath $DriveFolder -Filter "seizo0_runtime_backup_*.zip" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -Skip $KeepBackupCount |
            Remove-Item -Force
        Write-Log "Pruned Google Drive folder to newest $KeepBackupCount backup(s)"
    }
    exit 0
}

$rclone = Get-Command rclone -ErrorAction SilentlyContinue
if (-not $rclone) {
    Write-Log "rclone not found; falling back to Google Drive folder"
    Copy-ToDriveFolder
}

$remoteName = ($RcloneRemote -split ":", 2)[0]
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $configuredRemotes = & rclone listremotes 2>$null
    $remoteCheckCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousPreference
}
if ($remoteCheckCode -ne 0 -or -not ($configuredRemotes -contains "$remoteName`:")) {
    Write-Log "rclone remote '$remoteName' is not configured; falling back to Google Drive folder"
    Copy-ToDriveFolder
}

$exitCode = Invoke-NativeAndLog -Exe "rclone" -ArgList @("copy", $latest.FullName, $RcloneRemote, "--create-empty-src-dirs")
if ($exitCode -ne 0) {
    throw "rclone upload failed with exit code $exitCode"
}

if ($KeepBackupCount -gt 0) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $remoteFiles = & rclone lsf $RcloneRemote --files-only --format "tp" 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw "rclone remote list failed with exit code $exitCode`: $remoteFiles"
    }

    $oldRemoteFiles = $remoteFiles |
        Where-Object { $_ -match "seizo0_runtime_backup_.*\.zip$" } |
        Sort-Object -Descending |
        Select-Object -Skip $KeepBackupCount

    foreach ($remoteLine in $oldRemoteFiles) {
        $remoteFileName = ($remoteLine -split ";")[-1]
        if ($remoteFileName) {
            $exitCode = Invoke-NativeAndLog -Exe "rclone" -ArgList @("deletefile", "$RcloneRemote/$remoteFileName")
            if ($exitCode -ne 0) {
                throw "rclone remote delete failed for $remoteFileName with exit code $exitCode"
            }
            Write-Log "Deleted old remote backup: $remoteFileName"
        }
    }
}

Write-Log "Upload completed: $RcloneRemote"
