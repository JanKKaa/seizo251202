# Generated for G-TECH plastic molding equipment type presets.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0003_plastic_factory_categories"),
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
    ]

