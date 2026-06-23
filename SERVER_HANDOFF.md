# Seizo0 Server Handoff

Doc nay la ban tom tat nhanh de doi server hoac tiep quan van hanh.

## Hien trang chinh
- Project: Django, root `C:\seigi-server\seizo0\trang_chu`
- Settings: `trang_chu.settings`
- Runtime chinh: Docker Compose
- DB chinh: PostgreSQL service `postgres`, container `seizo0-postgres`, volume `postgres-data`
- SQLite `db.sqlite3`: chi la fallback/snapshot cu sau migration 2026-05-11, khong phai DB runtime chinh.
- Time zone: `Asia/Tokyo`

## Container nen chay
- `seizo0-postgres`: PostgreSQL DB chinh
- `seizo0-redis`: cache/redis
- `seizo0-django`: Django web
- `seizo0-nginx`: HTTPS reverse proxy
- `seizo0-esp32-bridge`: ESP32 bridge port `9000`
- `trang_chu-iot-worker-serial-1`: worker IoT tuan tu
- `trang_chu-fax-reminder-daily-1`: nhac FAX hang ngay

Lenh xem nhanh:

```powershell
cd C:\seigi-server\seizo0\trang_chu
docker compose ps
```

## Cach start tren server moi
```powershell
cd C:\seigi-server\seizo0\trang_chu
Copy-Item .env.example .env
notepad .env
docker compose up -d --build
docker compose --profile workers up -d iot-worker-serial fax-reminder-daily
```

Sau khi web recreate neu nginx 502:

```powershell
docker restart seizo0-nginx
```

## Worker policy
- Chay IoT bang `iot-worker-serial` de tranh worker trung nhau.
- `iot-worker-serial` dang chay:
  - 30s: `update_machine_counter`, `update_mold_shot`, `update_esp32_shot`
  - 180s: `update_net100_shots`, `sync_chatwork`
- `fetch_mail_notify` khong chay theo yeu cau van hanh hien tai.
- Khong bat cac worker IoT rieng le dang profile `disabled`, vi de gay ghi trung logic.

## Backup quan trong
- Backup tu dong hang ngay dung `scripts\backup_runtime_to_drive.ps1`.
- Sau migration 2026-05-11, zip backup tu dong chua PostgreSQL dump tai `postgres/seizo0_postgres.dump`; `manifest.json` phai ghi `database_kind=postgresql`.
- Backup test da tao thanh cong:
  - `backup_db/daily/seizo0_runtime_backup_20260511_181452.zip`
- Backup truoc/sau khi cuu bu du lieu `quet_anh` hom nay:
  - Truoc: `backup_db/postgres/seizo0_before_quetanh_recover_20260511_184335.dump`
  - Sau: `backup_db/postgres/seizo0_after_quetanh_recover_20260511_184758.dump`
- SQLite recovered dung de cuu `quet_anh`:
  - `backup_db/quetanh_recovery/recovered_20260511_171737.sqlite3`
- PostgreSQL backup sau migration:
  - `backup_db/postgres/seizo0_postgres_20260511_174911.dump`
- SQLite snapshot truoc khi chuyen Postgres:
  - `backup_db/postgres_migration/db_before_postgres_20260511_172616.sqlite3`
- JSON dump da import vao Postgres:
  - `backup_db/postgres_migration/sqlite_dump_20260511_172616.json`

Tao backup PostgreSQL moi:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
New-Item -ItemType Directory -Force -Path backup_db\postgres | Out-Null
docker exec seizo0-postgres pg_dump -U seizo0 -d seizo0 -Fc -f /tmp/seizo0_postgres.dump
docker cp seizo0-postgres:/tmp/seizo0_postgres.dump "backup_db\postgres\seizo0_postgres_$stamp.dump"
docker exec seizo0-postgres rm -f /tmp/seizo0_postgres.dump
```

Chay thu backup tu dong local, khong upload:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_runtime_to_drive.ps1 -SkipUpload -KeepBackupCount 3
```

Restore PostgreSQL dump tren server moi:

```powershell
docker compose up -d postgres redis
docker cp backup_db\postgres\seizo0_postgres_YYYYMMDD_HHMMSS.dump seizo0-postgres:/tmp/seizo0_postgres.dump
docker exec seizo0-postgres pg_restore -U seizo0 -d seizo0 --clean --if-exists /tmp/seizo0_postgres.dump
```

## Kiem tra sau restore/start
```powershell
docker compose exec web python manage.py check
docker compose exec web python -c "import django; django.setup(); from django.db import connection; print(connection.vendor)"
curl.exe -k -I --max-time 60 https://192.168.10.250/iot/dashboard/
docker compose logs --tail=80 iot-worker-serial
```

Ket qua mong doi:
- DB vendor: `postgresql`
- `/iot/dashboard/`: `HTTP/1.1 200 OK`
- Worker log co `database health check ok (postgresql)`

## Canh bao
- Dung PostgreSQL la huong chinh. Dung SQLite tren Windows bind mount da tung gay `database disk image is malformed`.
- Doi server can backup/restore PostgreSQL dump hoac Docker volume `postgres-data`; chi copy `db.sqlite3` la khong du.
- `.env` co secret/email/DB password, khong dua len chat hoac public git.
- Neu `quet_anh` xuat kho OCR/so sanh deu ra 0%, xem `SERVER_RECOVERY_RUNBOOK.md` muc OCR. Kiem tra PaddleOCR model va dung cau hinh on dinh `use_angle_cls=False`, `cls=False`, `enable_mkldnn=False`.
