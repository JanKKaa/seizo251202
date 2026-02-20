from django.utils import timezone
from django.db import transaction
import re
from .models import Machine, MachineStatusEvent, MachineAlarmEvent, STATUS_CHOICES, Esp32Device, Esp32StatusLog

STATUS_LABEL_MAP = dict(STATUS_CHOICES)

def log_status_change(machine: Machine, new_code: str):
    if machine.status != new_code:
        MachineStatusEvent.objects.create(
            machine=machine,
            status_code=new_code,
            status_jp=STATUS_LABEL_MAP.get(new_code,"不明")
        )
        machine.status = new_code
        machine.save(update_fields=["status","last_update"])

@transaction.atomic
def log_alarm(machine: Machine, alarm_code: str, alarm_name: str, message: str = ""):
    today = timezone.localdate()
    last_same = (
        MachineAlarmEvent.objects
        .filter(machine=machine, alarm_code=alarm_code, created_at__date=today)
        .order_by("-id")
        .first()
    )
    if last_same and last_same.is_active and (timezone.now() - last_same.created_at).total_seconds() < 15:
        last_same.occurrence_count += 1
        last_same.save(update_fields=["occurrence_count"])
        return last_same
    return MachineAlarmEvent.objects.create(
        machine=machine,
        alarm_code=alarm_code,
        alarm_name=alarm_name,
        message=message
    )

def clear_alarm(machine: Machine, alarm_code: str | None):
    qs = MachineAlarmEvent.objects.filter(machine=machine, cleared_at__isnull=True)
    if alarm_code:
        qs = qs.filter(alarm_code=alarm_code)
    ev = qs.order_by("-id").first()
    if ev:
        ev.cleared_at = timezone.now()
        ev.save(update_fields=["cleared_at"])
    return ev

def save_esp32_status(device_id, pins, status_code, status_jp):
    device, _ = Esp32Device.objects.get_or_create(device_id=device_id)
    Esp32StatusLog.objects.create(
        device=device,
        pins=pins,
        status_code=status_code,
        status_jp=status_jp
    )
    device.name = f"{re.search(r'(\\d+)', device_id).group(1)}号機" if re.search(r'(\\d+)', device_id) else device_id
    device.save()

def get_latest_esp32_status():
    from .models import Esp32Device, Esp32StatusLog
    out = []
    for device in Esp32Device.objects.all():
        latest = Esp32StatusLog.objects.filter(device=device).order_by('-created_at').first()
        if latest:
            out.append({
                'address': device.name,
                'name': device.name,
                'runtime_status_code': latest.status_code,
                'runtime_status_jp': latest.status_jp,
                'alarm_active': latest.status_code == 'alarm',
                'shotno': '',
                'cycletime': '',
                'alarm_count': Esp32StatusLog.objects.filter(device=device, status_code='alarm').count(),
            })
        else:
            out.append({
                'address': device.name,
                'name': device.name,
                'runtime_status_code': 'offline',
                'runtime_status_jp': 'オフライン',
                'alarm_active': False,
                'shotno': '',
                'cycletime': '',
                'alarm_count': 0,
            })
    return out