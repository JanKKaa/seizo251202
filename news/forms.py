# filepath: c:\seizo_web\seizo0\trang_chu\news\forms.py
from django import forms
from .models import NewsArticle, NewsImage

class NewsArticleForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={'size': 100}))
    content = forms.CharField(widget=forms.Textarea(attrs={'rows': 10, 'cols': 100}))
    subtitle1 = forms.CharField(widget=forms.TextInput(attrs={'size': 100}), required=False)
    subcontent1 = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'cols': 100}), required=False)
    subtitle2 = forms.CharField(widget=forms.TextInput(attrs={'size': 100}), required=False)
    subcontent2 = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'cols': 100}), required=False)
    subtitle3 = forms.CharField(widget=forms.TextInput(attrs={'size': 100}), required=False)
    subcontent3 = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'cols': 100}), required=False)

    class Meta:
        model = NewsArticle
        fields = ['title', 'content', 'main_image', 'subtitle1', 'subcontent1', 'subtitle2', 'subcontent2', 'subtitle3', 'subcontent3']

class NewsImageForm(forms.ModelForm):
    class Meta:
        model = NewsImage
        fields = ['image', 'caption']