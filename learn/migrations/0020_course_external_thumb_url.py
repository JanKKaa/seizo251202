from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learn', '0019_enrollment_q1_use_case_enrollment_q2_pre_issue_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='external_thumb_url',
            field=models.URLField(blank=True, default='', help_text='外部URLから取得したサムネイルURLを保存します。', verbose_name='外部サムネイルURL'),
        ),
    ]
