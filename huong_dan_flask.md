# HƯỚNG DẪN CÀI ĐẶT VÀ CHẠY FLASK SERVER NHẬN LỆNH NHẬP LIỆU TRÊN MÁY 192.168.0.24

## 1. Cài đặt Python

- Tải Python tại: https://www.python.org/downloads/
- Cài đặt và chọn **Add Python to PATH** khi cài.

## 2. Cài đặt các thư viện cần thiết

Mở Command Prompt (cmd) và chạy:

```sh
pip install flask pyautogui
```

## 3. Tạo file Flask server

- Tạo file mới tên `auto_input_api.py` (hoặc dùng file đã có).
- Nội dung mẫu:

```python
from flask import Flask, request
import pyautogui

app = Flask(__name__)

@app.route('/send_input', methods=['POST'])
def send_input():
    data = request.json.get('data')
    action = request.json.get('action', 'enter')
    pyautogui.write(data, interval=0.1)
    if action == 'enter':
        pyautogui.press('enter')
    elif action == 'tab':
        pyautogui.press('tab')
    return {"message": "Đã nhập dữ liệu"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

## 4. Chạy Flask server

Mở Command Prompt tại thư mục chứa file `auto_input_api.py` và chạy:

```sh
py auto_input_api.py
```
hoặc
```sh
py auto_input_api.py
```

Nếu dùng Python 3, có thể dùng:

```sh
python3 auto_input_api.py
```

## 5. Mở cổng 5000 trên firewall (nếu cần)

- Vào **Windows Defender Firewall** > Advanced settings > Inbound Rules > New Rule...
- Chọn **Port**, nhập `5000`, cho phép kết nối.

## 6. Thiết lập tự động chạy Flask server khi khởi động Windows

### Cách 1: Thêm vào thư mục Startup

1. Tạo file `run_flask.bat` với nội dung:
    ```bat
    cd /d C:\seizo0 250425AA\trang_chu
    py auto_input_api.py
    ```
    (Thay đường dẫn cho đúng thư mục chứa file .py)

2. Nhấn `Windows + R`, nhập `shell:startup` rồi Enter.

3. Copy file `run_flask.bat` (hoặc shortcut của nó) vào thư mục này.

### Cách 2: Dùng Task Scheduler

1. Mở **Task Scheduler** (Trình lập lịch tác vụ).
2. Chọn **Create Task**.
3. Tab **General**: Đặt tên, chọn "Run whether user is logged on or not".
4. Tab **Actions**:  
   - Action: Start a program  
   - Program/script: `py`  
   - Add arguments: `auto_input_api.py`  
   - Start in: `C:\seizo0 250425AA\trang_chu`
5. Tab **Triggers**:  
   - New...  
   - Begin the task: At startup
6. Nhấn OK, nhập mật khẩu nếu được hỏi.

## 7. Kiểm tra hoạt động

- Đảm bảo máy khác trong mạng LAN có thể truy cập:  
  `http://192.168.0.24:5000/send_input`
- Khi Django gửi lệnh, máy sẽ tự động nhập dữ liệu.

---

**Lưu ý:**  
- Luôn chạy Flask server trước khi gửi lệnh từ Django, hoặc thiết lập tự động chạy như hướng dẫn trên.
- Không cần tổ hợp phím Ctrl + Shift + G (đã bỏ chức năng này).

git remote add origin https://github.com/JanKKaa/seizo0-250521A.git