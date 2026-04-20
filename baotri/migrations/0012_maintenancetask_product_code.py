from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("baotri", "0011_maintenancetask_start_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="maintenancetask",
            name="product_code",
            field=models.CharField(blank=True, default="", max_length=50, null=True, verbose_name="製品コード"),
        ),
    ]
