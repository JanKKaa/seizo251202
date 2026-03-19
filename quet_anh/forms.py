from django import forms
from .models import QAResult, QADeviceInfo, QAMaterialMaster, QAMaterialStockLedger, QAMaterialOutStockLedger

class QAResultForm(forms.ModelForm):
    class Meta:
        model = QAResult
        fields = ['device', 'machine_number', 'processed_image', 'data', 'result']
        
    machine_number = forms.CharField(max_length=100)

class QADeviceInfoForm(forms.ModelForm):
    material_master = forms.ModelChoiceField(
        label="材料マスター連携",
        queryset=QAMaterialMaster.objects.none(),
        required=False,
        empty_label="手入力を維持（連携しない）",
    )

    class Meta:
        model = QADeviceInfo
        fields = ['name', 'material_code', 'material', 'product', 'ratio', 'compare_ratio']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material_master"].queryset = QAMaterialMaster.objects.filter(is_active=True).order_by("material_name")
        if self.instance and self.instance.pk and not self.is_bound:
            linked = QAMaterialMaster.objects.filter(
                is_active=True,
                material_code=self.instance.material_code or "",
            ).first()
            if linked:
                self.fields["material_master"].initial = linked.pk


class QAMaterialMasterForm(forms.ModelForm):
    class Meta:
        model = QAMaterialMaster
        fields = ["material_name", "material_code", "qr_content", "is_active"]

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
            "workstation_management_no",
            "supervisor_confirmed",
            "supervisor_name",
        ]
        widgets = {
            "stock_in_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "supervisor_confirmed":
                field.widget.attrs["class"] = "form-check-input"
            else:
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
            "workstation_management_no",
            "supervisor_confirmed",
            "supervisor_name",
        ]
        widgets = {
            "stock_out_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "supervisor_confirmed":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
