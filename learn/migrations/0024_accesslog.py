from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('learn', '0023_course_created_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ma_so', models.CharField(blank=True, default='', max_length=20, verbose_name='社員番号')),
                ('ten', models.CharField(blank=True, default='', max_length=100, verbose_name='氏名')),
                ('path', models.CharField(max_length=255, verbose_name='パス')),
                ('method', models.CharField(default='GET', max_length=10, verbose_name='メソッド')),
                ('ip', models.CharField(blank=True, default='', max_length=45, verbose_name='IP')),
                ('user_agent', models.CharField(blank=True, default='', max_length=255, verbose_name='User-Agent')),
                ('duration_ms', models.IntegerField(default=0, verbose_name='滞在時間(ms)')),
                ('created_at', models.DateTimeField(default=timezone.now, verbose_name='アクセス日時')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'アクセスログ',
                'verbose_name_plural': 'アクセスログ',
                'ordering': ['-created_at'],
            },
        ),
    ]
