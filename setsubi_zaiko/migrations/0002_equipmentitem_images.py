# Generated for G-TECH development test app.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("setsubi_zaiko", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipmentitem",
            name="item_image",
            field=models.ImageField(blank=True, null=True, upload_to="setsubi_zaiko/items/", verbose_name="外観写真"),
        ),
        migrations.AddField(
            model_name="equipmentitem",
            name="nameplate_image",
            field=models.ImageField(blank=True, null=True, upload_to="setsubi_zaiko/nameplates/", verbose_name="銘板・ラベル写真"),
        ),
    ]

