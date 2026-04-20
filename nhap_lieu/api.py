from flask import Flask, jsonify, request
import csv
import ctypes
from ctypes import wintypes
import os
import re
import subprocess
import threading
import time

import pyautogui
import pyperclip
import requests
import urllib3
import unicodedata
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# ---- Runtime config (override via env) ----
# Backward-compatible:
# - INPUT_EXE_PATH / INPUT_WORKING_DIR / INPUT_PROCESS_NAME (legacy, ưu tiên cho 出庫)
# New split per mode:
# - INPUT_EXE_PATH_OUT / INPUT_EXE_PATH_IN
# - INPUT_WORKING_DIR_OUT / INPUT_WORKING_DIR_IN
# - INPUT_PROCESS_NAME_OUT / INPUT_PROCESS_NAME_IN
PATH_EXE_OUT = os.getenv(
    "INPUT_EXE_PATH_OUT",
    os.getenv("INPUT_EXE_PATH", r"\\Jimusyoserver\d\WINNC_V10\HAYASHITC\SK5030.EXE"),
)
PATH_EXE_IN = os.getenv(
    "INPUT_EXE_PATH_IN",
    r"\\Jimusyoserver\d\WINNC_V10\HAYASHITC\SK7010.EXE",
)
WORKING_DIR_OUT = os.getenv(
    "INPUT_WORKING_DIR_OUT",
    os.getenv("INPUT_WORKING_DIR", r"\\Jimusyoserver\d\WINNC_V10\HAYASHITC"),
)
WORKING_DIR_IN = os.getenv("INPUT_WORKING_DIR_IN", WORKING_DIR_OUT)
URL_DJANGO_CALLBACK = os.getenv(
    "DJANGO_CALLBACK_URL",
    "https://192.168.10.250/nhap_lieu/api/cap-nhat-ket-qua/",
)

# select area (screen coords)
SELECT_START_X = int(os.getenv("SELECT_START_X", "100"))
SELECT_START_Y = int(os.getenv("SELECT_START_Y", "100"))
SELECT_END_X = int(os.getenv("SELECT_END_X", "800"))
SELECT_END_Y = int(os.getenv("SELECT_END_Y", "600"))

APP_BOOT_WAIT = float(os.getenv("APP_BOOT_WAIT", "2.5"))
PRE_SELECT_WAIT = float(os.getenv("PRE_SELECT_WAIT", "0.3"))
CALLBACK_TIMEOUT = float(os.getenv("CALLBACK_TIMEOUT", "5"))
CALLBACK_RETRIES = int(os.getenv("CALLBACK_RETRIES", "2"))
CALLBACK_RETRY_BASE_DELAY = float(os.getenv("CALLBACK_RETRY_BASE_DELAY", "0.3"))
OCR_READ_RETRIES = int(os.getenv("OCR_READ_RETRIES", "2"))
OCR_RETRY_DELAY = float(os.getenv("OCR_RETRY_DELAY", "0.25"))
CALLBACK_CONNECT_TIMEOUT = float(os.getenv("CALLBACK_CONNECT_TIMEOUT", "5"))
CALLBACK_READ_TIMEOUT = float(os.getenv("CALLBACK_READ_TIMEOUT", "20"))
CALLBACK_VERIFY_SSL = os.getenv("CALLBACK_VERIFY_SSL", "0").strip() in {"1", "true", "True", "yes", "YES"}
PROCESS_KILL_NAME_OUT = os.getenv(
    "INPUT_PROCESS_NAME_OUT",
    os.getenv("INPUT_PROCESS_NAME", os.path.basename(PATH_EXE_OUT)),
)
PROCESS_KILL_NAME_IN = os.getenv("INPUT_PROCESS_NAME_IN", os.path.basename(PATH_EXE_IN))
FOCUS_RETRIES = int(os.getenv("FOCUS_RETRIES", "3"))
FOCUS_RETRY_DELAY = float(os.getenv("FOCUS_RETRY_DELAY", "0.12"))
AUTO_MAXIMIZE_WINDOW = os.getenv("AUTO_MAXIMIZE_WINDOW", "1").strip() in {"1", "true", "True", "yes", "YES"}
FOCUS_PREP_ESC_COUNT = int(os.getenv("FOCUS_PREP_ESC_COUNT", "1"))
FOCUS_PREP_USE_SHOW_DESKTOP = os.getenv("FOCUS_PREP_USE_SHOW_DESKTOP", "1").strip() in {"1", "true", "True", "yes", "YES"}
COPY_MOUSE_DOWN_WAIT = float(os.getenv("COPY_MOUSE_DOWN_WAIT", "0.08"))
COPY_DRAG_DURATION = float(os.getenv("COPY_DRAG_DURATION", "0.22"))
COPY_MOUSE_UP_WAIT = float(os.getenv("COPY_MOUSE_UP_WAIT", "0.08"))
COPY_AFTER_COPY_WAIT = float(os.getenv("COPY_AFTER_COPY_WAIT", "0.12"))

if not CALLBACK_VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

pyautogui.FAILSAFE = True
JOB_LOCK = threading.Lock()

# Session riêng cho callback để ổn định kết nối khi chạy liên tục.
CALLBACK_SESSION = requests.Session()
CALLBACK_ADAPTER = HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=Retry(total=0),
)
CALLBACK_SESSION.mount("http://", CALLBACK_ADAPTER)
CALLBACK_SESSION.mount("https://", CALLBACK_ADAPTER)


def _to_ascii_digits(text: str) -> str:
    if not text:
        return ""
    # NFKC để đổi số full-width (０１２３...) về ASCII
    return unicodedata.normalize("NFKC", text)


def extract_invoice_number(full_text: str) -> str:
    text = _to_ascii_digits(full_text or "")
    if not text:
        return "---"

    # 1) Ưu tiên các pattern có ngữ nghĩa "mã quản lý / số đăng ký"
    strong_patterns = [
        r"(?:管理番号|登録番号|伝票番号|処理番号|No\.?|NO\.?|番号)\s*[:：]?\s*([0-9]{4,10})",
        r"([0-9]{4,10})\s*(?:に登録|を登録|登録|完了)",
    ]
    for pattern in strong_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1)

    # 2) Fallback: lấy cụm số cuối cùng 4-10 chữ số (thường là mã vừa sinh mới nhất)
    candidates = re.findall(r"([0-9]{4,10})", text)
    if candidates:
        return candidates[-1]

    return "---"


def extract_hinmei_name(full_text: str) -> str:
    text = _to_ascii_digits(full_text or "")
    if not text:
        return ""
    # Ưu tiên mẫu: 品名: XXXX hoặc 品名 XXXX (lấy đến hết dòng)
    m = re.search(r"品名\s*[:：]?\s*([^\r\n]+)", text)
    if m:
        return (m.group(1) or "").strip()
    return ""


def press_or_type(item: str):
    if item == "ENTER":
        pyautogui.press("enter")
    elif item == "TAB":
        pyautogui.press("tab")
    elif item == "DELETE":
        pyautogui.press("delete")
    elif item == "LEFT":
        pyautogui.press("left")
    elif item == "RIGHT":
        pyautogui.press("right")
    elif item == "UP":
        pyautogui.press("up")
    elif item == "DOWN":
        pyautogui.press("down")
    elif item in {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"}:
        pyautogui.press(item.lower())
    else:
        pyperclip.copy(item)
        pyautogui.hotkey("ctrl", "v")


def normalize_kg_value(raw: str) -> str:
    value = (raw or "").strip().replace(",", ".")
    if not value:
        return ""
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?|\.[0-9]+", value):
        return ""
    return value


def normalize_material_code(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    # Normalize full-width/half-width and unify dash variants to ASCII '-'
    value = unicodedata.normalize("NFKC", value)
    value = (
        value.replace("ー", "-")
        .replace("－", "-")
        .replace("―", "-")
        .replace("‐", "-")
        .replace("‑", "-")
        .replace("‒", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("―", "-")
    )
    return value


def normalize_mode_value(raw: str) -> str:
    value = (raw or "").strip()
    if value in {"1", "2"}:
        return value
    return ""


def today_yymmdd() -> str:
    return time.strftime("%y%m%d", time.localtime())


def normalize_date_yymmdd(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    digits = re.sub(r"[^0-9]", "", value)
    if re.fullmatch(r"[0-9]{6}", digits):
        return digits
    return ""


def normalize_order_no(raw: str) -> str:
    value = unicodedata.normalize("NFKC", (raw or "").strip())
    value = value.replace(" ", "")
    if re.fullmatch(r"[0-9]{4,12}-[1-3]", value):
        return value
    return ""


def resolve_target_app(mode_value: str):
    """Chọn app theo mode: 1=入庫(SK7010), 2=出庫(SK5030)."""
    normalized = normalize_mode_value(mode_value)
    if normalized == "1":
        return PATH_EXE_IN, WORKING_DIR_IN, PROCESS_KILL_NAME_IN
    return PATH_EXE_OUT, WORKING_DIR_OUT, PROCESS_KILL_NAME_OUT


def type_kg_keys(kg_value: str):
    """Nhập kg bằng từng phím số thay vì paste clipboard."""
    normalized = normalize_kg_value(kg_value)
    if not normalized:
        raise ValueError("kg_value không hợp lệ hoặc rỗng cho token KG_KEYS")
    pyautogui.write(normalized, interval=0.03)


def type_material_code_keys(material_code_value: str):
    """Nhập mã nguyên liệu bằng chuỗi phím."""
    normalized = normalize_material_code(material_code_value)
    if not normalized:
        raise ValueError("material_code_value rỗng cho token MATERIAL_CODE_KEYS")
    # Không dùng clipboard/paste để tránh app đích chặn Ctrl+V.
    # Ưu tiên phím cứng cho '-' (numpad subtract), fallback sang minus.
    for ch in normalized:
        if ch.isdigit():
            pyautogui.press(ch)
        elif "A" <= ch <= "Z" or "a" <= ch <= "z":
            pyautogui.press(ch.lower())
        elif ch == "-":
            try:
                pyautogui.press("subtract")
            except Exception:
                pyautogui.press("minus")
        else:
            pyautogui.write(ch, interval=0.01)
        time.sleep(0.02)


def type_product_code_keys(product_code_value: str):
    """Nhập mã sản phẩm bằng chuỗi phím (tương tự MATERIAL_CODE_KEYS)."""
    normalized = normalize_material_code(product_code_value)
    if not normalized:
        raise ValueError("product_code_value rỗng cho token PRODUCT_CODE_KEYS")
    # Gõ trực tiếp toàn chuỗi để đảm bảo ký tự '-' luôn đúng dạng 1701-01.
    pyautogui.write(normalized, interval=0.03)


def type_inout_mode_keys(mode_value: str):
    """Nhập chế độ 入/出庫: 1=入庫, 2=出庫."""
    normalized = normalize_mode_value(mode_value)
    if not normalized:
        raise ValueError("mode_value không hợp lệ cho token INOUT_MODE_KEYS (chỉ nhận 1 hoặc 2)")
    pyautogui.press(normalized)


def type_date_yymmdd_keys(date_value: str):
    """Nhập ngày theo dạng YYMMDD bằng phím cứng."""
    normalized = normalize_date_yymmdd(date_value)
    if not normalized:
        raise ValueError("date_yymmdd_value không hợp lệ cho token DATE_YYMMDD_KEYS")
    pyautogui.write(normalized, interval=0.03)


def type_order_no_keys(order_no_value: str):
    """
    Nhập 注文No. theo thao tác thực tế của app đích:
    - Gõ mã base (vd: 5044)
    - Nhấn RIGHT 3 lần
    - Gõ số thứ tự 1/2/3
    """
    normalized = normalize_order_no(order_no_value)
    if not normalized:
        raise ValueError("order_no_value không hợp lệ cho token ORDER_NO_KEYS")
    m = re.fullmatch(r"([0-9]{4,12})-([1-3])", normalized)
    if not m:
        raise ValueError("order_no_value không đúng định dạng base-suffix cho token ORDER_NO_KEYS")

    base_no, suffix_no = m.group(1), m.group(2)
    pyautogui.write(base_no, interval=0.03)
    pyautogui.press("right", presses=3, interval=0.03)
    pyautogui.write(suffix_no, interval=0.03)


def copy_selected_text() -> str:
    pyautogui.mouseDown(SELECT_START_X, SELECT_START_Y)
    time.sleep(max(0.0, COPY_MOUSE_DOWN_WAIT))
    pyautogui.moveTo(SELECT_END_X, SELECT_END_Y, duration=max(0.0, COPY_DRAG_DURATION))
    time.sleep(max(0.0, COPY_MOUSE_UP_WAIT))
    pyautogui.mouseUp()
    time.sleep(max(0.0, COPY_AFTER_COPY_WAIT))
    pyautogui.hotkey("ctrl", "c")
    time.sleep(max(0.0, COPY_AFTER_COPY_WAIT))
    return pyperclip.paste() or ""


def capture_final_text_and_code(retries: int = OCR_READ_RETRIES, retry_delay: float = OCR_RETRY_DELAY):
    """Đọc màn hình nhiều lần để lấy full_text cuối cùng và mã quản lý ổn định."""
    retries = max(1, int(retries or 1))
    retry_delay = max(0.0, float(retry_delay or 0))
    last_text = ""
    last_code = "---"

    for idx in range(retries):
        text = copy_selected_text().strip()
        code = extract_invoice_number(text)
        if text:
            last_text = text
        if code and code != "---":
            last_code = code
            return text or last_text, last_code
        last_code = code or "---"
        if idx < retries - 1:
            time.sleep(retry_delay)

    return last_text, last_code


def post_callback(payload: dict):
    last_error = None
    for i in range(CALLBACK_RETRIES):
        response = None
        try:
            response = CALLBACK_SESSION.post(
                URL_DJANGO_CALLBACK,
                json=payload,
                timeout=(CALLBACK_CONNECT_TIMEOUT, CALLBACK_READ_TIMEOUT),
                verify=CALLBACK_VERIFY_SSL,
                headers={"Connection": "close"},
            )
            if 200 <= response.status_code < 300:
                return True, response.status_code
            last_error = f"HTTP {response.status_code}: {response.text}"
        except Exception as exc:
            last_error = str(exc)
        finally:
            try:
                if response is not None:
                    response.close()
            except Exception:
                pass

        time.sleep(max(0.0, CALLBACK_RETRY_BASE_DELAY * (i + 1)))

    return False, last_error


def force_close_target_app(process=None, process_name: str = ""):
    """Đóng app đích chắc chắn, kể cả khi subprocess handle không trỏ đúng process UI."""
    try:
        if process and process.poll() is None:
            process.terminate()
            time.sleep(0.3)
            if process.poll() is None:
                process.kill()
    except Exception:
        pass

    # Fallback: kill theo tên tiến trình (ổn định hơn với app kiểu launcher).
    target_process_name = (process_name or "").strip()
    if not target_process_name:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", target_process_name],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        pass


def _find_pids_by_image_name(image_name: str):
    """Tìm PID theo tên exe (hỗ trợ app kiểu launcher)."""
    name = (image_name or "").strip()
    if not name:
        return []
    if not name.lower().endswith(".exe"):
        name = f"{name}.exe"

    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return []

    rows = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    pids = []
    for row in rows:
        if row.startswith("INFO:"):
            continue
        try:
            parsed = next(csv.reader([row]))
        except Exception:
            continue
        if len(parsed) < 2:
            continue
        try:
            pids.append(int(parsed[1]))
        except Exception:
            continue
    return pids


def _bring_window_to_front_by_pid(pid: int) -> bool:
    """Đưa cửa sổ top-level thuộc PID lên foreground (focus mạnh)."""
    if not pid:
        return False

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    target_hwnd = wintypes.HWND(0)
    best_title_len = ctypes.c_int(-1)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_windows_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True

        proc_id = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value != pid:
            return True

        title_len = int(user32.GetWindowTextLengthW(hwnd))
        if title_len > best_title_len.value:
            target_hwnd.value = int(hwnd)
            best_title_len.value = title_len
        return True

    try:
        user32.EnumWindows(enum_windows_proc, 0)
        if not target_hwnd.value:
            return False

        hwnd = target_hwnd
        SW_RESTORE = 9
        SW_MAXIMIZE = 3
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2

        user32.ShowWindow(hwnd, SW_RESTORE)
        if AUTO_MAXIMIZE_WINDOW:
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

        current_tid = kernel32.GetCurrentThreadId()
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        fg_hwnd = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

        attached1 = False
        attached2 = False
        try:
            if fg_tid and fg_tid != current_tid:
                attached1 = bool(user32.AttachThreadInput(current_tid, fg_tid, True))
            if target_tid and target_tid != current_tid:
                attached2 = bool(user32.AttachThreadInput(current_tid, target_tid, True))

            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached2:
                user32.AttachThreadInput(current_tid, target_tid, False)
            if attached1:
                user32.AttachThreadInput(current_tid, fg_tid, False)

        return bool(user32.GetForegroundWindow() == hwnd)
    except Exception:
        return False


def _get_foreground_pid() -> int:
    """Lấy PID của cửa sổ foreground hiện tại."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return 0
        proc_id = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        return int(proc_id.value or 0)
    except Exception:
        return 0


def _prepare_focus_surface(use_show_desktop: bool = True):
    """Giảm khả năng bị popup/notification giữ foreground."""
    try:
        for _ in range(max(0, FOCUS_PREP_ESC_COUNT)):
            pyautogui.press("esc")
            time.sleep(0.05)
    except Exception:
        pass

    if use_show_desktop and FOCUS_PREP_USE_SHOW_DESKTOP:
        try:
            pyautogui.hotkey("win", "d")
            time.sleep(0.2)
        except Exception:
            pass


def ensure_target_app_focus(process=None, process_name: str = "", preserve_state: bool = False) -> bool:
    """Buộc focus về app hệ thống; preserve_state=True thì không gửi ESC/Win+D."""
    pids = set()
    if process is not None:
        try:
            if process.poll() is None and process.pid:
                pids.add(int(process.pid))
        except Exception:
            pass

    for pid in _find_pids_by_image_name(process_name):
        pids.add(pid)

    if not pids:
        return False

    # Dọn foreground trước khi bắt đầu ép focus (tránh dùng khi cần giữ nguyên màn hình hiện tại).
    if not preserve_state:
        _prepare_focus_surface(use_show_desktop=True)

    for _ in range(max(1, FOCUS_RETRIES)):
        for pid in list(pids):
            if _bring_window_to_front_by_pid(pid):
                # Xác nhận foreground đã là app đích.
                if _get_foreground_pid() in pids:
                    return True
        # Nếu vẫn bị popup giữ foreground thì dọn lại rồi thử tiếp.
        if not preserve_state:
            _prepare_focus_surface(use_show_desktop=False)
        time.sleep(max(0.05, FOCUS_RETRY_DELAY))

    # Lần cuối: chấp nhận nếu foreground đã đúng PID.
    if _get_foreground_pid() in pids:
        return True

    return False


def build_callback_payload(
    *,
    job_id: str,
    ten_chuong_trinh: str,
    ip: str,
    status: str,
    ma_nhap_lieu: str = "",
    full_text: str = "",
    error: str = "",
):
    return {
        "job_id": job_id,
        "ma_job": job_id,  # backward-compatible alias
        "ten_chuong_trinh": ten_chuong_trinh or "",
        "ma_nhap_lieu": ma_nhap_lieu or "",
        "full_text": full_text or "",
        "ip": ip or "",
        "status": status,
        "error": error or "",
    }


def _send_input_impl(typing_only: bool = False):
    if not JOB_LOCK.acquire(blocking=False):
        return jsonify({"message": "BUSY", "status": "Đang bận xử lý job khác"}), 409

    process = None
    app_launched = False
    scan_started = False
    job_id = ""
    ten_chuong_trinh = ""
    target_process_name = ""
    typing_only = bool(typing_only)
    error_occurred = False
    mode_value = ""
    workstation_ip = request.host.split(":")[0]
    try:
        data = request.get_json(force=True) or {}
        quy_tac = data.get("quy_tac", [])
        kg_value = str(data.get("kg_value") or "").strip()
        material_code_value = str(data.get("material_code_value") or "").strip()
        product_code_value = str(data.get("product_code_value") or "").strip()
        mode_value = str(data.get("mode_value") or "").strip()
        lot_number_value = str(data.get("lot_number") or "").strip()
        date_yymmdd_value = str(data.get("date_yymmdd_value") or "").strip()
        order_no_value = str(data.get("order_no_value") or "").strip()
        hinmei_check_only = str(data.get("hinmei_check_only") or "").strip().lower() in {"1", "true", "yes"}
        delay = float(data.get("delay", 0.1))
        start_step = int(data.get("start_step") or 1)
        job_id = str(data.get("job_id") or data.get("ma_job") or "").strip()
        ten_chuong_trinh = str(data.get("ten_chuong_trinh") or "").strip()

        if not job_id:
            error_occurred = True
            return jsonify({"message": "Thiếu job_id", "status": "error"}), 400

        if not isinstance(quy_tac, list) or not quy_tac:
            error_occurred = True
            return jsonify({"message": "Không có dữ liệu để nhập"}), 400

        normalized_mode = normalize_mode_value(mode_value)
        if normalized_mode == "2" and not lot_number_value:
            error_occurred = True
            return jsonify({"message": "Xuất kho bắt buộc nhập Số lot (lot_number)"}), 400
        normalized_date = normalize_date_yymmdd(date_yymmdd_value)
        if normalized_mode == "1" and not normalized_date:
            normalized_date = today_yymmdd()
        normalized_order_no = normalize_order_no(order_no_value)
        if normalized_mode == "1" and not normalized_order_no:
            error_occurred = True
            return jsonify({"message": "Nhập kho bắt buộc nhập 注文No. dạng 5044-1/2/3"}), 400

        if not typing_only:
            target_exe, target_working_dir, target_process_name = resolve_target_app(mode_value)
            if not os.path.exists(target_exe):
                error_occurred = True
                return jsonify({"message": f"Không tìm thấy file tại {target_exe}"}), 500

            process = subprocess.Popen([target_exe], cwd=target_working_dir)
            app_launched = True
            time.sleep(APP_BOOT_WAIT)
            focused = ensure_target_app_focus(
                process,
                process_name=target_process_name,
                preserve_state=False,
            )
            if not focused:
                # Không click fallback để tránh chạm nhầm nút đóng app.
                time.sleep(0.05)

        # Đã tách app riêng cho 入庫/出庫, nên không cần gõ mode 1/2 trong app nữa.
        # mode_value chỉ dùng để chọn app cần mở (SK7010/SK5030).

        # start_step is 1-based index for quy_tac
        if start_step < 1:
            start_step = 1
        for raw in quy_tac[start_step - 1 :]:
            item = str(raw).strip()
            if not item:
                continue

            if item in {"CTRL+A", "CTRL+C"}:
                break

            if item == "KG_KEYS":
                type_kg_keys(kg_value)
                time.sleep(delay)
                continue
            if item in {"MATERIAL_CODE_KEYS", "MATERIAL CODE", "MATERIAL_CODE", "材料コード", "材料ｺｰﾄﾞ"}:
                type_material_code_keys(material_code_value)
                time.sleep(delay)
                continue
            if item in {"PRODUCT_CODE_KEYS", "PRODUCT CODE", "PRODUCT_CODE", "PRODUCTCODE", "製品コード", "製品ｺｰﾄﾞ"}:
                type_product_code_keys(product_code_value)
                time.sleep(delay)
                continue
            if item in {"INOUT_MODE_KEYS", "入/出庫"}:
                # Bỏ qua token mode để tránh nhập thừa 1/2 khi đã tách app theo luồng.
                continue
            if item in {"DATE_YYMMDD_KEYS", "YYMMDD_DATE_KEYS", "日付YYMMDD"}:
                type_date_yymmdd_keys(normalized_date)
                time.sleep(delay)
                continue
            if item in {"ORDER_NO_KEYS", "CHUMON_NO_KEYS", "注文NO_KEYS", "注文No._KEYS"}:
                type_order_no_keys(normalized_order_no)
                time.sleep(delay)
                continue
            if item in {"HINMEI_CHECK_KEYS", "HINMEI_KEYS", "品名"}:
                hinmei_full_text = copy_selected_text().strip()
                hinmei_text = extract_hinmei_name(hinmei_full_text)
                if hinmei_check_only:
                    return jsonify(
                        {
                            "message": "HINMEI_OK",
                            "status": "hinmei_checked",
                            "job_id": job_id,
                            "hinmei_text": hinmei_text,
                            "full_text": hinmei_full_text,
                            "callback_ok": False,
                            "callback_info": "hinmei_precheck",
                        }
                    )
                continue

            press_or_type(item)
            time.sleep(delay)

        time.sleep(PRE_SELECT_WAIT)
        scan_started = True
        full_text, ma_nhap_lieu = capture_final_text_and_code()

        if not full_text:
            err_msg = "Không đọc được full_text từ màn hình sau khi nhập liệu"
            payload_back = build_callback_payload(
                job_id=job_id,
                ten_chuong_trinh=ten_chuong_trinh,
                ip=workstation_ip,
                status="failed",
                error=err_msg,
            )
            post_callback(payload_back)
            error_occurred = True
            return jsonify(
                {
                    "message": err_msg,
                    "status": "failed",
                    "job_id": job_id,
                    "data_ocr": "---",
                    "full_text": "",
                    "callback_ok": False,
                    "callback_info": "no_full_text",
                }
            ), 500

        if ma_nhap_lieu == "---":
            err_msg = "Không lấy được mã đăng ký từ full_text cuối cùng"
            payload_back = build_callback_payload(
                job_id=job_id,
                ten_chuong_trinh=ten_chuong_trinh,
                ip=workstation_ip,
                status="failed",
                ma_nhap_lieu="---",
                full_text=full_text,
                error=err_msg,
            )
            ok, callback_info = post_callback(payload_back)
            error_occurred = True
            return jsonify(
                {
                    "message": err_msg,
                    "status": "failed",
                    "job_id": job_id,
                    "data_ocr": "---",
                    "full_text": full_text,
                    "callback_ok": ok,
                    "callback_info": callback_info,
                }
            ), 500

        payload_back = build_callback_payload(
            job_id=job_id,
            ten_chuong_trinh=ten_chuong_trinh,
            ip=workstation_ip,
            status="success",
            ma_nhap_lieu=ma_nhap_lieu,
            full_text=full_text,
        )
        ok, callback_info = post_callback(payload_back)

        return jsonify(
            {
                "message": "OK",
                "status": "success",
                "job_id": job_id,
                "data_ocr": ma_nhap_lieu,
                "full_text": full_text,
                "callback_ok": ok,
                "callback_info": callback_info,
            }
        )
    except Exception as exc:
        err_msg = str(exc)
        if job_id:
            payload_back = build_callback_payload(
                job_id=job_id,
                ten_chuong_trinh=ten_chuong_trinh,
                ip=workstation_ip,
                status="failed",
                error=err_msg,
            )
            post_callback(payload_back)
        error_occurred = True
        return jsonify({"message": f"Lỗi: {err_msg}", "status": "failed", "job_id": job_id}), 500
    finally:
        if error_occurred:
            # On any error, close workstation app to allow safe restart.
            if not target_process_name and mode_value:
                try:
                    _, _, target_process_name = resolve_target_app(mode_value)
                except Exception:
                    target_process_name = ""
            force_close_target_app(process, process_name=target_process_name)
        # Chỉ đóng app sau khi đã vào bước quét/copy.
        # Nếu lỗi xảy ra sớm trước bước này thì giữ app mở để tránh "tắt ngang".
        if app_launched and scan_started and not typing_only:
            force_close_target_app(process, process_name=target_process_name)
        # Với typing_only, vẫn đóng app khi đã hoàn tất quét/copy thành công.
        if typing_only and scan_started and not error_occurred:
            if not target_process_name and mode_value:
                try:
                    _, _, target_process_name = resolve_target_app(mode_value)
                except Exception:
                    target_process_name = ""
            force_close_target_app(process, process_name=target_process_name)
        JOB_LOCK.release()


@app.route("/send_input", methods=["POST"])
def send_input():
    return _send_input_impl(typing_only=False)


@app.route("/send_input_typing_only", methods=["POST"])
def send_input_typing_only():
    """
    Luồng nhập liệu tối giản: chỉ gõ phím theo quy tắc + quét/copy + callback.
    Không mở app, không focus, không đóng app.
    """
    return _send_input_impl(typing_only=True)


@app.route("/close_app", methods=["POST"])
def close_app():
    data = request.get_json(silent=True) or {}
    mode_value = str(data.get("mode_value") or "").strip()
    _, _, target_process_name = resolve_target_app(mode_value)
    force_close_target_app(process=None, process_name=target_process_name)
    return jsonify(
        {
            "status": "closed",
            "mode_value": normalize_mode_value(mode_value) or mode_value,
            "process_name": target_process_name,
        }
    )


if __name__ == "__main__":
    print("=== Workstation Input API ===")
    print("Flow: open app -> click focus -> input -> select/copy -> callback Django")
    app.run(host="0.0.0.0", port=5000)
