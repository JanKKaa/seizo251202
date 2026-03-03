from django.contrib import admin

from .models import ChuongTrinhNhapLieu, KetQuaNhapLieu, MayTinh, PhienNhapLieu


@admin.register(PhienNhapLieu)
class PhienNhapLieuAdmin(admin.ModelAdmin):
    list_display = ("ma_job", "ip_may", "trang_thai", "ma_nhap_lieu", "ngay_tao", "ngay_cap_nhat")
    search_fields = ("ma_job", "ip_may", "ma_nhap_lieu")
    list_filter = ("trang_thai", "ngay_tao")


@admin.register(KetQuaNhapLieu)
class KetQuaNhapLieuAdmin(admin.ModelAdmin):
    list_display = ("id", "ip_may", "ma_nhap_lieu", "trang_thai", "ngay_nhan")
    search_fields = ("ip_may", "ma_nhap_lieu")
    list_filter = ("trang_thai", "ngay_nhan")


admin.site.register(ChuongTrinhNhapLieu)
admin.site.register(MayTinh)
