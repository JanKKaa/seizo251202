# Generated for G-TECH plastic molding factory domain presets.

from django.db import migrations


def seed_plastic_factory_categories(apps, schema_editor):
    category_model = apps.get_model("setsubi_zaiko", "EquipmentCategory")
    defaults = [
        ("JSW-MACHINE", "JSW射出成形機", "production_equipment", "JSW射出成形機本体・主要ユニット"),
        ("JSW-PART", "JSW成形機部品", "consumable_spare", "JSW射出成形機の交換部品・予備部品"),
        ("MOLD", "金型", "production_equipment", "製品金型本体"),
        ("MOLD-PART", "金型部品", "consumable_spare", "入れ子、ピン、スライド、ブッシュ等の金型部品"),
        ("YUSHIN-ROBOT", "ユーシン取出機", "production_equipment", "ユーシン取出機本体"),
        ("YUSHIN-PART", "ユーシン取出機部品", "consumable_spare", "ユーシン取出機の交換部品・予備部品"),
        ("MOLDING-AUX", "成形周辺機器", "production_equipment", "温調機、ホッパードライヤー、コンベア等"),
        ("MOLDING-SENSOR", "成形センサー・電装品", "consumable_spare", "センサー、リレー、ケーブル、電装部品"),
        ("MOLDING-HYD", "油圧・空圧部品", "consumable_spare", "油圧、空圧、継手、チューブ関連部品"),
    ]
    for code, name, group, description in defaults:
        category_model.objects.update_or_create(
            code=code,
            defaults={"name": name, "group": group, "description": description, "is_active": True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0002_equipmentitem_images"),
    ]

    operations = [
        migrations.RunPython(seed_plastic_factory_categories, migrations.RunPython.noop),
    ]

