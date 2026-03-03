from flask import Flask, jsonify, request
import os
import re
import subprocess
import threading
import time

import pyautogui
import pyperclip
import requests

app = Flask(__name__)

# ---- Runtime config (override via env) ----
PATH_EXE = os.getenv("INPUT_EXE_PATH", r"\\Jimusyoserver\d\WINNC_V10\HAYASHITC\SK5030.EXE")
WORKING_DIR = os.getenv("INPUT_WORKING_DIR", r"\\Jimusyoserver\d\WINNC_V10\HAYASHITC")
URL_DJANGO_CALLBACK = os.getenv(
    "DJANGO_CALLBACK_URL",
    "http://192.168.10.71:8000/nhap-lieu/api/cap-nhat-ket-qua/",
)

# select area (screen coords)
SELECT_START_X = int(os.getenv("SELECT_START_X", "100"))
SELECT_START_Y = int(os.getenv("SELECT_START_Y", "100"))
SELECT_END_X = int(os.getenv("SELECT_END_X", "800"))
SELECT_END_Y = int(os.getenv("SELECT_END_Y", "600"))

APP_BOOT_WAIT = float(os.getenv("APP_BOOT_WAIT", "12"))
PRE_SELECT_WAIT = float(os.getenv("PRE_SELECT_WAIT", "2"))
CALLBACK_TIMEOUT = float(os.getenv("CALLBACK_TIMEOUT", "5"))
CALLBACK_RETRIES = int(os.getenv("CALLBACK_RETRIES", "3"))

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
            response = requests.post(URL_DJANGO_CALLBACK, json=payload, timeout=CALLBACK_TIMEOUT)
            if 200 <= response.status_code < 300:
                return True, response.status_code
            last_error = f"HTTP {response.status_code}: {response.text}"
        except Exception as exc:
            last_error = str(exc)

        time.sleep(1 + i)

    return False, last_error


@app.route("/send_input", methods=["POST"])
def send_input():
    if not JOB_LOCK.acquire(blocking=False):
        return jsonify({"message": "BUSY", "status": "Đang bận xử lý job khác"}), 409

    process = None
    try:
        data = request.get_json(force=True) or {}
        quy_tac = data.get("quy_tac", [])
        delay = float(data.get("delay", 0.1))

        if not isinstance(quy_tac, list) or not quy_tac:
            return jsonify({"message": "Không có dữ liệu để nhập"}), 400

        if not os.path.exists(PATH_EXE):
            return jsonify({"message": f"Không tìm thấy file tại {PATH_EXE}"}), 500

        process = subprocess.Popen([PATH_EXE], cwd=WORKING_DIR)
        time.sleep(APP_BOOT_WAIT)

        for raw in quy_tac:
            item = str(raw).strip()
            if not item:
                continue

            if item in {"CTRL+A", "CTRL+C"}:
                break

            press_or_type(item)
            time.sleep(delay)

        time.sleep(PRE_SELECT_WAIT)
        full_text = copy_selected_text().strip()
        ma_nhap_lieu = extract_invoice_number(full_text)

        payload_back = {
            "ma_nhap_lieu": ma_nhap_lieu,
            "full_text": full_text,
            "ip": request.host.split(":")[0],
            "status": "Hoàn thành",
        }
        ok, callback_info = post_callback(payload_back)

        return jsonify(
            {
                "message": "OK",
                "status": "Thành công",
                "data_ocr": ma_nhap_lieu,
                "callback_ok": ok,
                "callback_info": callback_info,
            }
        )
    except Exception as exc:
        return jsonify({"message": f"Lỗi: {exc}"}), 500
    finally:
        try:
            if process and process.poll() is None:
                process.terminate()
                time.sleep(1)
                if process.poll() is None:
                    process.kill()
        except Exception:
            pass
        JOB_LOCK.release()


if __name__ == "__main__":
    print("=== Workstation Input API ===")
    print("Flow: open app -> input -> select/copy -> callback Django")
    app.run(host="0.0.0.0", port=5000)
