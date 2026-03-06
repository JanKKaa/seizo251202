from django.contrib import admin

from .models import QADeviceInfo, QAResult, QAAutoInputLedger


@admin.register(QADeviceInfo)
class QADeviceInfoAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "material", "product", "ratio", "compare_ratio")
    search_fields = ("name", "material", "product")


@admin.register(QAResult)
class QAResultAdmin(admin.ModelAdmin):
    list_display = ("id", "machine_number", "operator_name", "result", "match_ratio", "created_at")
    search_fields = ("machine_number", "operator_name", "data", "result")
    list_filter = ("result", "created_at")


@admin.register(QAAutoInputLedger)
class QAAutoInputLedgerAdmin(admin.ModelAdmin):
    list_display = ("id", "job_id", "job_status", "workstation_ip", "qa_machine_number", "ma_nhap_lieu", "created_at")
    search_fields = ("job_id", "workstation_ip", "qa_machine_number", "qa_material", "qa_product", "ma_nhap_lieu")
    list_filter = ("job_status", "created_at")
