from django.contrib import admin

from .models import QADeviceInfo, QAResult, QAMaterialMaster, QAAutoInputLedger, QAMaterialStockLedger, QAMaterialOutStockLedger


@admin.register(QADeviceInfo)
class QADeviceInfoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "maintenance_task",
        "material_code",
        "material",
        "product_name",
        "product_management_code",
        "ratio",
        "compare_ratio",
    )
    search_fields = ("name", "material_code", "material", "product", "maintenance_task__name", "maintenance_task__code")


@admin.register(QAResult)
class QAResultAdmin(admin.ModelAdmin):
    list_display = ("id", "machine_number", "operator_name", "product_code", "result", "match_ratio", "created_at")
    search_fields = ("machine_number", "operator_name", "product_code", "data", "result")
    list_filter = ("result", "created_at")


@admin.register(QAMaterialMaster)
class QAMaterialMasterAdmin(admin.ModelAdmin):
    list_display = ("id", "material_name", "material_code", "bag_weight_kg", "qr_content", "is_active", "updated_at")
    search_fields = ("material_name", "material_code", "qr_content", "qr_content_in")
    list_filter = ("is_active", "updated_at")


@admin.register(QAAutoInputLedger)
class QAAutoInputLedgerAdmin(admin.ModelAdmin):
    list_display = ("id", "job_id", "job_status", "workstation_ip", "qa_machine_number", "ma_nhap_lieu", "created_at")
    search_fields = ("job_id", "workstation_ip", "qa_machine_number", "qa_material", "qa_product", "ma_nhap_lieu")
    list_filter = ("job_status", "created_at")


@admin.register(QAMaterialStockLedger)
class QAMaterialStockLedgerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "auto_input_ledger",
        "stock_in_date",
        "material_name",
        "material_code",
        "hinmei_name",
        "lot_number",
        "order_no",
        "lot_color",
        "weight_kg",
        "workstation_management_no",
        "supervisor_confirmed",
    )
    search_fields = (
        "material_name",
        "material_code",
        "hinmei_name",
        "lot_number",
        "order_no",
        "workstation_management_no",
        "supervisor_name",
        "auto_input_ledger__job_id",
    )
    list_filter = ("stock_in_date", "lot_color", "supervisor_confirmed")


@admin.register(QAMaterialOutStockLedger)
class QAMaterialOutStockLedgerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "auto_input_ledger",
        "stock_out_date",
        "material_name",
        "material_code",
        "lot_number",
        "product_code",
        "lot_color",
        "weight_kg",
        "workstation_management_no",
        "supervisor_confirmed",
    )
    search_fields = (
        "material_name",
        "material_code",
        "lot_number",
        "product_code",
        "workstation_management_no",
        "supervisor_name",
        "auto_input_ledger__job_id",
    )
    list_filter = ("stock_out_date", "lot_color", "supervisor_confirmed")
