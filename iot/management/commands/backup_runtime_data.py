import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Back up runtime data: database dump, media files, and small runtime state files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="backup_db/daily",
            help="Directory where backup zip files are written.",
        )
        parser.add_argument(
            "--keep-local-days",
            type=int,
            default=14,
            help="Delete local backup zip files older than this many days.",
        )
        parser.add_argument(
            "--keep-local-count",
            type=int,
            default=2,
            help="Keep only this many newest local backup zip files. Use 0 to disable count pruning.",
        )
        parser.add_argument(
            "--no-media",
            action="store_true",
            help="Do not include media/ in the backup zip.",
        )
        parser.add_argument(
            "--include-staticfiles",
            action="store_true",
            help="Include staticfiles/. Usually not needed because collectstatic can rebuild it.",
        )
        parser.add_argument(
            "--include-logs",
            action="store_true",
            help="Include logs/ in the backup zip.",
        )
        parser.add_argument(
            "--include-nginx",
            action="store_true",
            help="Include nginx/ config in the backup zip.",
        )
        parser.add_argument(
            "--include-env",
            action="store_true",
            help="Include .env in the backup zip. This may contain secrets.",
        )
        parser.add_argument(
            "--include-source",
            action="store_true",
            help="Include project source code under source/.",
        )
        parser.add_argument(
            "--full-runtime",
            action="store_true",
            help="Include all restore data: source, DB, media, staticfiles, logs, nginx, and .env.",
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR).resolve()
        db_settings = settings.DATABASES["default"]
        db_engine = db_settings["ENGINE"]

        output_dir = Path(options["output_dir"])
        if not output_dir.is_absolute():
            output_dir = base_dir / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        backup_name = f"seizo0_runtime_backup_{stamp}.zip"
        backup_path = output_dir / backup_name
        include_staticfiles = options["include_staticfiles"] or options["full_runtime"]
        include_logs = options["include_logs"] or options["full_runtime"]
        include_nginx = options["include_nginx"] or options["full_runtime"]
        include_env = options["include_env"] or options["full_runtime"]
        include_source = options["include_source"] or options["full_runtime"]
        include_media = not options["no_media"]

        with tempfile.TemporaryDirectory(prefix="seizo0_backup_") as tmp:
            staging = Path(tmp)
            if "postgresql" in db_engine:
                db_backup = staging / "postgres.dump"
                self._backup_postgres(db_settings, db_backup)
                db_arcname = "postgres/seizo0_postgres.dump"
                db_kind = "postgresql"
            else:
                db_path = Path(db_settings["NAME"]).resolve()
                if not db_path.exists():
                    raise CommandError(f"Database not found: {db_path}")
                db_backup = staging / "db.sqlite3"
                self._backup_sqlite(db_path, db_backup)
                self._check_sqlite(db_backup)
                db_arcname = "db.sqlite3"
                db_kind = "sqlite"

            manifest = {
                "created_at": timezone.localtime().isoformat(),
                "database": db_arcname,
                "database_kind": db_kind,
                "included": [db_arcname],
                "notes": [
                    "media/ is included by default.",
                    "Use --full-runtime to include staticfiles/, logs/, nginx/, and .env.",
                    ".env may contain secrets.",
                ],
            }

            with ZipFile(backup_path, "w", ZIP_DEFLATED, allowZip64=True) as zf:
                if include_source:
                    self._add_source_tree(zf, base_dir, manifest)

                zf.write(db_backup, db_arcname)

                if include_media:
                    self._add_tree(zf, base_dir / "media", "media", manifest)

                if include_staticfiles:
                    self._add_tree(zf, base_dir / "staticfiles", "staticfiles", manifest)

                if include_logs:
                    self._add_tree(zf, base_dir / "logs", "logs", manifest)

                if include_nginx:
                    self._add_tree(zf, base_dir / "nginx", "nginx", manifest)

                self._add_small_runtime_files(zf, base_dir, manifest, include_logs=include_logs)

                if include_env:
                    env_path = base_dir / ".env"
                    if env_path.exists():
                        zf.write(env_path, ".env")
                        manifest["included"].append(".env")

                manifest_path = staging / "manifest.json"
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
                zf.write(manifest_path, "manifest.json")

        self._prune_old_backups(output_dir, options["keep_local_days"], options["keep_local_count"])
        self.stdout.write(self.style.SUCCESS(f"Backup created: {backup_path}"))

    def _backup_sqlite(self, source_path, dest_path):
        source = sqlite3.connect(str(source_path), timeout=30)
        dest = sqlite3.connect(str(dest_path))
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()

    def _check_sqlite(self, db_path):
        conn = sqlite3.connect(str(db_path))
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
        if not result or result[0] != "ok":
            raise CommandError(f"SQLite integrity_check failed: {result}")

    def _backup_postgres(self, db_settings, dest_path):
        env = os.environ.copy()
        password = db_settings.get("PASSWORD")
        if password:
            env["PGPASSWORD"] = str(password)

        args = [
            "pg_dump",
            "-h",
            str(db_settings.get("HOST") or "postgres"),
            "-p",
            str(db_settings.get("PORT") or "5432"),
            "-U",
            str(db_settings.get("USER") or "seizo0"),
            "-d",
            str(db_settings.get("NAME") or "seizo0"),
            "-Fc",
            "-f",
            str(dest_path),
        ]
        try:
            result = subprocess.run(args, env=env, check=False, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise CommandError("pg_dump not found. Rebuild the Docker image with postgresql-client.") from exc
        if result.returncode != 0:
            raise CommandError(f"pg_dump failed: {result.stderr.strip()}")
        if not dest_path.exists() or dest_path.stat().st_size == 0:
            raise CommandError("pg_dump produced an empty backup file")

    def _add_tree(self, zf, root, arc_root, manifest):
        if not root.exists():
            return
        for path in root.rglob("*"):
            if path.is_file():
                zf.write(path, f"{arc_root}/{path.relative_to(root).as_posix()}")
        manifest["included"].append(f"{arc_root}/")

    def _add_source_tree(self, zf, base_dir, manifest):
        excluded_dirs = {
            ".git",
            ".git_broken",
            ".venv",
            "__pycache__",
            "backup_db",
            "logs",
            "media",
            "staticfiles",
            "seizo0_backup",
        }
        excluded_suffixes = {
            ".pyc",
            ".pyo",
            ".pyd",
            ".sqlite3",
            ".log",
            ".pem",
            ".key",
        }
        excluded_names = {".env"}

        for root, dirs, files in os.walk(base_dir):
            root_path = Path(root)
            dirs[:] = [
                dirname
                for dirname in dirs
                if dirname not in excluded_dirs and dirname not in excluded_names
            ]
            rel_root = root_path.relative_to(base_dir)
            if set(rel_root.parts) & excluded_dirs:
                continue
            for filename in files:
                if filename in excluded_names:
                    continue
                path = root_path / filename
                if path.suffix.lower() in excluded_suffixes:
                    continue
                rel = path.relative_to(base_dir)
                zf.write(path, f"source/{rel.as_posix()}")
        manifest["included"].append("source/")

    def _add_small_runtime_files(self, zf, base_dir, manifest, include_logs=False):
        candidates = [
            base_dir / "DOCKER_DEPLOY.md",
            base_dir / "ARCHITECTURE.md",
            base_dir / "PROJECT_CHANGELOG.md",
            base_dir / "docker-compose.yml",
            base_dir / ".env.example",
        ]
        if not include_logs:
            candidates.append(base_dir / "logs" / "esp32_bridge_state.json")
        for path in candidates:
            if path.exists() and path.is_file():
                zf.write(path, path.relative_to(base_dir).as_posix())
                manifest["included"].append(path.relative_to(base_dir).as_posix())

    def _prune_old_backups(self, output_dir, keep_days, keep_count):
        backups = sorted(
            output_dir.glob("seizo0_runtime_backup_*.zip"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        delete_paths = set()

        if keep_count > 0:
            delete_paths.update(backups[keep_count:])

        if keep_days > 0:
            cutoff = timezone.now() - timedelta(days=keep_days)
            for path in backups:
                modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone())
                if modified < cutoff:
                    delete_paths.add(path)

        for path in delete_paths:
            if path.exists():
                path.unlink()
