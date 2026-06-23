from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quet_anh", "0028_tablet_device_inspection"),
    ]

    operations = [
        migrations.AddField(
            model_name="qatabletinspection",
            name="qr_sample_checked_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="QR確認日時"),
        ),
        migrations.AddField(
            model_name="qatabletinspection",
            name="qr_sample_text",
            field=models.TextField(blank=True, default="", verbose_name="QR読取内容"),
        ),
    ]
