from django import forms
from django.forms import inlineformset_factory
from .models import (
    Machine, Component, ComponentReplacementHistory,
    MoldLifetime, ManualMachine
)

# -------- MACHINE (Thiết bị) --------
# Dùng cho device_create / device_update trong views_devices.py
class MachineForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = [
            'address', 'name', 'condname', 'status',
            'active', 'shot_total', 'last_shot'
        ]
        labels = {
            'address': 'IP / Address',
            'name': '機械名',
            'condname': '成形条件名',
            'status': '状態',
            'active': 'Active',
            'shot_total': 'Shot Total (DB)',
            'last_shot': 'Last Shot (DB)',
        }

# (Nếu bạn có form quản trị thiết bị khác theo setsubi_no / model_type / manufacturer
# thì tạo một form khác tên khác, tránh trùng):
class MachineMetaForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = ['setsubi_no', 'model_type', 'manufacturer']
        labels = {
            'setsubi_no': '設備管理No',
            'model_type': '型式',
            'manufacturer': 'メーカー',
        }

# -------- COMPONENT (Inline truyền thống nếu còn dùng ở một view khác) --------
class ComponentForm(forms.ModelForm):
    class Meta:
        model = Component
        fields = ['code', 'name', 'lifetime', 'detail',
                  'management_code', 'manufacturer', 'note']
        labels = {
            'code': '部品コード',
            'name': '部品名',
            'lifetime': '部品寿命（ショット数）',
            'detail': '部品詳細',
            'management_code': '管理コード',
            'manufacturer': '部品メーカー',
            'note': '備考',
        }

ComponentFormSet = inlineformset_factory(
    Machine, Component, form=ComponentForm,
    extra=5, can_delete=True
)

# -------- COMPONENT CREATE (AJAX) --------
class ComponentCreateForm(forms.ModelForm):
    machine_address = forms.CharField(label="Địa chỉ IP máy", required=True)

    class Meta:
        model = Component
        fields = [
            'management_code', 'manufacturer', 'name', 'code',
            'lifetime', 'detail', 'note'
        ]
        widgets = {
            'management_code': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'code': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'lifetime': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0'}),
            'detail': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'note': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
        }

# -------- COMPONENT QUICK UPDATE (AJAX) --------
class ComponentQuickUpdateForm(forms.ModelForm):
    class Meta:
        model = Component
        fields = [
            'management_code', 'manufacturer', 'name', 'code',
            'lifetime', 'detail', 'note'
        ]
        widgets = {
            'management_code': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'code': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'lifetime': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0'}),
            'detail': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'note': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
        }

# -------- COMPONENT REPLACEMENT (AJAX) --------
class ComponentQuickReplaceForm(forms.ModelForm):
    class Meta:
        model = ComponentReplacementHistory
        fields = [
            'note', 'confirmed_by',
            'image1', 'image2', 'image3', 'image4', 'image5',
            'attachment'
        ]
        widgets = {
            'note': forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm'}),
            'confirmed_by': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }

# -------- REPLACEMENT HISTORY (FORM CHÍNH nếu dùng trang dạng form chuẩn) --------
class ComponentReplacementForm(forms.ModelForm):
    class Meta:
        model = ComponentReplacementHistory
        fields = [
            'note', 'image1', 'image2', 'image3', 'image4', 'image5',
            'confirmed_by', 'attachment'
        ]
        widgets = {
            'note': forms.Textarea(attrs={'class': 'form-control'}),
            'confirmed_by': forms.TextInput(attrs={'class': 'form-control'}),
        }

# -------- MOLD LIFETIME --------
class MoldLifetimeForm(forms.ModelForm):
    class Meta:
        model = MoldLifetime
        fields = ['total_shot', 'lifetime']
        widgets = {
            'lifetime': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

# -------- MACHINE SHOT TOTAL EDIT --------
class MachineShotTotalForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = ['shot_total']
        labels = {'shot_total': 'Tổng số shot'}

# -------- MANUAL MACHINE (nếu còn dùng) --------
class ManualMachineForm(forms.ModelForm):
    class Meta:
        model = ManualMachine
        fields = ['name', 'condname', 'status', 'shotno', 'cycletime', 'note']
        labels = {
            'name': '機械名',
            'condname': '成形条件名',
            'status': '状態',
            'shotno': 'ショット数',
            'cycletime': 'サイクルタイム（秒）',
            'note': '備考',
        }