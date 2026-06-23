# Generated for G-TECH UI label cleanup.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0004_alter_equipmentitem_equipment_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipmentitem",
            name="name",
            field=models.CharField(max_length=160, verbose_name="機器・部品名"),
        ),
        migrations.AlterField(
            model_name="equipmentstockledger",
            name="item",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ledgers",
                to="setsubi_zaiko.equipmentitem",
                verbose_name="機器・部品",
            ),
        ),
    ]

