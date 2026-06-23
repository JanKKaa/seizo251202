import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0010_equipment_ledger_categories"),
    ]

    operations = [
        migrations.CreateModel(
            name="EquipmentPartLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("usage_location", models.CharField(blank=True, max_length=120, verbose_name="使用箇所")),
                ("standard_quantity", models.DecimalField(decimal_places=2, default=1, max_digits=10, verbose_name="標準使用数")),
                ("criticality", models.CharField(choices=[("A", "A: 停止・品質に直結"), ("B", "B: 工程影響あり"), ("C", "C: 一般管理")], default="B", max_length=1, verbose_name="重要度")),
                ("replacement_cycle_days", models.PositiveIntegerField(blank=True, null=True, verbose_name="交換目安(日)")),
                ("note", models.TextField(blank=True, verbose_name="備考")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="作成日時")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新日時")),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="linked_parts", to="setsubi_zaiko.equipmentitem", verbose_name="設備・金型")),
                ("part", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="used_by_assets", to="setsubi_zaiko.equipmentitem", verbose_name="使用部品")),
            ],
            options={
                "verbose_name": "設備・金型 使用部品",
                "verbose_name_plural": "設備・金型 使用部品",
                "ordering": ["asset__code", "criticality", "part__code"],
                "unique_together": {("asset", "part", "usage_location")},
            },
        ),
    ]
