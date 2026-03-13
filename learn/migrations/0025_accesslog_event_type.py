from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learn', '0024_accesslog'),
    ]

    operations = [
        migrations.AddField(
            model_name='accesslog',
            name='event_type',
            field=models.CharField(default='pageview', max_length=20, verbose_name='種別'),
        ),
    ]
