from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quet_anh', '0023_qaresult_product_code_qamaterialoutstockledger_product_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='QAFeatureToggle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('outstock_auto_input_enabled', models.BooleanField(default=True, verbose_name='出庫自動入力')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '機能トグル',
                'verbose_name_plural': '機能トグル',
            },
        ),
    ]
