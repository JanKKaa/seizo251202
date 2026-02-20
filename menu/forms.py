from django import forms
from .models import MonAn

class MonAnForm(forms.ModelForm):
    class Meta:
        model = MonAn
        fields = '__all__'
        labels = {
            'ten': '料理名',
            'mo_ta': '説明',
            'gia': '価格',
            'hinh_anh': '画像',
        }