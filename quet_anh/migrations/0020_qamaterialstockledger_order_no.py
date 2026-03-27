from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quet_anh", "0019_qamaterialmaster_bag_weight_kg"),
    ]

    operations = [
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="order_no",
            field=models.CharField(blank=True, db_index=True, default="", max_length=120, verbose_name="注文No."),
        ),
    ]

