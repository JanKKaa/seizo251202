from django import forms
from django.db.models import Q

from iot.models import Esp32CardSnapshot, Machine, MoldLifetime

from .models import EquipmentCatalogNode, EquipmentCategory, EquipmentItem, EquipmentPartLink, EquipmentPartReplacementHistory, EquipmentStockLedger


MOLD_PART_TYPES = {
    "mold_part",
    "mold_insert",
    "mold_core_pin",
    "mold_ejector_pin",
    "mold_slide_core",
    "mold_guide_part",
    "mold_spring",
    "mold_cooling_part",
    "mold_plate",
    "mold_hot_runner_part",
}


class EquipmentCategoryForm(forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = ["code", "name", "group", "parent", "description", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parent_queryset = EquipmentCategory.objects.filter(is_active=True).order_by("group", "code")
        if self.instance and self.instance.pk:
            parent_queryset = parent_queryset.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = parent_queryset
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs["class"] = css


class EquipmentCatalogNodeForm(forms.ModelForm):
    class Meta:
        model = EquipmentCatalogNode
        fields = ["code", "name", "item_kind", "parent", "sort_order", "is_active", "note"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parent_queryset = EquipmentCatalogNode.objects.filter(is_active=True).order_by("item_kind", "sort_order", "code")
        if self.instance and self.instance.pk:
            parent_queryset = parent_queryset.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = parent_queryset
        self.fields["code"].help_text = "例: MOLD-023-A, MOLD-023-A-900-Z, EQ-DRYER-MATSUI"
        self.fields["name"].help_text = "例: 023 cty A, 900 製品Z, runner lock, 乾燥機"
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs["class"] = css


class EquipmentItemForm(forms.ModelForm):
    class Meta:
        model = EquipmentItem
        fields = [
            "code",
            "name",
            "category",
            "catalog_node",
            "equipment_type",
            "item_kind",
            "equipment_group_name",
            "equipment_series_name",
            "maker",
            "model_no",
            "serial_no",
            "department",
            "maker_part_no",
            "applicable_machine_no",
            "applicable_mold_no",
            "mold_customer_code",
            "mold_customer_name",
            "mold_product_code",
            "mold_product_name",
            "mold_component_name",
            "mold_drawing_root_path",
            "mold_drawing_subfolder_path",
            "equipment_document_root_path",
            "equipment_document_subfolder_path",
            "shelf_no",
            "minimum_stock",
            "reorder_point",
            "quality_rank",
            "supplier_name",
            "location",
            "status",
            "current_quantity",
            "unit",
            "item_image",
            "nameplate_image",
            "note",
        ]

    def __init__(self, *args, fixed_item_kind=None, part_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        category_queryset = EquipmentCategory.objects.filter(is_active=True).select_related("parent").order_by("group", "parent__code", "code")
        catalog_queryset = EquipmentCatalogNode.objects.filter(is_active=True).select_related("parent").order_by("item_kind", "sort_order", "code")
        if fixed_item_kind == EquipmentItem.KIND_EQUIPMENT:
            category_queryset = category_queryset.filter(Q(code="EQUIPMENT-LEDGER") | Q(parent__code="EQUIPMENT-LEDGER"))
            catalog_queryset = catalog_queryset.filter(item_kind=EquipmentItem.KIND_EQUIPMENT)
        elif fixed_item_kind == EquipmentItem.KIND_MOLD:
            category_queryset = category_queryset.filter(Q(code="MOLD") | Q(parent__code="MOLD"))
            catalog_queryset = catalog_queryset.filter(item_kind=EquipmentItem.KIND_MOLD)
        elif fixed_item_kind == EquipmentItem.KIND_PART:
            category_queryset = category_queryset.exclude(Q(code="EQUIPMENT-LEDGER") | Q(parent__code="EQUIPMENT-LEDGER"))
            catalog_queryset = catalog_queryset.none()
            if part_scope == "mold_parts":
                category_queryset = category_queryset.filter(Q(code="MOLD") | Q(parent__code="MOLD"))
            elif part_scope == "equipment_parts":
                category_queryset = category_queryset.exclude(Q(code="MOLD") | Q(parent__code="MOLD"))
        self.fields["category"].queryset = category_queryset
        self.fields["catalog_node"].queryset = catalog_queryset
        if fixed_item_kind in {EquipmentItem.KIND_EQUIPMENT, EquipmentItem.KIND_MOLD, EquipmentItem.KIND_PART}:
            self.fields["item_kind"].initial = fixed_item_kind
            self.fields["item_kind"].widget = forms.HiddenInput()
        if fixed_item_kind == EquipmentItem.KIND_MOLD:
            self.fields["equipment_type"].choices = [choice for choice in EquipmentItem.TYPE_CHOICES if choice[0] == "mold"]
        elif fixed_item_kind == EquipmentItem.KIND_PART and part_scope == "mold_parts":
            self.fields["equipment_type"].choices = [choice for choice in EquipmentItem.TYPE_CHOICES if choice[0] in MOLD_PART_TYPES]
        elif fixed_item_kind == EquipmentItem.KIND_PART and part_scope == "equipment_parts":
            self.fields["equipment_type"].choices = [
                choice for choice in EquipmentItem.TYPE_CHOICES if choice[0] not in MOLD_PART_TYPES and choice[0] != "mold"
            ]
        self.fields["code"].help_text = "例: MOLD-PIN-001, JSW-HEATER-001"
        self.fields["name"].help_text = "現場で分かる名称を入力してください。"
        self.fields["maker_part_no"].help_text = "MISUMI/メーカー品番があれば入力します。"
        self.fields["equipment_group_name"].help_text = "例: 乾燥機, 粉砕機, 取出機"
        self.fields["equipment_series_name"].help_text = "例: ホッパードライヤー, 箱型乾燥機, メーカー型式シリーズ"
        self.fields["mold_drawing_root_path"].help_text = r"例: O:\共有フォルダー\04_生産技術課\13_図面\13.1.金型図\023マグプロスト"
        self.fields["mold_drawing_subfolder_path"].help_text = r"例: 900 製品Z\runner lock"
        self.fields["mold_customer_code"].help_text = "例: 023"
        self.fields["mold_customer_name"].help_text = "例: cty A"
        self.fields["mold_product_code"].help_text = "例: 900"
        self.fields["mold_product_name"].help_text = "例: 製品Z"
        self.fields["mold_component_name"].help_text = "例: runner lock, EP"
        self.fields["equipment_document_root_path"].help_text = r"例: O:\共有フォルダー\04_生産技術課\06_設備管理\乾燥機"
        self.fields["equipment_document_subfolder_path"].help_text = "例: MATSUI MJ3-50 21号機"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        for image_field in ["item_image", "nameplate_image"]:
            self.fields[image_field].widget.attrs.update({
                "accept": "image/*",
                "capture": "environment",
            })


class EquipmentPartLinkForm(forms.ModelForm):
    class Meta:
        model = EquipmentPartLink
        fields = ["asset", "part", "usage_location", "standard_quantity", "criticality", "replacement_cycle_days", "lifetime_shots", "shot_source_machine", "shot_source_mold", "note"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, asset=None, **kwargs):
        super().__init__(*args, **kwargs)
        asset_q = Q(item_kind__in=[EquipmentItem.KIND_EQUIPMENT, EquipmentItem.KIND_MOLD])
        part_q = Q(item_kind=EquipmentItem.KIND_PART)
        self.fields["asset"].queryset = EquipmentItem.objects.select_related("category").filter(asset_q).order_by("code")
        self.fields["part"].queryset = EquipmentItem.objects.select_related("category").filter(part_q).order_by("code")
        if asset is not None:
            self.fields["asset"].initial = asset
            self.fields["asset"].widget = forms.HiddenInput()
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        asset = cleaned.get("asset")
        machine = cleaned.get("shot_source_machine")
        mold = cleaned.get("shot_source_mold")
        if machine and mold:
            raise forms.ValidationError("shot元は成形機または金型のどちらか一つを選択してください。")
        if asset and asset.item_kind == EquipmentItem.KIND_EQUIPMENT and mold:
            self.add_error("shot_source_mold", "設備部品は成形機shot元を選択してください。")
        if asset and asset.item_kind == EquipmentItem.KIND_MOLD and machine:
            self.add_error("shot_source_machine", "金型部品は金型shot元を選択してください。")
        return cleaned


class IoTMachineChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return " / ".join(filter(None, [obj.setsubi_no, obj.name, obj.address, f"累積 {obj.shot_total} shot"]))


class IoTMoldLifetimeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return " / ".join(filter(None, [obj.mold.code, obj.mold.name, obj.condname, obj.esp32_machine, f"累積 {obj.total_shot} shot"]))


class IoTEsp32MachineChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        product = obj.primary_product or obj.product_display
        return " / ".join(filter(None, [f"ESP32 {obj.address}", product, f"累積 {obj.total_shot} shot"]))


class EquipmentShotSourceForm(forms.ModelForm):
    iot_machine = IoTMachineChoiceField(
        label="IoT側の成形機",
        queryset=Machine.objects.none(),
        required=False,
        help_text="名前が違っていても、アドレス・設備No.を確認して手動で選択します。",
    )
    iot_mold_lifetime = IoTMoldLifetimeChoiceField(
        label="IoT側の金型",
        queryset=MoldLifetime.objects.none(),
        required=False,
        help_text="setsubiの金型名と一致する必要はありません。正しいIoT金型を手動で選択します。",
    )
    iot_esp32_machine = IoTEsp32MachineChoiceField(
        label="IoT側のESP32成形機",
        queryset=Esp32CardSnapshot.objects.none(),
        required=False,
        help_text="ESP32でshotを取得する設備はこちらを選択します。",
    )

    class Meta:
        model = EquipmentItem
        fields = ["iot_machine", "iot_esp32_machine", "iot_mold_lifetime"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["iot_machine"].queryset = Machine.objects.filter(active=True).order_by("setsubi_no", "name", "address")
        self.fields["iot_esp32_machine"].queryset = Esp32CardSnapshot.objects.order_by("address")
        self.fields["iot_mold_lifetime"].queryset = MoldLifetime.objects.select_related("mold").order_by("mold__code", "mold__name", "condname")
        if self.instance.item_kind == EquipmentItem.KIND_EQUIPMENT:
            self.fields.pop("iot_mold_lifetime")
        elif self.instance.item_kind == EquipmentItem.KIND_MOLD:
            self.fields.pop("iot_machine")
            self.fields.pop("iot_esp32_machine")
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("iot_machine") and cleaned.get("iot_esp32_machine"):
            raise forms.ValidationError("成形機shot元はNET100またはESP32のどちらか一つを選択してください。")
        return cleaned


class EquipmentPartReplacementForm(forms.ModelForm):
    class Meta:
        model = EquipmentPartReplacementHistory
        fields = ["replaced_at", "operator_name", "note"]
        widgets = {
            "replaced_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "note": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["replaced_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class LedgerItemChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        tokens = [
            obj.code,
            obj.name,
            obj.category.full_name() if obj.category_id else "",
            obj.get_equipment_type_display(),
            obj.applicable_machine_no,
            obj.applicable_mold_no,
            obj.shelf_no,
            f"在庫 {obj.current_quantity} {obj.unit}",
        ]
        return " / ".join(str(token) for token in tokens if token)


class EquipmentStockLedgerForm(forms.Form):
    item = LedgerItemChoiceField(label="機器・部品", queryset=EquipmentItem.objects.none())
    transaction_type = forms.ChoiceField(label="取引区分", choices=EquipmentStockLedger.TRANSACTION_CHOICES)
    reason_code = forms.ChoiceField(label="理由", choices=EquipmentStockLedger.REASON_CHOICES)
    quantity = forms.DecimalField(label="数量", min_value=0)
    lot_no = forms.CharField(label="ロットNo.", required=False)
    from_location = forms.CharField(label="移動元", required=False)
    to_location = forms.CharField(label="移動先", required=False)
    memo = forms.CharField(label="理由メモ", widget=forms.Textarea, required=False)
    operator_name = forms.CharField(label="作業者", required=False)
    supervisor_confirmed = forms.BooleanField(label="上長確認済", required=False)
    supervisor_name = forms.CharField(label="確認者", required=False)

    def __init__(self, *args, transaction_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = EquipmentItem.objects.select_related("category").filter(item_kind=EquipmentItem.KIND_PART).order_by("code")
        self.fields["item"].widget.attrs["data-ledger-item-select"] = "1"
        if transaction_type:
            self.fields["transaction_type"].initial = transaction_type
            self.fields["transaction_type"].widget = forms.HiddenInput()
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs["class"] = css


class EquipmentStockLedgerEditForm(forms.ModelForm):
    class Meta:
        model = EquipmentStockLedger
        fields = [
            "item",
            "transaction_type",
            "reason_code",
            "quantity",
            "lot_no",
            "from_location",
            "to_location",
            "memo",
            "operator_name",
            "supervisor_confirmed",
            "supervisor_name",
        ]
        widgets = {
            "memo": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = EquipmentItem.objects.filter(item_kind=EquipmentItem.KIND_PART).order_by("code")
        self.fields["item"].disabled = True
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs["class"] = css
