# Hướng dẫn thiết lập và sử dụng dự án Django trên macOS

## Tạo môi trường ảo

1. **Điều hướng đến thư mục dự án**:
    ```sh
    cd /path/to/du-an-xu-ly-anh/seizo0\ 250425B
    ```

2. **Tạo môi trường ảo**:
    ```sh
    python3 -m venv .venv
    ```

3. **Kích hoạt môi trường ảo**:
    ```sh
    source .venv/bin/activate
    ```

## Cài đặt các thư viện cần thiết

1. **Cài đặt Django**:
    ```sh
    python3 -m pip install django
    ```

2. **Tạo tệp `requirements.txt` và thêm các thư viện cần thiết**:
    ```plaintext
    Django>=3.2,<4.0
    djangorestframework
    django-crispy-forms
    ```

3. **Cài đặt các thư viện từ tệp `requirements.txt`**:
    ```sh
    python3 -m pip install -r requirements.txt
    ```

## Tạo dự án Django mới

1. **Tạo một dự án Django mới**:
    ```sh
    django-admin startproject my_django_app
    ```

2. **Điều hướng vào thư mục dự án**:
    ```sh
    cd my_django_app
    ```

## Chạy máy chủ phát triển

1. **Chạy lệnh di chuyển cơ sở dữ liệu**:
    ```sh
    python3 manage.py migrate
    ```

2. **Khởi động máy chủ phát triển**:
    ```sh
    python3 manage.py runserver
    ```

## Các lệnh thường dùng

- **Kích hoạt môi trường ảo**:
    ```sh
    source .venv/bin/activate

    cd trang_chu
    ```
- **Cài đặt các thư viện từ `requirements.txt`**:
    ```sh
    python3 -m pip install -r requirements.txt
    ```
- **Chạy lệnh di chuyển cơ sở dữ liệu**:
    ```sh
    python3 manage.py migrate
    ```
    - Tạo các migration:
    ```sh
    python3 manage.py makemigrations
    ```
- **Khởi động máy chủ phát triển**:
    ```sh
    python3 manage.py runserver
    ```

## Ghi chú

- Đảm bảo rằng bạn đang sử dụng phiên bản Python 3 tương thích với Django.
- Nếu gặp lỗi về quyền truy cập, hãy kiểm tra quyền của thư mục dự án hoặc sử dụng `sudo` khi cần thiết.
- Nếu gặp lỗi không tìm thấy pip, hãy dùng: `python3 -m ensurepip --upgrade`

## Tạo các ứng dụng Django

- **Tạo ứng dụng quản lý tài khoản**:
    ```sh
    python3 manage.py startapp quan_ly_tai_khoan
    ```

- **Tạo ứng dụng quản lý linh kiện**:
    ```sh
    python3 manage.py startapp quan_ly_linh_kien
    ```

- **Tạo ứng dụng phê duyệt giấy tờ**:
    ```sh
    python3 manage.py startapp phe_duyet_giay_to
    ```

- **Tạo ứng dụng tổng hợp hàng lỗi**:
    ```sh
    python3 manage.py startapp tong_hop_hang_loi
    ```

- **Tạo ứng dụng tin tức**:
    ```sh
    python3 manage.py startapp tin_tuc
    ```

- **Tạo ứng dụng hoạt động máy**:
    ```sh
    python3 manage.py startapp hoat_dong_may
    ```

- **Tạo migration cho app `trang_chu`**:
    ```sh
    python3 manage.py makemigrations trang_chu
    ```

- **Tạo superuser**:
    ```sh
    python3 manage.py createsuperuser
    ```

## Truy cập trang quản trị

- Mở trình duyệt và truy cập: [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)

---

python3 manage.py runserver 192.168.0.24:8000


python3 manage.py runserver_plus 192.168.0.23:8000 --cert-file cert.pem --key-file key.pem
python3 manage.py runserver_plus 192.168.0.24:8000 --cert-file cert.pem --key-file key.pem