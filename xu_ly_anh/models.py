from django.db import models
from django.contrib.auth.models import User





class DeviceInfo(models.Model):
    name = models.CharField(max_length=100)
    material = models.CharField(max_length=100)
    product = models.CharField(max_length=100)
    ratio = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} - {self.product}"

class XuLyAnh2(models.Model):
    machine = models.ForeignKey('DeviceInfo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="デバイス名")
    machine_number = models.PositiveIntegerField("Số máy", default=1)
    image = models.ImageField(upload_to='xu_ly_anh2/')
    processed_image = models.ImageField(upload_to='xu_ly_anh2/processed/', null=True, blank=True)
    data = models.TextField(blank=True)
    result = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Máy {self.machine_number} - {self.created_at}"

