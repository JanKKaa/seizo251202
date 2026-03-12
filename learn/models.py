from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.conf import settings
from menu.models import NhanVien

class Course(models.Model):
    title = models.CharField(max_length=200, verbose_name='研修・講習タイトル', help_text='研修・講習のタイトルを入力してください。')
    description = models.TextField(blank=True, verbose_name='説明', help_text='研修・講習の詳細説明を入力してください。')
    start_date = models.DateField(null=True, blank=True, verbose_name='開始日', help_text='研修・講習の開始日を選択してください。')
    end_date = models.DateField(null=True, blank=True, verbose_name='終了日', help_text='研修・講習の終了日を選択してください。')
    external_url = models.URLField(blank=True, verbose_name='外部URL', help_text='外部リンクがある場合は入力してください。')
    is_active = models.BooleanField(default=True, verbose_name='アクティブ', help_text='研修・講習がアクティブかどうかを選択してください。')
    price = models.CharField(max_length=100, default='0', verbose_name='価格', help_text='研修・講習の価格を入力してください。')
    duration = models.CharField(max_length=100, blank=True, verbose_name='期間', help_text='研修・講習の期間を入力してください。')
    capacity = models.IntegerField(default=1, verbose_name='定員', help_text='研修・講習の定員を入力してください。')
    location = models.CharField(max_length=100, blank=True, verbose_name='場所', help_text='研修・講習の場所を入力してください。')
    target = models.TextField(blank=True, verbose_name='対象', help_text='研修・講習の対象者を入力してください。')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    material = models.FileField("資料", upload_to="materials/", blank=True, null=True)
    external_thumb_url = models.URLField(blank=True, default="", verbose_name='外部サムネイルURL', help_text='外部URLから取得したサムネイルURLを保存します。')

    class Meta:
        verbose_name = '研修・講習'
        verbose_name_plural = '研修・講習'

    def __str__(self):
        return self.title

class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    q1_use_case = models.TextField("活用予定業務", blank=True, default="")
    q2_pre_issue = models.TextField("受講前課題", blank=True, default="")
    q3_post_state = models.TextField("受講後の状態", blank=True, default="")
    q4_purpose_summary = models.TextField("受講目的まとめ", blank=True, default="")
    completed = models.BooleanField(default=False)
    score = models.FloatField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending_supervisor', '上司承認待ち'),
        ('pending_kanri', '管理者承認待ち'),
        ('approved', '承認済み'),
        ('rejected', '拒否')
    ], default='pending_supervisor')
    report_file = models.FileField(upload_to='reports/', null=True, blank=True)
    report_approved_by_supervisor = models.BooleanField(default=False)
    report_approved_by_kanri = models.BooleanField(default=False)
    report_supervisor_approved_at = models.DateTimeField(null=True, blank=True)
    report_kanri_approved_at = models.DateTimeField(null=True, blank=True)
    report_supervisor_approved_by = models.ForeignKey(User, null=True, blank=True, related_name='supervisor_approved_reports', on_delete=models.SET_NULL)
    report_kanri_approved_by = models.ForeignKey(User, null=True, blank=True, related_name='kanri_approved_reports', on_delete=models.SET_NULL)
    report_status = models.CharField(
        max_length=20,
        choices=[
            ('pending_supervisor', '上司承認待ち'),
            ('pending_kanri', '管理者承認待ち'),
            ('approved', '承認済み'),
            ('rejected', '拒否')
        ],
        default='pending_supervisor'
    )
    report_supervisor_comment = models.TextField(blank=True, null=True)
    report_kanri_comment = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'course')
        verbose_name = '登録'
        verbose_name_plural = '登録'

class Certificate(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, verbose_name='登録', help_text='証明書を発行する登録を選択してください。')
    issued_date = models.DateTimeField(default=timezone.now, verbose_name='発行日時', help_text='証明書の発行日時を入力してください。')
    certificate_file = models.FileField(upload_to='certificates/', blank=True, null=True, verbose_name='証明書ファイル', help_text='証明書ファイルをアップロードしてください。')

    class Meta:
        verbose_name = '証明書'
        verbose_name_plural = '証明書'

    def __str__(self):
        return f"{self.enrollment.user.username} の証明書 - {self.enrollment.course.title}"

class ApprovalHistory(models.Model):
    enrollment = models.ForeignKey('Enrollment', on_delete=models.CASCADE, related_name='histories')
    action = models.CharField(max_length=20, choices=[('approve', '承認'), ('reject', '拒否')])
    comment = models.TextField(blank=True, null=True)
    acted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '承認履歴'
        verbose_name_plural = '承認履歴'

    def __str__(self):
        return f"{self.enrollment} - {self.get_action_display()} by {self.acted_by} at {self.acted_at}"

class BangCap(models.Model):
    LOAI_BANG = [
        ('QC検定', 'QC検定'),
        ('電気系資格', '電気系資格'),
        ('プラスチック成形技能', 'プラスチック成形技能'),
        ('国家資格', '国家資格'),
        ('講習研修修了証', '講習研修修了証'),
        ('クレーン運転', 'クレーン運転'),
        ('日本語能力', '日本語能力'),
        ('英語能力', '英語能力'),
        ('中国語能力', '中国語能力'),
        ('IT関係資格', 'IT関係資格'),
        ('その他', 'その他'),
        # Thêm loại khác nếu cần
    ]
    CAP_DO = [
        ('特急', '特急'),
        ('1級', '1級'),
        ('2級', '2級'),
        ('3級', '3級'),
        ('4級', '4級'),
        # Thêm cấp khác nếu cần
    ]
    nhan_vien = models.ForeignKey(NhanVien, on_delete=models.CASCADE, related_name='bang_caps')
    loai_bang = models.CharField(max_length=32, choices=LOAI_BANG)
    cap_do = models.CharField(max_length=8, choices=CAP_DO)
    file = models.FileField(upload_to='bangcap/')
    ngay_cap = models.DateField(null=True, blank=True)
    ghi_chu = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.nhan_vien.ten} - {self.loai_bang} - {self.cap_do}"

class MotivationalQuote(models.Model):
    text = models.CharField("名言", max_length=255)
    author = models.CharField("著者", max_length=100, blank=True, default="匿名")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.text} — {self.author}"

