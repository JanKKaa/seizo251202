from pathlib import Path
import re

from django.core.management.base import BaseCommand, CommandError

from setsubi_zaiko.models import EquipmentCategory, EquipmentItem


def make_code(folder_name, prefix):
    normalized = re.sub(r"[^0-9A-Za-z]+", "-", folder_name).strip("-").upper()
    if not normalized:
        normalized = re.sub(r"\s+", "-", folder_name).strip("-")
    return f"{prefix}{normalized}"[:60]


class Command(BaseCommand):
    help = "Sync direct child folders under an equipment document root as 設備台帳 records."

    def add_arguments(self, parser):
        parser.add_argument("root_path", help="Root equipment document folder, e.g. ...\\乾燥機")
        parser.add_argument("--category-code", default="EQ-KS", help="Category code for created equipment records.")
        parser.add_argument("--equipment-type", default="dryer", help="Equipment type value, e.g. dryer.")
        parser.add_argument("--group-name", default="", help="設備グループ, e.g. 乾燥機.")
        parser.add_argument("--series-name", default="", help="設備シリーズ・型式分類.")
        parser.add_argument("--maker", default="", help="メーカー.")
        parser.add_argument("--code-prefix", default="EQ-", help="Prefix for generated unique equipment codes.")
        parser.add_argument("--dry-run", action="store_true", help="Show target records without saving.")

    def handle(self, *args, **options):
        root = Path(options["root_path"])
        if not root.exists() or not root.is_dir():
            raise CommandError(f"Folder not found: {root}")

        category = EquipmentCategory.objects.filter(code=options["category_code"]).first()
        if category is None:
            raise CommandError(f"Category not found: {options['category_code']}")

        group_name = options["group_name"] or category.name
        child_folders = sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.name)
        created = 0
        updated = 0
        for folder in child_folders:
            code = make_code(folder.name, options["code_prefix"])
            defaults = {
                "name": folder.name,
                "category": category,
                "equipment_type": options["equipment_type"],
                "item_kind": EquipmentItem.KIND_EQUIPMENT,
                "equipment_group_name": group_name,
                "equipment_series_name": options["series_name"],
                "maker": options["maker"],
                "equipment_document_root_path": str(root),
                "equipment_document_subfolder_path": folder.name,
                "unit": "式",
                "current_quantity": 1,
            }
            if options["dry_run"]:
                self.stdout.write(f"{code}: {folder.name} -> {root}\\{folder.name}")
                continue
            _, was_created = EquipmentItem.objects.update_or_create(code=code, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"equipment folders synced: created={created}, updated={updated}, scanned={len(child_folders)}"))
