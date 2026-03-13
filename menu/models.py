from django.conf import settings
from django.db import models
from django.utils import timezone

class MonAn(models.Model):
    ten = models.CharField(max_length=100)
    mo_ta = models.TextField(blank=True)
    gia = models.DecimalField(max_digits=8, decimal_places=0)
    gia2 = models.DecimalField(max_digits=8, decimal_places=0, null=True, blank=True)  # Giá thứ 2
    hinh_anh = models.ImageField(upload_to='menu/', blank=True, null=True)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ten

class NhanVien(models.Model):
    ma_so = models.CharField("社員番号", max_length=20, unique=True)
    ten = models.CharField("氏名", max_length=100)
    supervisor = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates', verbose_name='上司')
    email = models.EmailField(max_length=255, null=True, blank=True, verbose_name="Email")
    chuc_vu = models.CharField("役職", max_length=100, blank=True, null=True)  # Thêm trường chức vụ
    created_at = models.DateTimeField("作成日時", default=timezone.now)

    class Meta:
        verbose_name = '社員'
        verbose_name_plural = '社員'

    def __str__(self):
        return f"{self.ma_so} - {self.ten}"

class Order(models.Model):
    ma_nv = models.CharField("社員番号", max_length=20)
    ten_nv = models.CharField("氏名", max_length=100, blank=True)
    mon_an = models.ForeignKey(MonAn, on_delete=models.CASCADE)
    so_luong = models.PositiveIntegerField(default=1)
    ghi_chu = models.TextField("備考", blank=True)
    thoi_gian = models.DateTimeField(auto_now_add=True)  # Ngày đặt hàng (tự động)
    ngay_giao = models.DateField(null=True, blank=True)  # Ngày giao hàng (người dùng chọn)
    calamviec = models.CharField(
        max_length=10,
        choices=[('日勤', '日勤'), ('夜勤', '夜勤')],
        default='日勤',
        verbose_name='勤務区分'
    )

    def __str__(self):
        return f"{self.ma_nv} - {self.ten_nv} - {self.mon_an.ten} ({self.so_luong})"

    @property
    def order_date(self):
        return self.thoi_gian.date()

class Holiday(models.Model):
    date = models.DateField(unique=True, verbose_name="休日の日付")
    note = models.CharField(max_length=100, blank=True, verbose_name="備考")

    def __str__(self):
        return f"{self.date} {self.note}"

class FaxStatus(models.Model):
    ngay = models.DateField(unique=True)
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    def __str__(self):
        return f"{self.ngay} - {'SENT' if self.sent else 'PENDING'}"
