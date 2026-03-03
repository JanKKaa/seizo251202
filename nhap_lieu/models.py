from django.db import models
from django.contrib.auth.models import User


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
    ip = models.GenericIPAddressField(protocol="both", unpack_ipv4=True, blank=True, null=True)
    mo_ta = models.CharField(max_length=255, blank=True)
    nguoi_phu_trach = models.CharField(max_length=100, blank=True)
    trang_thai = models.CharField(
        max_length=20,
        choices=[("active", "Đang hoạt động"), ("inactive", "Không hoạt động")],
        default="active",
    )

    def __str__(self):
        return self.ten_hien_thi or self.ten_may


class KetQuaNhapLieu(models.Model):
    """Lưu kết quả callback từ máy trạm nhập liệu."""

    chuong_trinh = models.ForeignKey(ChuongTrinhNhapLieu, on_delete=models.CASCADE, null=True, blank=True)
    may_tinh = models.ForeignKey(MayTinh, on_delete=models.CASCADE, null=True, blank=True)
    ip_may = models.CharField(max_length=45, db_index=True, help_text="IP máy gửi dữ liệu")
    ma_nhap_lieu = models.TextField(help_text="Dữ liệu text được copy từ app")
    full_text = models.TextField(blank=True, help_text="Toàn bộ text (nếu có)")
    trang_thai = models.CharField(
        max_length=50,
        default="Chờ xử lý",
        db_index=True,
        choices=[
            ("Chờ xử lý", "Chờ xử lý"),
            ("Thành công", "Thành công"),
            ("Lỗi", "Lỗi"),
        ],
    )
    ghi_chu = models.TextField(blank=True)
    ngay_nhan = models.DateTimeField(auto_now_add=True, db_index=True)
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ngay_nhan"]
        verbose_name_plural = "Kết quả nhập liệu"
        indexes = [
            models.Index(fields=["ip_may", "-ngay_nhan"]),
            models.Index(fields=["trang_thai", "-ngay_nhan"]),
        ]

    def __str__(self):
        return f"{self.ip_may} - {self.ma_nhap_lieu[:50]} ({self.ngay_nhan})"
