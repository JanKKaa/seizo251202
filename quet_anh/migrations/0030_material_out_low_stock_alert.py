from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quet_anh", "0029_tablet_inspection_qr_evidence"),
    ]

    operations = [
        migrations.AddField(
            model_name="qamaterialoutstockledger",
            name="low_stock_alert_sent_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="安全在庫割れ通知日時"),
        ),
    ]
