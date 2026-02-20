from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Change4MEntry


class Change4MEntryForm(forms.ModelForm):
    CODE_CHOICES = [
        ('Man（人）', 'Man（人）'),
        ('Machine（機械）', 'Machine（機械）'),
        ('Material（材料）', 'Material（材料）'),
        ('Method（方法）', 'Method（方法）'),
        # Thêm các lựa chọn khác nếu cần
    ]
    code = forms.ChoiceField(choices=CODE_CHOICES, label='区分', widget=forms.Select(attrs={'class': 'form-select'}))
    active_from = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S']
    )
    active_until = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'],
        required=False
    )

    class Meta:
        model = Change4MEntry
        fields = [
            'code',
            'message',
            'detail',
            'reporter',
            'tags',
            'highlight',
            'active_from',
            'active_until',
        ]
        labels = {
            'code': '区分',
            'message': '内容',
            'detail': '詳細',
            'reporter': '担当者',
            'tags': 'タグ',
            'highlight': '重要',
            'active_from': '開始日時',
            'active_until': '終了日時',
        }
        widgets = {
            'detail': forms.Textarea(attrs={'rows': 3}),
            # Không cần khai báo lại widget cho active_from/active_until ở đây
        }


@login_required
def change4m_manage(request):
    entries = Change4MEntry.objects.order_by('-active_from', '-created_at')
    create_form = Change4MEntryForm(initial={'active_from': timezone.localtime()})
    edit_form = None
    edit_target = None

    if request.method == 'POST':
        if 'delete' in request.POST:
            target = get_object_or_404(Change4MEntry, pk=request.POST.get('delete'))
            target.delete()
            return redirect('iot:change4m-manage')

        entry_id = request.POST.get('entry_id')
        if entry_id:
            edit_target = get_object_or_404(Change4MEntry, pk=entry_id)
            edit_form = Change4MEntryForm(request.POST, instance=edit_target)
            if edit_form.is_valid():
                obj = edit_form.save(commit=False)
                if not obj.created_by:
                    obj.created_by = request.user.get_username()
                obj.save()
                return redirect('iot:change4m-manage')
        else:
            create_form = Change4MEntryForm(request.POST)
            if create_form.is_valid():
                obj = create_form.save(commit=False)
                obj.created_by = request.user.get_username()
                obj.save()
                return redirect('iot:change4m-manage')
    else:
        edit_id = request.GET.get('edit')
        if edit_id:
            edit_target = get_object_or_404(Change4MEntry, pk=edit_id)
            edit_form = Change4MEntryForm(instance=edit_target)

    context = {
        'entries': entries,
        'create_form': create_form,
        'edit_form': edit_form,
        'edit_target': edit_target,
        'now': timezone.now(),
    }
    return render(request, 'iot/4M.html', context)


def change4m_updates_api(request):
    now = timezone.now()
    queryset = Change4MEntry.objects.filter(
        active_from__lte=now
    ).filter(
        Q(active_until__isnull=True) | Q(active_until__gt=now)
    ).order_by('-active_from', '-created_at').values(
        'id', 'code', 'message', 'detail', 'reporter', 'tags', 'highlight', 'created_by', 'active_from', 'active_until'
    )[:50]

    entries = []
    for entry in queryset:
        # Sửa lại: dùng entry['active_from'] thay vì entry.active_from
        active_from_local = timezone.localtime(entry['active_from'])
        active_until_local = timezone.localtime(entry['active_until']) if entry['active_until'] else None
        tags = [t.strip() for t in (entry['tags'] or '').replace('、', ',').split(',') if t.strip()]
        entries.append({
            'id': entry['id'],
            'code': entry['code'],
            'message': entry['message'],
            'detail': entry['detail'],
            'reporter': entry['reporter'],
            'tags': tags,
            'highlight': entry['highlight'],
            'timestamp': active_from_local.strftime('%Y/%m/%d %H:%M'),
            'stop_at': active_until_local.strftime('%Y/%m/%d %H:%M') if active_until_local else None,
            'sender': '',
        })

    return JsonResponse({
        'entries': entries,
        'generated_at': now.strftime('%Y/%m/%d %H:%M'),
    })