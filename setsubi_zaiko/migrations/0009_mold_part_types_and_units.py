from django.db import migrations, models


def seed_mold_categories(apps, schema_editor):
    category_model = apps.get_model("setsubi_zaiko", "EquipmentCategory")
    mold_parent, _ = category_model.objects.update_or_create(
        code="MOLD",
        defaults={
            "name": "金型",
            "group": "production_equipment",
            "description": "製品金型本体",
            "is_active": True,
        },
    )
    rows = [
        ("MOLD-INSERT", "入れ子", "入れ子、キャビティ、コアブロック"),
        ("MOLD-CORE-PIN", "コアピン", "コアピン、成形部ピン"),
        ("MOLD-EJECTOR-PIN", "エジェクタピン", "エジェクタピン、リターンピン"),
        ("MOLD-SLIDE-CORE", "スライドコア", "スライド、カム、可動入れ子"),
        ("MOLD-GUIDE", "ガイド部品", "ガイドピン、ガイドブッシュ"),
        ("MOLD-SPRING", "スプリング", "金型用ばね、戻しばね"),
        ("MOLD-COOLING-PART", "冷却部品", "冷却配管、カプラ、温調継手"),
        ("MOLD-PLATE", "プレート", "取付板、スペーサ、プレート類"),
        ("MOLD-HOT-RUNNER", "ホットランナー部品", "ヒーター、熱電対、ノズル、マニホールド関連"),
    ]
    for code, name, description in rows:
        category_model.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "group": "consumable_spare",
                "parent": mold_parent,
                "description": description,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0008_iatf_item_control_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipmentitem",
            name="equipment_type",
            field=models.CharField(
                choices=[
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
                ],
                default="other",
                max_length=40,
                verbose_name="機器種別",
            ),
        ),
        migrations.AlterField(
            model_name="equipmentitem",
            name="unit",
            field=models.CharField(
                choices=[("個", "個"), ("枚", "枚"), ("式", "式"), ("本", "本"), ("セット", "セット"), ("その他", "その他")],
                default="個",
                max_length=20,
                verbose_name="単位",
            ),
        ),
        migrations.RunPython(seed_mold_categories, migrations.RunPython.noop),
    ]
