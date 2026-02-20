from flask import Flask, request, jsonify
import pyautogui
import pyperclip
import time
import traceback   # Thêm dòng này

app = Flask(__name__)

@app.route('/send_input', methods=['POST'])
def send_input():
    try:
        print("Đã nhận request")  # Thêm log này để xác nhận nhận request
        data = request.get_json(force=True)
        print("Nhận được:", data)
        quy_tac = data.get('quy_tac')
        print("Nhận quy_tac:", quy_tac)
        if not quy_tac or not isinstance(quy_tac, list):
            return jsonify({"message": "Không có dữ liệu để nhập", "clipboard": ""}), 400

        delay = float(data.get('delay', 0.5))  # Mặc định 0.5 giây nếu không có
        clipboard_content = ""
        for item in quy_tac:
            if not item or not str(item).strip():
                continue
            item_str = str(item).strip()
            if item_str == "DELAY_5S":
                time.sleep(5)
                continue
            if item_str == "CTRL+A":
                pyautogui.hotkey('ctrl', 'a')
            elif item_str == "CTRL+C":
                pyautogui.hotkey('ctrl', 'c')
            elif item_str == "ENTER":
                pyautogui.press('enter')
            elif item_str == "TAB":
                pyautogui.press('tab')
            elif item_str == "DELETE":
                pyautogui.press('delete')
            elif item_str == "LEFT":
                pyautogui.press('left')
            elif item_str == "RIGHT":
                pyautogui.press('right')
            elif item_str == "UP":
                pyautogui.press('up')
            elif item_str == "DOWN":
                pyautogui.press('down')
            elif item_str in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]:
                pyautogui.press(item_str.lower())
            elif item_str == "Data":
                try:
                    clipboard_content = pyperclip.paste()
                except Exception as e:
                    clipboard_content = ""
            else:
                try:
                    pyperclip.copy(item_str)
                    pyautogui.hotkey('ctrl', 'v')
                except Exception as e:
                    print("Clipboard or paste error:", e)
            time.sleep(delay)  # Thêm dòng này để chờ giữa các lệnh
        return jsonify({"message": "OK", "clipboard": clipboard_content})
    except Exception as e:
        print("Lỗi xử lý:", e)
        traceback.print_exc()  # In toàn bộ stack trace lỗi ra màn hình
        return jsonify({"message": f"Lỗi xử lý: {e}", "clipboard": ""}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)