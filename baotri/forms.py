from django import forms
from django.forms import modelformset_factory
from .models import MaintenanceTask, TaskCode, MaintenanceMistake

class MaintenanceTaskForm(forms.ModelForm):
    class Meta:
        model = MaintenanceTask
        fields = ['name', 'code', 'machine_count', 'quantity', 'material', 'maintenance_frequency', 'task_image', 'product_image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '製品名を入力してください'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'コードを入力してください'}),
            'machine_count': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '機械番号'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '取数を入力してください'}),
            'material': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '材料を入力してください'}),
            'maintenance_frequency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'メンテナンス頻度を入力してください'}),
            'task_image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'product_image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }
        labels = {
            'name': '名前',
            'code': 'コード',
            'machine_count': '機械の数',
            'quantity': '数量',
            'material': '材料',
            'maintenance_frequency': 'メンテナンス頻度',
            'task_image': 'タスク画像',
            'product_image': '製品画像',
        }
        help_texts = {
            'name': '名前を入力してください。',
            'code': 'コードを入力してください。',
            'machine_count': '機械の数を入力してください。',
            'quantity': '数量を入力してください。',
            'material': '材料を入力してください。',
            'maintenance_frequency': 'メンテナンス頻度を入力してください。',
        }

class SupervisorConfirmForm(forms.ModelForm):
    supervisor_comment = forms.CharField(label='コメント（任意）', required=False, widget=forms.Textarea(attrs={'rows':3}))
    class Meta:
        model = TaskCode
        fields = ['supervisor_stamp', 'supervisor_comment']
        labels = {'supervisor_stamp': '承認印（画像を選択）'}

class MaintenanceMistakeForm(forms.ModelForm):
    class Meta:
        model = MaintenanceMistake
        fields = ['product', 'description', 'solution', 'image1', 'image2', 'image3', 'image4']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'solution': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        for field in ['image1', 'image2', 'image3', 'image4']:
            img = cleaned_data.get(field)
            if img and img.size > 5 * 1024 * 1024:
                self.add_error(field, "画像サイズは5MB以下にしてください。")
        return cleaned_data

MaintenanceMistakeFormSet = modelformset_factory(
    MaintenanceMistake,
    fields=['product', 'description', 'solution', 'image1', 'image2', 'image3', 'image4'],
    extra=5,  # Số dòng nhập mới mặc định
    widgets={
        'description': forms.Textarea(attrs={'rows': 2, 'style': 'min-width:200px;'}),
        'solution': forms.Textarea(attrs={'rows': 2, 'style': 'min-width:200px;'}),
    }
)

from django.forms import modelformset_factory
from .models import MaintenanceMistake

QuickMistakeFormSet = modelformset_factory(
    MaintenanceMistake,
    fields=['product', 'description'],
    extra=1,  # Chỉ 1 dòng nhập mới mặc định
    widgets={
        'description': forms.Textarea(attrs={'rows': 1, 'style': 'min-width:180px;'}),
    }
)