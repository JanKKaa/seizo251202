from django.db import migrations, models


def backfill_iatf_audit_fields(apps, schema_editor):
    stock_model = apps.get_model("quet_anh", "QAMaterialStockLedger")
    out_model = apps.get_model("quet_anh", "QAMaterialOutStockLedger")

    stock_model.objects.filter(transaction_type="").update(transaction_type="IN")
    out_model.objects.filter(transaction_type="").update(transaction_type="OUT")

    stock_adj_rows = stock_model.objects.filter(
        models.Q(order_no="ADJ")
        | models.Q(lot_number="ADJ")
        | models.Q(workstation_management_no__startswith="ADJ-")
    )
    for row in stock_adj_rows.iterator():
        row.transaction_type = "ADJ+"
        row.adjustment_reason_code = row.adjustment_reason_code or "migration"
        row.adjustment_reason = row.adjustment_reason or "移行データ補正"
        row.adjustment_note = row.adjustment_note or (row.hinmei_name or "")
        row.save(update_fields=["transaction_type", "adjustment_reason_code", "adjustment_reason", "adjustment_note"])

    out_adj_rows = out_model.objects.filter(
        models.Q(product_code="ADJ")
        | models.Q(lot_number="ADJ")
        | models.Q(workstation_management_no__startswith="ADJ-")
    )
    for row in out_adj_rows.iterator():
        row.transaction_type = "ADJ-"
        row.adjustment_reason_code = row.adjustment_reason_code or "migration"
        row.adjustment_reason = row.adjustment_reason or "移行データ補正"
        row.adjustment_note = row.adjustment_note or ""
        row.save(update_fields=["transaction_type", "adjustment_reason_code", "adjustment_reason", "adjustment_note"])


class Migration(migrations.Migration):

    dependencies = [
        ("quet_anh", "0026_qamaterialstockledger_operator_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="adjustment_note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="adjustment_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="adjustment_reason_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cycle_count", "Cycle count difference / 棚卸差異"),
                    ("input_error", "Input error correction / 入力ミス修正"),
                    ("damage", "Scrap or damage / 廃棄・破損"),
                    ("migration", "Data migration correction / 移行データ補正"),
                    ("customer_approved", "Customer approved correction / 顧客承認補正"),
                    ("other", "Other documented reason / その他"),
                ],
                db_index=True,
                default="",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="stock_after_kg",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="stock_before_kg",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="qamaterialstockledger",
            name="transaction_type",
            field=models.CharField(
                choices=[
                    ("IN", "Normal stock-in"),
                    ("ADJ+", "Inventory adjustment increase"),
                    ("CORR", "Correction"),
                ],
                db_index=True,
                default="IN",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="adjustment_note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="adjustment_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="adjustment_reason_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cycle_count", "Cycle count difference / 棚卸差異"),
                    ("input_error", "Input error correction / 入力ミス修正"),
                    ("damage", "Scrap or damage / 廃棄・破損"),
                    ("migration", "Data migration correction / 移行データ補正"),
                    ("customer_approved", "Customer approved correction / 顧客承認補正"),
                    ("other", "Other documented reason / その他"),
                ],
                db_index=True,
                default="",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="operator_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="stock_after_kg",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="stock_before_kg",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="transaction_type",
            field=models.CharField(
                choices=[
                    ("OUT", "Normal stock-out"),
                    ("ADJ-", "Inventory adjustment decrease"),
                    ("CORR", "Correction"),
                ],
                db_index=True,
                default="OUT",
                max_length=12,
            ),
        ),
        migrations.RunPython(backfill_iatf_audit_fields, migrations.RunPython.noop),
    ]
