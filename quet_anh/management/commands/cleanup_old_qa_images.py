from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from quet_anh.models import QAResult


class Command(BaseCommand):
    help = "Delete scanned image files older than retention period, keep text data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Retention days for image files (default: 365).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without modifying data.",
        )

    def handle(self, *args, **options):
        days = int(options["days"])
        dry_run = bool(options["dry_run"])

        cutoff = timezone.now() - timedelta(days=days)
        has_original = Q(image__isnull=False) & ~Q(image="")
        has_processed = Q(processed_image__isnull=False) & ~Q(processed_image="")
        qs = QAResult.objects.filter(created_at__lt=cutoff).filter(has_original | has_processed)

        total = qs.count()
        self.stdout.write(
            self.style.NOTICE(
                f"[quet_anh] cutoff={cutoff:%Y-%m-%d %H:%M:%S}, targets={total}, dry_run={dry_run}"
            )
        )

        deleted_original = 0
        deleted_processed = 0
        touched_rows = 0

        for item in qs.iterator(chunk_size=200):
            changed = False

            if item.image:
                if not dry_run:
                    item.image.delete(save=False)
                    item.image = ""
                deleted_original += 1
                changed = True

            if item.processed_image:
                if not dry_run:
                    item.processed_image.delete(save=False)
                    item.processed_image = None
                deleted_processed += 1
                changed = True

            if changed:
                touched_rows += 1
                if not dry_run:
                    item.save(update_fields=["image", "processed_image", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. rows={touched_rows}, original_deleted={deleted_original}, processed_deleted={deleted_processed}, keep_text_only=True"
            )
        )
