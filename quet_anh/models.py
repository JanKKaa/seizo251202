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


class QAAutoInputLedger(models.Model):
    """Sổ cái quản lý luồng quét ảnh -> nhập liệu tự động."""

    phien_nhap_lieu = models.OneToOneField(
        "nhap_lieu.PhienNhapLieu",
        on_delete=models.CASCADE,
        related_name="qa_ledger",
        null=True,
        blank=True,
    )
    qa_result = models.ForeignKey(
        QAResult,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auto_input_ledgers",
    )

    job_id = models.CharField(max_length=64, db_index=True)
    job_status = models.CharField(max_length=20, db_index=True, blank=True, default="")
    job_message = models.TextField(blank=True, default="")
    workstation_ip = models.CharField(max_length=45, db_index=True, blank=True, default="")
    ma_nhap_lieu = models.TextField(blank=True, default="")
    full_text = models.TextField(blank=True, default="")

    qa_machine_number = models.CharField(max_length=100, blank=True, default="")
    qa_device_name = models.CharField(max_length=100, blank=True, default="")
    qa_material = models.CharField(max_length=100, blank=True, default="")
    qa_product = models.CharField(max_length=100, blank=True, default="")
    qa_ratio = models.CharField(max_length=50, blank=True, default="")
    qa_operator_name = models.CharField(max_length=100, blank=True, default="")
    qa_result_status = models.CharField(max_length=255, blank=True, default="")
    qa_match_ratio = models.FloatField(null=True, blank=True)
    qa_input_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sổ cái job nhập liệu tự động"
        verbose_name_plural = "Sổ cái job nhập liệu tự động"
        indexes = [
            models.Index(fields=["job_status", "-created_at"]),
            models.Index(fields=["workstation_ip", "-created_at"]),
            models.Index(fields=["job_id"]),
        ]

    def __str__(self):
        return f"{self.job_id} - {self.job_status}"
