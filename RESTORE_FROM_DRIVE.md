# Restore Seizo0 From Google Drive Backup

Huong dan nay dung khi laptop server cu bi hong va can dung server moi.

## 1) Can chuan bi tren server moi

- Windows.
- Docker Desktop da cai va dang chay.
- Google Drive for Desktop hoac tai file backup zip tu Google Drive.

File backup nam trong:

```text
G:\マイドライブ\seizo0-backups
```

Ten file dang co dang:

```text
seizo0_runtime_backup_YYYYMMDD_HHMMSS.zip
```

## 2) Giai nen backup

Tao thu muc lam viec:

```powershell
New-Item -ItemType Directory -Force C:\seigi-server\seizo0
```

Giai nen file zip moi nhat vao thu muc tam, vi du:

```powershell
Expand-Archive "G:\マイドライブ\seizo0-backups\seizo0_runtime_backup_YYYYMMDD_HHMMSS.zip" "C:\seigi-server\restore_tmp" -Force
```

## 3) Khoi phuc source code

Backup full co thu muc `source/`. Copy source vao project root:

```powershell
Copy-Item "C:\seigi-server\restore_tmp\source\*" "C:\seigi-server\seizo0\trang_chu" -Recurse -Force
```

Neu thu muc `C:\seigi-server\seizo0\trang_chu` chua co:

```powershell
New-Item -ItemType Directory -Force "C:\seigi-server\seizo0\trang_chu"
```

## 4) Khoi phuc runtime data

Tu 2026-05-11, DB chinh la PostgreSQL. Neu backup co PostgreSQL dump, khoi phuc dump do thay vi chi copy `db.sqlite3`.

Copy PostgreSQL dump/source backup neu co:

```powershell
Copy-Item "C:\seigi-server\restore_tmp\backup_db\postgres" "C:\seigi-server\seizo0\trang_chu\backup_db\postgres" -Recurse -Force
```

`db.sqlite3` chi la fallback/snapshot cu. Chi copy neu can giu tham chieu:

```powershell
Copy-Item "C:\seigi-server\restore_tmp\db.sqlite3" "C:\seigi-server\seizo0\trang_chu\db.sqlite3" -Force
```

Copy media/static/logs/nginx/env neu co trong backup:

```powershell
Copy-Item "C:\seigi-server\restore_tmp\media" "C:\seigi-server\seizo0\trang_chu\media" -Recurse -Force
Copy-Item "C:\seigi-server\restore_tmp\staticfiles" "C:\seigi-server\seizo0\trang_chu\staticfiles" -Recurse -Force
Copy-Item "C:\seigi-server\restore_tmp\logs" "C:\seigi-server\seizo0\trang_chu\logs" -Recurse -Force
Copy-Item "C:\seigi-server\restore_tmp\nginx" "C:\seigi-server\seizo0\trang_chu\nginx" -Recurse -Force
Copy-Item "C:\seigi-server\restore_tmp\.env" "C:\seigi-server\seizo0\trang_chu\.env" -Force
```

## 5) Start server

```powershell
cd C:\seigi-server\seizo0\trang_chu
docker compose up -d --build
docker compose --profile workers up -d iot-worker-serial fax-reminder-daily
```

Neu can restore PostgreSQL dump:

```powershell
docker compose up -d postgres redis
docker cp backup_db\postgres\seizo0_postgres_YYYYMMDD_HHMMSS.dump seizo0-postgres:/tmp/seizo0_postgres.dump
docker exec seizo0-postgres pg_restore -U seizo0 -d seizo0 --clean --if-exists /tmp/seizo0_postgres.dump
docker restart seizo0-django seizo0-nginx
```

Kiem tra container:

```powershell
docker compose ps
```

Kiem tra web:

```text
http://localhost:8000/
http://192.168.10.250:8000/
```

Neu server moi co IP khac, can sua `.env`:

```text
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
```

## 6) Kiem tra nhanh sau khi restore

```powershell
docker compose exec web python manage.py check
docker compose exec web python -c "import django; django.setup(); from django.db import connection; print(connection.vendor)"
```

Mo cac man hinh quan trong:

- `/iot/`
- `/iot/api/esp32_machines/`
- `/quet_anh/`
- `/menu/`

## 7) Bat lai backup tu dong

Sau khi Google Drive for Desktop hoat dong tren server moi:

```powershell
cd C:\seigi-server\seizo0\trang_chu
.\scripts\install_daily_backup_task.ps1 -DriveFolder "G:\マイドライブ\seizo0-backups" -KeepBackupCount 2
```

## Luu y

- File backup full co `.env`, trong do co secret/email password. Can bao ve file zip tren Drive.
- Sau migration PostgreSQL, chi copy `db.sqlite3` la khong du de khoi phuc du lieu moi nhat.
- Docker image/container khong can backup rieng vi co the build lai tu source + `Dockerfile` + `docker-compose.yml`.
- Backup chi giu 2 ban moi nhat de tiet kiem dung luong.
