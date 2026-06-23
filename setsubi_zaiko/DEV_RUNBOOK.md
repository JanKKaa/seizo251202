# 設備・部品在庫管理 Runbook

App: `setsubi_zaiko`

Purpose:
- Hayashi Techno equipment, spare-part, machine-part stock in/out/inventory management.
- Main domain is a plastic molding factory:
  - JSW injection molding machines.
  - Mold masters and mold parts.
  - Yushin take-out robots and robot parts.
  - Molding auxiliary equipment and spare parts.
- Production Docker enabled from 2026-05-25.

## Production Route

Production URL:

```text
/setsubi-zaiko/
```

Legacy dev URL redirects to production URL:

```text
/dev/setsubi-zaiko/
```

## Production Docker

Deploy/check example:

```powershell
cd C:\seigi-server\seizo0\trang_chu
docker compose build web
docker compose run --rm web python manage.py migrate setsubi_zaiko
docker compose up -d --force-recreate web nginx
docker compose exec -T web python manage.py check
```

Uploaded item photos are stored under `media/setsubi_zaiko/` and served by nginx `/media/`.

## Local Development Commands

PowerShell local run example:

```powershell
$env:DB_ENGINE="sqlite"
$env:SQLITE_DB_NAME="db_setsubi_dev.sqlite3"
python manage.py migrate setsubi_zaiko
python manage.py runserver 0.0.0.0:8000
```

Use this when you want to test separately from Docker production.
This creates/uses `db_setsubi_dev.sqlite3` instead of the production PostgreSQL Docker DB.

Docker one-shot check without changing production containers:

```powershell
docker compose run --rm --no-deps -e DB_ENGINE=sqlite -v ${PWD}:/app-src web python /app-src/manage.py check
```

Docker test with temporary SQLite test DB:

```powershell
docker compose run --rm --no-deps -e DB_ENGINE=sqlite -v ${PWD}:/app-src web python /app-src/manage.py test setsubi_zaiko
```

## Current Features

- Equipment/category master.
- Group classification:
  - 成形機
    - 電装部品
    - 機械部品
    - スクリュー関連
    - ヒーター・温調部品
    - 油圧・空圧部品
  - 金型
    - 入れ子・コア
    - ピン・エジェクタ
    - スライド・可動部品
    - 冷却・温調部品
  - ユーシン取出機
    - 電装部品
    - 機械部品
    - 吸着・チャック部品
  - JSW射出成形機
  - JSW成形機部品
  - 金型
  - 金型部品
  - ユーシン取出機
  - ユーシン取出機部品
  - 成形周辺機器
  - 成形センサー・電装品
  - 油圧・空圧部品
  - 生産設備
  - 品質確認機器
  - 保全工具
  - IT端末
  - 倉庫備品
  - 安全備品
  - 消耗品・予備品
  - その他
- Stock ledger:
  - IN
  - OUT
  - ADJ+
  - ADJ-
  - RETURN
  - SCRAP
- Before/after quantity.
- Reason code/label/memo.
- Operator and supervisor confirmation fields.
- CSV audit export.
- Pagination 10 rows per page.
- IATF readiness fields:
  - 品質ランク.
  - Control Plan No.
  - 管理責任者.
  - 購入先 and 購入先URL.
  - 最終棚卸日 and 次回棚卸期限.
- Dashboard audit alerts:
  - 最低在庫以下.
  - 校正期限切れ.
  - 棚卸期限切れ.
  - 未確認台帳.
- Item list audit filters:
  - 品質ランク.
  - 最低在庫以下.
  - 校正期限切れ.
  - 棚卸期限切れ.
  - Aランク管理情報不足.

## Before Production Deploy

Required review:
- Confirm required equipment groups and item types.
- Confirm permission rules.
- Confirm stock negative prevention.
- Confirm whether item master quantity can be edited directly or only via ledger.
- Confirm CSV format with manager.
- Confirm whether ledger hard delete remains disabled in UI/admin.
- Confirm backup and restore path.
