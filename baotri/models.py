from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User

class MaintenanceTask(models.Model):
    name = models.CharField(max_length=255, verbose_name="製品名")
    code = models.CharField(max_length=50, verbose_name="コード")
    machine_count = models.IntegerField(verbose_name="機械番号")
    quantity = models.CharField(max_length=50, verbose_name="取数", blank=True, null=True, default="未定義")
    material = models.CharField(max_length=50, verbose_name="材料", blank=True, null=True, default="未定義")
    maintenance_frequency = models.CharField(max_length=50, verbose_name="メンテナンス頻度", blank=True, null=True, default="毎月")
    task_image = models.ImageField(upload_to='task_images/', blank=True, null=True, verbose_name="製品画像")
    product_image = models.ImageField(upload_to='product_images/', blank=True, null=True, verbose_name="金型画像")  # Thêm trường hình ảnh sản phẩm
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="作成者")
    created_at = models.DateTimeField(default=now, verbose_name="作成日時")
    start_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

class TaskDetail(models.Model):
    task = models.ForeignKey(MaintenanceTask, on_delete=models.CASCADE, related_name='details')
    item = models.CharField(max_length=255, verbose_name="作業名")
    description = models.TextField(verbose_name="説明", blank=True, null=True)
    reference_image = models.ImageField(upload_to='task_details/', blank=True, null=True, verbose_name="参考画像")
    drawing_size = models.CharField(max_length=50, verbose_name="寸法", blank=True, null=True)
    order = models.PositiveIntegerField(default=1)  # Thêm trường này

    def __str__(self):
        return self.item

class TaskResult(models.Model):
    task = models.ForeignKey(MaintenanceTask, on_delete=models.CASCADE, related_name='results')
    detail = models.ForeignKey(TaskDetail, on_delete=models.CASCADE, related_name='results')
    result = models.TextField(verbose_name="結果")
    actual_image = models.ImageField(upload_to='actual_images/', blank=True, null=True, verbose_name="実際の画像")
    actual_size = models.CharField(max_length=50, verbose_name="実際の寸法", blank=True, null=True)
    maintainer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="担当者")
    is_confirmed = models.BooleanField(default=False, verbose_name="確認済み")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")

    def __str__(self):
        return f"{self.detail.item} の結果"

class TaskCode(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="コード")
    task = models.ForeignKey('MaintenanceTask', on_delete=models.CASCADE, related_name='task_codes')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="作成者")
    created_at = models.DateTimeField(default=now, verbose_name="作成日時")
    end_time = models.DateTimeField(null=True, blank=True)  # Thêm trường này
    is_confirmed_by_supervisor = models.BooleanField(default=False)
    supervisor_stamp = models.ImageField(upload_to='stamps/', null=True, blank=True)
    supervisor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='confirmed_tasks')
    supervisor_confirmed_at = models.DateTimeField(null=True, blank=True)
    supervisor_comment = models.TextField(null=True, blank=True)
    counter_total = models.IntegerField(default=0, blank=True, null=True, verbose_name="カウンター総数")

    def __str__(self):
        return self.code

class TaskCodeDetail(models.Model):
    task_code = models.ForeignKey(TaskCode, on_delete=models.CASCADE, related_name='details', verbose_name="タスクコード")
    detail = models.ForeignKey(TaskDetail, on_delete=models.CASCADE, related_name='task_code_details', verbose_name="作業詳細")
    result = models.TextField(verbose_name="結果", blank=True, null=True)
    actual_image = models.ImageField(upload_to='task_code_details/', blank=True, null=True, verbose_name="実際の写真")
    actual_size = models.CharField(max_length=50, verbose_name="実際の寸法", blank=True, null=True)
    maintainer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="担当者")
    is_confirmed = models.BooleanField(default=False, verbose_name="確認済み")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    counter_total = models.IntegerField(default=0, blank=True, null=True, verbose_name="カウンター総数")

    def __str__(self):
        return f"{self.task_code.code} - {self.detail.item}"

class MaintenanceMistake(models.Model):
    product = models.ForeignKey('MaintenanceTask', on_delete=models.SET_NULL, null=True, verbose_name="製品")
    description = models.TextField(verbose_name="内容・原因")
    solution = models.TextField(verbose_name="対策", blank=True)
    image1 = models.ImageField(upload_to='mistake_images/', null=True, blank=True, verbose_name="参考画像1")
    image2 = models.ImageField(upload_to='mistake_images/', null=True, blank=True, verbose_name="参考画像2")
    image3 = models.ImageField(upload_to='mistake_images/', null=True, blank=True, verbose_name="参考画像3")
    image4 = models.ImageField(upload_to='mistake_images/', null=True, blank=True, verbose_name="参考画像4")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.task_code.code} - {self.description[:20]}"

