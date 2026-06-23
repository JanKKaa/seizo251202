from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("iot", "0071_alter_change4mentry_tags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="maillog",
            name="mail_uid",
            field=models.CharField(max_length=512, unique=True),
        ),
        migrations.AlterField(
            model_name="maillog",
            name="sender",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="maillog",
            name="subject",
            field=models.CharField(blank=True, max_length=512),
        ),
    ]
