from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0012_equipmentitem_item_kind"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipmentitem",
            name="item_kind",
            field=models.CharField(
                choices=[("equipment", "設備台帳"), ("mold", "金型台帳"), ("part", "部品在庫")],
                db_index=True,
                default="part",
                max_length=20,
                verbose_name="管理区分",
            ),
        ),
    ]
