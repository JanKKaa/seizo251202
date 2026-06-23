# Docker Deploy Quick Start

Run from this folder (`trang_chu`).

## 1) Prepare env
Copy `.env.example` to `.env` and set real values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Important values:
- `DJANGO_PORT=8000`
- `DB_ENGINE=postgres`
- `POSTGRES_DB=seizo0`
- `POSTGRES_USER=seizo0`
- `POSTGRES_PASSWORD=...` (doi mat khau that tren server moi)
- `DJANGO_ALLOWED_HOSTS=192.168.10.250,localhost,127.0.0.1`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://192.168.10.250,http://192.168.10.250`
- `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` if mail features are used.

## 2) Start
```powershell
docker compose up -d --build
docker compose --profile workers up -d iot-worker-serial fax-reminder-daily
```

The web container runs:
- `python manage.py migrate`
- `python manage.py collectstatic --noinput`
- `python manage.py runserver 0.0.0.0:8000`

## 3) Check
```powershell
docker compose ps
docker compose logs -f web
```

Open:
- `http://localhost:8000/`
- `http://192.168.10.250:8000/`

## 4) Runtime data
Current primary database:
- PostgreSQL Docker service `postgres`
- Docker volume `postgres-data`

These host paths are still mounted into Django:
- `db.sqlite3` (legacy SQLite fallback/snapshot, not primary DB after 2026-05-11)
- `media/`
- `staticfiles/`
- `logs/dashboard.log`

Back up PostgreSQL (`pg_dump` or volume backup), `media/`, `.env`, nginx config, and source separately from git.

Daily/runtime backup script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_runtime_to_drive.ps1 -SkipUpload
```

After 2026-05-11 migration, the runtime backup zip should contain `postgres/seizo0_postgres.dump`, and `manifest.json` should say `database_kind=postgresql`.

Quick PostgreSQL backup:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
New-Item -ItemType Directory -Force -Path backup_db\postgres | Out-Null
docker exec seizo0-postgres pg_dump -U seizo0 -d seizo0 -Fc -f /tmp/seizo0_postgres.dump
docker cp seizo0-postgres:/tmp/seizo0_postgres.dump "backup_db\postgres\seizo0_postgres_$stamp.dump"
docker exec seizo0-postgres rm -f /tmp/seizo0_postgres.dump
```

## 5) Stop / restart
```powershell
docker compose restart web
docker compose down
```
