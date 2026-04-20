from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("baotri", "0011_maintenancetask_start_time"),
        ("quet_anh", "0021_qamaterialstockledger_hinmei_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="qadeviceinfo",
            name="maintenance_task",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="qa_devices",
                to="baotri.maintenancetask",
                verbose_name="製品マスター連携",
            ),
        ),
    ]
