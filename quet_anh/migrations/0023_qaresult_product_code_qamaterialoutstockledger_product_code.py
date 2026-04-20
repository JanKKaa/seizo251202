from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quet_anh", "0022_qadeviceinfo_maintenance_task"),
    ]

    operations = [
        migrations.AddField(
            model_name="qaresult",
            name="product_code",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="製品コード"),
        ),
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="product_code",
            field=models.CharField(blank=True, db_index=True, default="", max_length=120, verbose_name="製品コード"),
        ),
    ]
