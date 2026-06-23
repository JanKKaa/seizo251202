# Generated for G-TECH development test app.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_categories(apps, schema_editor):
    category_model = apps.get_model("setsubi_zaiko", "EquipmentCategory")
    defaults = [
        ("PROD-EQ", "生産設備", "production_equipment", "生産設備・機械本体"),
        ("QA-EQ", "品質確認機器", "qa_equipment", "測定器・カメラ・検査機器"),
        ("MAIN-TOOL", "保全工具", "maintenance_tool", "保全作業用工具"),
        ("IT-DEVICE", "IT端末", "it_device", "PC・タブレット・周辺機器"),
        ("WH-TOOL", "倉庫備品", "warehouse_tool", "倉庫作業用備品"),
        ("SAFE", "安全備品", "safety_device", "安全用品"),
        ("SPARE", "消耗品・予備品", "consumable_spare", "交換部品・予備品"),
        ("OTHER", "その他", "other", "その他分類"),
    ]
    for code, name, group, description in defaults:
        category_model.objects.get_or_create(
            code=code,
            defaults={"name": name, "group": group, "description": description, "is_active": True},
        )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EquipmentCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True, verbose_name="分類コード")),
                ("name", models.CharField(max_length=120, verbose_name="分類名")),
                ("group", models.CharField(choices=[("production_equipment", "生産設備"), ("qa_equipment", "品質確認機器"), ("maintenance_tool", "保全工具"), ("it_device", "IT端末"), ("warehouse_tool", "倉庫備品"), ("safety_device", "安全備品"), ("consumable_spare", "消耗品・予備品"), ("other", "その他")], default="other", max_length=40, verbose_name="大分類")),
                ("description", models.TextField(blank=True, verbose_name="説明")),
                ("is_active", models.BooleanField(default=True, verbose_name="有効")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="作成日時")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新日時")),
            ],
            options={"verbose_name": "設備分類", "verbose_name_plural": "設備分類", "ordering": ["group", "code"]},
        ),
        migrations.CreateModel(
            name="EquipmentItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=60, unique=True, verbose_name="機器コード")),
                ("name", models.CharField(max_length=160, verbose_name="機器名")),
                ("equipment_type", models.CharField(choices=[("tablet", "タブレット"), ("barcode_scanner", "バーコードスキャナ"), ("qr_reader", "QRリーダー"), ("camera", "カメラ"), ("pc", "PC"), ("printer", "プリンタ"), ("measuring_tool", "測定器"), ("jig", "治具"), ("sensor", "センサー"), ("network_device", "ネットワーク機器"), ("machine_part", "機械部品"), ("hand_tool", "手工具"), ("spare_part", "予備部品"), ("safety_item", "安全用品"), ("other", "その他")], default="other", max_length=40, verbose_name="機器種別")),
                ("serial_no", models.CharField(blank=True, max_length=100, verbose_name="シリアルNo.")),
                ("model_no", models.CharField(blank=True, max_length=100, verbose_name="型式")),
                ("maker", models.CharField(blank=True, max_length=100, verbose_name="メーカー")),
                ("location", models.CharField(blank=True, max_length=120, verbose_name="保管場所")),
                ("department", models.CharField(blank=True, max_length=120, verbose_name="使用部署")),
                ("received_date", models.DateField(blank=True, null=True, verbose_name="購入・受入日")),
                ("calibration_due_date", models.DateField(blank=True, null=True, verbose_name="校正期限")),
                ("status", models.CharField(choices=[("in_stock", "在庫"), ("in_use", "使用中"), ("reserved", "予約中"), ("repair", "修理中"), ("stopped", "使用停止"), ("scrapped", "廃棄済"), ("lost", "紛失")], default="in_stock", max_length=30, verbose_name="状態")),
                ("current_quantity", models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name="現在数量")),
                ("unit", models.CharField(default="個", max_length=20, verbose_name="単位")),
                ("note", models.TextField(blank=True, verbose_name="備考")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="作成日時")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新日時")),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="setsubi_zaiko.equipmentcategory", verbose_name="分類")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_equipment_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "設備・部品マスター", "verbose_name_plural": "設備・部品マスター", "ordering": ["category__group", "category__code", "code"]},
        ),
        migrations.CreateModel(
            name="EquipmentStockLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_type", models.CharField(choices=[("IN", "入庫"), ("OUT", "出庫"), ("ADJ+", "在庫調整増"), ("ADJ-", "在庫調整減"), ("RETURN", "返却"), ("SCRAP", "廃棄")], max_length=12, verbose_name="取引区分")),
                ("reason_code", models.CharField(choices=[("new_purchase", "新規購入"), ("return_to_stock", "返却入庫"), ("repair_return", "修理完了"), ("transfer_in", "移動入庫"), ("issue_to_use", "使用払出"), ("transfer_out", "移動出庫"), ("send_repair", "修理出し"), ("scrap_disposal", "廃棄処理"), ("inventory_plus", "棚卸増"), ("inventory_minus", "棚卸減"), ("found_legacy", "未登録品発見"), ("lost_damage", "紛失・破損"), ("migration", "移行データ"), ("other", "その他")], max_length=40, verbose_name="理由コード")),
                ("reason_label", models.CharField(max_length=120, verbose_name="理由")),
                ("memo", models.TextField(blank=True, verbose_name="理由メモ")),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="数量")),
                ("quantity_before", models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name="調整前数量")),
                ("quantity_after", models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name="調整後数量")),
                ("lot_no", models.CharField(blank=True, max_length=100, verbose_name="ロットNo.")),
                ("from_location", models.CharField(blank=True, max_length=120, verbose_name="移動元")),
                ("to_location", models.CharField(blank=True, max_length=120, verbose_name="移動先")),
                ("operator_name", models.CharField(blank=True, max_length=120, verbose_name="作業者")),
                ("supervisor_confirmed", models.BooleanField(default=False, verbose_name="上長確認")),
                ("supervisor_name", models.CharField(blank=True, max_length=120, verbose_name="確認者")),
                ("confirmed_at", models.DateTimeField(blank=True, null=True, verbose_name="確認日時")),
                ("system_no", models.CharField(blank=True, max_length=80, unique=True, verbose_name="システムNo.")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="記録日時")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="equipment_stock_ledgers", to=settings.AUTH_USER_MODEL)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledgers", to="setsubi_zaiko.equipmentitem", verbose_name="機器")),
            ],
            options={"verbose_name": "設備在庫台帳", "verbose_name_plural": "設備在庫台帳", "ordering": ["-created_at", "-id"]},
        ),
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]

