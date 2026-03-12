from flask import Flask, jsonify, request
import os
import re
import subprocess
import threading
import time

import pyautogui
import pyperclip
import requests
import urllib3

app = Flask(__name__)

# ---- Runtime config (override via env) ----
PATH_EXE = os.getenv("INPUT_EXE_PATH", r"\\Jimusyoserver\d\WINNC_V10\HAYASHITC\SK5030.EXE")
WORKING_DIR = os.getenv("INPUT_WORKING_DIR", r"\\Jimusyoserver\d\WINNC_V10\HAYASHITC")
URL_DJANGO_CALLBACK = os.getenv(
    "DJANGO_CALLBACK_URL",
    "https://192.168.10.250/nhap_lieu/api/cap-nhat-ket-qua/",
)

# select area (screen coords)
SELECT_START_X = int(os.getenv("SELECT_START_X", "100"))
SELECT_START_Y = int(os.getenv("SELECT_START_Y", "100"))
SELECT_END_X = int(os.getenv("SELECT_END_X", "800"))
SELECT_END_Y = int(os.getenv("SELECT_END_Y", "600"))

APP_BOOT_WAIT = float(os.getenv("APP_BOOT_WAIT", "5"))
PRE_SELECT_WAIT = float(os.getenv("PRE_SELECT_WAIT", "1"))
CALLBACK_TIMEOUT = float(os.getenv("CALLBACK_TIMEOUT", "5"))
CALLBACK_RETRIES = int(os.getenv("CALLBACK_RETRIES", "3"))
CALLBACK_VERIFY_SSL = os.getenv("CALLBACK_VERIFY_SSL", "0").strip() in {"1", "true", "True", "yes", "YES"}
PROCESS_KILL_NAME = os.getenv("INPUT_PROCESS_NAME", os.path.basename(PATH_EXE))

if not CALLBACK_VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

pyautogui.FAILSAFE = True
JOB_LOCK = threading.Lock()


def extract_invoice_number(full_text: str) -> str:
    match1 = re.search(r"(\d{5,6})\s*に登録", full_text)
    if match1:
        return match1.group(1)

    match2 = re.search(r"(\d{5,6})", full_text)
    if match2:
        return match2.group(1)

    return "---"


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


def type_kg_keys(kg_value: str):
    """Nhập kg bằng từng phím số thay vì paste clipboard."""
    normalized = normalize_kg_value(kg_value)
    if not normalized:
        raise ValueError("kg_value không hợp lệ hoặc rỗng cho token KG_KEYS")
    pyautogui.write(normalized, interval=0.03)


def copy_selected_text() -> str:
    pyautogui.mouseDown(SELECT_START_X, SELECT_START_Y)
    time.sleep(0.2)
    pyautogui.moveTo(SELECT_END_X, SELECT_END_Y, duration=0.5)
    time.sleep(0.2)
    pyautogui.mouseUp()
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.3)
    return pyperclip.paste() or ""


def post_callback(payload: dict):
    last_error = None
    for i in range(CALLBACK_RETRIES):
        try:
            response = requests.post(
                URL_DJANGO_CALLBACK,
                json=payload,
                timeout=CALLBACK_TIMEOUT,
                verify=CALLBACK_VERIFY_SSL,
            )
            if 200 <= response.status_code < 300:
                return True, response.status_code
            last_error = f"HTTP {response.status_code}: {response.text}"
        except Exception as exc:
            last_error = str(exc)

        time.sleep(1 + i)

    return False, last_error


def force_close_target_app(process=None):
    """Đóng app đích chắc chắn, kể cả khi subprocess handle không trỏ đúng process UI."""
    try:
        if process and process.poll() is None:
            process.terminate()
            time.sleep(1)
            if process.poll() is None:
                process.kill()
    except Exception:
        pass

    # Fallback: kill theo tên tiến trình (ổn định hơn với app kiểu launcher).
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", PROCESS_KILL_NAME],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        pass


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


@app.route("/send_input", methods=["POST"])
def send_input():
    if not JOB_LOCK.acquire(blocking=False):
        return jsonify({"message": "BUSY", "status": "Đang bận xử lý job khác"}), 409

    process = None
    job_id = ""
    ten_chuong_trinh = ""
    workstation_ip = request.host.split(":")[0]
    try:
        data = request.get_json(force=True) or {}
        quy_tac = data.get("quy_tac", [])
        kg_value = str(data.get("kg_value") or "").strip()
        delay = float(data.get("delay", 0.1))
        job_id = str(data.get("job_id") or data.get("ma_job") or "").strip()
        ten_chuong_trinh = str(data.get("ten_chuong_trinh") or "").strip()

        if not job_id:
            return jsonify({"message": "Thiếu job_id", "status": "error"}), 400

        if not isinstance(quy_tac, list) or not quy_tac:
            return jsonify({"message": "Không có dữ liệu để nhập"}), 400

        if not os.path.exists(PATH_EXE):
            return jsonify({"message": f"Không tìm thấy file tại {PATH_EXE}"}), 500

        process = subprocess.Popen([PATH_EXE], cwd=WORKING_DIR)
        time.sleep(APP_BOOT_WAIT)

        # CLICK vào giữa màn hình để đảm bảo app đích nhận focus trước khi gõ phím
        screen_w, screen_h = pyautogui.size()
        pyautogui.click(screen_w // 2, screen_h // 2)

        for raw in quy_tac:
            item = str(raw).strip()
            if not item:
                continue

            if item in {"CTRL+A", "CTRL+C"}:
                break

            if item == "KG_KEYS":
                type_kg_keys(kg_value)
                time.sleep(delay)
                continue

            press_or_type(item)
            time.sleep(delay)

        time.sleep(PRE_SELECT_WAIT)
        full_text = copy_selected_text().strip()
        ma_nhap_lieu = extract_invoice_number(full_text)

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
        return jsonify({"message": f"Lỗi: {err_msg}", "status": "failed", "job_id": job_id}), 500
    finally:
        force_close_target_app(process)
        JOB_LOCK.release()


if __name__ == "__main__":
    print("=== Workstation Input API ===")
    print("Flow: open app -> click focus -> input -> select/copy -> callback Django")
    app.run(host="0.0.0.0", port=5000)
