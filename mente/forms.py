from django import forms
from .models import Product, Checksheet

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        
        fields = ['name', 'code', 'machine_count', 'quantity', 'material', 'maintenance_frequency', 'product_image', 'mold_image']  # Thêm các trường hình ảnh
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'machine_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control'}),
            'material': forms.TextInput(attrs={'class': 'form-control'}),
            'maintenance_frequency': forms.TextInput(attrs={'class': 'form-control'}),
        
        }

class ChecksheetForm(forms.ModelForm):
    class Meta:
        model = Checksheet
        fields = ['product', 'item', 'status', 'notes']