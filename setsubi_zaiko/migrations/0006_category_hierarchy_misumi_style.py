# Generated for MISUMI-style category hierarchy.

import django.db.models.deletion
from django.db import migrations, models


def seed_misumi_style_categories(apps, schema_editor):
    category_model = apps.get_model("setsubi_zaiko", "EquipmentCategory")

    def upsert(code, name, group, description="", parent_code=None):
        parent = category_model.objects.filter(code=parent_code).first() if parent_code else None
        obj, _ = category_model.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "group": group,
                "parent": parent,
                "description": description,
                "is_active": True,
            },
        )
        return obj

    production = "production_equipment"
    spare = "consumable_spare"

    upsert("MOLDING-MACHINE", "成形機", production, "射出成形機本体・成形機関連の親分類")
    upsert("MOLDING-ELECTRIC", "電装部品", spare, "リレー、基板、ケーブル、電装ユニット", "MOLDING-MACHINE")
    upsert("MOLDING-MECHANICAL", "機械部品", spare, "リンク、ベアリング、シャフト、機械構成部品", "MOLDING-MACHINE")
    upsert("MOLDING-SCREW", "スクリュー関連", spare, "スクリュー、シリンダー、ノズル、逆止弁関連", "MOLDING-MACHINE")
    upsert("MOLDING-HEATER", "ヒーター・温調部品", spare, "バンドヒーター、熱電対、温調関連", "MOLDING-MACHINE")
    upsert("MOLDING-HYD-PNEU", "油圧・空圧部品", spare, "油圧、空圧、継手、チューブ関連", "MOLDING-MACHINE")

    upsert("MOLD", "金型", production, "製品金型本体")
    upsert("MOLD-CORE", "入れ子・コア", spare, "入れ子、コア、キャビティ関連", "MOLD")
    upsert("MOLD-PIN", "ピン・エジェクタ", spare, "エジェクタピン、リターンピン、ガイドピン", "MOLD")
    upsert("MOLD-SLIDE", "スライド・可動部品", spare, "スライド、カム、可動入れ子関連", "MOLD")
    upsert("MOLD-COOLING", "冷却・温調部品", spare, "冷却配管、カプラ、温調継手関連", "MOLD")

    upsert("YUSHIN-ROBOT", "ユーシン取出機", production, "ユーシン取出機本体")
    upsert("YUSHIN-ELECTRIC", "電装部品", spare, "ユーシン取出機の電装・制御部品", "YUSHIN-ROBOT")
    upsert("YUSHIN-MECHANICAL", "機械部品", spare, "ユーシン取出機のアーム、ガイド、駆動部品", "YUSHIN-ROBOT")
    upsert("YUSHIN-SUCTION", "吸着・チャック部品", spare, "吸着パッド、チャック、配管関連", "YUSHIN-ROBOT")

    # Keep older broad categories but attach them to the new hierarchy where useful.
    remap = {
        "JSW-MACHINE": "MOLDING-MACHINE",
        "JSW-PART": "MOLDING-MACHINE",
        "MOLD-PART": "MOLD",
        "YUSHIN-PART": "YUSHIN-ROBOT",
        "MOLDING-HYD": "MOLDING-MACHINE",
        "MOLDING-SENSOR": "MOLDING-MACHINE",
    }
    for code, parent_code in remap.items():
        obj = category_model.objects.filter(code=code).first()
        parent = category_model.objects.filter(code=parent_code).first()
        if obj and parent and obj.pk != parent.pk:
            obj.parent = parent
            obj.save(update_fields=["parent"])


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0005_fix_japanese_verbose_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipmentcategory",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="children",
                to="setsubi_zaiko.equipmentcategory",
                verbose_name="親分類",
            ),
        ),
        migrations.RunPython(seed_misumi_style_categories, migrations.RunPython.noop),
    ]

