from django import forms
from .models import QAResult, QADeviceInfo, QAMaterialMaster, QAMaterialStockLedger, QAMaterialOutStockLedger
from baotri.models import MaintenanceTask

class QAResultForm(forms.ModelForm):
    class Meta:
        model = QAResult
        fields = ['device', 'machine_number', 'processed_image', 'data', 'result']
        
    machine_number = forms.CharField(max_length=100)

class QADeviceInfoForm(forms.ModelForm):
    maintenance_task = forms.ModelChoiceField(
        label="製品マスター連携（保全）",
        queryset=MaintenanceTask.objects.none(),
        required=False,
        empty_label="手入力を維持（連携しない）",
    )
    material_master = forms.ModelChoiceField(
        label="材料マスター連携",
        queryset=QAMaterialMaster.objects.none(),
        required=False,
        empty_label="手入力を維持（連携しない）",
    )

    class Meta:
        model = QADeviceInfo
        fields = [
            'name',
            'maintenance_task',
            'material_code',
            'material',
            'product',
            'ratio',
            'compare_ratio',
            'outstock_auto_input_enabled',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["maintenance_task"].queryset = MaintenanceTask.objects.all().order_by("name")
        self.fields["material_master"].queryset = QAMaterialMaster.objects.filter(is_active=True).order_by("material_name")
        self.fields["product"].required = False
        self.fields["outstock_auto_input_enabled"].widget.attrs["class"] = "form-check-input"
        if self.instance and self.instance.pk and not self.is_bound:
            if self.instance.maintenance_task_id:
                self.fields["maintenance_task"].initial = self.instance.maintenance_task_id
            linked = QAMaterialMaster.objects.filter(
                is_active=True,
                material_code=self.instance.material_code or "",
            ).first()
            if linked:
                self.fields["material_master"].initial = linked.pk

    def clean(self):
        cleaned = super().clean()
        task = cleaned.get("maintenance_task")
        if task and not (cleaned.get("product") or "").strip():
            cleaned["product"] = (task.name or "").strip()
        return cleaned


class QAMaterialMasterForm(forms.ModelForm):
    class Meta:
        model = QAMaterialMaster
        fields = ["material_name", "material_code", "bag_weight_kg", "qr_content", "qr_content_in", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "is_active":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class QAMaterialStockLedgerForm(forms.ModelForm):
    class Meta:
        model = QAMaterialStockLedger
        fields = [
            "material_name",
            "material_code",
            "stock_in_date",
            "lot_color",
            "weight_kg",
            "bag_sequence_no",
            "lot_number",
            "hinmei_name",
            "order_no",
            "workstation_management_no",
        ]
        widgets = {
            "stock_in_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class QAMaterialOutStockLedgerForm(forms.ModelForm):
    class Meta:
        model = QAMaterialOutStockLedger
        fields = [
            "material_name",
            "material_code",
            "stock_out_date",
            "lot_color",
            "weight_kg",
            "bag_sequence_no",
            "lot_number",
            "product_code",
            "workstation_management_no",
        ]
        widgets = {
            "stock_out_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
