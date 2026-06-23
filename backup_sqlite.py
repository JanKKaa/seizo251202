import datetime
import os
import sqlite3
from pathlib import Path


DB_PATH = "db.sqlite3"
BACKUP_DIR = "backup_db"
KEEP_COUNT = 2


def backup_sqlite(source_path, backup_path):
    source = sqlite3.connect(source_path, timeout=30)
    dest = sqlite3.connect(backup_path)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()


def check_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    if not result or result[0] != "ok":
        raise SystemExit(f"Backup integrity_check failed: {result}")


def prune_old_backups(backup_dir):
    backups = sorted(
        Path(backup_dir).glob("db_backup_*.sqlite3"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[KEEP_COUNT:]:
        old_backup.unlink()
    return backups[:KEEP_COUNT]


os.makedirs(BACKUP_DIR, exist_ok=True)
today = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = os.path.join(BACKUP_DIR, f"db_backup_{today}.sqlite3")

backup_sqlite(DB_PATH, backup_file)
check_sqlite(backup_file)
kept = prune_old_backups(BACKUP_DIR)

print(f"Backup created: {backup_file}")
print("Kept database backups:")
for item in kept:
    print(f"- {item}")
