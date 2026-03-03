# Django Architecture (Short)

## 1) Tong quan
- Project root: `trang_chu`
- Django settings module: `trang_chu.settings`
- DB: SQLite (`db.sqlite3`)
- Time zone: `Asia/Tokyo`
- Static: `static/` -> `staticfiles/`
- Media: `media/` (hien tai khong track trong git)

## 2) URL map (cap project)
File: `trang_chu/urls.py`
- `/` -> trang chu (`trang_chu.views.index`)
- `/admin/`
- `/login/`, `/logout/`, `/register/`, `/profile/`
- `/phe_duyet/` -> app `phe_duyet`
- `/news/` -> app `news`
- `/mente/` -> app `mente`
- `/baotri/` -> app `baotri`
- `/quet_anh/` -> app `quet_anh`
- `/iot/` -> app `iot` (namespace `iot`)
- `/nhap_lieu/` -> app `nhap_lieu`
- `/menu/` -> app `menu`
- `/learn/` -> app `learn` (namespace `learn`)

## 3) App-by-app

### `trang_chu` (core user/profile/home)
- Main routes: `/`, `/login/`, `/logout/`, `/register/`, `/profile/`, `/delete_user/`
- Main model: `UserProfile`
- Notes:
  - Custom error handlers: 404/500
  - Home page show `news` with pagination

### `iot` (factory dashboard + machine + alarm + esp32/net100)
- Main routes:
  - Dashboard: `/iot/`, `/iot/dashboard/`, `/iot/center2/`
  - Device CRUD: `/iot/devices/...`
  - APIs: `/iot/api/...` (devices, alarms, esp32, weather, ticker, chatwork)
  - Production plan: `/iot/upload_plan/`, `/iot/upload_material_plan/`, `/iot/plan_status/`
  - Mold/machine tools: `/iot/molding/...`, `/iot/machine-counter/`
- Main models:
  - `Machine`, `Component`, `ComponentReplacementHistory`
  - `Mold`, `MoldLifetime`
  - `MachineStatusEvent`, `MachineAlarmEvent`, `DashboardNotification`
  - `Esp32*`, `Net100CycleShot`, `ProductShotMaster`, `ProductMonthlyShot`
  - `ProductionPlan`, `Change4MEntry`, `ChatworkMessage`
- Commands:
  - `python manage.py fetch_device_batch`
  - `python manage.py fetch_mail_notify`
  - `python manage.py sync_chatwork`
  - `python manage.py update_esp32_shot`
  - `python manage.py update_machine_counter`
  - `python manage.py update_mold_shot`
  - `python manage.py update_net100_shots`

### `menu` (meal ordering)
- Main routes:
  - `/menu/` list/create/update/delete menu
  - `/menu/<pk>/dat-mon/`, `/menu/order-history/`, `/menu/order_kanri/`
  - Employee/holiday/fax flows
- Main models: `MonAn`, `NhanVien`, `Order`, `Holiday`, `FaxStatus`
- Command:
  - `python manage.py fax_reminder`

### `learn` (training/course/approval)
- Main routes:
  - `/learn/`, `/learn/courses/`, `/learn/enroll/<id>/`, `/learn/my-courses/`
  - Admin training: create/edit/delete course, training report
  - Approval/report flows, certificate (`bangcap`) flows
- Main models:
  - `Course`, `Enrollment`, `Certificate`, `ApprovalHistory`, `BangCap`, `MotivationalQuote`

### `phe_duyet` (document approval)
- Main routes:
  - `/phe_duyet/`, create/upload/download document
  - approve/reject, inbox/message, export csv/pdf
- Main models: `Document`, `Approval`, `Message`, `Comment`

### `baotri` (maintenance task/checklist)
- Main routes:
  - `/baotri/`, add/edit/delete task
  - task code/start/confirm/detail
  - dashboard + export csv/pdf + mistake manage
- Main models:
  - `MaintenanceTask`, `TaskDetail`, `TaskResult`, `TaskCode`, `TaskCodeDetail`, `MaintenanceMistake`

### `mente` (checksheet quality flow)
- Main routes:
  - `/mente/`, product add/delete
  - checksheet CRUD/update
  - history (`lich-su-kiem-tra`) + checker management
- Main models: `Product`, `Checksheet`, `LichSuKiemTra`, `Checker`

### `news` (internal news)
- Main routes:
  - `/news/`, `/news/create/`, `/news/<pk>/edit/`, `/news/<pk>/delete/`, `/news/<pk>/`
- Main models: `NewsArticle`, `NewsImage`

### `quet_anh` (QA scan/compare)
- Main routes:
  - `/quet_anh/`, upload/history/device CRUD
  - dashboard + API latest events
- Main models: `QADeviceInfo`, `QAResult`

### `xu_ly_anh` (image processing v2)
- Main routes:
  - `/xu_ly_anh/`, upload, device-info CRUD, history
- Main models: `DeviceInfo`, `XuLyAnh2`

### `nhap_lieu` (data entry template)
- Main routes:
  - `/nhap_lieu/`, `mau-nhap-lieu`, `mau-list`, `quanly-may`
- Main models: `ChuongTrinhNhapLieu`, `MayTinh`

## 4) Van hanh nhanh
- Run server:
  - `python manage.py runserver`
- Migrate:
  - `python manage.py makemigrations`
  - `python manage.py migrate`
- Daily backup (code-only):
  - `git add -A && git commit -m "backup: ..." && git push`

## 5) Tech debt / canh bao quan trong
- Secret/SMTP password dang hardcode trong source (`settings.py`, mot so command iot).
- Nen chuyen sang env vars (`.env`) de an toan va de deploy.
- `iot/management/commands/fetch_device_batch.py` dang set `DJANGO_SETTINGS_MODULE='seizo0.settings'`, can doi ve `trang_chu.settings` neu chay loi.

## 6) Team docs
- COLLAB_RULES.md (quy tac phoi hop va quy dinh ghi thay doi lon)
- PROJECT_CHANGELOG.md (nhat ky thay doi lon de handoff nhanh)

