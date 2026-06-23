from django import forms
from django.apps import apps
from django.contrib.auth.models import User
from django.db.models import Q

from .models import Approval, Document, Message


BLOCKED_APPROVER_NAMES = ("9999", "生産技術課", "管理課", "test")


def _employee_code_usernames():
    usernames = set()
    for app_label in ("menu", "learn"):
        try:
            nhan_vien_model = apps.get_model(app_label, "NhanVien")
        except LookupError:
            continue
        usernames.update(
            nhan_vien_model.objects.exclude(ma_so="").values_list("ma_so", flat=True)
        )
    return usernames


def approval_login_users(current_user=None):
    queryset = User.objects.filter(is_active=True)
    if current_user:
        queryset = queryset.exclude(id=current_user.id)

    employee_codes = _employee_code_usernames()
    if employee_codes:
        queryset = queryset.exclude(username__in=employee_codes)

    blocked_users = Q()
    for name in BLOCKED_APPROVER_NAMES:
        blocked_users |= (
            Q(username__iexact=name)
            | Q(first_name__iexact=name)
            | Q(last_name__iexact=name)
        )
    queryset = queryset.exclude(blocked_users)

    return queryset.order_by("last_name", "first_name", "username")


def user_display_name(user):
    japanese_order_name = f"{user.last_name} {user.first_name}".strip()
    return japanese_order_name or user.username


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["category", "title", "file", "recipient"]
        labels = {
            "category": "分類",
            "title": "タイトル",
            "file": "ファイル",
            "recipient": "承認者",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super(DocumentForm, self).__init__(*args, **kwargs)
        self.fields["recipient"].queryset = approval_login_users(user)
        self.fields["recipient"].label_from_instance = user_display_name
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control rounded-pill"


class ApprovalForm(forms.ModelForm):
    class Meta:
        model = Approval
        fields = ["approved"]

    def __init__(self, *args, **kwargs):
        super(ApprovalForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control rounded-pill"


class RejectionForm(forms.ModelForm):
    class Meta:
        model = Approval
        fields = ["rejected"]

    def __init__(self, *args, **kwargs):
        super(RejectionForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control rounded-pill"


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["recipient", "subject", "body"]
        labels = {
            "recipient": "宛先",
            "subject": "件名",
            "body": "本文",
        }

    def __init__(self, *args, **kwargs):
        super(MessageForm, self).__init__(*args, **kwargs)
        self.fields["recipient"].queryset = approval_login_users()
        self.fields["recipient"].label_from_instance = user_display_name
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control squared-pill"


class DocumentUpdateFileForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["file"]
