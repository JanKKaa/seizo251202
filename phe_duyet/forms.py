from django import forms
from .models import Document, Approval, Message
from django.contrib.auth.models import User

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'file', 'recipient']
        labels = {
            'title': 'タイトル',
            'file': 'ファイル',
            'recipient': '受信者',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(DocumentForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['recipient'].queryset = User.objects.exclude(id=user.id)
        self.fields['recipient'].label_from_instance = lambda obj: f"{obj.last_name}"
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control rounded-pill'

class ApprovalForm(forms.ModelForm):
    class Meta:
        model = Approval
        fields = ['approved']

    def __init__(self, *args, **kwargs):
        super(ApprovalForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control rounded-pill'

class RejectionForm(forms.ModelForm):
    class Meta:
        model = Approval
        fields = ['rejected']

    def __init__(self, *args, **kwargs):
        super(RejectionForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control rounded-pill'

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['recipient', 'subject', 'body']
        labels = {
            'recipient': '受信者',
            'subject': '件名',
            'body': '本文',
        }

    def __init__(self, *args, **kwargs):
        super(MessageForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control squared-pill'

class DocumentUpdateFileForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['file']