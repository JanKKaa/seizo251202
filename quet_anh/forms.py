from django import forms
from .models import QAResult, QADeviceInfo

class QAResultForm(forms.ModelForm):
    class Meta:
        model = QAResult
        fields = ['device', 'machine_number', 'processed_image', 'data', 'result']
        
    machine_number = forms.CharField(max_length=100)

class QADeviceInfoForm(forms.ModelForm):
    class Meta:
        model = QADeviceInfo
        fields = ['name', 'material', 'product', 'ratio', 'compare_ratio']