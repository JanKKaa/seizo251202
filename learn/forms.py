from django import forms
from .models import BangCap, MotivationalQuote, Course, TrainingProviderLink

class BangCapForm(forms.ModelForm):
    class Meta:
        model = BangCap
        fields = ['loai_bang', 'cap_do', 'file', 'ngay_cap', 'ghi_chu']
        labels = {
            'loai_bang': '資格の種類',
            'cap_do': '級',
            'file': '証明書ファイル（PDFまたは画像）',
            'ngay_cap': '発行日',
            'ghi_chu': '備考',
        }
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.pdf,image/*'}),
            'ngay_cap': forms.DateInput(attrs={'type': 'date'}),
        }


class MotivationalQuoteForm(forms.ModelForm):
    class Meta:
        model = MotivationalQuote
        fields = ['text', 'author']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CourseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # description đã ẩn khỏi UI nên không bắt buộc để tránh lỗi submit
        required_fields = {
            'title',
            'external_url',
            'start_date',
            'end_date',
            'price',
            'duration',
            'location',
            'target',
        }
        for name, field in self.fields.items():
            field.required = name in required_fields

    class Meta:
        model = Course
        fields = [
            'title', 'external_url', 'start_date', 'end_date', 'price', 'duration',
            'material', 'location', 'target', 'is_active'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class TrainingProviderLinkForm(forms.ModelForm):
    class Meta:
        model = TrainingProviderLink
        fields = ['name', 'url', 'category', 'icon_class', 'is_active']
        labels = {
            'name': '会社・団体名',
            'url': 'URL',
            'category': 'カテゴリ',
            'icon_class': 'アイコン（任意）',
            'is_active': '表示',
            'title': '研修・講習名',
            'external_url': '外部リンク',
            'start_date': '開始日',
            'end_date': '終了日',
            'price': '受講料',
            'duration': '研修期間（時間）',
            'material': '資料アップロード',
            'location': '場所',
            'target': '対象',
            'description': '参加の理由',
            
        }
        error_messages = {
            'title': {
                'required': '研修・講習名は必須項目です。',
                'max_length': '研修・講習名が長すぎます。',
            },
            'external_url': {
                'required': '外部リンクは必須項目です。',
                'invalid': '有効なURLを入力してください。',
            },
            'start_date': {
                'required': '開始日は必須項目です。',
                'invalid': '有効な日付を入力してください。',
            },
            'end_date': {
                'required': '終了日は必須項目です。',
                'invalid': '有効な日付を入力してください。',
            },
            'price': {
                'required': '受講料は必須項目です。',
                'invalid': '数字で入力してください。',
            },
            'duration': {
                'required': '研修期間は必須項目です。',
                'invalid': '数字で入力してください。',
            },
            'material': {
                'invalid': 'PDFまたは画像ファイルをアップロードしてください。',
            },
            'location': {
                'required': '場所は必須項目です。',
            },
            'target': {
                'required': '対象は必須項目です。',
            },
            'description': {
                'required': '参加の理由は必須項目です。',
            },
            'is_active': {
                'invalid': '有効な値を選択してください。',
            },
        }
