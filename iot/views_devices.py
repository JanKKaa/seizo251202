from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_GET
from django.core.paginator import Paginator
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Max, Count
import csv
import io

from .models import Machine
from .forms import MachineForm
from .snapshot_service import fetch_runtime_index
from .maintenance_service import compute_component_prediction
from .forms import ComponentQuickUpdateForm, ComponentQuickReplaceForm
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Component
from django.db import transaction
from .models import ArduinoPinLog, MachineAlarmEvent

RUNTIME_CACHE_TTL = 3  # seconds

def _get_runtime_map():
    """
    Cache ngắn danh sách runtime từ NET100.
    Trả về dict[address] = runtime_dict
    """
    ck = 'runtime_index_map'
    data = cache.get(ck)
    if data is None:
        lst = fetch_runtime_index()
        data = {m['address']: m for m in lst}
        cache.set(ck, data, RUNTIME_CACHE_TTL)
    return data

# --- Filter Form đơn giản (không tạo file riêng) ---
from django import forms
class MachineFilterForm(forms.Form):
    q = forms.CharField(label="検索", required=False)
    status = forms.ChoiceField(
        label="状態",
        required=False,
        choices=[('', '--- 全て ---'), ('production', 'Production'), ('stop', 'Stop'), ('maintenance', 'Maintenance')]
    )
    active = forms.ChoiceField(
        label="有効",
        required=False,
        choices=[('', '---'), ('1', 'ON'), ('0', 'OFF')]
    )

# ------ LIST ------
def device_list(request):
    qs = Machine.objects.all().order_by('address')
    form = MachineFilterForm(request.GET or None)
    if form.is_valid():
        q = form.cleaned_data.get('q')
        if q:
            qs = qs.filter(
                Q(address__icontains=q) |
                Q(name__icontains=q) |
                Q(condname__icontains=q)
            )
        status = form.cleaned_data.get('status')
        if status:
            qs = qs.filter(status=status)
        active = form.cleaned_data.get('active')
        if active == '1':
            qs = qs.filter(active=True)
        elif active == '0':
            qs = qs.filter(active=False)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    # --- Gắn runtime thực tế từ NET100 ---
    runtime_map = _get_runtime_map()
    runtime_fields = ['runtime_status_code','runtime_status_jp','shotno','cycletime','offline','alarm_active','name','condname']
    for m in page_obj:
        r = runtime_map.get(m.address)
        if r:
            # Ghi đè hiển thị bằng runtime
            m.rt_name = r.get('name') or m.name
            m.rt_condname = r.get('condname') or m.condname
            for f in runtime_fields:
                if f not in ['name','condname']:
                    setattr(m, f'rt_{f}', r.get(f))
        else:
            m.rt_name = m.name
            m.rt_condname = m.condname
            setattr(m, 'rt_offline', True)
            setattr(m, 'rt_runtime_status_code', 'offline')
            setattr(m, 'rt_runtime_status_jp', 'オフライン')
            setattr(m, 'rt_shotno', None)
            setattr(m, 'rt_cycletime', None)
            setattr(m, 'rt_alarm_active', False)

    return render(request, 'iot/device_list.html', {
        'form': form,
        'page_obj': page_obj,
        'total': qs.count()
    })

# ------ DETAIL ------
def device_detail(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    runtime_map = _get_runtime_map()
    r = runtime_map.get(machine.address)
    if not r:
        r = {
            'runtime_status_code': 'offline',
            'runtime_status_jp': 'オフライン',
            'shotno': machine.last_shot,
            'cycletime': '',
            'offline': True,
            'alarm_active': False,
            'name': machine.name,
            'condname': machine.condname
        }

    current_shot = r.get('shotno') or 0
    try:
        cycletime = float(r.get('cycletime') or 0)
    except:
        cycletime = 0

    component_rows = []
    for comp in machine.components.all().order_by('id'):
        lifetime = comp.lifetime or 0
        pred = compute_component_prediction(
            lifetime=lifetime,
            baseline_shot=comp.baseline_shot,
            current_shot=current_shot,
            cycletime_s=cycletime
        )
        status_level = 'normal'
        if pred['pct_used'] is not None:
            if pred['pct_used'] >= 100:
                status_level = 'danger'
            elif pred['pct_used'] >= 90:
                status_level = 'danger'
            elif pred['pct_used'] >= 75:
                status_level = 'warning'
        component_rows.append({
            'obj': comp,
            'lifetime': lifetime,
            'baseline_shot': comp.baseline_shot,
            'prediction': pred,
            'status_level': status_level,
        })

    return render(request, 'iot/device_detail.html', {
        'machine': machine,
        'runtime': r,
        'runtime_name': r.get('name') or machine.name,
        'runtime_condname': r.get('condname') or machine.condname,
        'name_diff': (machine.name and r.get('name') and machine.name != r.get('name')),
        'condname_diff': (machine.condname and r.get('condname') and machine.condname != r.get('condname')),
        'components_enriched': component_rows,
        'current_shot': current_shot,
        'cycletime': cycletime
    })

# ------ CREATE ------
def device_create(request):
    if request.method == 'POST':
        form = MachineForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Tạo thiết bị thành công.")
            return redirect('device_list')
    else:
        form = MachineForm()
    return render(request, 'iot/device_form.html', {'form': form, 'mode': 'create'})

# ------ UPDATE ------
def device_update(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    if request.method == 'POST':
        form = MachineForm(request.POST, instance=machine)
        if form.is_valid():
            form.save()
            messages.success(request, "Cập nhật thành công.")
            return redirect('device_detail', pk=machine.pk)
    else:
        form = MachineForm(instance=machine)
    return render(request, 'iot/device_form.html', {'form': form, 'mode': 'update', 'machine': machine})

# ------ DELETE ------
def device_delete(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    if request.method == 'POST':
        machine.delete()
        messages.success(request, "Đã xóa thiết bị.")
        return redirect('device_list')
    return render(request, 'iot/device_delete_confirm.html', {'machine': machine})

# ------ TOGGLE ACTIVE (AJAX/POST) ------
@require_http_methods(["POST"])
def device_toggle_active(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    machine.active = not machine.active
    machine.save(update_fields=['active'])
    return JsonResponse({'ok': True, 'active': machine.active})

# ------ BULK IMPORT CSV ------
def device_bulk_import(request):
    """
    CSV columns: address,name,condname,status,active
    """
    if request.method == 'POST' and request.FILES.get('file'):
        f = request.FILES['file']
        try:
            data = f.read().decode('utf-8')
        except UnicodeDecodeError:
            return HttpResponseBadRequest("File phải là UTF-8.")
        reader = csv.DictReader(io.StringIO(data))
        created = updated = 0
        for row in reader:
            address = (row.get('address') or '').strip()
            if not address:
                continue
            defaults = {
                'name': (row.get('name') or '').strip(),
                'condname': (row.get('condname') or '').strip(),
                'status': (row.get('status') or '').strip() or 'production',
                'active': (row.get('active') or '').strip().lower() in ['1', 'true', 'yes', 'on']
            }
            obj, is_created = Machine.objects.update_or_create(address=address, defaults=defaults)
            if is_created:
                created += 1
            else:
                updated += 1
        messages.success(request, f"Import xong. Tạo mới {created}, cập nhật {updated}.")
        return redirect('device_list')
    return render(request, 'iot/device_bulk_import.html')

# ------ JSON API: LIST ------
def api_devices(request):
    qs = Machine.objects.all().order_by('address')
    payload = []
    for m in qs:
        payload.append({
            'id': m.pk,
            'address': m.address,
            'name': m.name,
            'condname': m.condname,
            'status': m.status,
            'active': m.active,
            'shot_total': m.shot_total,
            'last_update': m.last_update.isoformat() if m.last_update else None
        })
    return JsonResponse({'devices': payload})

# ------ JSON API: DETAIL ------
def api_device_detail(request, pk):
    m = get_object_or_404(Machine, pk=pk)
    return JsonResponse({
        'id': m.pk,
        'address': m.address,
        'name': m.name,
        'condname': m.condname,
        'status': m.status,
        'active': m.active,
        'shot_total': m.shot_total,
        'last_shot': m.last_shot,
        'last_update': m.last_update.isoformat() if m.last_update else None
    })

# ------ SIMPLE METRICS (tạm) ------
def api_device_metrics(request):
    total = Machine.objects.count()
    active_cnt = Machine.objects.filter(active=True).count()
    prod = Machine.objects.filter(status='production').count()
    return JsonResponse({
        'total': total,
        'active': active_cnt,
        'production': prod,
        'inactive': total - active_cnt,
        'timestamp': timezone.now().isoformat()
    })

# ------ REATIME DATA (AJAX) ------
@require_GET
def api_device_realtime(request, pk):
    """
    Trả về số liệu realtime đơn giản (shot_total, last_shot, timestamp).
    Client sẽ polling định kỳ.
    """
    m = get_object_or_404(Machine, pk=pk)
    r = _get_runtime_map().get(m.address)
    if r:
        shot_total = r.get('shotno', m.shot_total)
        last_shot = r.get('shotno', m.last_shot)
        status_code = r.get('runtime_status_code', 'offline')
        name_rt = r.get('name') or m.name
        cond_rt = r.get('condname') or m.condname
    else:
        shot_total = m.shot_total
        last_shot = m.last_shot
        status_code = 'offline'
        name_rt = m.name
        cond_rt = m.condname
    return JsonResponse({
        'id': m.pk,
        'address': m.address,
        'name_runtime': name_rt,
        'condname_runtime': cond_rt,
        'shot_total': shot_total,
        'last_shot': last_shot,
        'status': status_code,
        'last_update': timezone.now().isoformat(),
        'ts': timezone.now().isoformat()
    })

# ------ JSON API: RUNTIME ------
def api_devices_runtime(request):
    runtime_map = _get_runtime_map()
    return JsonResponse({'runtime': list(runtime_map.values()), 'count': len(runtime_map)})

@require_POST
@transaction.atomic
def component_replace_ajax(request, component_id):
    comp = get_object_or_404(Component, pk=component_id)
    runtime = _get_runtime_map().get(comp.machine.address)
    current_shot = (runtime or {}).get('shotno') or comp.machine.last_shot or 0

    form = ComponentQuickReplaceForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)

    history = form.save(commit=False)
    history.component = comp
    history.shot_at_replacement = current_shot
    history.baseline_shot_before = comp.baseline_shot
    history.save()

    comp.baseline_shot = current_shot
    comp.save(update_fields=['baseline_shot'])

    return JsonResponse({
        'ok': True,
        'component_id': comp.id,
        'history_id': history.id,
        'new_baseline_shot': comp.baseline_shot
    })

def component_history_ajax(request, component_id):
    comp = get_object_or_404(Component, pk=component_id)
    histories = comp.replacement_histories.order_by('-replaced_at')[:30]
    data = []
    for h in histories:
        imgs = []
        for i in range(1,6):
            f = getattr(h, f'image{i}')
            if f:
                imgs.append(f.url)
        data.append({
            'id': h.id,
            'replaced_at': h.replaced_at.strftime('%Y-%m-%d %H:%M'),
            'note': h.note,
            'confirmed_by': h.confirmed_by,
            'shot_at_replacement': h.shot_at_replacement,
            'baseline_shot_before': h.baseline_shot_before,
            'images': imgs
        })
    return JsonResponse({'ok': True, 'history': data})

@require_POST
def component_update_ajax(request, component_id):
    """
    Cập nhật nhanh thông tin linh kiện (name/code/lifetime/detail).
    POST fields: name, code, lifetime, detail
    """
    comp = get_object_or_404(Component, pk=component_id)
    form = ComponentQuickUpdateForm(request.POST, instance=comp)
    if form.is_valid():
        form.save()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False, 'errors': form.errors}, status=400)

@csrf_exempt
def arduino_data(request):
    pins = ['pin3', 'pin6', 'pin7', 'pin8', 'pin9', 'pin10', 'pin11', 'pin12', 'A0']
    if request.method == 'POST':
        address = request.POST.get('address')
        pin_states = {p: request.POST.get(p) for p in pins}
    else:
        address = request.GET.get('address')
        pin_states = {p: request.GET.get(p) for p in pins}

    if address and any(pin_states.values()):
        # Lưu vào DB
        ArduinoPinLog.objects.create(
            address=address,
            **{p: int(pin_states[p]) if pin_states[p] is not None else None for p in pins}
        )
        return JsonResponse({'ok': True, 'address': address, 'pins': pin_states})
    return JsonResponse({'ok': False, 'error': 'Missing address or pin states'}, status=400)

from django.views.decorators.http import require_GET

@require_GET
def arduino_status_latest(request):
    address = request.GET.get('address')
    if not address:
        return JsonResponse({'ok': False, 'error': 'Missing address'}, status=400)
    log = ArduinoPinLog.objects.filter(address=address).order_by('-timestamp').first()
    if not log:
        return JsonResponse({'ok': False, 'error': 'No data'}, status=404)
    pins = ['pin3', 'pin6', 'pin7', 'pin8', 'pin9', 'pin10', 'pin11', 'pin12', 'A0']
    pin_states = {p: getattr(log, p) for p in pins}
    return JsonResponse({'ok': True, 'address': address, 'timestamp': log.timestamp, 'pins': pin_states})

def arduino_status_page(request):
    address = request.GET.get('address', '')
    return render(request, 'iot/arduino_status.html', {'address': address})

def arduino_status_all(request):
    # Lấy address của tất cả thiết bị đã gửi dữ liệu
    latest_logs = (
        ArduinoPinLog.objects
        .values('address')
        .annotate(latest_id=Max('id'))
    )
    # Lấy log mới nhất cho từng thiết bị
    logs = ArduinoPinLog.objects.filter(id__in=[l['latest_id'] for l in latest_logs])
    pins = ['pin3', 'pin6', 'pin7', 'pin8', 'pin9', 'pin10', 'pin11', 'pin12', 'A0']
    devices = []
    for log in logs:
        pin_states = {p: getattr(log, p) for p in pins}
        devices.append({
            'address': log.address,
            'timestamp': log.timestamp,
            'pins': pin_states
        })
    return JsonResponse({'ok': True, 'devices': devices})

def arduino_status_all_page(request):
    return render(request, 'iot/arduino_status_all.html')

from django.views.decorators.http import require_GET
from .snapshot_service import fetch_runtime_index

@require_GET
def api_device_raw(request):
    addr = request.GET.get('address')
    if not addr:
        return JsonResponse({'ok': False, 'error': 'missing address'}, status=400)
    data = fetch_runtime_index(address_filter=[addr], include_raw=True)
    return JsonResponse({'ok': True, 'devices': data})

@require_GET
def api_alarms_active(request):
    qs = MachineAlarmEvent.objects.filter(active=True).select_related('machine').order_by('-started_at')[:200]
    data = []
    for ev in qs:
        data.append({
            'address': ev.machine.address,
            'alarm_code': ev.alarm_code,
            'alarm_name': ev.alarm_name,
            'started_at': ev.started_at.isoformat(),
        })
    return JsonResponse({'ok': True, 'alarms': data})

@require_GET
def api_alarm_distribution(request):
    days = int(request.GET.get('days', 30))
    since = timezone.now() - timezone.timedelta(days=days)
    qs = MachineAlarmEvent.objects.filter(started_at__gte=since)
    agg = qs.values('alarm_category','alarm_category_label').annotate(cnt=Count('id'))
    total = sum(a['cnt'] for a in agg) or 1
    data = []
    for a in agg:
        data.append({
            'category': a['alarm_category'] or '',
            'label': a['alarm_category_label'] or '',
            'count': a['cnt'],
            'percent': round(a['cnt']*100/total,2)
        })
    return JsonResponse({'ok':True,'window_days':days,'total':total,'distribution':data})