# Hướng dẫn thiết lập và sử dụng dự án Django (Windows)

## 1. Tạo môi trường ảo

```powershell
python -m venv .venv
```

### Kích hoạt môi trường ảo:
- PowerShell:
    ```powershell
    .\.venv\Scripts\Activate.ps1
    ```
- Command Prompt:
    ```cmd
    .\.venv\Scripts\activate
    ```
cd trang_chu

## 2. Cài đặt thư viện

```powershell
pip install django
pip install -r requirements.txt
```

## 3. Tạo và di chuyển vào dự án

```powershell

cd trang_chu
```

## 4. Chạy migrate và server

```powershell
python manage.py migrate
python manage.py runserver
python manage.py runserver_plus 192.168.0.24:8000 --cert-file cert.pem --key-file key.pem
```

## 5. Một số lệnh thường dùng

- Tạo app mới:
    ```powershell
    python manage.py startapp ten_app
    ```
- Tạo migration:
    ```powershell
    python manage.py makemigrations
    ```
- Tạo migration cho app cụ thể:
    ```powershell
    python manage.py makemigrations trang_chu
    ```
- Tạo superuser:
    ```powershell
    python manage.py createsuperuser
    ```

## 6. Ghi chú

- Nếu gặp lỗi chính sách thực thi trên PowerShell, chạy:
    ```powershell
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    ```
- Đảm bảo đã cài Python 3 và pip.
- Luôn kích hoạt môi trường ảo trước khi cài thư viện hoặc chạy lệnh Django.
- Truy cập trang quản trị: http://127.0.0.1:8000/admin

---

## Hướng dẫn tạo chứng chỉ tự ký để chạy HTTPS với runserver_plus

### 1. Cài đặt OpenSSL (nếu chưa có)

- Nếu bạn chưa có OpenSSL, hãy cài đặt:
    - **Với Chocolatey:**  
        ```powershell
        choco install openssl
        ```
    - **Hoặc tải từ trang chủ:**  
        https://slproweb.com/products/Win32OpenSSL.html

### 2. Tạo chứng chỉ tự ký

- Mở PowerShell hoặc Command Prompt tại thư mục chứa `manage.py` và chạy lệnh sau:
    ```powershell
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
    ```
- Khi được hỏi thông tin, bạn có thể nhấn Enter để bỏ qua hoặc nhập thông tin tùy ý.

### 3. Đảm bảo file chứng chỉ

- Sau khi chạy xong, bạn sẽ có 2 file: `cert.pem` và `key.pem` trong thư mục dự án (cùng cấp với `manage.py`)

### 4. Chạy server với HTTPS

- Sử dụng lệnh:
    ```powershell
    python manage.py runserver_plus 192.168.0.24:8000 --cert-file cert.pem --key-file key.pem
    ```

---

**Lưu ý:**  
- Nếu gặp lỗi "openssl is not recognized", hãy kiểm tra lại biến môi trường PATH hoặc cài đặt lại OpenSSL.
- Chứng chỉ tự ký chỉ dùng cho phát triển, không dùng cho môi trường production.
- Để thêm thuộc tính CSS cho các trường form, sử dụng phương thức `__init__` trong class form.
- Để sử dụng CKEditor, thêm vào `requirements.txt` và cài đặt theo hướng dẫn của CKEditor cho Django.