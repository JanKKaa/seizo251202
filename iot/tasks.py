from celery import shared_task
from django.core.cache import cache
import requests
import xml.etree.ElementTree as ET
from .views import xml_to_dict
from .models import MoldLifetime, ProductionPlan
from django.utils import timezone
import json

@shared_task
def fetch_device_data():
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
                merged = {**info, **live_info}
                shotno = int(merged.get('shotno', 0) or 0)
                merged['shotno'] = shotno
                machines.append(merged)
    except Exception:
        machines = []
    # Lưu vào cache
    cache.set('iot_device_machines', machines, 60)  # cache 60s