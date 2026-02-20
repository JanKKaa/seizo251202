from django.db import models
from django.utils import timezone
import re

STATUS_CHOICES = [
    ("production", "稼働中"),
    ("stop", "停止"),
    ("arrange", "段取り中"),
    ("alarm", "アラーム"),
    ("offline", "オフライン"),
    ("unknown", "不明"),
]

class Machine(models.Model):
    """Máy ép / device.

    Giữ các field cần thiết; thêm indexes để tối ưu các truy vấn filter thường gặp.
    """
    address = models.CharField("IP/Address", max_length=50, unique=True, db_index=True)
    name = models.CharField("機械名", max_length=100, blank=True)
    condname = models.CharField("成形条件名", max_length=100, blank=True)

    status = models.CharField("状態", max_length=20, blank=True, default='production', db_index=True)
    active = models.BooleanField("Active", default=True, db_index=True)
    shot_total = models.PositiveIntegerField("Shot Total(DB)", default=0)
    last_shot = models.PositiveIntegerField("Last Shot(DB)", default=0)
    last_update = models.DateTimeField(auto_now=True)

    # Cho phép NULL để tránh prompt khi migrate
    setsubi_no = models.CharField("設備管理No", max_length=50, blank=True, null=True, db_index=True)
    model_type = models.CharField("型式", max_length=100, blank=True, null=True)
    manufacturer = models.CharField("メーカー", max_length=100, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["active"]),
            models.Index(fields=["setsubi_no"]),
        ]

    def __str__(self):
        return f"{self.address} - {self.name or ''}"



class Component(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='components')
    code = models.CharField("部品コード", max_length=50, db_index=True)
    name = models.CharField("部品名", max_length=100)
    lifetime = models.PositiveIntegerField("部品寿命（ショット数）")
    detail = models.CharField("部品詳細", max_length=200, blank=True)  # mô tả kỹ thuật (giữ nguyên)
    management_code = models.CharField("管理コード", max_length=100, blank=True, db_index=True)  # Mã số quản lý
    manufacturer = models.CharField("部品メーカー", max_length=100, blank=True)
    note = models.TextField("備考", blank=True, default='')
    baseline_shot = models.IntegerField(default=0, help_text="Shot của máy tại thời điểm lắp / thay mới", db_index=True)
    predicted_next_replacement = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["management_code"]),
            models.Index(fields=["baseline_shot"]),
        ]

    def __str__(self):
        mc = f"[{self.management_code}] " if self.management_code else ""
        return f"{mc}{self.machine.name} - {self.name}"

class ComponentReplacementHistory(models.Model):
    component = models.ForeignKey(Component, related_name='replacement_histories', on_delete=models.CASCADE)
    replaced_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, default='')
    shot_at_replacement = models.IntegerField(null=True, blank=True)
    baseline_shot_before = models.IntegerField(null=True, blank=True)
    image1 = models.ImageField(upload_to='component_replace/', null=True, blank=True)
    image2 = models.ImageField(upload_to='component_replace/', null=True, blank=True)
    image3 = models.ImageField(upload_to='component_replace/', null=True, blank=True)
    image4 = models.ImageField(upload_to='component_replace/', null=True, blank=True)
    image5 = models.ImageField(upload_to='component_replace/', null=True, blank=True)
    confirmed_by = models.CharField(max_length=100, blank=True, default='')
    attachment = models.FileField(upload_to='component_attachments/', null=True, blank=True)

    class Meta:
        ordering = ['-replaced_at']

    def images(self):
        return [f for f in [self.image1, self.image2, self.image3, self.image4, self.image5] if f]

    def __str__(self):
        return f"{self.component.name} ({self.replaced_at})"

class Mold(models.Model):
    STATUS_CHOICES = [
        ('active', '生産中'),
        ('inactive', '生産終了'),
    ]
    name = models.CharField(max_length=100)
    code = models.CharField("金型品番", max_length=100, blank=True, default="")
    status = models.CharField("状態", max_length=10, choices=STATUS_CHOICES, default='active')  # Thêm trường này

    def __str__(self):
        return self.name

class MoldLifetime(models.Model):
    mold = models.ForeignKey(Mold, on_delete=models.CASCADE, related_name='lifetimes')
    condname = models.CharField(max_length=255, blank=True, null=True)
    esp32_machine = models.CharField(max_length=20, blank=True, default="")
    esp32_product_name = models.CharField(max_length=150, blank=True, default="")
    total_shot = models.PositiveIntegerField(default=0)
    lifetime = models.IntegerField(default=1000000)
    last_shot = models.IntegerField(default=0)  # Thêm dòng này
    last_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.mold.name} - {self.condname}"

class CycleHistory(models.Model):
    """(DEPRECATED) Không còn dùng trong logic hiện tại.

    Giữ lại để tránh lỗi import; đặt managed=False để Django không tạo / sửa bảng.
    Có thể xoá hẳn sau khi backup DB và xoá mọi import liên quan.
    """
    condname = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    value = models.FloatField(default=0)

    class Meta:
        managed = False

    def __str__(self):
        return f"{self.condname} - {self.timestamp}"

class ManualMachine(models.Model):
    name = models.CharField(max_length=100)
    condname = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, default='manual')
    shotno = models.IntegerField(default=0)
    cycletime = models.FloatField(default=0)
    note = models.TextField(blank=True)

class ArduinoPinLog(models.Model):
    address = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    pin3 = models.IntegerField(null=True, blank=True)
    pin6 = models.IntegerField(null=True, blank=True)
    pin7 = models.IntegerField(null=True, blank=True)
    pin8 = models.IntegerField(null=True, blank=True)
    pin9 = models.IntegerField(null=True, blank=True)
    pin10 = models.IntegerField(null=True, blank=True)
    pin11 = models.IntegerField(null=True, blank=True)
    pin12 = models.IntegerField(null=True, blank=True)
    A0 = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.address} @ {self.timestamp}"

class MachineStatusEvent(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="status_events")
    status_code = models.CharField(max_length=16, choices=STATUS_CHOICES)
    status_jp = models.CharField(max_length=16)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["created_at","status_code"])]

    def __str__(self):
        return f"{self.machine.name} {self.status_code} {self.created_at:%H:%M:%S}"

class MachineAlarmEvent(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="alarm_events")
    alarm_code = models.CharField(max_length=32, blank=True, null=True, db_index=True)
    alarm_name = models.CharField(max_length=128, blank=True, null=True)
    message = models.CharField(max_length=256, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    cleared_at = models.DateTimeField(blank=True, null=True, db_index=True)
    occurrence_count = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["cleared_at"]),
            models.Index(fields=["alarm_code"]),
        ]

    @property
    def is_active(self):
        return self.cleared_at is None

    def __str__(self):
        state = "ACTIVE" if self.is_active else "CLEARED"
        return f"{self.machine.name} {self.alarm_code} {state}"

class DashboardNotification(models.Model):
    message = models.TextField()
    priority = models.IntegerField(default=1)
    is_alarm = models.BooleanField(default=False)
    sender = models.CharField(max_length=255, blank=True)
    appear_at = models.DateTimeField(default=timezone.now)   # Thêm dòng này
    expire_at = models.DateTimeField()                       # Thêm dòng này

    def __str__(self):
        return self.message


 

class MailLog(models.Model):
    mail_uid = models.CharField(max_length=128, unique=True)
    sender = models.CharField(max_length=128, blank=True)
    subject = models.CharField(max_length=256, blank=True)
    received_at = models.DateTimeField()
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class DemAlarm(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=0)
    last_update_year = models.IntegerField(default=0)
    last_update_month = models.IntegerField(default=0)

    class Meta:
        unique_together = ('machine',)



class Esp32Device(models.Model):
    device_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=64, blank=True)
    last_update = models.DateTimeField(auto_now=True)

class Esp32StatusLog(models.Model):
    device = models.ForeignKey(Esp32Device, on_delete=models.CASCADE)
    pins = models.JSONField()
    status_code = models.CharField(max_length=32)
    status_jp = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

class Esp32AlarmEvent(models.Model):
    device = models.ForeignKey(Esp32Device, on_delete=models.CASCADE)
    alarm_code = models.CharField(max_length=32, blank=True, null=True)
    alarm_name = models.CharField(max_length=128, blank=True, null=True)
    alarm_content = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    cleared_at = models.DateTimeField(blank=True, null=True, db_index=True)

    @property
    def is_active(self):
        return self.cleared_at is None

    def __str__(self):
        state = "ACTIVE" if self.is_active else "CLEARED"
        return f"{self.device.name or self.device.device_id} {self.alarm_code} {state}"

class Esp32AlarmCount(models.Model):
    address = models.CharField(max_length=32, unique=True)
    count = models.IntegerField(default=0)
    last_status = models.CharField(max_length=16, default="")
    last_update_year = models.IntegerField(default=0)
    last_update_month = models.IntegerField(default=0)
    last_status_change_time = models.DateTimeField(null=True, blank=True)
    # Thêm trường này để lưu trạng thái đã gửi email alarm
    alarm_sent_this_time = models.BooleanField(default=False)
    # Có thể thêm các trường khác nếu cần

    def __str__(self):
        return f"{self.address} ({self.last_status})"

class Esp32CycleShot(models.Model):
    address = models.CharField(max_length=20, unique=True)
    shot = models.PositiveIntegerField(default=0)      # giá trị counter hiện tại trên máy
    cycletime = models.FloatField(default=0.0)
    last_ej_on = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    shotplan = models.PositiveIntegerField(default=0, help_text="Tổng số shot kế hoạch trong tháng", db_index=True)
    current_product = models.CharField(max_length=100, default="", help_text="Tên sản phẩm hiện tại", db_index=True)
    # NEW: giống Net100
    month = models.CharField(max_length=7, default="", db_index=True)  # "YYYY-MM"
    monthly_shot = models.PositiveIntegerField(default=0)              # shot tích lũy trong tháng hiện tại

    def __str__(self):
        return f"{self.address} (shot: {self.shot}, monthly: {self.monthly_shot}, shotplan: {self.shotplan})"

class ProductionPlan(models.Model):
    machine = models.CharField(max_length=64)
    plan_shot = models.IntegerField(default=0)
    plan_date = models.DateField()
    product_name = models.CharField(max_length=128, blank=True, default='')
    plan_month_year = models.CharField(max_length=16, blank=True, default='')    # Tháng/năm kế hoạch
    plan_created_date = models.CharField(max_length=16, blank=True, default='')  # Ngày tạo file CSV
    cell_note = models.CharField(max_length=256, blank=True, default='')  # Thông tin bổ sung cho cell
    note_color = models.CharField(max_length=32, blank=True, default='bg-secondary')

    def __str__(self):
        return f"{self.machine} - {self.plan_date} - {self.product_name} - {self.plan_shot}"

class Change4MEntry(models.Model):
    code = models.CharField(max_length=16, default='4M')
    message = models.CharField(max_length=255)
    detail = models.TextField(blank=True, default='')
    reporter = models.CharField(max_length=128, blank=True, default='')
    tags = models.CharField(
        max_length=512,
        blank=True,
        default='',
        help_text='タグをカンマ(,)または読点(、)で区切って複数指定できます。',
    )
    highlight = models.BooleanField(default=False)
    active_from = models.DateTimeField(default=timezone.now)
    active_until = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-active_from', '-created_at']

    def tag_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in re.split(r'[,\u3001]', self.tags) if t.strip()]

    def __str__(self):
        return f"{self.code} - {self.message}"

class Esp32CardSnapshot(models.Model):
    address = models.CharField(max_length=20, unique=True)
    product_display = models.CharField(max_length=255, blank=True, default="")
    primary_product = models.CharField(max_length=150, blank=True, default="")
    shot = models.IntegerField(default=0)
    cycletime = models.CharField(max_length=20, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.address} ({self.primary_product})"

class ChatworkMessage(models.Model):
    message = models.TextField("メッセージ内容")
    sender = models.CharField("送信者", max_length=128, blank=True, default='')
    time = models.DateTimeField("受信日時", default=timezone.now, db_index=True)
    image_url = models.TextField(blank=True, null=True)
    room_id = models.CharField("ルームID", max_length=64, blank=True, default='')
    message_id = models.CharField("メッセージID", max_length=64, blank=True, default='', unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    

    class Meta:
        ordering = ['-time', '-created_at']

    def __str__(self):
        return f"{self.sender} @ {self.time:%Y-%m-%d %H:%M} - {self.message[:30]}"

class ProductShotMaster(models.Model):
    machine = models.CharField(max_length=64, db_index=True)
    product_name = models.CharField(max_length=128, db_index=True)
    standard_shot = models.PositiveIntegerField(default=0, help_text="Giá trị shot chuẩn cho sản phẩm này trên máy này")
    kodori = models.PositiveIntegerField(default=1, help_text="Số lượng sản phẩm trong 1 shot", db_index=True)  # Thêm trường này
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        unique_together = ('machine', 'product_name')

    def __str__(self):
        return f"{self.machine} - {self.product_name}: {self.standard_shot} (kodori: {self.kodori})"

class Net100CycleShot(models.Model):
    address = models.CharField(max_length=20, db_index=True)
    name = models.CharField(max_length=100, default="", db_index=True)  # Thêm trường này
    shot = models.PositiveIntegerField(default=0)
    cycletime = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)
    shotplan = models.PositiveIntegerField(default=0, help_text="Tổng số shot kế hoạch trong tháng", db_index=True)
    current_product = models.CharField(max_length=100, default="", help_text="Tên sản phẩm hiện tại", db_index=True)
    month = models.CharField(max_length=7, db_index=True)  # "YYYY-MM"
     # Thêm trường mới:
    monthly_shot = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.address} ({self.name}) {self.month}: {self.shot}"

class ProductMonthlyShot(models.Model):
    SOURCE_CHOICES = [
        ("net100", "NET100"),
        ("esp32", "ESP32"),
    ]
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    address = models.CharField(max_length=20, db_index=True)      # "28号機" ...
    machine_name = models.CharField(max_length=100, blank=True)   # "28号機" / "1号機" ...
    product_name = models.CharField(max_length=100, db_index=True)
    month = models.CharField(max_length=7, db_index=True)         # "YYYY-MM"
    shot = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("source", "address", "product_name", "month")

    def __str__(self):
        return f"{self.source}:{self.address} {self.product_name} {self.month} = {self.shot}"
