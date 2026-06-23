from django.contrib import admin

from .models import EquipmentCatalogNode, EquipmentCategory, EquipmentItem, EquipmentPartLink, EquipmentStockLedger


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "parent", "group", "is_active", "updated_at")
    list_filter = ("group", "parent", "is_active")
    search_fields = ("code", "name", "parent__name", "description")


@admin.register(EquipmentCatalogNode)
class EquipmentCatalogNodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "item_kind", "parent", "sort_order", "is_active", "updated_at")
    list_filter = ("item_kind", "is_active")
    search_fields = ("code", "name", "parent__name", "note")


@admin.register(EquipmentItem)
class EquipmentItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "maker_part_no", "quality_rank", "category", "equipment_type", "status", "current_quantity", "unit", "shelf_no", "minimum_stock", "reorder_point", "next_inventory_check_date", "has_item_image")
    list_filter = ("quality_rank", "category__group", "category", "equipment_type", "status", "location", "department")
    search_fields = (
        "code",
        "name",
        "internal_name",
        "maker_part_no",
        "alternative_part_no",
        "control_plan_no",
        "process_owner",
        "supplier_name",
        "applicable_machine_no",
        "applicable_mold_no",
        "mold_customer_code",
        "mold_customer_name",
        "mold_product_code",
        "mold_product_name",
        "mold_component_name",
        "mold_drawing_root_path",
        "mold_drawing_subfolder_path",
        "equipment_group_name",
        "equipment_series_name",
        "equipment_document_root_path",
        "equipment_document_subfolder_path",
        "shelf_no",
        "serial_no",
        "model_no",
        "maker",
        "location",
        "department",
    )

    @admin.display(boolean=True, description="写真")
    def has_item_image(self, obj):
        return bool(obj.item_image)


@admin.register(EquipmentPartLink)
class EquipmentPartLinkAdmin(admin.ModelAdmin):
    list_display = ("asset", "part", "usage_location", "standard_quantity", "criticality", "replacement_cycle_days", "updated_at")
    list_filter = ("criticality", "asset__category", "part__category")
    search_fields = ("asset__code", "asset__name", "part__code", "part__name", "usage_location", "note")


@admin.register(EquipmentStockLedger)
class EquipmentStockLedgerAdmin(admin.ModelAdmin):
    list_display = ("system_no", "item", "transaction_type", "reason_code", "quantity", "quantity_before", "quantity_after", "operator_name", "supervisor_confirmed", "created_at")
    list_filter = ("transaction_type", "reason_code", "supervisor_confirmed", "created_at")
    search_fields = ("system_no", "item__code", "item__name", "lot_no", "operator_name", "supervisor_name", "memo")
    readonly_fields = ("system_no", "quantity_before", "quantity_after", "created_at")
