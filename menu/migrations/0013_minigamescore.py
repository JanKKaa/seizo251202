from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0012_nhanvien_created_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="MiniGameScore",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True, verbose_name="名前")),
                ("best_score", models.PositiveIntegerField(default=0, verbose_name="最高スコア")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="作成日時")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新日時")),
            ],
            options={
                "verbose_name": "ミニゲームスコア",
                "verbose_name_plural": "ミニゲームスコア",
                "ordering": ["-best_score", "-updated_at"],
            },
        ),
    ]
