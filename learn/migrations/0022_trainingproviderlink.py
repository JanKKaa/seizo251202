from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learn', '0021_alter_course_options_alter_course_capacity_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingProviderLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='会社・団体名')),
                ('url', models.URLField(verbose_name='URL')),
                ('category', models.CharField(choices=[('koshukai', '講習会'), ('online', 'オンラインセミナー')], max_length=20, verbose_name='カテゴリ')),
                ('icon_class', models.CharField(blank=True, default='', max_length=100, verbose_name='アイコン')),
                ('is_active', models.BooleanField(default=True, verbose_name='表示')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': '研修・講習リンク',
                'verbose_name_plural': '研修・講習リンク',
                'ordering': ['-created_at'],
            },
        ),
    ]
