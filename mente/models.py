from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User
from datetime import timedelta

class Product(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    machine_count = models.IntegerField()
    
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="作成者")
    created_at = models.DateTimeField(default=now)  # Thời gian khởi tạo
    product_image = models.ImageField(upload_to='product_images/', blank=True, null=True)  # Hình ảnh sản phẩm
    mold_image = models.ImageField(upload_to='mold_images/', blank=True, null=True)  # Hình ảnh khuôn
    start_time = models.DateTimeField(null=True, blank=True)  # Thời gian bắt đầu kiểm tra

     # Thêm các trường mới
    quantity = models.CharField(
        max_length=50,
        verbose_name="取数",
        blank=True,
        null=True,
        default="2個取り"  # Giá trị mặc định
    )
    material = models.CharField(
        max_length=50,
        verbose_name="材料",
        blank=True,
        null=True,
        default="未設定"  # Giá trị mặc định
    ) 
    maintenance_frequency = models.CharField(
        max_length=50,
        verbose_name="メンテナンス頻度",
        blank=True,
        null=True,
        default="毎月"  # Giá trị mặc định
    )  
    def __str__(self):
        return self.name

class Checksheet(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='checksheets')
    item = models.CharField(max_length=255)  # Hạng mục
    description = models.TextField(blank=True, null=True)  # Mô tả
    reference_image = models.ImageField(upload_to='reference_images/', blank=True, null=True)  # Hình ảnh tham khảo
    current_image = models.ImageField(upload_to='current_images/', blank=True, null=True)  # Hình ảnh hiện tại
    drawing_size = models.CharField(max_length=100, blank=True, null=True)  # Kích thước bản vẽ
    actual_size = models.CharField(max_length=100, blank=True, null=True)  # Kích thước thực tế
    is_checked = models.BooleanField(default=False)  # Checkbox
    checker_name = models.CharField(max_length=255, blank=True, null=True)  # Tên người kiểm tra
    approver_name = models.CharField(max_length=255, blank=True, null=True)  # Tên người phê duyệt
    status = models.CharField(max_length=50, choices=[('Đạt', 'Đạt'), ('Không đạt', 'Không đạt')], blank=True, null=True)
    notes = models.TextField(blank=True, null=True)  # Ghi chú

    def __str__(self):
        return f"{self.item} - {self.product.name}"

class LichSuKiemTra(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='lich_su_kiem_tra')
    item = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    reference_image = models.ImageField(upload_to='lich_su_kiem_tra/reference_images/', null=True, blank=True)
    current_image = models.ImageField(upload_to='lich_su_kiem_tra/current_images/', null=True, blank=True)
    drawing_size = models.CharField(max_length=255, null=True, blank=True)
    actual_size = models.CharField(max_length=255, null=True, blank=True)
    is_checked = models.BooleanField(default=False)
    checker_name = models.CharField(max_length=255, null=True, blank=True)
    approver_name = models.CharField(max_length=255, null=True, blank=True)
    start_time = models.DateTimeField(verbose_name="開始時間")
    end_time = models.DateTimeField(verbose_name="終了時間", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def duration_formatted(self):
        if self.start_time and self.end_time:
            duration_seconds = (self.end_time - self.start_time).total_seconds()
            duration = str(timedelta(seconds=duration_seconds)).split(".")[0]
            return duration
        return "不明"

    def __str__(self):
        return f"Lịch sử kiểm tra - {self.product.name} - {self.item}"

class Checker(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
