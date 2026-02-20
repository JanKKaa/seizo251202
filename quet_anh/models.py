from django.db import models
from django.contrib.auth.models import User

class QADeviceInfo(models.Model):
    name = models.CharField(max_length=100)
    material = models.CharField(max_length=100)
    product = models.CharField(max_length=100)
    ratio = models.CharField("混合率", max_length=50, blank=True, default="")
    compare_ratio = models.DecimalField("画像とQR比較一致率(%)", max_digits=5, decimal_places=2, default=80)

    def __str__(self):
        return f"{self.name} - {self.product}"

class QAResult(models.Model):
    device = models.ForeignKey(QADeviceInfo, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="デバイス名")
    machine_number = models.CharField(max_length=100)
    image = models.ImageField(upload_to='quet_anh2/')
    processed_image = models.ImageField(upload_to='quet_anh2/processed/', null=True, blank=True)
    data = models.TextField(blank=True)
    result = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    operator_name = models.CharField(max_length=100, blank=True, verbose_name="作業者名")
    match_ratio = models.FloatField("一致率（％）", null=True, blank=True)
    input_weight = models.DecimalField("投入した材料の重さ (kg)", max_digits=8, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"機械番号 {self.machine_number} - {self.created_at}"
