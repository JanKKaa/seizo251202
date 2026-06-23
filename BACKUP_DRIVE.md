# Daily Backup To Google Drive

Backup nay tao file zip trong `backup_db/daily/`.

Management command mac dinh gom:
- `db.sqlite3` duoc copy bang SQLite backup API va chay `PRAGMA integrity_check`.
- `media/`.
- Mot so file van hanh nho: `docker-compose.yml`, `.env.example`, `DOCKER_DEPLOY.md`, `ARCHITECTURE.md`, `PROJECT_CHANGELOG.md`, `logs/esp32_bridge_state.json`.

PowerShell script `backup_runtime_to_drive.ps1` mac dinh chay che do full runtime. Che do full runtime gom them:
- `source/` chua source code project de co the phuc hoi khi mat server cu
- `staticfiles/`
- `logs/`
- `nginx/`
- `.env`

`.env` co secret, nhung can thiet neu muon phuc hoi server gan nhu y nguyen.

Mac dinh chi giu 2 ban backup moi nhat:
- Local: `backup_db/daily/`
- Google Drive: thu muc `RcloneRemote`

Muon doi so luong giu lai:

```powershell
.\scripts\backup_runtime_to_drive.ps1 -KeepBackupCount 3
```

## Chay backup local

Tu thu muc `trang_chu`:

```powershell
.\scripts\backup_runtime_to_drive.ps1 -SkipUpload
```

Backup day du du lieu Docker runtime:

```powershell
.\scripts\backup_runtime_to_drive.ps1 -SkipUpload
```

Test nhanh khong gom `media/`:

```powershell
.\scripts\backup_runtime_to_drive.ps1 -SkipUpload -NoMedia
```

## Cau hinh Google Drive upload

Script uu tien `rclone` neu co cau hinh. Neu khong co `rclone`, script copy vao Google Drive Desktop folder:

```text
G:\マイドライブ\seizo0-backups
```

Laptop hien tai dang dung Google Drive Desktop theo cach nay.

Neu dung `rclone`, can cai va login Google Drive mot lan tren laptop server.

Remote mac dinh:

```text
gdrive:seizo0-backups
```

Sau khi cau hinh xong `rclone`, test upload:

```powershell
.\scripts\backup_runtime_to_drive.ps1 -RcloneRemote "gdrive:seizo0-backups"
```

Neu dung Google Drive Desktop, test upload:

```powershell
.\scripts\backup_runtime_to_drive.ps1 -DriveFolder "G:\マイドライブ\seizo0-backups"
```

Upload full runtime:

```powershell
.\scripts\backup_runtime_to_drive.ps1 -RcloneRemote "gdrive:seizo0-backups"
```

Neu `rclone` chua co trong PATH, script van tao backup local va ghi log upload skipped.

## Cai lich chay hang ngay

Mac dinh chay luc `02:30`:

```powershell
.\scripts\install_daily_backup_task.ps1 -RcloneRemote "gdrive:seizo0-backups"
```

Chi backup local, chua upload:

```powershell
.\scripts\install_daily_backup_task.ps1 -SkipUpload
```

Log:

```text
logs/daily_backup.log
```

## Khoi phuc nhanh

Xem chi tiet trong `RESTORE_FROM_DRIVE.md`.

Tom tat:

1. Giai nen file `seizo0_runtime_backup_*.zip`.
2. Copy `source/` vao `C:\seigi-server\seizo0\trang_chu`.
3. Copy `db.sqlite3`, `media/`, `staticfiles/`, `logs/`, `nginx/`, `.env`.
4. Chay:

```powershell
docker compose up -d --build
```
