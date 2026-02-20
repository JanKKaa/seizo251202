from django.http import JsonResponse
from django.utils import timezone
from .models import Machine, MachineStatusEvent
from .snapshot_service import fetch_runtime_index

def oee_today(request):
    today = timezone.localdate()
    machines = Machine.objects.all()
    # Lấy runtime snapshot (danh sách dict, mỗi dict có address và cycletime)
    runtime_map = {m['address']: m for m in fetch_runtime_index() if m.get('address')}
    out = []
    for m in machines:
        # Lấy cycle time từ snapshot, nếu không có thì mặc định 1
        cycle_time = 1
        rt = runtime_map.get(m.address)
        if rt and rt.get('cycletime'):
            try:
                cycle_time = float(rt['cycletime'])
            except Exception:
                cycle_time = 1
        # Lấy các event trạng thái của máy trong ngày
        status_events = MachineStatusEvent.objects.filter(
            machine=m, created_at__date=today
        ).order_by('created_at')
        total_prod = 0
        total_stop = 0
        total_alarm = 0
        prev_time = None
        prev_status = None
        for ev in status_events:
            if prev_time and prev_status:
                delta = (ev.created_at - prev_time).total_seconds()
                if prev_status == 'production':
                    total_prod += delta
                elif prev_status == 'stop':
                    total_stop += delta
                elif prev_status == 'alarm':
                    total_alarm += delta
            prev_time = ev.created_at
            prev_status = ev.status_code
        planned_time = 28800  # 8h
        # Sản lượng thực tế (shot)
        shot_start = status_events.first().machine.shot_total if status_events else 0
        shot_end = status_events.last().machine.shot_total if status_events else 0
        actual_shot = max(shot_end - shot_start, 0)
        availability = total_prod / planned_time if planned_time else 0
        performance = (actual_shot * cycle_time) / total_prod if total_prod else 0
        quality = 1.0  # Nếu chưa có NG, mặc định 100%
        oee = availability * performance * quality * 100
        # Thêm vào dict trả về để debug
        out.append({
            "name": m.name,
            "availability": round(availability * 100, 1),
            "performance": round(performance * 100, 1),
            "quality": round(quality * 100, 1),
            "oee": round(oee, 1),
            "event_count": status_events.count(),
            "shot_start": shot_start,
            "shot_end": shot_end,
            "total_prod": total_prod,
        })
    return JsonResponse({"oee": out})