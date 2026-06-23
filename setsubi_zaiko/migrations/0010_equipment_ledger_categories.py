from django.db import migrations, models


TYPE_CHOICES = [
    ("injection_molding_machine", "射出成形機"),
    ("jsw_machine_part", "JSW成形機部品"),
    ("mold", "金型"),
    ("mold_part", "金型部品"),
    ("mold_insert", "金型入れ子"),
    ("mold_core_pin", "金型コアピン"),
    ("mold_ejector_pin", "エジェクタピン"),
    ("mold_slide_core", "スライドコア"),
    ("mold_guide_part", "金型ガイド部品"),
    ("mold_spring", "金型スプリング"),
    ("mold_cooling_part", "金型冷却部品"),
    ("mold_plate", "金型プレート"),
    ("mold_hot_runner_part", "ホットランナー部品"),
    ("takeout_robot", "取出し機"),
    ("crusher", "粉砕機"),
    ("dryer", "乾燥機"),
    ("vacuum_pump", "真空ポンプ"),
    ("compressor", "コンプレッサー"),
    ("mold_monitor_camera", "金型監視カメラ"),
    ("air_vent", "エアーベント"),
    ("washer", "洗浄機"),
    ("demagnetizer", "脱磁機"),
    ("automatic_machine", "自動機"),
    ("mixer", "混合機"),
    ("material_loader", "輸送システムローダ"),
    ("yushin_takeout_robot", "ユーシン取出機"),
    ("yushin_robot_part", "ユーシン取出機部品"),
    ("temperature_controller", "温調機"),
    ("hopper_dryer", "ホッパードライヤー"),
    ("conveyor", "コンベア"),
    ("hydraulic_part", "油圧部品"),
    ("electric_part", "電装部品"),
    ("pneumatic_part", "空圧部品"),
    ("tablet", "タブレット"),
    ("barcode_scanner", "バーコードスキャナ"),
    ("qr_reader", "QRリーダー"),
    ("camera", "カメラ"),
    ("pc", "PC"),
    ("printer", "プリンタ"),
    ("measuring_tool", "測定器"),
    ("jig", "治具"),
    ("sensor", "センサー"),
    ("network_device", "ネットワーク機器"),
    ("machine_part", "機械部品"),
    ("hand_tool", "手工具"),
    ("spare_part", "予備部品"),
    ("safety_item", "安全用品"),
    ("other", "その他"),
]


def seed_equipment_ledger_categories(apps, schema_editor):
    category_model = apps.get_model("setsubi_zaiko", "EquipmentCategory")
    parent, _ = category_model.objects.update_or_create(
        code="EQUIPMENT-LEDGER",
        defaults={
            "name": "設備管理台帳",
            "group": "production_equipment",
            "description": "設備リスト.xlsx の管理番号体系に合わせた設備本体分類",
            "is_active": True,
        },
    )
    rows = [
        ("SK", "成形機", "射出成形機本体"),
        ("TD", "取出し機", "取出しロボット"),
        ("FS", "粉砕機", "ランナー・不良品粉砕機"),
        ("OC", "温調機", "金型温調機"),
        ("KS", "乾燥機", "材料乾燥機"),
        ("SP", "真空ポンプ", "真空・吸引系設備"),
        ("KP", "コンプレッサー", "工場エアー供給設備"),
        ("KC", "金型監視カメラ", "金型監視カメラ本体"),
        ("AB", "エアーベント", "エアーベント関連設備"),
        ("KB", "コンベヤ", "搬送コンベヤ"),
        ("SJ", "洗浄機", "洗浄機本体"),
        ("DT", "脱磁機", "脱磁機本体"),
        ("JD", "自動機", "工程自動機"),
        ("KG", "混合機", "混合機・タンブラー"),
        ("HR", "輸送システムローダ", "材料輸送ローダ"),
    ]
    for symbol, name, description in rows:
        category_model.objects.update_or_create(
            code=f"EQ-{symbol}",
            defaults={
                "name": name,
                "group": "production_equipment",
                "parent": parent,
                "description": description,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0009_mold_part_types_and_units"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipmentitem",
            name="equipment_type",
            field=models.CharField(
                choices=TYPE_CHOICES,
                default="other",
                max_length=40,
                verbose_name="機器種別",
            ),
        ),
        migrations.RunPython(seed_equipment_ledger_categories, migrations.RunPython.noop),
    ]
