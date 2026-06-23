from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0007_misumi_item_master_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipmentitem",
            name="quality_rank",
            field=models.CharField(choices=[("A", "A: 品質・安全重要"), ("B", "B: 工程影響あり"), ("C", "C: 一般管理")], default="C", max_length=1, verbose_name="品質ランク"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="control_plan_no",
            field=models.CharField(blank=True, max_length=80, verbose_name="Control Plan No."),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="process_owner",
            field=models.CharField(blank=True, max_length=120, verbose_name="管理責任者"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="supplier_name",
            field=models.CharField(blank=True, max_length=120, verbose_name="購入先"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="supplier_part_url",
            field=models.URLField(blank=True, verbose_name="購入先URL"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="last_inventory_check_date",
            field=models.DateField(blank=True, null=True, verbose_name="最終棚卸日"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="next_inventory_check_date",
            field=models.DateField(blank=True, null=True, verbose_name="次回棚卸期限"),
        ),
    ]
