from pathlib import Path
import re

from django.core.management.base import BaseCommand, CommandError

from setsubi_zaiko.models import EquipmentCategory, EquipmentItem


def make_code(parts, prefix):
    raw = "-".join(parts)
    normalized = re.sub(r"[^0-9A-Za-z]+", "-", raw).strip("-").upper()
    if not normalized:
        normalized = re.sub(r"\s+", "-", raw).strip("-")
    return f"{prefix}{normalized}"[:60]


def split_code_name(folder_name):
    tokens = folder_name.split(maxsplit=1)
    if tokens and tokens[0].isdigit():
        return tokens[0], tokens[1] if len(tokens) > 1 else ""
    return "", folder_name


class Command(BaseCommand):
    help = "Sync mold folders as 顧客 -> 製品 -> 金型部品・構成品 records."

    def add_arguments(self, parser):
        parser.add_argument("root_path", help="Root mold drawing folder containing customer folders, e.g. ...\\13.1.金型図")
        parser.add_argument("--category-code", default="MOLD", help="Category code for created mold records.")
        parser.add_argument("--code-prefix", default="MOLD-", help="Prefix for generated unique mold codes.")
        parser.add_argument("--dry-run", action="store_true", help="Show target records without saving.")

    def handle(self, *args, **options):
        root = Path(options["root_path"])
        if not root.exists() or not root.is_dir():
            raise CommandError(f"Folder not found: {root}")

        category = EquipmentCategory.objects.filter(code=options["category_code"]).first()
        if category is None:
            category, _ = EquipmentCategory.objects.update_or_create(
                code="MOLD",
                defaults={
                    "name": "金型",
                    "group": EquipmentCategory.GROUP_PRODUCTION,
                    "is_active": True,
                },
            )

        component_folders = []
        for customer_folder in sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.name):
            for product_folder in sorted([path for path in customer_folder.iterdir() if path.is_dir()], key=lambda path: path.name):
                children = sorted([path for path in product_folder.iterdir() if path.is_dir()], key=lambda path: path.name)
                if children:
                    for component_folder in children:
                        component_folders.append((customer_folder, product_folder, component_folder))
                else:
                    component_folders.append((customer_folder, product_folder, product_folder))
        created = 0
        updated = 0
        for customer_folder, product_folder, component_folder in component_folders:
            customer_code, customer_name = split_code_name(customer_folder.name)
            product_code, product_name = split_code_name(product_folder.name)
            component_name = component_folder.name
            relative_path = str(component_folder.relative_to(root))
            code = make_code([customer_folder.name, product_folder.name, component_name], options["code_prefix"])
            defaults = {
                "name": component_name,
                "category": category,
                "equipment_type": "mold",
                "item_kind": EquipmentItem.KIND_MOLD,
                "applicable_mold_no": product_code or product_folder.name.split()[0],
                "mold_customer_code": customer_code,
                "mold_customer_name": customer_name,
                "mold_product_code": product_code,
                "mold_product_name": product_name,
                "mold_component_name": component_name,
                "mold_drawing_root_path": str(root),
                "mold_drawing_subfolder_path": relative_path,
                "unit": "式",
                "current_quantity": 1,
            }
            if options["dry_run"]:
                self.stdout.write(f"{code}: {customer_folder.name} > {product_folder.name} > {component_name} -> {root}\\{relative_path}")
                continue
            _, was_created = EquipmentItem.objects.update_or_create(code=code, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"mold folders synced: created={created}, updated={updated}, scanned={len(component_folders)}"))
