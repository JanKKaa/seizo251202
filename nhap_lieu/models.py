from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class ChuongTrinhNhapLieu(models.Model):
    ten_chuong_trinh = models.CharField(max_length=255, unique=True)
    dong1 = models.CharField(max_length=255, blank=True)
    dong2 = models.CharField(max_length=255, blank=True)
    dong3 = models.CharField(max_length=255, blank=True)
    dong4 = models.CharField(max_length=255, blank=True)
    dong5 = models.CharField(max_length=255, blank=True)
    quy_tac = models.TextField(help_text="Lưu thứ tự nhập liệu, dạng JSON hoặc text")
    nguoi_thiet_ke = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ten_chuong_trinh

class MayTinh(models.Model):
    ten_may = models.CharField(max_length=100, unique=True)
    ten_hien_thi = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(protocol='both', unpack_ipv4=True, blank=True, null=True)
    mo_ta = models.CharField(max_length=255, blank=True)
    nguoi_phu_trach = models.CharField(max_length=100, blank=True)
    trang_thai = models.CharField(max_length=20, choices=[('active', 'Đang hoạt động'), ('inactive', 'Không hoạt động')], default='active')

    def __str__(self):
        return self.ten_hien_thi or self.ten_may
