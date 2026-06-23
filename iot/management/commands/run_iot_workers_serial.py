import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Run IoT background commands sequentially to avoid concurrent SQLite writes."

    fast_commands = (
        "update_machine_counter",
        "update_mold_shot",
        "update_esp32_shot",
    )
    slow_commands = (
        "update_net100_shots",
        "sync_chatwork",
    )

    def add_arguments(self, parser):
        parser.add_argument("--fast-interval", type=int, default=10)
        parser.add_argument("--slow-interval", type=int, default=60)
        parser.add_argument("--db-check-interval", type=int, default=300)

    def handle(self, *args, **options):
        fast_interval = max(1, int(options["fast_interval"]))
        slow_interval = max(fast_interval, int(options["slow_interval"]))
        db_check_interval = max(fast_interval, int(options["db_check_interval"]))
        last_slow_run = 0.0
        last_db_check = 0.0

        self.stdout.write(
            self.style.SUCCESS(
                "Starting serial IoT worker: "
                f"fast={fast_interval}s slow={slow_interval}s db_check={db_check_interval}s"
            )
        )

        while True:
            loop_started = time.monotonic()
            now = time.monotonic()
            if now - last_db_check >= db_check_interval:
                self._check_sqlite_health()
                last_db_check = time.monotonic()

            self._run_commands(self.fast_commands)

            now = time.monotonic()
            if now - last_slow_run >= slow_interval:
                self._run_commands(self.slow_commands)
                last_slow_run = time.monotonic()

            elapsed = time.monotonic() - loop_started
            time.sleep(max(1, fast_interval - elapsed))

    def _run_commands(self, commands):
        for command_name in commands:
            close_old_connections()
            started_at = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
            self.stdout.write(f"[{started_at}] run {command_name}")
            try:
                command_started = time.monotonic()
                call_command(command_name)
                elapsed = time.monotonic() - command_started
                self.stdout.write(f"[OK] {command_name} finished in {elapsed:.1f}s")
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"[ERROR] {command_name}: {exc}"))
            finally:
                close_old_connections()

    def _check_sqlite_health(self):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                if connection.vendor == "sqlite":
                    cursor.execute("PRAGMA quick_check")
                    result = cursor.fetchone()[0]
                    if result != "ok":
                        self.stderr.write(self.style.ERROR(f"SQLite quick_check failed: {result}"))
                        time.sleep(60)
                        raise RuntimeError(f"SQLite quick_check failed: {result}")
                else:
                    cursor.execute("SELECT 1")
            checked_at = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
            self.stdout.write(f"[{checked_at}] database health check ok ({connection.vendor})")
        finally:
            close_old_connections()
