# Hướng dẫn gửi thông báo mail để dashboard nhận và hiển thị

## 1. Định dạng nội dung email để dashboard nhận

**Chỉ nhận email có block bắt đầu bằng dòng:**
```
post
```
(không phân biệt hoa thường, có thể là POST, Post...)

**Nội dung block phải theo mẫu sau:**
```
post
内容: <nội dung thông báo>
時間: <giờ>:<phút>
レベル: <mức độ>
```

- `内容:` là nội dung thông báo sẽ hiển thị trên dashboard.
- `時間:` là thời gian xuất hiện thông báo (có thể nhiều mốc giờ, ví dụ: 14:15, 21:45).
- `レベル:` là mức độ ưu tiên (1, 2, 3). Nếu không có, mặc định là 1.

**Ví dụ email hợp lệ:**
```
post
内容: ★2026年1月26日 生産技術課より連絡
時間: 14:15
レベル: 2
```

**Có thể gửi nhiều block post trong một email, hệ thống chỉ lấy block đầu tiên.**

---

## 2. Lưu ý khi gửi email

- KHÔNG gửi email chỉ có "内容:" mà không có dòng "post" ở đầu block.
- KHÔNG chia nhiều dòng hoặc thêm ký tự thừa ngoài mẫu trên.
- Nếu có nhiều thời gian trong dòng `時間:`, hệ thống sẽ tạo nhiều thông báo tương ứng.

---

## 3. Ý nghĩa các trường

- **内容:** Nội dung hiển thị trên ticker. Nếu có "より連絡", dashboard sẽ chỉ hiện tên rút gọn và "より連絡:".
- **時間:** Thời gian xuất hiện thông báo (giờ:phút, ví dụ 14:15).
- **レベル:** Mức độ ưu tiên (1: thường, 2: quan trọng, 3: cảnh báo). Thời gian hiển thị sẽ dài hơn với mức độ cao.

---

## 4. Địa chỉ người gửi

- Địa chỉ email nên có dạng `<ten@domain.com>`, ví dụ: `<giang@hayashi-p.co.jp>`.
- Dashboard sẽ tự động lấy phần tên trước dấu `@` và loại bỏ `< >` để hiển thị.

---

## 5. Ví dụ email hoàn chỉnh

```
post
内容: Có sự cố máy số 5, vui lòng kiểm tra!
時間: 09:30
レベル: 3
```

Hoặc:

```
post
内容: ★2026年1月26日 生産技術課より連絡
時間: 14:15 21:45
レベル: 2
```

---

## 6. Quy trình xử lý

- Hệ thống chỉ lấy block bắt đầu bằng "post".
- Chỉ lấy dòng đầu tiên "内容:" sau "post" làm nội dung thông báo.
- Nếu không có "post", email sẽ bị bỏ qua.

---

**Nếu có vấn đề về hiển thị hoặc gửi mail, liên hệ quản trị viên để kiểm tra lại cấu hình.**