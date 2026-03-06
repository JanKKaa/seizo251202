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

### [2026-03-03] Hoan thien luong quet_anh -> nhap_lieu -> may tram va so cai realtime
- Pham vi:
  - `nhap_lieu/models.py`, `nhap_lieu/views.py`, `nhap_lieu/urls.py`, `nhap_lieu/admin.py`
  - `nhap_lieu/workstation_flask_api.py`
  - `quet_anh/models.py`, `quet_anh/views.py`, `quet_anh/urls.py`, `quet_anh/apps.py`, `quet_anh/admin.py`, `quet_anh/signals.py`
  - `templates/nhap_lieu/index.html`, `templates/quet_anh/index_qa.html`, `templates/quet_anh/auto_input_ledger.html`
  - migration moi: `nhap_lieu/0003`, `nhap_lieu/0004`, `quet_anh/0009`
- Noi dung:
  - Bo sung `PhienNhapLieu` + `job_id` de theo doi tung job nhap lieu.
  - May tram Flask chuan hoa callback: gui `job_id`, `status`, `ma_nhap_lieu`, `full_text`, `ip`; callback dung HTTPS noi bo.
  - Xu ly timeout job `sent` tu dong chuyen `failed` de tranh treo.
  - Bo sung fallback dong bo ket qua ngay tu response may tram khi callback async bi cham.
  - Tao so cai `QAAutoInputLedger` trong app `quet_anh`, co tim kiem tu khoa, loc ngay, loc trang thai, phan trang.
  - Them signal realtime: khi `PhienNhapLieu`/`KetQuaNhapLieu` doi trang thai se cap nhat so cai ngay.
  - Them lien ket 1-1: `PhienNhapLieu.qa_result` de map truc tiep voi ket qua quet anh (uu tien map truc tiep, fallback theo thoi gian neu thieu du lieu).
  - Them nut vao man hinh `index_qa`: `自動入力台帳`.
- Anh huong:
  - Luong thuc te da test thanh cong, may tram chay va dong app duoc.
  - Da co mot so job cu bi treo `sent` va da dong tay thanh `failed`.
  - Tu nay job moi khong can dong tay neu callback/timeout dung luong.
- Lenh da chay:
  - `python manage.py makemigrations nhap_lieu`
  - `python manage.py migrate nhap_lieu`
  - `python manage.py makemigrations quet_anh`
  - `python manage.py migrate quet_anh`
  - `python manage.py check`
- Luu y van hanh:
  - Callback may tram phai dung:
    - `https://192.168.10.250/nhap_lieu/api/cap-nhat-ket-qua/`
  - Neu dung cert noi bo, may tram dang de `verify=False` (co the bat lai bang env `CALLBACK_VERIFY_SSL=1` khi ha tang cert san sang).
  - Trang HTML moi/chinh sua uu tien hien thi tieng Nhat.
- Ke hoach tiep theo (ngay mai):
  - Lam endpoint/bridge trong `quet_anh` de goi `nhap_lieu` tu dong ngay sau khi OCR+kg hop le (khong thao tac tay trung gian).
  - Truyen `qa_result_id` day du trong luong goi job de dam bao map 1-1 tuyet doi.
  - Bo sung trang tong quan KPI cho so cai (done/failed/sent theo ngay, theo may tram, theo nguyen lieu).
