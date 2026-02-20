from django import forms
from .models import XuLyAnh2, DeviceInfo

class XuLyAnhForm(forms.ModelForm):
    class Meta:
        model = XuLyAnh2
        fields = ['machine_number', 'image', 'processed_image', 'data', 'result', 'user']
        # ĐÃ BỎ 'created_at'

class DeviceInfoForm(forms.ModelForm):
    class Meta:
        model = DeviceInfo
        fields = ['name', 'material', 'product', 'ratio']