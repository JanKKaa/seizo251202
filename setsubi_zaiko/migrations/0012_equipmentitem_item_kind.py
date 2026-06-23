from django.db import migrations, models


def classify_existing_items(apps, schema_editor):
    equipment_item = apps.get_model("setsubi_zaiko", "EquipmentItem")
    equipment_item.objects.update(item_kind="part")
    equipment_item.objects.filter(category__parent__code="EQUIPMENT-LEDGER").update(item_kind="equipment")
    equipment_item.objects.filter(equipment_type="mold").update(item_kind="mold")


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0011_equipmentpartlink"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipmentitem",
            name="item_kind",
            field=models.CharField(
                choices=[("equipment", "設備台帳"), ("mold", "金型台帳"), ("part", "部品在庫")],
                default="part",
                max_length=20,
                verbose_name="管理区分",
            ),
        ),
        migrations.RunPython(classify_existing_items, migrations.RunPython.noop),
    ]
