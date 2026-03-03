# Project Changelog (Major Changes Only)

Tai lieu nay chi ghi thay doi lon de handoff nhanh.

## Template
### [YYYY-MM-DD] Tieu de thay doi
- Pham vi: app/file...
- Noi dung:
  - ...
- Anh huong:
  - ...
- Lenh da chay / can chay:
  - ...
- Rollback:
  - ...
- Ghi chu:
  - ...

---

### [2026-02-20] Chuyen sang backup code-only va giam nhe git
- Pham vi: git workflow, `.gitignore`, remote `main`
- Noi dung:
  - Bo track cac du lieu runtime/lon: `media/`, `staticfiles/`, `backup_db/`, `.git_broken/`, `cert.pem`, `key.pem`.
  - Tao lich su nhe cho nhanh `main` va dong bo local `main` track `origin/main`.
  - Tao tai lieu: `ARCHITECTURE.md`, `cap nhat git.md`.
- Anh huong:
  - Tu nay backup nhanh hon, chi tap trung code/logic.
  - File media local van giu tren may nhung khong con backup bang git.
- Lenh can chay hang ngay:
  - `git add -A`
  - `git commit -m "backup: ..."`
  - `git push`
- Rollback:
  - Dung nhanh local `main-heavy-backup` de doi chieu neu can.
- Ghi chu:
  - Neu can backup media, dung co che rieng (NAS/cloud/zip), khong dua vao git.

### [2026-02-20] Nâng cấp luồng nhap_lieu + callback máy trạm
- Phạm vi: `nhap_lieu/models.py`, `nhap_lieu/views.py`, `nhap_lieu/urls.py`, `trang_chu/urls.py`, migration mới, script Flask mẫu.
- Nội dung:
  - Thêm model `KetQuaNhapLieu` để lưu lịch sử callback từ máy trạm.
  - Thêm API:
    - `api/cap-nhat-ket-qua/`
    - `api/latest-result/`
    - `api/latest-by-ip/`
    - `api/sse-latest-result/`
  - Tối ưu polling/SSE để giảm lag khi chạy liên tục.
  - Thêm alias route `nhap-lieu/` để tương thích callback URL hiện tại của Flask.
  - Thêm file `nhap_lieu/workstation_flask_api.py` (bản ổn định cho máy trạm: lock chống chồng job, callback retry, kill process theo PID).
- Ảnh hưởng:
  - Chưa đụng app `quet_anh` (đảm bảo không ảnh hưởng vận hành hằng ngày).
  - Luồng callback/đọc kết quả của `nhap_lieu` ổn định hơn khi chạy lâu.
- Lệnh cần chạy:
  - `python manage.py migrate nhap_lieu`
  - restart Django service
  - deploy script Flask mới lên máy trạm nếu cần
- Rollback:
  - revert commit liên quan `nhap_lieu`
  - rollback migration `nhap_lieu 0002_ketquanhaplieu`
