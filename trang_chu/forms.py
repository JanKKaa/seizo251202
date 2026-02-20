import os
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile
from django.forms.widgets import ClearableFileInput
from django.conf import settings

class CustomClearableFileInput(ClearableFileInput):
    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['class'] = 'custom-avatar-class'
        output = super().render(name, value, attrs, renderer)
        custom_button = (
            f'<label for="{attrs["id"]}" class="btn btn-primary rounded-pill">ファイルを選択</label>'
            f'<input type="file" name="{name}" accept="image/*" id="{attrs["id"]}" style="display:none;" class="custom-avatar-class">'
            f'<span id="file-name" class="form-control rounded-pill" style="display:none;"></span>'
        )
        return f'{custom_button}{output}'

class UserRegisterForm(UserCreationForm):
    position = forms.ChoiceField(choices=[
        ('社員', '社員'),
        ('リーダー', 'リーダー'),
        ('係長', '係長'),
        ('課長', '課長'),
        ('部長', '部長'),
    ], required=True, label='役職')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'password1', 'password2', 'position']
        labels = {
            'username': 'ユーザー名',
            'first_name': '名',
            'last_name': '姓',
            'password1': 'パスワード',
            'password2': 'パスワード確認',
            'position': '役職',
        }
        error_messages = {
            'username': {
                'required': 'ユーザー名は必須です。',
                'max_length': 'ユーザー名は150文字以内で入力してください。',
                'invalid': 'ユーザー名は文字、数字、および@/./+/-/_のみを含めることができます。',
            },
            'first_name': {
                'required': '名は必須です。',
                'max_length': '名は30文字以内で入力してください。',
            },
            'last_name': {
                'required': '姓は必須です。',
                'max_length': '姓は30文字以内で入力してください。',
            },
            'password1': {
                'required': 'パスワードは必須です。',
                'min_length': 'パスワードは8文字以上で入力してください。',
            },
            'password2': {
                'required': 'パスワード確認は必須です。',
                'min_length': 'パスワードは8文字以上で入力してください。',
                'password_mismatch': 'パスワードが一致しません。',
            },
        }

    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control rounded-pill'

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("パスワードが一致しません。")
        return password2

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['position', 'avatar']
        labels = {
            'position': '役職',
            'avatar': 'アバター',
        }

    def __init__(self, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.fields['position'].widget.attrs['readonly'] = True

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': 'ユーザー名',
            'first_name': '名',
            'last_name': '姓',
            'email': 'メールアドレス',
        }
        help_texts = {
            'username': '',  # デフォルトのヘルプテキストを削除
        }

    def __init__(self, *args, **kwargs):
        super(UserUpdateForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control rounded-pill'
        self.fields['username'].widget.attrs['readonly'] = True

class ProfileUpdateForm(forms.ModelForm):
    avatar = forms.ImageField(label='アバター', required=False, widget=CustomClearableFileInput())

    class Meta:
        model = UserProfile
        fields = ['avatar']

    def __init__(self, *args, **kwargs):
        super(ProfileUpdateForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'avatar':
                field.widget.attrs['class'] = 'form-control rounded-pill'
