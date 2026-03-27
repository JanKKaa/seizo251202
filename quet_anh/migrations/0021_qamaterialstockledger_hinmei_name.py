from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quet_anh", "0020_qamaterialstockledger_order_no"),
    ]

    operations = [
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="hinmei_name",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="品名"),
        ),
    ]

