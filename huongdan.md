Dưới đây là nội dung hướng dẫn thao tác trên Command Prompt để khởi động lại server và gia hạn chứng chỉ SSL bằng OpenSSL. Bạn có thể lưu nội dung này vào file huongdan.md:

Hướng dẫn thao tác trên Command Prompt
1. Khởi động lại server (Nginx)
Nếu bạn đang sử dụng Nginx trên Windows, bạn có thể thực hiện các bước sau:

    1/Mở Command Prompt với quyền Administrator:

Nhấn Windows + S, gõ command promt
    2/Điều hướng đến thư mục cài đặt Nginx:
    cd C:\nginx
Dừng Nginx:
    nginx -s stop
Khởi động lại Nginx:
    nginx
Kiểm tra cấu hình Nginx (tùy chọn): Trước khi khởi động lại, bạn có thể kiểm tra cấu hình Nginx để đảm bảo không có lỗi:
    nginx -t
2. Gia hạn chứng chỉ SSL bằng OpenSSL
Nếu bạn sử dụng OpenSSL để tạo và gia hạn chứng chỉ SSL, hãy làm theo các bước sau:

    1/Mở Command Prompt với quyền Administrator.

    2/Tạo khóa riêng (Private Key): Nếu bạn cần tạo một khóa riêng mới:
    cd C:\nginx\conf\
    openssl req -x509 -nodes -days 36500 -newkey rsa:2048 -keyout selfsigned.key -out selfsigned.crt

    openssl x509 -in "C:\nginx\conf\selfsigned.crt" -noout -text
    
Tạo yêu cầu ký chứng chỉ (CSR): Tạo một yêu cầu ký chứng chỉ (Certificate Signing Request - CSR):

Bạn sẽ được yêu cầu nhập thông tin như:
Country Name (C): Mã quốc gia (ví dụ: JP).
State or Province Name (ST): tokyo
Locality Name (L): tokyo
Organization Name (O): hayashi
Organizational Unit Name (OU): IT
Common Name (CN): 192.168.10.250
Email Address: pts@hayashi-p.co.jp
Gia hạn chứng chỉ: Gửi file CSR (request.csr) đến nhà cung cấp chứng chỉ SSL (CA). Sau khi được cấp chứng chỉ mới, bạn sẽ nhận được file .crt.

Kết hợp chứng chỉ: Kết hợp chứng chỉ được cấp với khóa riêng:

Cập nhật cấu hình Nginx: Mở file cấu hình Nginx (ví dụ: nginx.conf) và đảm bảo rằng các đường dẫn đến chứng chỉ và khóa riêng là chính xác:

Tải lại Nginx: Sau khi cập nhật cấu hình, tải lại Nginx:

3. Kiểm tra chứng chỉ SSL
Để kiểm tra chứng chỉ SSL đã được gia hạn thành công, bạn có thể sử dụng lệnh sau:

Lệnh này sẽ hiển thị thông tin chi tiết về chứng chỉ, bao gồm ngày hết hạn.

Lưu ý
C:\nginx\conf
Đảm bảo bạn sao lưu các file quan trọng như private.key, request.csr, và certificate.crt trước khi thực hiện bất kỳ thay đổi nào.
Nếu bạn sử dụng Let's Encrypt, bạn có thể sử dụng công cụ certbot để tự động gia hạn chứng chỉ.


🛠 Cách 2: Dùng Task Scheduler (Trình lập lịch tác vụ)
Cách này mạnh hơn và chạy script ngay cả khi không mở màn hình desktop.
- Mở Task Scheduler (Taskschd.msc).
- Chọn Create Basic Task → đặt tên (VD: StartServer).
- Chọn trigger là When the computer starts.
- Chọn Start a program → trỏ tới file .bat hoặc script của bạn.
- Hoàn tất và kiểm tra bằng cách khởi động lại.


