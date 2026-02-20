import requests
import xml.etree.ElementTree as ET
import csv
import io
import json
import os

NET100_MACHINE_URL = 'http://192.168.10.220/net100/machine'
NET100_LIVE_URL = 'http://192.168.10.220/net100/livelist'
AUTH = ('giang', 'ht798701')

STATUS_CODE_MAP = {
    'production': ('production', '生産中'),
    '生産中': ('production', '生産中'),
    'arrange': ('arrange', '段取り'),
    'setup': ('arrange', '段取り'),
    'standby': ('arrange', '段取り'),
    '段取り': ('arrange', '段取り'),
    'stop': ('stop', '停止'),
    'down': ('stop', '停止'),
    '停止': ('stop', '停止'),
    'offline': ('offline', 'オフライン'),
    'alarm': ('alarm', 'アラーム'),
    'アラーム': ('alarm', 'アラーム'),
}

def normalize_ip(addr: str) -> str:
    return (addr or '').strip()

def _xml_to_dict(el):
    d = {}
    for c in el:
        tag = c.tag
        if tag.startswith('{'):
            tag = tag.split('}', 1)[1]
        d[tag] = c.text
    return d

def _map_status(raw: str, offline: bool):
    if offline:
        return 'offline', 'オフライン'
    r = (raw or '').strip()
    return STATUS_CODE_MAP.get(r, ('unknown', '不明'))

def fetch_latest_alarm_status(address):
    url = f"http://192.168.10.220/net100/machine/{address}/log/alarm"
    try:
        res = requests.get(url, auth=AUTH, timeout=5)
        if res.status_code != 200 or not res.content:
            return False, '', '', ''
        content = res.content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            alarm_code = str(row.get('Alarm Code', '')).strip()
            alarm_name = str(row.get('Alarm Name', '')).strip()
            alarm_time = str(row.get('Alarm Date Time', '')).strip()
            # Chỉ lấy dòng có mã lỗi khác 0 và tên lỗi khác "Alarm reset"
            if alarm_code and alarm_code != '0' and alarm_name.lower() != 'alarm reset':
                return True, alarm_code, alarm_name, alarm_time
        return False, '', '', ''
    except Exception:
        return False, '', '', ''

def fetch_runtime_index():
    """
    Lấy danh sách máy trực tiếp từ NET100.
    Nếu không kết nối được, trả về [] và in log lỗi.
    """
    machines = []
    try:
        resp = requests.get(NET100_MACHINE_URL, auth=AUTH, timeout=3)
        rm = requests.get(NET100_MACHINE_URL, auth=AUTH, timeout=5)
        rl = requests.get(NET100_LIVE_URL, auth=AUTH, timeout=5)
        if rm.status_code != 200 or rl.status_code != 200:
            print("NET100 API trả về mã lỗi:", rm.status_code, rl.status_code)
            return []
        ns = {'ns': 'http://www.jsw.co.jp/net100/2.0'}
        root_m = ET.fromstring(rm.content)
        root_l = ET.fromstring(rl.content)

        live_dict = {}
        for live in root_l.findall('.//ns:live', ns):
            info = _xml_to_dict(live)
            addr = normalize_ip(info.get('address', ''))
            if not addr:
                continue
            if info.get('lastshotinfo'):
                parts = info['lastshotinfo'].split(',')
                if len(parts) > 4:
                    info['cycletime'] = parts[4].replace('"', '').strip()
            try:
                info['shotno'] = int(info.get('shotno', '0') or 0)
            except:
                info['shotno'] = 0
            live_dict[addr] = info

        for entry in root_m.findall('.//ns:listentry', ns):
            info = _xml_to_dict(entry)
            addr = normalize_ip(info.get('address', ''))
            live_info = live_dict.get(addr, {})
            merged = {**info, **live_info}
            # Kiểm tra trường alarm trong live_info
            alarm_flag = str(live_info.get('alarm', '')).lower() == 'true'
            if alarm_flag:
                code = 'alarm'
                jp = 'アラーム'
            else:
                raw_status = merged.get('status', '')
                STATUS_CODE_MAP = {
                    'production': ('production', '生産中'),
                    'arrange': ('arrange', '段取り'),
                    'setup': ('arrange', '段取り'),
                    'standby': ('arrange', '段取り'),
                    'stop': ('stop', '停止'),
                    'down': ('stop', '停止'),
                    'offline': ('offline', 'オフライン'),
                    'alarm': ('alarm', 'アラーム'),
                }
                code, jp = STATUS_CODE_MAP.get(raw_status, ('unknown', '不明'))
            has_alarm, alarm_code, alarm_name, alarm_time = fetch_latest_alarm_status(addr)
            machines.append({
                'address': addr,
                'name': merged.get('name', '') or addr,
                'condname': merged.get('condname', ''),
                'shotno': merged.get('shotno', 0),
                'cycletime': merged.get('cycletime', ''),
                'runtime_status_code': code,
                'runtime_status_jp': jp,
                'alarm_active': alarm_flag,
                'latest_alarm': {
                    'alarm_code': alarm_code,
                    'alarm_name': alarm_name,
                    'alarm_time': alarm_time,
                } if has_alarm else None,
            })
        return machines
    except requests.exceptions.RequestException as e:
        print("Không thể kết nối tới NET100:", e)
        return []
    except Exception as e:
        print("Lỗi không xác định khi fetch_runtime_index:", e)
        return [{'address': None, 'runtime_status_code': 'offline', 'runtime_status_jp': 'NET100未接続', 'note': 'Không có tín hiệu từ NET100'}]

def fetch_log_types(address):
    url = f"http://192.168.10.220/net100/machine/{address}/log"
    try:
        res = requests.get(url, auth=AUTH, timeout=5)
        if res.status_code != 200 or not res.content:
            return []
        try:
            root = ET.fromstring(res.content)
            log_types = []
            for log in root:
                tag = log.tag
                if tag.startswith('{'):
                    tag = tag.split('}', 1)[1]
                log_types.append(tag)
            return log_types
        except Exception:
            # Nếu trả về HTML hoặc text, trả về nội dung để debug
            return [res.content.decode('utf-8')]
    except Exception:
        return []

ESP32_STATE_FILE = 'esp32_prod_state.json'
ESP32_PRODUCTION_STATE = {}

def load_esp32_state():
    global ESP32_PRODUCTION_STATE
    if os.path.exists(ESP32_STATE_FILE):
        try:
            with open(ESP32_STATE_FILE, 'r', encoding='utf-8') as f:
                ESP32_PRODUCTION_STATE = json.load(f)
        except Exception:
            ESP32_PRODUCTION_STATE = {}

def save_esp32_state():
    try:
        with open(ESP32_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(ESP32_PRODUCTION_STATE, f)
    except Exception:
        pass

# Gọi khi khởi động
load_esp32_state()

ESP32_PRODUCTION_FLAG = {}

def fetch_esp32_status_processed():
    ESP32_API_URL = 'http://192.168.10.250:9000/esp32/api/button_status/'
    try:
        resp = requests.get(ESP32_API_URL, timeout=3)
        data = resp.json()
        devices = data.get('devices', [])
        out = []
        for d in devices:
            pins = d.get('pins', {})
            import re
            m = re.search(r'(\d+)', d.get('device_id', ''))
            num = m.group(1) if m else None
            if num:
                name = f"{num}号機"
            else:
                name = d.get('device_id', '')

            if pins.get('gpio0', 0) == 1:
                code, jp = 'alarm', 'アラーム'
            elif pins.get('gpio2', 0) == 1:
                code, jp = 'production', '生産中'
            elif pins.get('gpio5', 0) == 1 and pins.get('gpio2', 0) == 0 and pins.get('gpio0', 0) == 0:
                code, jp = 'arrange', '段取り'
            else:
                code, jp = 'stop', '停止'

            out.append({
                'address': name,
                'name': name,
                'condname': '',
                'runtime_status_code': code,
                'runtime_status_jp': jp,
                'alarm_active': (code == 'alarm'),
                'shotno': '',
                'cycletime': '',
                'alarm_count': 0,
                'latest_alarm': None,
            })
        return out
    except Exception as e:
        print("ESP32 API error:", e)
        return []

