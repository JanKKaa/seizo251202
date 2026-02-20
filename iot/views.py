import csv
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import requests
import xml.etree.ElementTree as ET
from .models import Machine, Component, MoldLifetime, Mold, ManualMachine, ProductionPlan, Esp32CycleShot, Esp32CardSnapshot
from django.utils.dateparse import parse_datetime
from .forms import MachineForm, ComponentFormSet, ComponentReplacementForm, MachineShotTotalForm, ManualMachineForm
from django import forms
from datetime import datetime, timedelta
from django.core.cache import cache
from django.http import JsonResponse
from iot.models import DashboardNotification
from baotri.models import TaskCode
from django.contrib.auth import get_user_model
from . import views_esp32

def xml_to_dict(element, ns):
    """Chuyển tất cả trường con của 1 element thành dict"""
    d = {}
    for child in element:
        tag = child.tag
        if tag.startswith('{'):
            tag = tag.split('}', 1)[1]
        d[tag] = child.text
    return d




class MoldLifetimeForm(forms.ModelForm):
    class Meta:
        model = MoldLifetime
        fields = ['total_shot']

def molding_list(request):
    machines = cache.get('iot_device_machines') or []
    # Lấy danh sách khuôn/điều kiện đã đăng ký
    moldlifetimes = MoldLifetime.objects.select_related('mold').all()

    # Map condname / product -> MoldLifetime for ESP32 matching
    mold_map_by_cond = {}
    mold_map_by_product = {}
    mold_map_by_esp32 = {}
    for ml in moldlifetimes:
        cond_key = (ml.condname or "").strip().lower()
        if cond_key and cond_key not in mold_map_by_cond:
            mold_map_by_cond[cond_key] = ml
        mold_name = getattr(ml.mold, "name", None)
        product_key = (mold_name or "").strip().lower()
        if product_key and product_key not in mold_map_by_product:
            mold_map_by_product[product_key] = ml
        esp32_key = (ml.esp32_product_name or "").strip().lower()
        if esp32_key and esp32_key not in mold_map_by_esp32:
            mold_map_by_esp32[esp32_key] = ml

    # Tạo dict condname -> shotno realtime
    cond_shot_map = {}
    for m in machines:
        condname = m.get('condname', '')
        shotno = m.get('shotno', None)
        if condname and shotno is not None:
            cond_shot_map[condname] = shotno

    # Cập nhật last_shot realtime cho MoldLifetime nếu có
    for ml in moldlifetimes:
        shotno = cond_shot_map.get(ml.condname)
        if shotno is not None and shotno > 0:
            ml.last_shot = shotno
        # Tính toán các trường phụ
        max_life = ml.lifetime or 1000000
        ml.left = max_life - (ml.total_shot or 0)
        ml.percent = int(max(ml.left, 0) * 100 / max_life)
        ml.over_life = ml.left < 0
        if ml.over_life:
            ml.bar_class = "bg-danger"
            ml.bar_text = f"超過 {abs(ml.left)} ショット "
            ml.bar_width = 100
        else:
            if ml.percent < 10:
                ml.bar_class = "bg-danger"
            elif ml.percent < 30:
                ml.bar_class = "bg-warning"
            else:
                ml.bar_class = "bg-success"
            ml.bar_text = f"{ml.left} / {ml.lifetime} ショット残り"
            ml.bar_width = ml.percent

    # Hiển thị danh sách máy đang production
    active_machines = []
    for m in machines:
        if m.get('status') == 'production':
            # Gán last_shot realtime cho máy (theo condname)
            last_shot = cond_shot_map.get(m.get('condname', ''))
            m['last_shot'] = last_shot
            active_machines.append(m)

    active_count = len(active_machines)
    total_count = len(machines)
    utilization_percent = round(active_count / total_count * 100, 1) if total_count else 0
    total_shot = sum([m.get('shotno_24h', 0) for m in machines])
    avg_shot = round(total_shot / total_count, 1) if total_count else 0

    today = timezone.localdate()
    plan_map = {}
    for mc, prod in ProductionPlan.objects.filter(plan_date=today).values_list("machine", "product_name"):
        key = str(mc).strip()
        if key and prod:
            plan_map[key] = prod.strip()
    if not plan_map:
        for mc, prod in ProductionPlan.objects.order_by("-plan_date").values_list("machine", "product_name"):
            key = str(mc).strip()
            if key and prod and key not in plan_map:
                plan_map[key] = prod.strip()

    esp32_devices = []
    try:
        esp32_response = views_esp32.esp32_status_processed_targets(request)
        payload = getattr(esp32_response, "data", None)
        if payload is None:
            raw_content = getattr(esp32_response, "content", b"[]")
            payload = json.loads(raw_content or b"[]")
        if isinstance(payload, dict):
            esp32_devices = payload.get("machines") or payload.get("data") or payload.get("results") or []
        elif isinstance(payload, list):
            esp32_devices = payload
    except Exception:
        esp32_devices = []

    normalized_devices = []
    for dev in esp32_devices:
        if not isinstance(dev, dict):
            continue

        def to_int(value):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

        status_raw = str(
            dev.get("status")
            or dev.get("status_text")
            or dev.get("state")
            or dev.get("statusDisplay")
            or ""
        ).strip()
        status_lower = status_raw.lower()

        is_active_flag = dev.get("is_active", dev.get("active", dev.get("running")))
        if isinstance(is_active_flag, str):
            is_active_flag = is_active_flag.strip().lower() in {
                "1", "true", "yes", "y", "on", "active", "running", "稼働中", "運転中"
            }
        elif isinstance(is_active_flag, (int, float)):
            is_active_flag = is_active_flag != 0
        else:
            is_active_flag = bool(is_active_flag)

        is_running = is_active_flag or status_lower in {
            "active", "running", "run", "on", "online", "operating", "稼働中", "運転中"
        }

        util = dev.get("utilization") or dev.get("utilization_percent") or dev.get("util_percent")
        if isinstance(util, (int, float)):
            util_display = f"{util:.1f}%"
        else:
            util_display = util or "-"

        last_update_value = dev.get("last_update") or dev.get("updated_at")
        last_update_display = "-"
        if isinstance(last_update_value, str):
            parsed_dt = parse_datetime(last_update_value.replace("Z", "+00:00"))
            if parsed_dt:
                if timezone.is_naive(parsed_dt):
                    parsed_dt = timezone.make_aware(parsed_dt, timezone.get_current_timezone())
                last_update_display = timezone.localtime(parsed_dt).strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_update_display = last_update_value
        elif isinstance(last_update_value, datetime):
            aware_dt = last_update_value
            if timezone.is_naive(aware_dt):
                aware_dt = timezone.make_aware(aware_dt, timezone.get_current_timezone())
            last_update_display = timezone.localtime(aware_dt).strftime("%Y-%m-%d %H:%M:%S")

        product_name = (
            dev.get("product_name")
            or dev.get("item_name")
            or dev.get("mold_name")
            or dev.get("work_name")
            or ""
        )

        plan_list = dev.get("plan_products")
        if isinstance(plan_list, (list, tuple)):
            plan_list = [str(p).strip() for p in plan_list if p]
        elif isinstance(plan_list, str):
            plan_list = [plan_list.strip()] if plan_list.strip() else []
        else:
            plan_list = []
        plan_product = plan_list[0] if plan_list else None

        device_machine = str(dev.get("machine") or dev.get("name") or "").strip()
        plan_map_product = plan_map.get(device_machine)
        product_display = plan_product or product_name or plan_map_product or "-"

        # Match ESP32 device to MoldLifetime via condname or mold name
        matched_ml = None
        cond_candidates = [
            dev.get("condname"),
            dev.get("plan_condname"),
            dev.get("condition_name"),
        ]
        for cond_candidate in cond_candidates:
            key = (cond_candidate or "").strip().lower()
            if key:
                matched_ml = mold_map_by_cond.get(key)
                if matched_ml:
                    break
        if not matched_ml:
            product_candidates = [
                product_name,
                plan_product,
                dev.get("product_display"),
                dev.get("item_name"),
                dev.get("mold_name"),
                dev.get("work_name"),
            ]
            for product_candidate in product_candidates + [plan_map_product]:
                key = (product_candidate or "").strip().lower()
                if key:
                    matched_ml = mold_map_by_product.get(key) or mold_map_by_esp32.get(key)
                    if matched_ml:
                        break

        matched_last_shot = getattr(matched_ml, "last_shot", None) if matched_ml else None
        matched_total_shot = getattr(matched_ml, "total_shot", None) if matched_ml else None
        matched_condname = getattr(matched_ml, "condname", None) if matched_ml else None
        matched_last_update = getattr(matched_ml, "last_update", None) if matched_ml else None
        matched_mold_name = getattr(matched_ml.mold, "name", None) if matched_ml and matched_ml.mold else None

        current_shot = to_int(
            dev.get("current_shot")
            or dev.get("shot")
            or dev.get("shot_count")
            or dev.get("shotno")
            or dev.get("total_shot")
        )

        cycle_value = (
            dev.get("cycle_time")
            or dev.get("cycletime")
            or dev.get("cycle")
            or dev.get("ct")
            or dev.get("cycle_sec")
        )
        if isinstance(cycle_value, str):
            cycle_value = cycle_value.rstrip("s").strip()
            try:
                cycle_value = float(cycle_value)
            except ValueError:
                pass
        if isinstance(cycle_value, (int, float)):
            cycle_display = f"{cycle_value:.1f}s"
        else:
            cycle_display = cycle_value or "-"

        last_shot_value = to_int(
            dev.get("last_shot")
            or dev.get("last_shot_no")
            or dev.get("last_shot_count")
            or dev.get("shot_latest")
        )

        status_display = (
            dev.get("runtime_status_jp")
            or dev.get("status_jp")
            or dev.get("status_display")
            or dev.get("runtime_status")
            or status_raw
            or "-"
        )
        status_code = str(
            dev.get("runtime_status_code")
            or dev.get("status_code")
            or status_lower
            or "unknown"
        ).strip().replace(" ", "-")

        esp32_alias = (matched_ml.esp32_product_name or "").strip() if matched_ml else ""
        if product_display == "-" and esp32_alias:
            product_display = esp32_alias

        normalized_devices.append({
            **dev,
            "status_raw": status_raw or "-",
            "status_is_running": is_running,
            "status_badge_class": "badge badge-info " + status_code,
            "status_code": status_code,
            "status_display": status_display,
            "utilization_display": util_display,
            "last_update_display": last_update_display,
            "product_display": product_display,
            "current_shot_value": current_shot,
            "cycle_display": cycle_display,
            "last_shot_value": last_shot_value,
            "db_last_shot": matched_last_shot,
            "db_total_shot": matched_total_shot,
            "db_last_update": matched_last_update,
            "matched_condname": matched_condname,
            "matched_mold_name": matched_mold_name,
            "matched_esp32_product": esp32_alias,
        })

    context = {
        'active_count': active_count,
        'total_count': total_count,
        'utilization_percent': utilization_percent,
        'total_shot': total_shot,
        'avg_shot': avg_shot,
        'active_machines': active_machines,
        'moldlifetimes': moldlifetimes,
        'esp32_devices': normalized_devices,
    }
    cache_key = "iot_molding_list_context"
    cache.set(cache_key, context, 5)  # cache 5 giây
    return render(request, 'iot/molding.html', context)

def molding_edit(request, pk):
    molding = get_object_or_404(MoldLifetime, pk=pk)
    error_list = []
    if request.method == 'POST':
        mold_name = request.POST.get('mold_name')
        mold_code = request.POST.get('mold_code')
        condname = request.POST.get('condname')
        total_shot = int(request.POST.get('total_shot', molding.total_shot))
        lifetime = int(request.POST.get('lifetime', molding.lifetime))
        status = request.POST.get('status', 'active')

        mold, _ = Mold.objects.get_or_create(name=mold_name, defaults={'code': mold_code, 'status': status})
        mold.code = mold_code
        mold.status = status
        mold.save()
        molding.mold = mold
        molding.condname = condname
        molding.total_shot = total_shot
        molding.lifetime = lifetime
        molding.save()
        return redirect('iot:molding')
    return render(request, 'iot/molding_edit.html', {'molding': molding, 'error_list': error_list})

def molding_create(request):
    error_list = []
    if request.method == 'POST':
        mold_name = request.POST.get('mold_name')
        mold_code = request.POST.get('mold_code')
        status = request.POST.get('status', 'active')
        condname = request.POST.get('condname')
        total_shot = int(request.POST.get('total_shot', 0))
        lifetime = int(request.POST.get('lifetime', 1000000))

        # Kiểm tra trùng mã khuôn với bất kỳ khuôn nào
        if Mold.objects.filter(code=mold_code).exists():
            error_list.append("金型品番が既に存在します。")
        # Kiểm tra trùng tên khuôn với bất kỳ khuôn nào
        if Mold.objects.filter(name=mold_name).exists():
            error_list.append("金型品名が既に存在します。")
        # Kiểm tra trùng tên điều kiện với bất kỳ điều kiện nào
        if MoldLifetime.objects.filter(condname=condname).exists():
            error_list.append("成形条件名が既に存在します。")

        if not error_list:
            mold = Mold.objects.create(name=mold_name, code=mold_code, status=status)
            MoldLifetime.objects.create(
                mold=mold,
                condname=condname,
                total_shot=total_shot,
                lifetime=lifetime
            )
            return redirect('iot:molding')
    return render(request, 'iot/molding_create.html', {'error_list': error_list})

def molding_delete(request, pk):
    molding = get_object_or_404(MoldLifetime, pk=pk)
    molding.delete()
    return redirect('iot:molding')

def update_mold_shot():
    url_machine = 'http://192.168.10.220/net100/machine'
    url_live = 'http://192.168.10.220/net100/livelist'
    machines = []

    try:
        res_machine = requests.get(url_machine, auth=('giang', 'ht798701'), timeout=5)
        res_live = requests.get(url_live, auth=('giang', 'ht798701'), timeout=5)
        if res_machine.status_code == 200 and res_live.status_code == 200:
            ns = {'ns': 'http://www.jsw.co.jp/net100/2.0'}
            root_machine = ET.fromstring(res_machine.content)
            root_live = ET.fromstring(res_live.content)

            live_dict = {}
            for live in root_live.findall('.//ns:live', ns):
                info = xml_to_dict(live, ns)
                address = info.get('address', '')
                if 'lastshotinfo' in info and info['lastshotinfo']:
                    parts = info['lastshotinfo'].split(',')
                    if len(parts) > 4:
                        info['cycletime'] = parts[4].replace('"', '').strip()
                live_dict[address] = info

            for entry in root_machine.findall('.//ns:listentry', ns):
                info = xml_to_dict(entry, ns)
                address = info.get('address', '')
                live_info = live_dict.get(address, {})
                machines.append({**info, **live_info})
    except Exception as e:
        machines = []

    moldlifetimes = MoldLifetime.objects.select_related('mold').all()
    for m in machines:
        condname = m.get('condname', '')
        shotno = int(m.get('shotno', 0) or 0)
        ml = moldlifetimes.filter(condname=condname).first()
        if ml:
            last_shot = getattr(ml, 'last_shot', None)
            if last_shot is None:
                ml.last_shot = shotno
            elif shotno != last_shot:
                ml.total_shot += 1
                ml.last_shot = shotno
            # Nếu shotno không đổi thì chỉ cập nhật thời gian
            ml.last_update = timezone.now()
            ml.save()
    print("Đã cập nhật shot molding tự động!")

def machine_counter(request):
    url_machine = 'http://192.168.10.220/net100/machine'
    url_live = 'http://192.168.10.220/net100/livelist'
    machines = []

    try:
        res_machine = requests.get(url_machine, auth=('giang', 'ht798701'), timeout=5)
        res_live = requests.get(url_live, auth=('giang', 'ht798701'), timeout=5)
        if res_machine.status_code == 200 and res_live.status_code == 200:
            ns = {'ns': 'http://www.jsw.co.jp/net100/2.0'}
            root_machine = ET.fromstring(res_machine.content)
            root_live = ET.fromstring(res_live.content)

            # Tạo dict address -> info realtime
            live_map = {}
            for live in root_live.findall('.//ns:live', ns):
                info = xml_to_dict(live, ns)
                address = info.get('address', '')
                live_map[address] = info

            for entry in root_machine.findall('.//ns:listentry', ns):
                info = xml_to_dict(entry, ns)
                address = info.get('address', '')
                # Lấy realtime
                live_info = live_map.get(address, {})
                name = info.get('name', '')  # realtime
                status = live_info.get('status', '')  # realtime
                condname = info.get('condname', '')  # realtime
                cycletime = live_info.get('cycletime', '')  # realtime nếu có
                # Lấy shot từ DB
                machine_obj = Machine.objects.filter(address=address).first()
                shot_total = machine_obj.shot_total if machine_obj else 0
                last_update = machine_obj.last_update if machine_obj else None
                pk = machine_obj.pk if machine_obj else ''
                last_shot = machine_obj.last_shot if machine_obj else None
                machines.append({
                    'address': address,
                    'name': name,
                    'condname': condname,
                    'cycletime': cycletime,
                    'shot_total': shot_total,
                    'status': status,
                    'last_update': last_update,
                    'last_shot': last_shot,
                    'pk': pk,
                })
    except Exception as e:
        machines = []

    return render(request, 'iot/machine.html', {'machines': machines})

def update_machine_counter():
    """
    Hàm chạy ngầm để cập nhật counter máy (shot_total) cho từng máy.
    Mỗi lần shotno thay đổi (kể cả reset về 0), cộng dồn shot_total đúng số shot tăng thêm.
    Chỉ cộng dồn ở đây, không cộng dồn trong views!
    """
    url_machine = 'http://192.168.10.220/net100/machine'
    url_live = 'http://192.168.10.220/net100/livelist'

    try:
        res_machine = requests.get(url_machine, auth=('giang', 'ht798701'), timeout=5)
        res_live = requests.get(url_live, auth=('giang', 'ht798701'), timeout=5)
        if res_machine.status_code == 200 and res_live.status_code == 200:
            ns = {'ns': 'http://www.jsw.co.jp/net100/2.0'}
            root_machine = ET.fromstring(res_machine.content)
            root_live = ET.fromstring(res_live.content)

            live_dict = {}
            for live in root_live.findall('.//ns:live', ns):
                info = xml_to_dict(live, ns)
                address = info.get('address', '')
                shotno = int(info.get('shotno', 0) or 0)
                live_dict[address] = shotno

            from .models import Machine
            for entry in root_machine.findall('.//ns:listentry', ns):
                info = xml_to_dict(entry, ns)
                address = info.get('address', '')
                name = info.get('name', '')
                shotno = live_dict.get(address, 0)
                machine_obj, _ = Machine.objects.get_or_create(address=address, defaults={'name': name})
                last_shot = getattr(machine_obj, 'last_shot', None)
                if last_shot is None:
                    machine_obj.last_shot = shotno
                elif shotno != last_shot:
                    machine_obj.shot_total += 1
                    machine_obj.last_shot = shotno
                # Nếu shotno không đổi thì chỉ cập nhật thời gian
                machine_obj.last_update = timezone.now()
                machine_obj.save()
    except Exception as e:
        print(f"Lỗi cập nhật counter máy: {e}")

    print("Đã cập nhật counter máy tự động!")

def edit_shot_total(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    if request.method == 'POST':
        form = MachineShotTotalForm(request.POST, instance=machine)
        if form.is_valid():
            form.save()
            return redirect('machine_counter')
    else:
        form = MachineShotTotalForm(instance=machine)
    return render(request, 'iot/edit_shot_total.html', {'form': form, 'machine': machine})

def manual_machine_add(request):
    if request.method == 'POST':
        form = ManualMachineForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('index')
    else:
        form = ManualMachineForm()
    return render(request, 'iot/manual_machine_add.html', {'form': form})

def dashboard_notifications_json(request):
    now = timezone.now()
    notifs = DashboardNotification.objects.filter(
        appear_at__lte=now, expire_at__gt=now
    ).order_by('-priority', '-appear_at')
    data = [
        {
            'message': n.message,
            'priority': n.priority,
            'is_alarm': bool(n.is_alarm),
            'sender': n.sender,
            'seconds_left': int((n.expire_at - now).total_seconds())
        }
        for n in notifs
    ]
    return JsonResponse({'notifications': data})

def index(request):
    return render(request, 'iot/index.html')

def _esp32_extract_devices():
    try:
        response = views_esp32.esp32_status_processed_targets(None)
    except Exception:
        return []
    payload = getattr(response, "data", None)
    if payload is None:
        raw_content = getattr(response, "content", b"[]")
        try:
            payload = json.loads(raw_content or b"[]")
        except Exception:
            payload = []
    if isinstance(payload, dict):
        devices = payload.get("machines") or payload.get("data") or payload.get("results") or []
    elif isinstance(payload, list):
        devices = payload
    else:
        devices = []
    return [d for d in devices if isinstance(d, dict)]


def update_esp32_shot():
    snapshot_map = {
        (s.address or "").strip(): s
        for s in Esp32CardSnapshot.objects.all()
    }
    if not snapshot_map:
        return

    mold_map_machine = {}
    mold_map_product = {}
    for ml in MoldLifetime.objects.select_related("mold"):
        machine_key = (ml.esp32_machine or "").strip()
        if machine_key and machine_key not in mold_map_machine:
            mold_map_machine[machine_key] = ml
        product_key = (
            ml.esp32_product_name
            or getattr(ml.mold, "name", "")
            or ""
        ).strip().lower()
        if product_key and product_key not in mold_map_product:
            mold_map_product[product_key] = ml

    now = timezone.now()
    for machine, snapshot in snapshot_map.items():
        ml = mold_map_machine.get(machine)
        if not ml:
            product_key = (snapshot.primary_product or snapshot.product_display or "").strip().lower()
            if product_key:
                ml = mold_map_product.get(product_key)
        if not ml:
            continue

        current_shot = max(int(snapshot.shot or 0), 0)
        ts = snapshot.updated_at or now
        prev_shot = ml.last_shot if ml.last_shot is not None else 0

        if (ml.total_shot or 0) == 0 and prev_shot == 0:
            ml.last_shot = current_shot
            ml.last_update = ts
            ml.save(update_fields=["last_shot", "last_update"])
            continue

        delta = current_shot - prev_shot if current_shot >= prev_shot else current_shot
        updates = {}

        if delta > 0:
            ml.total_shot = (ml.total_shot or 0) + delta
            updates["total_shot"] = ml.total_shot

        if ml.last_shot != current_shot:
            ml.last_shot = current_shot
            updates["last_shot"] = current_shot

        if ml.last_update != ts:
            ml.last_update = ts
            updates["last_update"] = ts

        if updates:
            ml.save(update_fields=list(updates.keys()))


import requests
from django.http import JsonResponse

def control_esp32_proxy(request, action):
    # Lấy toàn bộ query string (?factory=1, ...)
    params = request.GET.urlencode()
    if params:
        esp32_url = f"http://192.168.11.40/{action}?{params}"
    else:
        esp32_url = f"http://192.168.11.40/{action}"

    try:
        response = requests.get(esp32_url, timeout=2)
        return JsonResponse({'status': 'ok', 'detail': 'Signal sent to ESP32'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)