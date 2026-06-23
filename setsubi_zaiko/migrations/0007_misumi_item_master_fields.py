# Generated for MISUMI-style item master fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0006_category_hierarchy_misumi_style"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipmentitem",
            name="internal_name",
            field=models.CharField(blank=True, max_length=160, verbose_name="社内呼称"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="maker_part_no",
            field=models.CharField(blank=True, max_length=120, verbose_name="メーカー品番"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="alternative_part_no",
            field=models.CharField(blank=True, max_length=120, verbose_name="代替品番"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="applicable_machine_no",
            field=models.CharField(blank=True, max_length=120, verbose_name="適用機械No."),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="applicable_mold_no",
            field=models.CharField(blank=True, max_length=120, verbose_name="適用金型No."),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="shelf_no",
            field=models.CharField(blank=True, max_length=80, verbose_name="棚番"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="minimum_stock",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name="最低在庫"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="reorder_point",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name="発注点"),
        ),
    ]

