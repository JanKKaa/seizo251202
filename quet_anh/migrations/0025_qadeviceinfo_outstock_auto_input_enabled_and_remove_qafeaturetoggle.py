from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quet_anh', '0024_qafeaturetoggle'),
    ]

    operations = [
        migrations.AddField(
            model_name='qadeviceinfo',
            name='outstock_auto_input_enabled',
            field=models.BooleanField(default=False, verbose_name='出庫自動入力ON/OFF'),
        ),
        migrations.DeleteModel(
            name='QAFeatureToggle',
        ),
    ]
