param(
    [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$TaskName = "Seizo0 Daily Backup",
    [string]$Time = "02:30",
    [string]$RcloneRemote = "gdrive:seizo0-backups",
    [string]$DriveFolder = "",
    [int]$KeepBackupCount = 2,
    [switch]$SkipUpload,
    [switch]$FullRuntime,
    [switch]$MinimalRuntime,
    [switch]$IncludeEnv,
    [switch]$RunHighest
)

$ErrorActionPreference = "Stop"

$backupScript = Join-Path $ProjectDir "scripts\backup_runtime_to_drive.ps1"
if (-not (Test-Path $backupScript)) {
    throw "Backup script not found: $backupScript"
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

$argsList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$backupScript`"",
    "-ProjectDir", "`"$ProjectDir`"",
    "-RcloneRemote", "`"$RcloneRemote`"",
    "-DriveFolder", "`"$DriveFolder`"",
    "-KeepBackupCount", "$KeepBackupCount"
)

if ($SkipUpload) {
    $argsList += "-SkipUpload"
}

if ($IncludeEnv) {
    $argsList += "-IncludeEnv"
}

if ($FullRuntime) {
    $argsList += "-FullRuntime"
}

if ($MinimalRuntime) {
    $argsList += "-MinimalRuntime"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argsList -join " ")
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
if ($RunHighest) {
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
} else {
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Description "Create Seizo0 runtime backup and upload to Google Drive via rclone or Google Drive Desktop." `
    -Force | Out-Null

Write-Host "Installed scheduled task '$TaskName' at $Time"
