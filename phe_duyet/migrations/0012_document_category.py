from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("phe_duyet", "0011_remove_document_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="category",
            field=models.CharField(
                choices=[
                    ("maintenance_request", "保全依頼"),
                    ("document_approval", "資料承認"),
                    ("purchase_order", "注文書"),
                    ("other", "その他"),
                ],
                default="other",
                max_length=32,
            ),
        ),
    ]
