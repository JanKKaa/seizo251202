from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.cache import cache
from django.core.mail import send_mail
import json
import requests
import time
from .models import (
    Esp32Device,
    Esp32StatusLog,
    Esp32AlarmCount,
    Esp32CycleShot,
    Esp32CardSnapshot,
    Machine,
    DemAlarm,
    ProductionPlan,
    ProductMonthlyShot,
)
from django.utils import timezone
from calendar import monthrange
from iot.views_index import _get_today_plan_map

ESP32_API_URL = 'http://192.168.10.250:9000/esp32/api/button_status/'

ESP32_TARGET_IDS = {'2号機', '8号機', '10号機', '12号機', '28号機'}

# Machine CT pin: chân dùng để tính chu kỳ (Cycle Time)/shot cho từng máy
DEFAULT_CT_PIN = 'gpio5'
MACHINE_CT_PIN = {
    'default': DEFAULT_CT_PIN,
    '2号機': 'gpio4',
    '8号機': 'gpio4',
    '10号機': 'gpio15',
    '12号機': 'gpio15',
    '28号機': 'gpio5',
    '40号機': 'gpio5',
}

def resolve_ct_pin(address):
    return MACHINE_CT_PIN.get(address, MACHINE_CT_PIN['default'])

@csrf_exempt
def esp32_data_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode())
            device_id = data.get('device_id')
            pins = data.get('pins', {})
            address = device_id.replace('seikei', '') + '号機' if device_id.startswith('seikei') else device_id
            status = get_esp32_machine_status(pins, device_id=device_id, address=address)
            # --- Xử lý cycle time & shot ---
            obj, _ = Esp32CycleShot.objects.get_or_create(address=address)
            ct_pin = resolve_ct_pin(address)
            curr_ej = pins.get(ct_pin, 0)
            now = timezone.localtime()
            last_ej_on = obj.last_ej_on
            cycletime = obj.cycletime
            shot = obj.shot

            cache_key = f'esp32_ej_prev_{address}'
            prev_ej = cache.get(cache_key, 0)
            # Ghi nhận khi cạnh OFF -> ON xuất hiện
            if prev_ej == 0 and curr_ej == 1:
                if last_ej_on:
                    cycletime = (now - last_ej_on).total_seconds()
                shot += 1
                last_ej_on = now
                obj.cycletime = cycletime
                obj.shot = shot
                obj.last_ej_on = last_ej_on
                obj.save(update_fields=['cycletime', 'shot', 'last_ej_on', 'updated_at'])
            cache.set(cache_key, curr_ej, timeout=24*3600)

            # --- Cập nhật trạng thái máy vào DB ---
            status = get_esp32_machine_status(pins, device_id=device_id, address=address)
            device, _ = Esp32Device.objects.get_or_create(device_id=device_id)
            device.status_code = status['code']
            device.status_jp = status['jp']
            device.pins = pins
            device.last_update = now
            device.save(update_fields=['status_code', 'status_jp', 'pins', 'last_update'])

            Esp32StatusLog.objects.create(
                device=device,
                pins=pins,
                status_code=status['code'],
                status_jp=status['jp']
            )
            return JsonResponse({"status": "ok"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse({"status": "error", "message": "Chỉ hỗ trợ POST"}, status=405)

def esp32_status_proxy(request):
    """
    API trả về dữ liệu gốc từ ESP32 (chưa xử lý trạng thái).
    """
    try:
        resp = requests.get(ESP32_API_URL, timeout=3)
        data = resp.json()
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'devices': [], 'error': str(e)}, status=500)

def _status_machine_2(pins, address=None, **_):
    """
    - Nếu trong 5 giây gần nhất, gpio0 ON/OFF >= 5 lần => vào trạng thái alarm.
    - Khi đã vào alarm thì duy trì alarm, chỉ khi gpio0 OFF liên tục >3s mới tắt alarm.
    """
    now = timezone.now()
    cache_key = f'esp32_alarm2_events_{address}'
    alarm_state_key = f'esp32_alarm2_state_{address}'
    last_off_key = f'esp32_alarm2_last_off_{address}'

    # Lưu lại lịch sử ON/OFF của gpio0 trong 5 giây gần nhất
    events = cache.get(cache_key, [])
    gpio0 = pins.get('gpio0', 0)
    prev_gpio0 = events[-1][1] if events else None

    # Nếu trạng thái thay đổi, lưu lại thời điểm
    if prev_gpio0 is None or gpio0 != prev_gpio0:
        events.append((now.timestamp(), gpio0))
        # Giữ tối đa 20 sự kiện gần nhất
        events = events[-20:]
        cache.set(cache_key, events, timeout=10)

    # Đếm số lần chuyển trạng thái trong 5 giây gần nhất
    recent_events = [e for e in events if now.timestamp() - e[0] <= 5]
    transitions = sum(1 for i in range(1, len(recent_events)) if recent_events[i][1] != recent_events[i-1][1])

    # Kiểm tra trạng thái alarm hiện tại
    alarm_active = cache.get(alarm_state_key, False)

    if not alarm_active:
        # Nếu chuyển trạng thái >=10 lần trong 5 giây => bật alarm
        if transitions >= 10:
            cache.set(alarm_state_key, True, timeout=60)
            return {'code': 'alarm', 'jp': 'アラーム'}
        # Chưa đủ điều kiện, trả về trạng thái bình thường
        if pins.get('gpio2', 0) == 1:
            return {'code': 'production', 'jp': '生産中'}
        return {'code': 'stop', 'jp': '停止'}
    else:
        # Đang ở trạng thái alarm, kiểm tra điều kiện tắt alarm
        if gpio0 == 0:
            last_off = cache.get(last_off_key)
            if not last_off:
                cache.set(last_off_key, now.timestamp(), timeout=10)
            elif now.timestamp() - cache.get(last_off_key) > 3:
                # OFF liên tục >3s thì tắt alarm
                cache.set(alarm_state_key, False, timeout=10)
                cache.delete(last_off_key)
                if pins.get('gpio2', 0) == 1:
                    return {'code': 'production', 'jp': '生産中'}
                return {'code': 'stop', 'jp': '停止'}
        else:
            cache.delete(last_off_key)
        # Duy trì trạng thái alarm
        return {'code': 'alarm', 'jp': 'アラーム'}


def _status_machine_8(pins, **_):
    if pins.get('gpio0', 0) == 1:
        return {'code': 'alarm', 'jp': 'アラーム'}
    if pins.get('gpio2', 0) == 1:
        return {'code': 'production', 'jp': '生産中'}
    if pins.get('gpio5', 0) == 1 and not pins.get('gpio2', 0) and not pins.get('gpio0', 0):
        return {'code': 'arrange', 'jp': '段取り'}
    return {'code': 'stop', 'jp': '停止'}


def _status_machine_10(pins, *, address=None, **_):
    monitored = ('gpio0', 'gpio4', 'gpio19', 'gpio21')

    # Không nhận được tín hiệu nào từ thiết bị
    if not pins:
        return {'code': 'offline', 'jp': 'オフライン'}

    def pin_on(name):
        return 1 if pins.get(name, 0) == 1 else 0

    if pin_on('gpio0'):
        return {'code': 'alarm', 'jp': 'アラーム'}

    if pin_on('gpio19'):
        return {'code': 'production', 'jp': '生産中'}

    cache_key = f'{address}_gpio4_last_on'
    if pin_on('gpio4'):
        cache.set(cache_key, timezone.now(), timeout=40)
        return {'code': 'production', 'jp': '生産中'}

    last_on = cache.get(cache_key)
    if last_on and (timezone.now() - last_on).total_seconds() <= 30:
        return {'code': 'production', 'jp': '生産中'}

    # Chỉ GPIO21 bật, các chân còn lại tắt -> STOP
    if pin_on('gpio21') == 1 and all(pin_on(p) == 0 for p in monitored if p != 'gpio21'):
        return {'code': 'stop', 'jp': '停止'}

    # Tất cả các chân theo dõi đều OFF -> Dandori
    if all(pin_on(p) == 0 for p in monitored):
        return {'code': 'arrange', 'jp': '段取り'}

    return {'code': 'stop', 'jp': '停止'}


def _status_machine_12(pins, **_):
    # TODO: cập nhật điều kiện cụ thể cho máy 12号機
    return _status_default(pins)


def _status_machine_28(pins, **_):
    if pins.get('gpio0', 0) == 1:
        return {'code': 'alarm', 'jp': 'アラーム'}
    if pins.get('gpio2', 0) == 1:
        return {'code': 'production', 'jp': '生産中'}
    if pins.get('gpio5', 0) == 1 and not pins.get('gpio2', 0) and not pins.get('gpio0', 0):
        return {'code': 'arrange', 'jp': '段取り'}
    return {'code': 'stop', 'jp': '停止'}


def _status_machine_40(pins, **_):
    # TODO: cập nhật điều kiện cụ thể cho máy 40号機
    return _status_default(pins)


def _status_default(pins, **_):
    if pins.get('gpio0', 0) == 1:
        return {'code': 'alarm', 'jp': 'アラーム'}
    if pins.get('gpio2', 0) == 1:
        return {'code': 'production', 'jp': '生産中'}
    if pins.get('gpio5', 0) == 1 and not pins.get('gpio2', 0) and not pins.get('gpio0', 0):
        return {'code': 'arrange', 'jp': '段取り'}
    return {'code': 'stop', 'jp': '停止'}


MACHINE_STATUS_HANDLERS = {
    '2号機': _status_machine_2,
    '8号機': _status_machine_8,
    '10号機': _status_machine_10,
    '12号機': _status_machine_12,
    '28号機': _status_machine_28,
    '40号機': _status_machine_40,
}


def get_esp32_machine_status(pins, device_id=None, address=None):
    handler = MACHINE_STATUS_HANDLERS.get(address)
    if handler:
        return handler(pins, device_id=device_id, address=address)
    return _status_default(pins, device_id=device_id, address=address)

def esp32_status_processed(request):
    """
    API trả về trạng thái đã xử lý cho từng thiết bị ESP32 (tất cả thiết bị).
    """
    try:
        resp = requests.get(ESP32_API_URL, timeout=3)
        data = resp.json()
        devices = data.get('devices', [])
        for d in devices:
            pins = d.get('pins', {})
            status = get_esp32_machine_status(pins)
            d['status_code'] = status['code']
            d['status_jp'] = status['jp']
        return JsonResponse({'devices': devices})
    except Exception as e:
        return JsonResponse({'devices': [], 'error': str(e)}, status=500)

def update_esp32_alarm_count(address, new_status):
    obj, _ = Esp32AlarmCount.objects.get_or_create(address=address)
    old_status = obj.last_status if hasattr(obj, 'last_status') else None
    now = timezone.localtime()
    year = now.year
    month = now.month

    # --- NEW: kiểm tra thời gian duy trì alarm ---
    alarm_start_key = f'esp32_alarm_start_{address}'
    alarm_start_time = cache.get(alarm_start_key)

    if new_status == "alarm":
        if not alarm_start_time:
            cache.set(alarm_start_key, time.time(), timeout=60*10)  # lưu thời điểm bắt đầu alarm
        else:
            elapsed = time.time() - alarm_start_time
            if elapsed >= 10:
                # Chỉ gửi mail và tăng count nếu vừa chuyển sang alarm hoặc chưa gửi trong lần này
                if old_status != "alarm" or not getattr(obj, 'alarm_sent_this_time', False):
                    obj.alarm_sent_this_time = True  # đánh dấu đã gửi mail cho lần alarm này
                    obj.save(update_fields=['alarm_sent_this_time'])
                    send_esp32_alarm_mail(address)
                    if obj.last_update_year != year or obj.last_update_month != month:
                        obj.count = 0
                    obj.count += 1
                    obj.last_update_year = year
                    obj.last_update_month = month
                    # --- Cập nhật vào DemAlarm để thống kê chung ---
                    machine = Machine.objects.filter(address=address).first()
                    if machine:
                        demalarm, _ = DemAlarm.objects.get_or_create(machine=machine)
                        if demalarm.last_update_year != year or demalarm.last_update_month != month:
                            demalarm.count = 0
                        demalarm.count += 1
                        demalarm.last_update_year = year
                        demalarm.last_update_month = month
                        demalarm.save(update_fields=['count', 'last_update_year', 'last_update_month'])
    else:
        cache.delete(alarm_start_key)
        obj.alarm_sent_this_time = False  # reset flag khi hết alarm

    obj.last_status = new_status
    obj.save(update_fields=['count', 'last_update_year', 'last_update_month', 'last_status', 'alarm_sent_this_time'])
    print(f"[ALARM CHECK] {address}: old={old_status}, new={new_status}")

def esp32_status_processed_targets(request):
    """
    API trả về trạng thái ổn định: nếu đã alarm thì giữ 'alarm' cho đến khi GPIO0 OFF.
    """
    try:
        resp = requests.get(ESP32_API_URL, timeout=3)
        data = resp.json()
        devices = data.get('devices', [])
        filtered = []
        plan_map = _get_today_plan_map()
        for d in devices:
            device_id = d.get('device_id', '')
            if device_id.startswith('seikei'):
                name = device_id.replace('seikei', '') + '号機'
            else:
                name = device_id
            if name in ESP32_TARGET_IDS:
                pins = d.get('pins', {})
                status = get_esp32_machine_status(pins, device_id=device_id, address=name)

                # Lấy trạng thái alarm đã lưu trong DB
                alarm_obj, _ = Esp32AlarmCount.objects.get_or_create(address=name)
                last_status = alarm_obj.last_status if hasattr(alarm_obj, 'last_status') else None

                # Nếu DB đang lưu là 'alarm' và GPIO0 vẫn ON, giữ 'alarm'
                # Nếu DB đang lưu là 'alarm' nhưng GPIO0 đã OFF, chuyển về trạng thái mới
                if last_status == "alarm":
                    if pins.get('gpio0', 0) == 1:
                        status = {'code': 'alarm', 'jp': 'アラーム'}
                    else:
                        status = get_esp32_machine_status(pins)

                # Cập nhật DB (đếm alarm)
                update_esp32_alarm_count(name, status['code'])

                # Lấy CT pin theo máy thay vì cố định gpio5
                ct_pin = resolve_ct_pin(name)
                curr_ej = pins.get(ct_pin, 0)
                update_shot_cycletime(name, curr_ej, status['code'])

                # Lấy dữ liệu từ DB
                alarm_count = alarm_obj.count if alarm_obj else 0
                cycle_obj = Esp32CycleShot.objects.filter(address=name).first()
                shot = cycle_obj.shot if cycle_obj else 0
                cycletime = f"{cycle_obj.cycletime:.2f}" if cycle_obj else "0.00"
                try:
                    if cycle_obj and cycle_obj.cycletime > 90:
                        cycletime = "不明"
                except Exception:
                    pass

                now = timezone.localtime()
                status_changed = False

                # Nếu trạng thái vừa thay đổi, lưu lại thời điểm đổi trạng thái
                if last_status != status['code']:
                    alarm_obj.last_status_change_time = now
                    alarm_obj.save(update_fields=['last_status_change_time'])
                    status_changed = True
                else:
                    # Nếu đã đổi trạng thái trước đó, kiểm tra thời gian
                    last_change = getattr(alarm_obj, 'last_status_change_time', None)
                    if last_change and (now - last_change).total_seconds() < 5:
                        status_changed = True

                # --- Thêm thông tin kế hoạch sản xuất ---
                num = None
                if name.endswith('号機'):
                    num_part = name[:-2]
                    if num_part.isdigit():
                        num = int(num_part)
                plan_info = plan_map.get(num, {}) if num is not None else {}
                plan_products = plan_info.get('products', [])
                plan_total_shot = plan_info.get('total_shot', 0)
                plan_in_today = bool(plan_products or plan_total_shot)

                # Thêm vào danh sách kết quả
                filtered.append({
                    "address": name,
                    "name": name,
                    "condname": "",
                    "shotno": shot,
                    "cycletime": cycletime,
                    "runtime_status_code": status['code'],
                    "runtime_status_jp": status['jp'],
                    "alarm_active": status['code'] == "alarm",
                    "latest_alarm": None,
                    "alarm_count": alarm_count,
                    "status_changed": status_changed,
                    "alarm_count_month": 0,
                    "pins": pins,
                    "plan_products": plan_products,
                    "plan_total_shot": plan_total_shot,
                    "plan_in_today": plan_in_today,
                })

                primary_product = plan_products[0] if plan_products else ""
                snapshot, _ = Esp32CardSnapshot.objects.get_or_create(address=name)
                snapshot.shot = shot
                snapshot.cycletime = cycletime
                snapshot.primary_product = primary_product
                snapshot.product_display = " / ".join(plan_products) if plan_products else ""
                snapshot.save(update_fields=["shot", "cycletime", "primary_product", "product_display", "updated_at"])
        return JsonResponse({'machines': filtered})
    except Exception as e:
        return JsonResponse({'machines': [], 'error': str(e)}, status=500)

def update_shot_cycletime(address, curr_ej, curr_status=None):
    cache_key = f'esp32_ej_prev_{address}'
    prev_ej = cache.get(cache_key, None)
    now = timezone.localtime()
    obj, _ = Esp32CycleShot.objects.get_or_create(address=address)
    rule = get_shot_reset_rule(address)

    # --- Reset shot khi sản phẩm trong kế hoạch thay đổi (GIỮ monthly_shot) ---
    from iot.views_index import _get_today_plan_map
    plan_machine = address
    if address.endswith('号機'):
        plan_machine = address[:-2]  # "28号機" -> "28"
    elif address.isdigit():
        plan_machine = address
        num = int(address)
    plan_map = _get_today_plan_map()
    plan_info = plan_map.get(int(plan_machine), {}) if plan_machine.isdigit() else {}
    plan_products = plan_info.get('products', [])
    current_product = plan_products[0] if plan_products else None

    product_cache_key = f'esp32_last_product_{address}'
    last_product = cache.get(product_cache_key)

    if last_product is not None and last_product != current_product:
        # CHỈ reset counter hiện tại, KHÔNG đụng đến monthly_shot
        obj.shot = 0
        obj.save(update_fields=['shot'])
        print(f"[{now}] {address} RESET SHOT (change product)")

    cache.set(product_cache_key, current_product, timeout=24*3600)

    # --- Đếm shot + tích lũy theo tháng ---
    if prev_ej is None:
        cache.set(cache_key, curr_ej, timeout=24*3600)
        return

    if prev_ej == 0 and curr_ej == 1:
        month_str = now.strftime("%Y-%m")
        if obj.month != month_str:
            obj.month = month_str
            obj.monthly_shot = 0

        obj.shot += 1
        obj.monthly_shot += 1
        obj.cycletime = (now - obj.last_ej_on).total_seconds() if obj.last_ej_on else 0
        obj.last_ej_on = now

        # --- NEW: lưu shot theo (máy, sản phẩm, tháng) ---
        if current_product:
            pms, _ = ProductMonthlyShot.objects.get_or_create(
                source="esp32",
                address=address,
                product_name=current_product,
                month=month_str,
                defaults={"machine_name": address, "shot": 0},
            )
            # Tăng shot bình thường (không dùng F để tránh lỗi)
            pms.shot = (pms.shot or 0) + 1
            pms.save(update_fields=["shot"])

        # Cập nhật shotplan cho máy và sản phẩm hiện tại (giữ nguyên logic cũ nếu bạn đang dùng)
        if current_product:
            shot_obj, _ = Esp32CycleShot.objects.get_or_create(
                address=address,
                defaults={'shotplan': 0, 'current_product': current_product}
            )
            if shot_obj.updated_at.date().month != now.month:
                shot_obj.shotplan = 0
            shot_obj.shotplan += 1
            shot_obj.current_product = current_product
            shot_obj.save(update_fields=['shotplan', 'updated_at', 'current_product'])

        obj.save(update_fields=['shot', 'monthly_shot', 'cycletime', 'last_ej_on', 'month', 'updated_at'])
        print(f"[{now}] {address} SHOT: {obj.shot}, MONTHLY: {obj.monthly_shot}, CT: {obj.cycletime:.2f}, SHOTPLAN(month): {obj.shotplan}, PRODUCT: {current_product}")

    cache.set(cache_key, curr_ej, timeout=24*3600)

def send_esp32_alarm_mail(address):
    subject = "【警告】機械アラーム発生"
    message = f"機械でアラームが発生しています。\nNo.{address.replace('号機','')}: {address}"
    recipient = ["giang@hayashi-p.co.jp"]
    
    send_mail(subject, message, None, recipient)

def esp32_alarm_popup(request):
    # Lấy tất cả ESP32 có last_status là "alarm"
    alarms = Esp32AlarmCount.objects.filter(last_status="alarm")
    # Chuyển thành list dict để trả về JSON
    machines = []
    for alarm in alarms:
        machines.append({
            "address": alarm.address,
            "last_status": alarm.last_status,
            "latest_alarm": getattr(alarm, "latest_alarm", None),  # nếu có trường này
            # thêm các trường khác nếu cần
        })
    return JsonResponse({"machines": machines})

# Quy tắc reset shot theo từng máy:
# - reset_statuses: tập trạng thái (arrange/stop/...) mà khi máy rơi vào sẽ xét reset.
# - idle_seconds: nếu thời gian không bắn vượt quá số giây này thì reset shot về 0.
SHOT_RESET_RULES = {
    'default': {'reset_statuses': {'arrange', 'stop'}, 'idle_seconds': 480},
    '10号機': {'reset_statuses': {'arrange', 'stop'}, 'idle_seconds': 600},
    '28号機': {'reset_statuses': {'arrange', 'stop'}, 'idle_seconds': 480},
    # thêm máy khác ở đây
}

def get_shot_reset_rule(address):
    return SHOT_RESET_RULES.get(address, SHOT_RESET_RULES['default'])

