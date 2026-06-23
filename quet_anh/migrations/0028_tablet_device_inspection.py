from django.db import migrations, models
import django.db.models.deletion


def seed_tablets(apps, schema_editor):
    tablet_model = apps.get_model("quet_anh", "QATabletDevice")
    for idx in range(1, 5):
        code = f"QA-TAB-{idx:02d}"
        tablet_model.objects.get_or_create(
            code=code,
            defaults={
                "name": f"タブレット{idx}",
                "os_name": "Android",
                "status": "active",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("quet_anh", "0027_iatf_inventory_audit_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="QATabletDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(db_index=True, max_length=20, unique=True, verbose_name="管理番号")),
                ("name", models.CharField(max_length=80, verbose_name="表示名")),
                ("os_name", models.CharField(default="Android", max_length=40, verbose_name="OS")),
                ("serial_no", models.CharField(blank=True, default="", max_length=120, verbose_name="シリアルNo.")),
                ("status", models.CharField(choices=[("active", "使用可"), ("stopped", "使用停止"), ("repair", "修理中")], db_index=True, default="active", max_length=20, verbose_name="状態")),
                ("note", models.TextField(blank=True, default="", verbose_name="備考")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "QAタブレット",
                "verbose_name_plural": "QAタブレット",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="QATabletInspection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("check_type", models.CharField(choices=[("startup", "始業前点検"), ("daily", "定期点検"), ("abnormal", "異常時点検"), ("recovery", "復旧確認")], default="startup", max_length=20, verbose_name="点検区分")),
                ("check_date", models.DateField(db_index=True, verbose_name="点検日")),
                ("camera_ok", models.BooleanField(default=True, verbose_name="カメラ確認")),
                ("qr_sample_ok", models.BooleanField(default=True, verbose_name="QRサンプル読取")),
                ("ocr_sample_ok", models.BooleanField(default=True, verbose_name="OCR/画像確認")),
                ("network_ok", models.BooleanField(default=True, verbose_name="通信確認")),
                ("workstation_ok", models.BooleanField(default=True, verbose_name="端末連携確認")),
                ("result", models.CharField(choices=[("ok", "OK"), ("ng", "NG")], db_index=True, default="ok", max_length=10, verbose_name="判定")),
                ("problem_category", models.CharField(choices=[("none", "異常なし"), ("qr", "QR読取不良"), ("camera", "カメラ不良"), ("ocr", "OCR不良"), ("network", "通信不良"), ("workstation", "端末連携不良"), ("app", "アプリ動作不良"), ("damage", "破損・汚れ"), ("other", "その他")], default="none", max_length=30, verbose_name="異常分類")),
                ("problem_detail", models.TextField(blank=True, default="", verbose_name="異常内容")),
                ("action_taken", models.TextField(blank=True, default="", verbose_name="処置内容")),
                ("checked_by", models.CharField(blank=True, default="", max_length=120, verbose_name="点検者")),
                ("confirmed_by", models.CharField(blank=True, default="", max_length=120, verbose_name="確認者")),
                ("confirmed_at", models.DateTimeField(blank=True, null=True, verbose_name="確認日時")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tablet", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inspections", to="quet_anh.qatabletdevice")),
            ],
            options={
                "verbose_name": "QAタブレット点検",
                "verbose_name_plural": "QAタブレット点検",
                "ordering": ["-check_date", "-id"],
                "indexes": [
                    models.Index(fields=["tablet", "-check_date"], name="quet_anh_qa_tablet__3f7ec4_idx"),
                    models.Index(fields=["result", "-check_date"], name="quet_anh_qa_result_caf165_idx"),
                ],
            },
        ),
        migrations.RunPython(seed_tablets, migrations.RunPython.noop),
    ]
