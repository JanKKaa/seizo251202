import time
from calendar import monthrange
from collections import defaultdict
from django.shortcuts import render, get_object_or_404, redirect
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count, Q, Sum, F, Value, Max
from django.db import transaction
from .models import Machine, MachineStatusEvent, MachineAlarmEvent, DemAlarm
from .snapshot_service import fetch_runtime_index, fetch_log_types
import re
from datetime import datetime, timedelta, date
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count
from baotri.models import TaskCode
from django.db.models.functions import Coalesce
from .services import get_latest_esp32_status
from iot.models import DashboardNotification, DemAlarm, Esp32AlarmCount, Esp32Device
from menu.models import Holiday
# thêm import ProductionPlan
from .models import ProductionPlan
import logging
from .views_center2 import get_material_plan_for_day, get_plan_for_day

from .models import Esp32CycleShot
from .models import ProductShotMaster

from iot.net100shot import update_all_net100_shots

ESP32_API_URL = 'http://192.168.10.250:9000/esp32/api/button_status/'

RUNTIME_CACHE_TTL = 3  # seconds

# ==== NEW: cấu hình khu phân xưởng + fallback ====
# Máy thuộc Factory 1 (theo số đứng đầu tên máy, ví dụ "1号機" -> 1)
FACTORY1_IDS = {1, 2, 3, 4, 5, 6, 9, 10, 12, 13, 27, 28}

# Nếu muốn cố định 2 hàng cho Factory 2, điền tên máy vào đây (tùy chọn).
# Để trống => tự chia đều 2 hàng theo tên.
ROW1_IDS = set()
ROW2_IDS = set()

# ==== FIX: remove stray token that breaks import (xóa dòng 'models') ====
# (XÓA dòng đơn lẻ 'models' trong file nếu còn xuất hiện)

# ==== NEW: status-change cache keys ====
STATUS_CACHE_KEY = "iot_prev_status_by_key"

ESP32_IDS = [2, 8, 10, 12, 28]

logger = logging.getLogger("dashboard")

def get_esp32_cards():
    """
    Luôn trả về 4 card cho các máy ESP32 (2, 10, 12, 28), lấy trạng thái mới nhất từ DB (do AJAX ESP32 gửi về).
    Nếu không có dữ liệu thì trạng thái là offline.
    """
    try:
        esp32_devices = get_latest_esp32_status()
        
    except Exception as e:
        
        esp32_devices = []
    esp32_map = {}
    for d in esp32_devices:
        m = re.match(r'^(\d+)', d.get('name', ''))
        if m:
            esp32_map[int(m.group(1))] = d
    
    cards = []
    for esp_id in ESP32_IDS:
        name = f"{esp_id}号機"
        d = esp32_map.get(esp_id)
        class Dummy:
            pass
        m = Dummy()
        m.address = name
        m.rt_name = name
        m.rt_condname = ''
        if d:
            m.rt_runtime_status_code = d.get('runtime_status_code', 'offline')
            m.rt_runtime_status_jp = d.get('runtime_status_jp', 'オフライン')
            m.rt_alarm_active = d.get('alarm_active', False)
            m.rt_shotno = d.get('shotno')
            m.rt_cycletime = d.get('cycletime')
            m.alarm_count = d.get('alarm_count', 0)
        else:
            m.rt_runtime_status_code = 'offline'
            m.rt_runtime_status_jp = 'オフライン'
            m.rt_alarm_active = False
            m.rt_shotno = None
            m.rt_cycletime = None
            m.alarm_count = 0
        m.rt_latest_alarm_code = ''
        m.rt_latest_alarm_name = ''
        m.rt_latest_alarm_time = ''
        m.log_types = []
        cards.append(m)
    
    return cards

def _machine_key(item: dict) -> str:
    # Khóa nhận diện: ưu tiên address, fallback name
    return item.get("address") or item.get("name") or ""

def _mark_status_changed(runtime_list: list[dict]) -> None:
    prev = cache.get(STATUS_CACHE_KEY, {})  # {key: status_code}
    cur = {}
    for m in runtime_list:
        key = _machine_key(m)
        if not key:
            continue
        code = m.get("runtime_status_code") or "unknown"
        m["status_changed"] = (prev.get(key) is not None and prev.get(key) != code)
        cur[key] = code
    # Lưu lại bản đồ trạng thái hiện tại
    cache.set(STATUS_CACHE_KEY, cur, 3600)

def get_machine_number(rt_name):
    # Lấy số ở đầu chuỗi, ví dụ "1号機" -> 1
    match = re.match(r'^(\d+)', rt_name)
    return int(match.group(1)) if match else None

def _get_runtime_map():
    """
    Trả về dict: address -> runtime dict, dựa trên fetch_runtime_index().
    """
    runtime_list = fetch_runtime_index()
    return {m.get("address"): m for m in runtime_list if m.get("address")}

def index(request):
    t0 = time.time()
    machines = Machine.objects.all().order_by('address')
    runtime_map = _get_runtime_map()
    print("Load machines + runtime_map:", time.time() - t0)

    t1 = time.time()
    try:
        net100_error = False
    except Exception as e:
        print("NET100 error:", e)
        runtime_map = {}
        net100_error = True

    for m in machines:
        r = runtime_map.get(m.address)
        if r:
            m.rt_name = r.get('name') or m.name
            m.rt_condname = r.get('condname') or m.condname
            m.rt_runtime_status_code = r.get('runtime_status_code')
            m.rt_runtime_status_jp = r.get('runtime_status_jp')
            m.rt_alarm_active = r.get('alarm_active')
            m.rt_shotno = r.get('shotno')
            m.rt_cycletime = r.get('cycletime')
            latest_alarm = r.get('latest_alarm')
            if latest_alarm:
                m.rt_latest_alarm_code = latest_alarm.get('alarm_code', '')
                m.rt_latest_alarm_name = latest_alarm.get('alarm_name', '')
                m.rt_latest_alarm_time = latest_alarm.get('alarm_time', '')
            else:
                m.rt_latest_alarm_code = ''
                m.rt_latest_alarm_name = ''
                m.rt_latest_alarm_time = ''
        else:
            m.rt_name = m.name
            m.rt_condname = m.condname
            m.rt_runtime_status_code = 'offline'
            m.rt_runtime_status_jp = 'オフライン'
            m.rt_alarm_active = False
            m.rt_shotno = None
            m.rt_cycletime = None
            m.rt_latest_alarm_code = ''
            m.rt_latest_alarm_name = ''
            m.rt_latest_alarm_time = ''
        m.log_types = fetch_log_types(m.address)
    now = timezone.localtime()
    notifications = DashboardNotification.objects.all().order_by('-appear_at')
    print("get_monthly_progress_list:", time.time() - t1)
    return render(request, 'iot/index.html', {
        'machines': machines,
        'net100_error': net100_error,
        'notifications': notifications,
    })

def _get_tomorrow_plan_list():
    """
    Trả về list kế hoạch cho ngày mai: [{date, machine_name, product_name, plan_shot, staff, content}]
    """
    tomorrow = timezone.localdate() + timezone.timedelta(days=1)
    rows = (ProductionPlan.objects
            .filter(plan_date=tomorrow, plan_shot__gt=0)
            .order_by('machine', 'id'))
    out = []
    for p in rows:
        out.append({
            'date': tomorrow,
            'machine_name': str(p.machine),
            'product_name': p.product_name or '',
            'plan_shot': int(p.plan_shot or 0),
            'staff': getattr(p, 'staff', '') or '',
            'content': f"{p.product_name or ''} / {int(p.plan_shot or 0)} shot",
        })
    return out

def get_next_plan_date(plan_dates, today):
    # Loại trùng và sắp xếp
    unique_dates = sorted(set(plan_dates))
    for d in unique_dates:
        if d > today:
            return d
    return None

def get_shotplan_map():
    """
    Trả về map: (machine_key, product_name_norm) -> shotplan (sản lượng thực tế trong tháng).

    machine_key chuẩn hoá theo SỐ MÁY 2 CHỮ SỐ (vd '01', '02', '03', '06', '14'...),
    để khớp trực tiếp với mã máy trong ProductionPlan (01, 02, 03, 06).
    """
    from .models import ProductMonthlyShot

    today = timezone.localdate()
    month_str = today.strftime("%Y-%m")

    shotplan_map: dict[tuple[str, str], int] = {}

    rows = (
        ProductMonthlyShot.objects
        .filter(month=month_str)
        .values('source', 'address', 'machine_name', 'product_name')
        .annotate(shotplan=Sum('shot'))
    )

    for r in rows:
        machine_raw = r.get('machine_name') or r.get('address') or ""
        m = re.match(r'^(\d+)', str(machine_raw))
        if m:
            num_int = int(m.group(1))
            # CHUẨN HOÁ: 2 chữ số, giữ số 0 phía trước: 1 -> "01", 3 -> "03", 14 -> "14"
            base_num = f"{num_int:02d}"
        else:
            # fallback nếu không parse được số
            base_num = str(machine_raw).strip() or ""

        prod = _norm_product_name(r.get('product_name') or "")
        if not base_num or not prod:
            continue

        key = (base_num, prod)
        shotplan_map[key] = shotplan_map.get(key, 0) + (r.get('shotplan') or 0)

    return shotplan_map


def get_monthly_progress_list():
    shotplan_map = get_shotplan_map()

    # --- KODORI MAP ---
    kodori_map = {}
    for master in ProductShotMaster.objects.all():
        machine = str(master.machine).strip()
        product_name = _norm_product_name(master.product_name)
        kodori_map[(machine, product_name)] = master.kodori

        m_num = re.match(r'^(\d+)', machine)
        if m_num:
            num_int = int(m_num.group(1))
            base_num = str(num_int)
            # alias: "3", "03", "3号機"
            kodori_map[(base_num, product_name)] = master.kodori
            kodori_map[(f"{num_int:02d}", product_name)] = master.kodori
            kodori_map[(f"{base_num}号機", product_name)] = master.kodori

    today = timezone.localdate()
    first_day = today.replace(day=1)
    last_day = monthrange(today.year, today.month)[1]
    last_date = today.replace(day=last_day)

    plan_qs = (
        ProductionPlan.objects
        .filter(plan_date__gte=first_day, plan_date__lte=last_date)
        .values('machine', 'product_name')
        .annotate(total_plan=Sum('plan_shot'))
        .order_by('machine', 'product_name')
    )

    plan_map = {}
    for p in plan_qs:
        machine = str(p['machine']).strip()
        product_name = _norm_product_name(p['product_name'])
        key = (machine, product_name)
        plan_map[key] = p['total_plan'] or 0

    # gom ngày kế hoạch (nếu bạn đã có phần này thì giữ nguyên)
    plan_dates_qs = (
        ProductionPlan.objects
        .filter(plan_date__gte=first_day, plan_date__lte=last_date)
        .values('machine', 'product_name', 'plan_date')
    )
    plan_dates_map = defaultdict(list)
    for p in plan_dates_qs:
        machine = str(p['machine']).strip()
        product_name = _norm_product_name(p['product_name'])
        plan_dates_map[(machine, product_name)].append(p['plan_date'])

    progress_list = []
    for key, total_plan in plan_map.items():
        machine, product_name = key

        m_num = re.match(r'^(\d+)', machine)
        if m_num:
            num_int = int(m_num.group(1))       # "03" -> 3
            base_num = str(num_int)             # "3"
        else:
            num_int = None
            base_num = None

        # bỏ máy helper nếu cần
        if num_int is not None and num_int >= 90 and num_int != 100:
            continue

        # ==== LOOKUP SHOTPLAN (sản lượng thực tế) ====
        shotplan = shotplan_map.get((machine, product_name), 0)
        if shotplan == 0 and base_num is not None:
            alias_keys = [
                (base_num, product_name),             # "3"
                (f"{num_int:02d}", product_name),     # "03"
                (f"{base_num}号機", product_name),     # "3号機"
            ]
            for ak in alias_keys:
                shotplan = shotplan_map.get(ak, 0)
                if shotplan:
                    break

        # ==== LOOKUP KODORI ====
        kodori = kodori_map.get((machine, product_name), 1)
        if kodori == 1 and base_num is not None:
            alias_keys = [
                (base_num, product_name),
                (f"{num_int:02d}", product_name),
                (f"{base_num}号機", product_name),
            ]
            for ak in alias_keys:
                v = kodori_map.get(ak, 1)
                if v != 1:
                    kodori = v
                    break

        produced_qty = shotplan * kodori

        # ngày kế hoạch
        plan_dates = sorted(set(plan_dates_map.get(key, [])))
        last_plan_date = plan_dates[-1] if plan_dates else None
        is_done = last_plan_date < today if last_plan_date else False

        percent = int(produced_qty * 100 / total_plan) if total_plan > 0 else 0

        progress_list.append({
            'machine': machine,
            'product_name': product_name,
            'total_plan': total_plan,
            'produced_qty': produced_qty,
            'percent': percent,
            'shotplan': shotplan,
            'kodori': kodori,
            'current_product': product_name,
            'plan_date': last_plan_date,
            'plan_dates': plan_dates,
            'is_done': is_done,
        })

    progress_list.sort(key=lambda x: (x['is_done'], x['plan_date'] or today, x['machine']))
    return progress_list

def get_shotplan_list():
    # Trả về list cho bảng DB Shotplan
    shotplan_map = get_shotplan_map()
    shotplan_list = []
    for (address, current_product), shotplan in shotplan_map.items():
        shotplan_list.append({
            'address': address,
            'current_product': current_product,
            'shotplan': shotplan,
        })
    return shotplan_list

def dashboard(request):
    t0 = time.time()
    now = timezone.localtime()
    is_weekend = now.weekday() in (5, 6)
    is_holiday = Holiday.objects.filter(date=now.date()).exists() or is_weekend
    sleep_mode = is_holiday and now.hour >= 7
    from .views_csv import update_net100_current_product_by_plan
    update_net100_current_product_by_plan()
    logger.info("update_net100_current_product_by_plan: %.2f", time.time() - t0)

    t1 = time.time()
    machines = Machine.objects.all().order_by('address')
    runtime_map = _get_runtime_map()
    logger.info("Load machines + runtime_map: %.2f", time.time() - t1)

    t2 = time.time()
    progress_list_all = get_monthly_progress_list()
    logger.info("get_monthly_progress_list: %.2f", time.time() - t2)

    logger.info("Tổng thời gian dashboard: %.2f", time.time() - t0)

    
    
    machines = Machine.objects.all().order_by('address')
    runtime_map = _get_runtime_map()
    for m in machines:
        r = runtime_map.get(m.address)
        if r:
            m.rt_name = r.get('name') or m.name
            m.rt_condname = r.get('condname') or getattr(m, 'condname', '')
            m.rt_runtime_status_code = r.get('runtime_status_code')
            m.rt_runtime_status_jp = r.get('runtime_status_jp')
            m.rt_alarm_active = r.get('alarm_active')
            m.rt_shotno = r.get('shotno')
            m.rt_cycletime = r.get('cycletime')
            latest_alarm = r.get('latest_alarm')
            if latest_alarm:
                m.rt_latest_alarm_code = latest_alarm.get('alarm_code', '')
                m.rt_latest_alarm_name = latest_alarm.get('alarm_name', '')
                m.rt_latest_alarm_time = latest_alarm.get('alarm_time', '')
            else:
                m.rt_latest_alarm_code = ''
                m.rt_latest_alarm_name = ''
                m.rt_latest_alarm_time = ''
        else:
            m.rt_name = m.name
            m.rt_condname = getattr(m, 'condname', '')
            m.rt_runtime_status_code = 'offline'
            m.rt_runtime_status_jp = 'オフライン'
            m.rt_alarm_active = False
            m.rt_shotno = None
            m.rt_cycletime = None
            m.rt_latest_alarm_code = ''
            m.rt_latest_alarm_name = ''
            m.rt_latest_alarm_time = ''
        m.log_types = fetch_log_types(m.address)
        m.alarm_count = get_alarm_count(m)

    # Đếm KPI
    total = len(machines)
    production = sum(1 for m in machines if m.rt_runtime_status_code == 'production')
    stop = sum(1 for m in machines if m.rt_runtime_status_code == 'stop')
    alarm = sum(1 for m in machines if m.rt_runtime_status_code == 'alarm')
    offline = sum(1 for m in machines if m.rt_runtime_status_code == 'offline')
    now = timezone.localtime()

    # Phân factory + chèn ESP32 cards
    machines_factory1 = [m for m in machines if get_machine_number(m.rt_name) in FACTORY1_IDS and get_machine_number(m.rt_name) not in ESP32_IDS]
    esp32_cards = get_esp32_cards()
    machines_factory1 += esp32_cards
    machines_factory2 = [m for m in machines if get_machine_number(m.rt_name) not in FACTORY1_IDS]

    # Chia 2 hàng Factory 2
    if ROW1_IDS or ROW2_IDS:
        machines_row1 = [m for m in machines_factory2 if m.rt_name in ROW1_IDS]
        machines_row2 = [m for m in machines_factory2 if m.rt_name in ROW2_IDS]
    else:
        f2_sorted = sorted(machines_factory2, key=lambda x: (x.rt_name or ''))
        mid = (len(f2_sorted) + 1) // 2
        machines_row1 = f2_sorted[:mid]
        machines_row2 = f2_sorted[mid:]

    # Định dạng thời gian alarm
    for m in machines_factory1 + machines_factory2:
        if hasattr(m, 'rt_latest_alarm_time') and m.rt_latest_alarm_time:
            if isinstance(m.rt_latest_alarm_time, datetime):
                m.alarm_time_str = m.rt_latest_alarm_time.strftime('%H:%M')
            else:
                try:
                    dt = datetime.fromisoformat(str(m.rt_latest_alarm_time))
                    m.alarm_time_str = dt.strftime('%H:%M')
                except Exception:
                    m.alarm_time_str = str(m.rt_latest_alarm_time)[:5]
        else:
            m.alarm_time_str = ''
    now = datetime.now()
    for m in machines_factory1 + machines_factory2:
        if hasattr(m, 'rt_latest_alarm_time') and m.rt_latest_alarm_time:
            alarm_time = m.rt_latest_alarm_time
            if not isinstance(alarm_time, datetime):
                try:
                    alarm_time = datetime.fromisoformat(str(alarm_time))
                except Exception:
                    alarm_time = None
            if alarm_time:
                delta = now - alarm_time
                minutes = delta.seconds // 60
                hours = delta.seconds // 3600
                if delta.days > 0 or hours > 0:
                    m.alarm_duration_str = f"{hours:02d}時間{minutes%60:02d}分"
                else:
                    m.alarm_duration_str = f"{minutes:02d}分"
            else:
                m.alarm_duration_str = ""
        else:
            m.alarm_duration_str = ""

    today = timezone.localdate()
    # --- Lấy danh sách ngày có kế hoạch trong tháng ---
    today_first = today.replace(day=1)
    last_day = monthrange(today.year, today.month)[1]
    plan_dates = list(
        ProductionPlan.objects
        .filter(plan_date__gte=today_first, plan_date__lte=today.replace(day=last_day), plan_shot__gt=0)
        .values_list('plan_date', flat=True)
    )
    days_with_plan = sorted(set(plan_dates))

    # --- Tìm ngày tiếp theo thực sự có kế hoạch sau hôm nay ---
    next_plan_date = None
    for d in days_with_plan:
        if d > today:
            next_plan_date = d
            break
    tomorrow = next_plan_date

    def _display_maintainer(user):
        name = (user.get_full_name() or user.username) if user else ''
        if not name:
            return ''
        return name.split()[-1]  # chỉ lấy họ (token đầu)

    maintenance_qs = TaskCode.objects.filter(
        end_time__isnull=True,
        created_at__date=today
    ).select_related('task', 'created_by').order_by('-created_at')
    maintenance_list = [
        {
            'mold_name': m.task.name if m.task else '',
            'maintainer': _display_maintainer(m.created_by),
            'start_time': m.created_at,
        }
        for m in maintenance_qs
    ]

    maintained_qs = TaskCode.objects.filter(
        end_time__date=today
    ).select_related('task', 'created_by').order_by('-end_time')

    maintained_list = []
    for m in maintained_qs:
        duration_str = ""
        if m.created_at and m.end_time:
            delta = m.end_time - m.created_at
            minutes = int(delta.total_seconds() // 60)
            hours = minutes // 60
            mins = minutes % 60
            if hours > 0:
                duration_str = f"{hours}時間{mins}分"
            else:
                duration_str = f"{mins}分"
        maintained_list.append({
            'mold_name': m.task.name if m.task else '',
            'maintainer': _display_maintainer(m.created_by),
            'end_time': m.end_time,
            'duration': duration_str,
        })

    molds_maintained_today = maintained_qs.count()

    # Tóm tắt kế hoạch hôm nay cho Factory 1 và Factory 2
    today_plan_map = _get_today_plan_map()
    summary_f1 = {
        'total_shot': sum(info['total_shot'] for num, info in today_plan_map.items() if num in FACTORY1_IDS),
        'products': sorted({prod for num, info in today_plan_map.items() if num in FACTORY1_IDS for prod in info['products']}),
    }
    summary_f2 = {
        'total_shot': sum(info['total_shot'] for num, info in today_plan_map.items() if num not in FACTORY1_IDS),
        'products': sorted({prod for num, info in today_plan_map.items() if num not in FACTORY1_IDS for prod in info['products']}),
    }

    plan_map = _get_today_plan_map()

    def attach_plan_fields(m_obj):
        num = get_machine_number(getattr(m_obj, 'rt_name', '') or getattr(m_obj, 'address', ''))
        info = plan_map.get(num)
        m_obj.in_plan = bool(info)
        m_obj.plan_products = (info or {}).get('products', [])
        m_obj.plan_total_shot = (info or {}).get('total_shot', 0)

    for m in machines_factory1:
        attach_plan_fields(m)
    for m in machines_factory2:
        attach_plan_fields(m)

    def summarize_plan(machine_list):
        names = []
        for m in machine_list:
            if getattr(m, 'in_plan', False):
                prod = (m.plan_products[0] if m.plan_products else '')
                label = (m.rt_name or m.name or '')
                names.append(f"{label}{' - ' + prod if prod else ''}")
        return {
            'count': len(names),
            'names': names[:8],
        }

    plan_summary_f1 = summarize_plan(machines_factory1)
    plan_summary_f2 = summarize_plan(machines_factory2)

    # NEW: kế hoạch ngày mai cho màn hình thứ 2
    schedule_list = _get_tomorrow_plan_list()
    n = len(schedule_list)
    left_count = (n + 1) // 2
    schedule_left = schedule_list[:left_count]
    schedule_right = schedule_list[left_count:]

    # So sánh kế hoạch hôm nay và ngày tiếp theo có kế hoạch cho từng máy
    plans_today = get_plan_for_day(today)
    plans_tomorrow = get_plan_for_day(tomorrow) if tomorrow else []

    today_dict = {p['machine']: p['product_name'] for p in plans_today}
    tomorrow_dict = {p['machine']: p['product_name'] for p in plans_tomorrow}
    compare_list = []
    all_machines = set(today_dict.keys()) | set(tomorrow_dict.keys())
    for machine in sorted(all_machines, key=lambda x: int(x) if str(x).isdigit() else str(x)):
        today_product = today_dict.get(machine)
        tomorrow_product = tomorrow_dict.get(machine)
        if tomorrow_product is not None:
            if today_product == tomorrow_product:
                status = "không thay đổi"
            else:
                status = tomorrow_product
            compare_list.append({
                'machine': machine,
                'machine_int': int(machine) if str(machine).isdigit() else None,
                'today_product': today_product,
                'tomorrow_product': tomorrow_product,
                'status': status,
            })

    # Lấy danh sách nguyên liệu hôm nay
    material_plans_today = get_material_plan_for_day(today)
    total_material_today = sum(plan['total_plan'] or 0 for plan in material_plans_today)
 # Lấy danh sách tiến độ sản xuất trong tháng và tách thành 2 list
    progress_list_all = get_monthly_progress_list()
    progress_list = [row for row in progress_list_all if not row['is_done']]
    progress_list_done = [row for row in progress_list_all if row['is_done']]

    context = {
        'machines_factory1': machines_factory1,
        'machines_factory2': machines_factory2,
        'machines_row1': machines_row1,
        'machines_row2': machines_row2,
        'total': total,
        'production': production,
        'stop': stop,
        'alarm': alarm,
        'offline': offline,
        'now': now,
        'maintenance_list': maintenance_list,
        'molds_maintained_today': molds_maintained_today,
        'maintained_list': maintained_list,
        'days_with_plan': [str(d) for d in days_with_plan],
        'today': today,
        'tomorrow': tomorrow,
        'compare_list': compare_list,
        'plan_summary_f1': plan_summary_f1,
        'plan_summary_f2': plan_summary_f2,
        'schedule_list': schedule_list,
        'tomorrow_date': tomorrow,
        'schedule_left': schedule_left,
        'schedule_right': schedule_right,
        'tomorrow_total_shot': sum(p.get('plan_shot', 0) for p in schedule_list),
        'material_plans_today': material_plans_today,
        'material_plans_tomorrow': get_material_plan_for_day(tomorrow),
        'today_label': f"本日（{today:%m/%d}）",
        'tomorrow_label': f"翌日（{tomorrow:%m/%d}）" if tomorrow else "翌日（--/--）",
        'shotplan_list': get_shotplan_list(),
        'progress_list': progress_list,          # chỉ sản phẩm chưa hoàn thành trong tuần
        'progress_list_done': progress_list_done,  # sản phẩm đã hoàn thành trong tuần
        'month_label': timezone.localdate().strftime("%Y年%m月"),
        'total_material_today': total_material_today,
    }
    context['sleep_mode'] = sleep_mode
    context['sleep_mode_reason'] = '休日' if is_holiday else ''
    return render(request, 'iot/dashboard.html', context)

# === NEW: theo dõi thay đổi trạng thái để frontend chớp 5s ===
STATUS_CHANGE_WINDOW = 5  # seconds
_STATUS_CHANGE_CACHE = {}  # key -> {'status': str, 'changed_at': datetime}

def _mark_status_changes(machine_dicts):
    now = timezone.now()
    for m in machine_dicts:
        key = m.get('id') or m.get('name')
        status = m.get('runtime_status_code') or 'unknown'
        rec = _STATUS_CHANGE_CACHE.get(key)
        changed = False
        if rec is None or rec['status'] != status:
            _STATUS_CHANGE_CACHE[key] = {'status': status, 'changed_at': now}
            changed = True
        else:
            if (now - rec['changed_at']).total_seconds() <= STATUS_CHANGE_WINDOW:
                changed = True
        m['status_changed'] = changed

def log_status_change(machine: Machine, new_code: str, new_label_jp: str):
    if machine.runtime_status_code != new_code:
        MachineStatusEvent.objects.create(
            machine=machine,
            status_code=new_code,
            status_jp=new_label_jp
        )
        machine.runtime_status_code = new_code
        machine.save(update_fields=["runtime_status_code","updated_at"])

@transaction.atomic
def log_alarm(machine: Machine, alarm_code: str, alarm_name: str, message: str = ""):
    # Tăng biến đếm alarm
    demalarm, created = DemAlarm.objects.get_or_create(machine=machine)
    demalarm.count = F('count') + 1
    demalarm.save(update_fields=['count'])
    demalarm.refresh_from_db()  # Đảm bảo lấy giá trị mới nhất

    return MachineAlarmEvent.objects.create(
        machine=machine,
        alarm_code=alarm_code,
        alarm_name=alarm_name,
        message=message
    )


def clear_alarm(machine: Machine, alarm_code: str):
    active = (MachineAlarmEvent.objects
              .filter(machine=machine, alarm_code=alarm_code, cleared_at__isnull=True)
              .order_by("-id")
              .first())
    if active:
        active.cleared_at = timezone.now()
        active.save(update_fields=["cleared_at"])
        return active
    return None

def _serialize_events_today(limit: int = 10, name_by_addr: dict | None = None):
    today = timezone.localdate()
    # Lấy cả alarm phát sinh hôm nay và clear hôm nay
    alarm_qs = (MachineAlarmEvent.objects
                .filter(Q(created_at__date=today) | Q(cleared_at__date=today))
                .select_related("machine")
                .order_by("-created_at"))
    status_qs = (MachineStatusEvent.objects
                 .filter(created_at__date=today)
                 .select_related("machine")
                 .order_by("-created_at"))

    events = []
    # Alarm triggers + clears
    for a in alarm_qs:
        # Ưu tiên tên snapshot theo address (nếu có)
        m_addr = getattr(a.machine, "address", None)
        base_name = getattr(a.machine, "name", "") or ""
        snap_name = name_by_addr.get(m_addr) if (name_by_addr and m_addr) else None
        m_name = snap_name or base_name

        if a.created_at.date() == today:
            events.append({
                "id": f"ALM-{a.id}",
                "ts": timezone.localtime(a.created_at).isoformat(),
                "type": "alarm",
                "machine_name": m_name,
                "alarm_code": a.alarm_code,
                "alarm_name": a.alarm_name,
                "message": a.message or "",
                "count": a.occurrence_count,
            })
        if a.cleared_at and a.cleared_at.date() == today:
            events.append({
                "id": f"CLR-{a.id}",
                "ts": timezone.localtime(a.cleared_at).isoformat(),
                "type": "alarm_clear",
                "machine_name": m_name,
                "message": f"{a.alarm_code or ''} 解除".strip(),
            })
    # Status events
    for s in status_qs:
        m_addr = getattr(s.machine, "address", None)
        base_name = getattr(s.machine, "name", "") or ""
        snap_name = name_by_addr.get(m_addr) if (name_by_addr and m_addr) else None
        m_name = snap_name or base_name

        events.append({
            "id": f"STS-{s.id}",
            "ts": timezone.localtime(s.created_at).isoformat(),
            "type": "status",
            "machine_name": m_name,
            "runtime_status_code": s.status_code,
            "status_jp": s.status_jp,
        })
    # Sort và giới hạn TOP 10 mới nhất
    events.sort(key=lambda e: e["ts"], reverse=True)
    return events[:limit]

def _serialize_alarm_machine_counts(name_by_addr: dict | None = None, top: int = 10):
    today = timezone.localdate()
    base = MachineAlarmEvent.objects.filter(created_at__date=today).select_related("machine")
    # Lấy theo máy: cần cả address để map tên snapshot
    rows = (base.values("machine__address", "machine__name")
                 .annotate(alarm_total=Count("id")))
    # Active (nếu cần hiển thị song song)
    active_rows = (base.filter(cleared_at__isnull=True)
                        .values("machine__address")
                        .annotate(active_cnt=Count("id")))
    active_map = {r["machine__address"]: r["active_cnt"] for r in active_rows}

    out = []
    for r in rows:
        addr = r["machine__address"]
        db_name = r["machine__name"]
        snap_name = name_by_addr.get(addr) if (name_by_addr and addr) else None
        out.append({
            "machine_name": snap_name or db_name,
            "alarm_total": r["alarm_total"],
            "alarm_active": active_map.get(addr, 0),
        })
    out.sort(key=lambda x: (-x["alarm_total"], -x["alarm_active"], x["machine_name"]))
    return out[:top]

def _build_offline_fixed(snapshot_list):
    snap_addrs = {m.get("address") for m in (snapshot_list or []) if m.get("address")}
    out = []
    for m in Machine.objects.exclude(address__in=snap_addrs).order_by("address"):
        out.append({
            "address": m.address,
            "name": m.name or m.address,
            "condname": getattr(m, "condname", "") or "",
            "shotno": 0,
            "cycletime": "0.00",
            "runtime_status_code": "offline",
            "runtime_status_jp": "オフライン",
            "alarm_active": False,
            "latest_alarm": None,
            "status_changed": False,
        })
    return out

ALARM_NAME_EN_TO_JP = {
    "Screw Idling Alarm": "スクリュー空転アラーム",
    "Screw Damage Prev.": "スクリュー損傷防止アラーム",
    "Quality Control Measurement Alar": "品質管理測定アラーム",
    "Cycle time upper": "サイクルタイム上限アラーム",
    "Precaution - 1": "注意事項１",
    "Stop as-clamped Alarm": "クランプ停止アラーム",
    "Temp.Upper fault": "温度上限異常",
    "Temp.Lower fault": "温度下限異常",
    "Temp upper limit": "温度上限アラーム",
}

def translate_alarm_name(en_name):
    if not en_name:
        return "未確定エラー"
    return ALARM_NAME_EN_TO_JP.get(en_name, en_name)

def update_net100_alarm_count(address, new_status):
    cache_key = f'net100_status_{address}'
    machine = Machine.objects.filter(address=address).first()
    if machine:
        now = timezone.localtime()
        year = now.year
        month = now.month
        obj, _ = DemAlarm.objects.get_or_create(machine=machine)
        # Reset nếu sang tháng mới
        if obj.last_update_year != year or obj.last_update_month != month:
            obj.count = 0
            obj.last_update_year = year
            obj.last_update_month = month
            obj.save(update_fields=['count', 'last_update_year', 'last_update_month'])
        # Tăng biến đếm nếu chuyển sang alarm
        old_status = cache.get(cache_key, None)
        if old_status != "alarm" and new_status == "alarm":
            obj.count += 1
            obj.save(update_fields=['count'])
    cache.set(cache_key, new_status, timeout=24*3600)

def _get_today_plan_map():
    """
    Trả về map: machine number (int) -> {'products': [...], 'total_shot': int}
    Dùng để gắn vào JSON dashboard.
    """
    today = timezone.localdate()
    rows = (ProductionPlan.objects
            .filter(plan_date=today, plan_shot__gt=0)
            .order_by('machine', 'id'))
    plan_map = {}
    for p in rows:
        # hỗ trợ machine lưu dạng "28" hoặc "28号機"
        m = re.match(r'^(\d+)', str(p.machine))
        if not m:
            continue
        num = int(m.group(1))
        if num not in plan_map:
            plan_map[num] = {'products': [], 'total_shot': 0}
        if p.product_name and p.product_name not in plan_map[num]['products']:
            plan_map[num]['products'].append(p.product_name)
        plan_map[num]['total_shot'] += int(p.plan_shot or 0)
    return plan_map

def dashboard_json(request):
    cache_key = "dashboard_json_cache"
    data = cache.get(cache_key)
    if data:
        return JsonResponse(data, json_dumps_params={"ensure_ascii": False})

    runtime_list = fetch_runtime_index()
    label_map = {
        "production": "稼働中", "stop": "停止", "arrange": "段取り中",
        "alarm": "アラーム", "offline": "オフライン", "unknown": "不明"
    }
    for m in runtime_list:
        code = m.get("runtime_status_code") or m.get("status") or "unknown"
        m["runtime_status_code"] = code
        m["runtime_status_jp"] = m.get("runtime_status_jp") or label_map.get(code, "不明")

        latest_alarm = m.get("latest_alarm")
        if latest_alarm and "alarm_name" in latest_alarm:
            en_name = latest_alarm["alarm_name"]
            latest_alarm["alarm_name"] = translate_alarm_name(en_name)

        addr = m.get('address')
        machine = Machine.objects.filter(address=addr).first() if addr else None
        m['alarm_count'] = get_alarm_count(machine) if machine else 0

        # --- Gọi hàm tăng biến đếm alarm cho NET100 ---
        update_net100_alarm_count(addr, code)

    _mark_status_changed(runtime_list)

    name_by_addr = {m.get("address"): (m.get("name") or m.get("address"))
                    for m in runtime_list if m.get("address")}

    def extract_num(name):
        import re
        if not name: return None
        mm = re.match(r'^(\d+)', name)
        return int(mm.group(1)) if mm else None

    factory1_idset = {1, 3, 4, 5, 6, 9, 13, 27}
    f1, f2 = [], []
    for m in runtime_list:
        (f1 if extract_num(m.get("name", "")) in factory1_idset else f2).append(m)

    now = timezone.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    alarms = (
        MachineAlarmEvent.objects
        .filter(created_at__gte=first_day, created_at__lte=now)
        .values('machine__address')
        .annotate(
            alarm_total=Count('id')
        )
    )
    alarm_count_map = {a['machine__address']: a['alarm_total'] for a in alarms}
    for m in runtime_list:
        m['alarm_count_month'] = alarm_count_map.get(m.get('address'), 0)

    # --- Lấy trạng thái ESP32 trực tiếp từ DB ---
    ESP32_IDS = [2, 8, 10, 12, 28]
    esp32_api_cards = get_latest_esp32_status()

    esp32_status_map = {}
    for m in esp32_api_cards:
        addr = m.get("name") or m.get("address")
        if addr and addr.endswith("号機"):
            try:
                addr_num = int(addr.replace("号機", ""))
                esp32_status_map[addr_num] = m
            except Exception:
                continue

    esp32_cards_full = []
    for esp_id in ESP32_IDS:
        name = f"{esp_id}号機"
        m = esp32_status_map.get(esp_id)
        machine_obj = Machine.objects.filter(address=name).first()
        alarm_count = get_alarm_count(machine_obj) if machine_obj else 0
        if m:
            m["alarm_count"] = alarm_count
            esp32_cards_full.append(m)
        else:
            esp32_cards_full.append({
                "address": name,
                "name": name,
                "runtime_status_code": "offline",
                "runtime_status_jp": "オフライン",
                "alarm_active": False,
                "latest_alarm": None,
                "alarm_count": alarm_count,
                "status_changed": False,
            })

    esp32_total = len(esp32_cards_full)
    esp32_production = sum(1 for m in esp32_cards_full if m.get("runtime_status_code") == "production")
    esp32_alarm = sum(1 for m in esp32_cards_full if m.get("runtime_status_code") == "alarm")
    esp32_arrange = sum(1 for m in esp32_cards_full if m.get("runtime_status_code") == "arrange")
    esp32_stop = sum(1 for m in esp32_cards_full if m.get("runtime_status_code") == "stop")
    esp32_offline = sum(1 for m in esp32_cards_full if m.get("runtime_status_code") == "offline")

    # --- kế hoạch hôm nay ---
    plan_map = _get_today_plan_map()
    def _attach_plan_fields(m):
        # name hoặc address start with number
        name = (m.get('name') or m.get('address') or '')
        mm = re.match(r'^(\d+)', str(name))
        num = int(mm.group(1)) if mm else None
        info = plan_map.get(num)
        m['plan_in_today'] = bool(info)
        m['plan_products'] = (info or {}).get('products', [])
        m['plan_total_shot'] = (info or {}).get('total_shot', 0)

    for m in runtime_list:
        _attach_plan_fields(m)

    # sau khi build esp32_cards_full, cũng attach
    for m in esp32_cards_full:
        _attach_plan_fields(m)

    data = {
        "machines_factory1": f1,
        "machines_factory2": f2,
        "machines_esp32": esp32_cards_full,
        "total": len(runtime_list) + esp32_total,
        "production": sum(1 for m in runtime_list if m["runtime_status_code"] == "production") + esp32_production,
        "stop": sum(1 for m in runtime_list if m["runtime_status_code"] == "stop") + esp32_stop,
        "arrange": sum(1 for m in runtime_list if m["runtime_status_code"] == "arrange") + esp32_arrange,
        "alarm": sum(1 for m in runtime_list if m["runtime_status_code"] == "alarm") + esp32_alarm,
        "offline": sum(1 for m in runtime_list if m["runtime_status_code"] == "offline") + esp32_offline,
        "esp32_total": esp32_total,
        "esp32_production": esp32_production,
        "esp32_alarm": esp32_alarm,
        "esp32_arrange": esp32_arrange,
        "esp32_stop": esp32_stop,
        "esp32_offline": esp32_offline,
        "now": timezone.localtime().strftime("%H:%M:%S"),
        "events_today": _serialize_events_today(limit=10, name_by_addr=name_by_addr),
        "alarm_machine_counts": _serialize_alarm_machine_counts(name_by_addr=name_by_addr, top=10),
    }

    data["offline_fixed"] = _build_offline_fixed(runtime_list)

    cache.set(cache_key, data, 3)  # cache 3 giây
    return JsonResponse(data, json_dumps_params={"ensure_ascii": False})

def alarm_top5_machine_month(request):
    # Lấy dữ liệu net100 từ DemAlarm
    net100_qs = (
        DemAlarm.objects
        .select_related('machine')
        .all()
    )
    net100_list = [
        {
            'machine__address': d.machine.address,
            'machine__name': d.machine.name,
            'alarm_count': d.count
        }
        for d in net100_qs
    ]

    # Lấy dữ liệu ESP32 từ Esp32AlarmCount
    esp32_qs = Esp32AlarmCount.objects.all()
    # Map address -> name nếu có Esp32Device
    esp32_name_map = {dev.device_id: dev.name for dev in Esp32Device.objects.all()}
    esp32_list = []
    for e in esp32_qs:
        name = esp32_name_map.get(e.address, e.address)
        esp32_list.append({
            'machine__address': e.address,
            'machine__name': name,
            'alarm_count': e.count
        })

    # Gộp và sắp xếp giảm dần theo alarm_count
    all_machines = net100_list + esp32_list
    all_machines_sorted = sorted(all_machines, key=lambda x: x.get('alarm_count', 0), reverse=True)
    top5 = all_machines_sorted[:5]

    return JsonResponse({'machines': top5})

def get_alarm_count(machine):
    try:
        return DemAlarm.objects.get(machine=machine).count
    except DemAlarm.DoesNotExist:
        return 0

def delete_notification(request, pk):
    notif = get_object_or_404(DashboardNotification, pk=pk)
    notif.delete()
    return redirect('iot_index')

from django.views.decorators.http import require_GET

@require_GET
def monthly_progress_json(request):
    progress_list_all = get_monthly_progress_list()
    today = timezone.localdate()

    # chỉ kế hoạch trong tuần hiện tại (Thứ 2–Chủ nhật)
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    def in_this_week(row):
        dates = row.get('plan_dates') or []
        return any(start_week <= d <= end_week for d in dates)

    progress_list = [
        row for row in progress_list_all
        if (not row['is_done']) and in_this_week(row)
    ]

    month_label = timezone.localdate().strftime("%Y年%m月")
    return JsonResponse(
        {
            "month_label": month_label,
            "progress_list": progress_list,
        },
        json_dumps_params={"ensure_ascii": False},
    )

def _norm_product_name(s: str) -> str:
    """
    Chuẩn hóa tên sản phẩm:
    - Chuyển None -> ""
    - Gộp nhiều khoảng trắng liên tiếp thành 1 space
    - strip 2 đầu
    """
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


# ...existing code...

def center2(request):
    from datetime import timedelta

    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    progress_list = get_monthly_progress_list()
    month_label = timezone.localdate().strftime("%Y年%m月")

    # Nếu cần so sánh kế hoạch hôm nay và ngày mai
    compare_list = []
    try:
        plans_today = get_plan_for_day(today)
        plans_tomorrow = get_plan_for_day(tomorrow)
        today_dict = {p['machine']: p['product_name'] for p in plans_today}
        tomorrow_dict = {p['machine']: p['product_name'] for p in plans_tomorrow}
        all_machines = set(today_dict.keys()) | set(tomorrow_dict.keys())
        for machine in sorted(all_machines, key=lambda x: int(x) if str(x).isdigit() else str(x)):
            today_product = today_dict.get(machine)
            tomorrow_product = tomorrow_dict.get(machine)
            if tomorrow_product is not None:
                if today_product == tomorrow_product:
                    status = "không thay đổi"
                else:
                    status = tomorrow_product
                compare_list.append({
                    'machine': machine,
                    'machine_int': int(machine) if str(machine).isdigit() else None,
                    'today_product': today_product,
                    'tomorrow_product': tomorrow_product,
                    'status': status,
                })
    except Exception:
        compare_list = []

    context = {
        'progress_list': progress_list,
        'today': today,
        'tomorrow': tomorrow,
        'compare_list': compare_list,
        'month_label': month_label,
    }
    return render(request, 'iot/partials/_center_panel2.html', context)
