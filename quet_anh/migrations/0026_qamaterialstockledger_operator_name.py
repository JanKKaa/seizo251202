from django.db import migrations, models


def backfill_operator_name(apps, schema_editor):
    stock_model = apps.get_model("quet_anh", "QAMaterialStockLedger")
    for row in stock_model.objects.filter(operator_name="", qa_result__isnull=False).select_related("qa_result"):
        operator_name = (row.qa_result.operator_name or "").strip()
        if operator_name:
            row.operator_name = operator_name
            row.save(update_fields=["operator_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("quet_anh", "0025_qadeviceinfo_outstock_auto_input_enabled_and_remove_qafeaturetoggle"),
    ]

    operations = [
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="operator_name",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="作業者"),
        ),
        migrations.RunPython(backfill_operator_name, migrations.RunPython.noop),
    ]
