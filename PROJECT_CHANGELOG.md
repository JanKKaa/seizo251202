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

### [2026-06-19] Hien thi thong bao 4M ngay khi co tin moi
- Pham vi: `static/iot/js/applyData.js`, `templates/base_dashboard.html`, `templates/iot/partials/_center_panel.html`.
- Noi dung:
  - Dashboard tu dong mo popup khi API phat hien ID 4M moi dang con hieu luc.
  - Moi trinh duyet chi hien mot lan cho moi ID, luu moc da xem bang `localStorage`.
  - Popup tu dong dong sau 60 giay; alarm van duoc uu tien va tin 4M se hien o lan polling sau khi alarm ket thuc.
  - Bo hai polling 4M trung lap trong template; chi giu mot request moi 60 giay tu `applyData.js`.
  - Them version query cho file JS de trinh duyet lay ban moi sau deploy.
- Anh huong:
  - Tin 4M moi hien trong toi da khoang 60 giay ma khong can doi chu ky popup 10 phut.
  - Giam request API 4M lap lai, khong them worker hay truy van nen moi.
- Lenh da chay:
  - `node --check static\iot\js\applyData.js` -> OK.
  - `docker compose exec -T web python manage.py check` -> OK.
  - `docker compose exec -T web python manage.py collectstatic --noinput` -> 1 static file copied.
- Rollback:
  - Revert 3 file tren va chay lai `collectstatic`.

### [2026-06-11] Cap nhat du bao thoi tiet Minami Minowa khong can OWM key
- Pham vi: `iot/views_weather.py`, `templates/iot/partials/_header.html`.
- Noi dung:
  - Doi `/iot/api/weather/minowa/` tu OpenWeatherMap can `OWM_API_KEY` sang Open-Meteo khong can API key.
  - Dung toa do Minami Minowa, Nagano: `35.8729, 137.9753`.
  - API tra thoi tiet hien tai va `forecast_1730` gan moc 17:30, giu cac field cu `temp`, `weather`, `humidity`, `wind`, `city`, `time`, `source`.
  - Doi header dashboard tu Minowa sang Minami Minowa va dung cung toa do.
- Anh huong:
  - `/iot/api/weather/minowa/` khong con 503 do thieu `OWM_API_KEY`.
  - Dashboard thoi tiet hien thi dung khu vuc Minami Minowa hon.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py check"` -> OK.
  - Goi thu `/iot/api/weather/minowa/` trong Django test client -> `200`, `city=Minami Minowa, Nagano`.
- Rollback:
  - Revert 2 file tren; neu quay lai OWM can khai bao `OWM_API_KEY` trong `.env` va recreate web.

### [2026-06-11] He thong route/API audit va sua loi link noi bo
- Pham vi: `iot/views_devices.py`, `iot/views_index.py`, `iot/views_weather.py`, `menu/views.py`, `learn/views.py`, template IoT, Docker runtime workers.
- Noi dung:
  - Quet 231 route/API bang Django client co timeout; truoc khi sua co loi 500/exception o API alarm IoT, form import/device IoT, manual machine IoT, PDF menu, va trang bang cap Learn khi session nhan vien cu.
  - Sua API alarm IoT theo model hien tai: dung `created_at`/`cleared_at` thay cho field cu `started_at`/`active`, va group distribution theo `alarm_code`/`alarm_name`.
  - Sua cac reverse/redirect IoT sang namespace `iot:*`.
  - Sua PDF menu dung key `gia` thay vi `gia2`.
  - Sua Learn bang cap: neu session `ma_nv` khong con nhan vien thi xoa session va quay ve dang nhap.
  - Doi `/iot/api/weather/minowa/` khi thieu `OWM_API_KEY` tu 500 sang 503 co JSON ro rang.
  - Dung cac worker IoT cu rieng le dang loi SQLite malformed; giu `iot-worker-serial` la worker chinh.
- Anh huong:
  - Route/API scan sau deploy khong con loi 500/exception; con canh bao cau hinh `/iot/api/weather/minowa/` tra 503 do thieu `OWM_API_KEY`.
  - Worker IoT tranh chay trung logic va tranh log SQLite malformed tu image/config cu.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py check"` -> OK.
  - `docker update --restart=no ...` va `docker stop ...` cho cac worker IoT cu.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker restart seizo0-nginx` sau 502 transient.
  - `docker compose up -d --force-recreate iot-worker-serial fax-reminder-daily`
  - `docker compose exec -T web python manage.py check` -> OK.
  - Scan 231 route/API sau deploy: `200=190`, `302=16`, `400=7`, `403=2`, `404=1`, `405=14`, `503=1`, khong con `500/EXC`.
- Rollback:
  - Revert cac file code/template tren va rebuild web; neu can bat lai worker cu thi phai dam bao chung dung PostgreSQL/config moi, khong khuyen nghi chay song song voi `iot-worker-serial`.

### [2026-06-10] 出庫OCRが0%になる問題を修正
- Pham vi: `quet_anh/views.py`, `Dockerfile`, `scripts/install_paddleocr_models.sh`.
- Noi dung:
  - Dieu tra loi xuat kho OCR/compare hien 0%: PaddleOCR model trong container bi loi native (`Cannot parse tensor desc`) va sau khi cai lai model, cau hinh angle classifier co the gay segfault khi OCR.
  - Sua script cai model PaddleOCR de dung Python download fallback khi container khong co `curl`.
  - Dua buoc `bash scripts/install_paddleocr_models.sh` vao Docker build de model OCR nam san trong image production sau moi lan rebuild.
  - Doi luong OCR xuat kho sang cau hinh on dinh: `use_angle_cls=False`, `cls=False`, `use_gpu=False`, `enable_mkldnn=False`, gioi han thread OpenMP/MKL.
  - Them logging exception neu PaddleOCR loi de khong con im lang thanh ket qua 0%.
- Anh huong:
  - Luong xuat kho doc OCR lai tren anh da test; giam rui ro tat ca ket qua so sanh ve 0%.
  - Docker build web lau hon vi tai/cai model PaddleOCR trong image.
- Lenh da chay:
  - `docker compose build web`
  - Test PaddleOCR init va OCR tren anh mau `processed_new_bduTRQ2.png` -> doc ra text, LEN 68.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/qa_ocr_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test quet_anh"` -> 13 tests OK.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/qa_ocr_manage_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py check"` -> OK.
- Rollback:
  - Revert 3 file tren va rebuild web image; neu rollback, can dam bao model PaddleOCR runtime khong bi hong.

### [2026-06-09] 修正: runtime backup が .git scan で失敗する問題を修正
- Pham vi: `iot/management/commands/backup_runtime_data.py`, backup runtime.
- Noi dung:
  - Sua luong gom `source/` de bo qua `.git/`, `media/`, `staticfiles/`, `logs/`, `backup_db/` truoc khi di sau vao cay thu muc.
  - Nguyen nhan: backup luc `2026-06-09 02:30` bi loi `Cannot allocate memory` khi quet `.git/objects`, tao zip loi chi co `source/`.
  - Tao lai backup full runtime hop le: `backup_db/daily/seizo0_runtime_backup_20260609_080515.zip`.
  - Copy backup hop le moi len Google Drive Desktop folder `G:\マイドライブ\seizo0-backups`.
- Anh huong:
  - Backup runtime tiep tuc gom PostgreSQL dump, `media/`, `staticfiles/`, `logs/`, `nginx/`, `.env`, va source code.
  - Da xoa zip loi `seizo0_runtime_backup_20260609_023015.zip` khoi local de tranh bi nham la backup hop le.
- Lenh da chay:
  - `docker compose build web`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_runtime_to_drive.ps1 -SkipUpload -KeepBackupCount 4`
  - Kiem tra manifest zip moi: `database_kind=postgresql`, included co `postgres/`, `media/`, `staticfiles/`, `logs/`, `nginx/`, `.env`, `source/`.
- Rollback:
  - Revert thay doi trong `backup_runtime_data.py`; khong khuyen nghi vi se co nguy co loi lai khi quet `.git`.

### [2026-05-29] タブレット使用前の日次点検ゲートを追加
- Pham vi: `quet_anh/views.py`, `quet_anh/urls.py`, `quet_anh/tests.py`, `templates/quet_anh/tablet_tenken_gate.html`, `templates/quet_anh/tablet_inspection_form.html`.
- Noi dung:
  - Them gate bat buoc chon tablet va hoan thanh tenken OK moi ngay truoc khi vao man hinh chinh, xuat kho, nhap kho.
  - Luu tablet dang dung bang session server; trinh duyet nho lua chon tablet bang localStorage de thao tac nhanh lan sau.
  - Sau khi tenken OK, gan tablet vao session va quay lai luong dang thao tac.
  - Neu tenken NG thi tablet chuyen trang thai stopped va xoa tablet khoi session hien tai.
- Anh huong:
  - Khong doc duoc MAC address tu browser; dung ma tablet da dang ky thay cho MAC.
  - Khong doi DB/migration vi da co `QATabletDevice` va `QATabletInspection`.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/qa_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test quet_anh"` -> 5 tests OK.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/qa_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py check"` -> OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - `curl.exe -k -I https://192.168.10.250/quet_anh/` -> `302` ve login.
- Rollback:
  - Revert cac file tren.

### [2026-05-28] 出庫スキャンで同一機械番号の製品選択を追加
- Pham vi: `quet_anh/views.py`, `templates/quet_anh/index_qa.html`, `quet_anh/tests.py`.
- Noi dung:
  - Nhom danh sach xuat kho theo ma quan ly may (`QADeviceInfo.name`).
  - Khi cung mot ma may co nhieu san pham/nguyen lieu dang ky, man hinh xuat kho hien them dropdown chon san pham de gui dung `device_id`.
  - QR may chi chon ma may; neu co nhieu ung vien, nguoi thao tac chon san pham truoc khi vao buoc chup/quet anh.
- Anh huong:
  - Giam rui ro xuat kho ghi sai san pham khi mot may dung cho nhieu san pham/nguyen lieu.
  - Khong doi DB/migration.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/qa_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test quet_anh"` -> 1 test OK.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/qa_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py check"` -> OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - `curl.exe -k -I https://192.168.10.250/quet_anh/` -> `302` ve login.
- Rollback:
  - Revert 3 file tren.

### [2026-05-28] 設備・金型の手動カタログツリーを追加
- Pham vi: `setsubi_zaiko/models.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, `templates/setsubi_zaiko/item_list.html`, `form.html`, migration `0017`, tests.
- Noi dung:
  - Them model `EquipmentCatalogNode` de tao catalog tree tuy y so tang cho `設備` va `金型`.
  - Item co the gan vao mot catalog node rieng, doc lap voi `分類`.
  - Them nut `カタログ登録` tren danh sach thiet bi/khuon.
  - Mega menu catalog hien tree parent-child va loc gom ca cac node con.
- Anh huong:
  - Ho tro quy tac: `cty A` -> `khuon B` -> `nhom C` -> `nhom D` -> `linh kien Z`.
  - Co migration DB moi.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 20 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py migrate setsubi_zaiko` -> OK.
  - `docker compose exec -T web python manage.py check` -> OK.
  - Tao catalog ban dau tu du lieu hien co: 104 catalog nodes, gan 6 khuon va 107 thiet bi vao catalog.
  - Playwright capture: `setsubi-catalog-tree-mold.png`.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/molds/` -> `302` ve login.
- Rollback:
  - Revert code va rollback migration `setsubi_zaiko 0017`.

### [2026-05-28] 金型台帳を顧客・製品・構成品階層へ拡張
- Pham vi: `setsubi_zaiko/models.py`, `forms.py`, `views.py`, `admin.py`, `management/commands/sync_mold_folders.py`, templates, migration `0016`, tests.
- Noi dung:
  - Them truong `金型顧客コード/名`, `金型製品コード/名`, `金型部品・構成品名`.
  - Detail/list hien cau truc `顧客 > 製品 > 構成品`.
  - `sync_mold_folders` doi sang quet 3 tang: customer folder -> product folder -> component folder.
- Anh huong:
  - Phu hop quy tac quan ly: `023 cty A` -> `900 san pham Z` -> `runner lock / EP`.
  - Co migration DB moi.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 19 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py migrate setsubi_zaiko` -> OK.
  - `docker compose exec -T web python manage.py check` -> OK.
  - Backfill 6 khuon cu vao cau truc `顧客 > 製品 > 構成品`.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/molds/` -> `302` ve login.
- Rollback:
  - Revert code va rollback migration `setsubi_zaiko 0016`.

### [2026-05-28] 設備台帳に詳細グループ・資料フォルダ連携を追加
- Pham vi: `setsubi_zaiko/models.py`, `forms.py`, `views.py`, `admin.py`, `management/commands/import_equipment_list.py`, `management/commands/sync_equipment_folders.py`, templates, migration `0015`, tests.
- Noi dung:
  - Them `設備グループ`, `設備シリーズ・型式分類`, `設備資料親フォルダ`, `設備資料サブフォルダ`.
  - Dua `メーカー`, `型式`, `シリアルNo.`, `使用部署` ra form nhap/sua thiet bi.
  - Hien nhom/series/hang/model va nut `資料フォルダ` tren danh sach/chi tiet thiet bi.
  - Search co the tim theo maker, department, group, series va duong dan thu muc.
  - Them command `sync_equipment_folders <root_path>` de tao/cap nhat thiet bi tu thu muc con.
- Anh huong:
  - Thiet bi co the quan ly ro theo `乾燥機 > メーカー > シリーズ/型式 > 管理番号`, tach voi khuon va linh kien kho.
  - Co migration DB moi.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 19 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py migrate setsubi_zaiko` -> OK.
  - `docker compose exec -T web python manage.py check` -> OK.
  - Backfill 107 thiet bi hien co: neu trong thi gan `設備グループ` theo category va `シリーズ` theo `型式`.
  - Playwright capture: `setsubi-equipment-grouped-fields.png`.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/equipment/` -> `302` ve login.
- Rollback:
  - Revert code va rollback migration `setsubi_zaiko 0015`.

### [2026-05-28] 金型台帳に図面フォルダ連携を追加
- Pham vi: `setsubi_zaiko/models.py`, `forms.py`, `admin.py`, `management/commands/sync_mold_folders.py`, templates, migration `0014`, tests.
- Noi dung:
  - Them truong `金型図面親フォルダ` va `金型図面サブフォルダ` cho master khuon.
  - Hien nut `図面フォルダ` tren danh sach/chi tiet khuon neu da co duong dan.
  - Them command `sync_mold_folders <root_path>` de tao/cap nhat record khuon tu cac thu muc con nhu `901 QMB`, `902 QMX`.
- Anh huong:
  - Khuon co the lien ket truc tiep voi cau truc thu muc ban ve hien co, khong dua vao ton kho linh kien.
  - Co migration DB moi.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 18 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py migrate setsubi_zaiko` -> OK.
  - `docker compose exec -T web python manage.py check` -> OK.
  - Tao san 6 khuon nhom `023マグプロスト`: `901 QMB`, `902 QMX`, `903 HGP`, `904 NAT`, `906 マグネット`, `918 TGK ASSY`.
  - Playwright capture: `setsubi-mold-folder-links.png`.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/molds/` -> `302` ve login.
- Rollback:
  - Revert code va rollback migration `setsubi_zaiko 0014`.

### [2026-05-28] MISUMI風カテゴリメニューを hover 表示へ調整
- Pham vi: `templates/setsubi_zaiko/item_list.html`
- Noi dung:
  - Doi vung `カテゴリから探す` / `よく使う分類` thanh mega menu an mac dinh.
  - Chi hien menu khi hover/focus vao nut `カテゴリ・分類から探す`, giup man hinh mac dinh gon hon.
- Anh huong:
  - Giao dien gan hon cach thao tac catalog MISUMI: mac dinh la search/filter/list, phan loai chi mo khi can.
  - Khong thay doi DB.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 16 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/parts/` -> `302` ve login sau khi web khoi dong xong.
  - Playwright capture: `setsubi-misumi-hover-hidden.png`, `setsubi-misumi-hover-open.png`.
- Rollback:
  - Revert `item_list.html`.

### [2026-05-28] MISUMI風カタログ導線へ setsubi_zaiko UI を刷新
- Pham vi: `templates/setsubi_zaiko/base.html`, `item_list.html`, `setsubi_zaiko/views.py`
- Noi dung:
  - `setsubi_zaiko/base.html` khong con ke thua `trang_chu/base.html`; bo sidebar/footer portal de app kho co shell rieng.
  - Them header dang catalog voi logo, search lon, nav 5 muc chinh.
  - Them vung `カテゴリから探す` va `よく使う分類` co card thumbnail/hinh anh neu item co `item_image`.
  - Loc category theo nghiep vu: `設備` chi hien category thiet bi, `金型` chi hien category khuon, `部品在庫` khong hien `設備管理台帳`.
  - Giu table/card list hien co ben duoi de thao tac quan ly kho.
- Anh huong:
  - UI gan hon luong chon category/search cua MISUMI, nhung van giu logic noi bo: thiet bi/khuon/linh kien tach rieng.
  - Khong thay doi DB.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 16 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - Playwright capture: `setsubi-misumi-parts-final.png`, `setsubi-misumi-equipment-final.png`.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/parts/` -> `302` ve login.
- Rollback:
  - Revert template/view changes; khong can rollback migration.

### [2026-05-28] UI tối giản hóa nút thao tác setsubi_zaiko
- Pham vi: `templates/setsubi_zaiko/base.html`, `dashboard.html`, `ledger_workflow.html`
- Noi dung:
  - Xoa nut `入出庫登録` bi lap tren header; header chi con 5 diem den chinh.
  - Xoa cac nut thao tac nhanh lap lai tren dashboard.
  - Xoa cum chon `入庫/出庫/調整` trong workflow; viec chon mode chi nam o `入出庫台帳`.
  - Sua loi man `調整` hien thua dropdown `入庫` do render `transaction_type` hai lan.
  - Lam hero workflow sang hon, toi gian hon, khong dung nen canvas/dark decoration.
- Anh huong:
  - Moi tac vu chi co mot vi tri nut chinh, giam nham lan khi thao tac hien truong.
  - Khong thay doi DB.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 16 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - Playwright capture: `setsubi-ledger-minimal-final.png`.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/ledger/adjust/` -> `302` ve login.
- Rollback:
  - Revert cac template tren; khong can rollback migration.

### [2026-05-26] 設備・金型・部品在庫の画面導線を完全分離
- Pham vi: `setsubi_zaiko/views.py`, `urls.py`, templates, `tests.py`
- Noi dung:
  - Them route rieng: `/setsubi-zaiko/equipment/`, `/setsubi-zaiko/molds/`, `/setsubi-zaiko/parts/`.
  - `/items/` mac dinh ve danh sach `部品在庫`, khong tron may moc vao ton kho.
  - Danh sach `設備・機械台帳` va `金型台帳` khong hien cot ton kho/IATF cua linh kien.
  - Doi UI thiet bi/khuon tu bang nhieu cot sang card/list de tranh chu bi be doc va phu hop luong asset master.
  - Dashboard va CSV ton kho chi tinh/export `部品在庫`, khong cong 107 thiet bi Excel vao ton kho.
- Anh huong:
  - May moc/thiet bi la asset master rieng; khuon la mold master rieng; linh kien moi la stock inventory.
  - Chua tach bang vat ly DB; van dung `item_kind` de dam bao khong tron nghiep vu, giam rui ro migration lon.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile ...`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py makemigrations setsubi_zaiko --check --dry-run"` -> no changes.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 16 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - Playwright capture sau chinh UI: `setsubi-equipment-final2.png`.
  - Production confirm: equipment=107, mold=0, part=0.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/equipment/` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/molds/` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/parts/` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/` -> `200 OK`.
- Rollback:
  - Revert route/template/view changes; khong can rollback DB.

### [2026-05-26] 設備台帳と部品在庫を管理区分で分離
- Pham vi: `setsubi_zaiko/models.py`, migration `0012`, `forms.py`, `views.py`, `management/commands/import_equipment_list.py`, templates, `tests.py`
- Noi dung:
  - Them `EquipmentItem.item_kind` gom `設備台帳`, `金型台帳`, `部品在庫`.
  - Excel `設備リスト.xlsx` import vao `設備台帳`, khong con bi xem la linh kien kho.
  - Nhap/xuat kho chi cho chon `部品在庫`; may moc/khuon chi dung lam master de link danh sach linh kien.
  - Bo sung filter `管理区分` tren danh sach va hien thi tren chi tiet.
- Anh huong:
  - Mot linh kien co the link voi nhieu may/khuon qua `EquipmentPartLink`.
  - `EquipmentItem.code` tiep tuc unique trong DB, khong cho trung ma quan ly.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile ...`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py makemigrations setsubi_zaiko --check --dry-run"` -> no changes.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 15 tests OK.
  - Backup production truoc deploy: `backup_db/postgres/seizo0_before_item_kind_split_20260526_143057.dump`.
  - `docker compose build web`
  - `docker compose run --rm web python manage.py migrate setsubi_zaiko` -> applied `0012`, `0013`.
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - Production confirm: equipment=107, mold=0, part=0.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/ledger/out/` -> `302` ve login.
  - `curl.exe -k -I "https://192.168.10.250/setsubi-zaiko/items/?item_kind=equipment"` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/` -> `200 OK`.
- Rollback:
  - Rollback migration ve `0011_equipmentpartlink` hoac restore PostgreSQL dump truoc deploy neu can.

### [2026-05-26] 入出庫 workflow に3段検索と分類集計を追加
- Pham vi: `setsubi_zaiko/forms.py`, `views.py`, `tests.py`, `templates/setsubi_zaiko/ledger_workflow.html`, `templates/setsubi_zaiko/ledger_list.html`
- Noi dung:
  - Bo sung 3 o loc keyword trong workflow nhap/xuat/dieu chinh de loc ung vien linh kien theo nhieu tang.
  - Label cua dropdown linh kien hien them code, ten, phan loai, loai thiet bi, may/khuon ap dung, ke, ton kho.
  - Them JS loc candidate truc tiep tren man hinh, ho tro vi du: `seikei` -> `sukuryu` -> `A-01`.
  - Lich su ledger them 3 bo loc server-side va the tong hop theo nhom phan loai + transaction type.
- Anh huong:
  - Nguoi dung tim linh kien khi nhap/xuat kho nhanh hon, giam chon nham.
  - Khong thay doi DB.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile ...`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 14 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/ledger/in/` -> `302` ve login.
  - `curl.exe -k -I "https://192.168.10.250/setsubi-zaiko/ledger/?q1=EQ&q2=13&q3="` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/` -> `200 OK`.
- Rollback:
  - Revert cac file tren; khong can rollback migration.

### [2026-05-26] 入出庫 UI を workflow 形式へ分離
- Pham vi: `setsubi_zaiko/forms.py`, `views.py`, `urls.py`, `tests.py`, `templates/setsubi_zaiko/ledger_workflow.html`, `templates/setsubi_zaiko/ledger_list.html`, `templates/setsubi_zaiko/dashboard.html`
- Noi dung:
  - Them route rieng cho `入庫`, `出庫`, `調整`: `/ledger/in/`, `/ledger/out/`, `/ledger/adjust/`.
  - Tach UI nhap/xuat kho thanh workflow rieng, nut lon, buoc ro rang, canvas nen nhe.
  - Man hinh lich su ledger co 3 nut thao tac lon thay vi mot form chung kho nhin.
  - Logic ghi ledger va audit trail giu nguyen, khong thay doi DB.
- Anh huong:
  - Nguoi dung hien truong co the vao thang luong nhap kho hoac xuat kho, giam nham lan transaction type.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile ...`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 13 tests OK.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/ledger/in/` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/ledger/out/` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/` -> `200 OK`.
- Rollback:
  - Revert cac file tren; khong can rollback migration vi khong co thay doi schema.

### [2026-05-26] 設備・金型中心の部品リンク管理 UI へ拡張
- Pham vi: `setsubi_zaiko/models.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, `templates/setsubi_zaiko/dashboard.html`, `templates/setsubi_zaiko/item_detail.html`, migration `0011`
- Noi dung:
  - Them model `EquipmentPartLink` de lien ket may moc/khuon voi linh kien su dung.
  - Them form va route dang ky link: `/setsubi-zaiko/items/<pk>/parts/add/`.
  - Nang dashboard thanh `設備管理ボード`, co canvas nen nhe va cac the thao tac nhanh cho thiet bi, linh kien, canh bao ton kho, nhap xuat.
  - Trang chi tiet may/khuon hien danh sach linh kien dang dung; trang chi tiet linh kien hien may/khuon dang su dung linh kien do.
- Anh huong:
  - Giu nguyen master thiet bi, khuon, linh kien hien co; chi them bang lien ket moi.
  - Day la nen tang cho trouble record, tenken checklist, replacement history va QR workflow tiep theo.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile ...`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py makemigrations setsubi_zaiko --check --dry-run"` -> no changes.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 11 tests OK.
  - Backup production truoc deploy: `backup_db/postgres/seizo0_before_asset_part_link_20260526_132441.dump`.
  - `docker compose build web`
  - `docker compose run --rm web python manage.py migrate setsubi_zaiko` -> applied `0011`.
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - Production confirm: `EquipmentPartLink` table OK, assets=107.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/` -> `302` ve login; `/` -> `200 OK`.
- Rollback:
  - Rollback migration ve `0010_equipment_ledger_categories` hoac restore dump `backup_db/postgres/seizo0_before_asset_part_link_20260526_132441.dump` neu can.

### [2026-05-26] Dong bo thiet bi tu Excel thiet bi list vao setsubi_zaiko
- Pham vi: `setsubi_zaiko/models.py`, `setsubi_zaiko/management/commands/import_equipment_list.py`, migration `0010`, `.dockerignore`
- Noi dung:
  - Doc file `設備リスト.xlsx`, sheet `設備管理台帳`, theo quy tac ma `種類記号-メーカー記号-型式短縮-連番`.
  - Them phan loai thiet bi theo ky hieu hien co: `SK`, `TD`, `FS`, `OC`, `KS`, `SP`, `KP`, `KC`, `AB`, `KB`, `SJ`, `DT`, `JD`, `KG`, `HR`.
  - Them command `import_equipment_list` de import/update thiet bi tu Excel, khong dung den nhom khuon.
  - Them `tmp` vao `.dockerignore` de ban copy Excel tam khong bi dua vao image Docker.
- Anh huong:
  - Co the dong bo thiet bi may moc dang quan ly bang Excel vao master `setsubi_zaiko`.
  - Ma quan ly Excel duoc dung lam `code`; loai thiet bi duoc gan vao category `EQ-*`.
- Lenh da chay / can chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile ...`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py makemigrations setsubi_zaiko --check --dry-run"` -> no changes.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 10 tests OK.
  - Dry-run import voi ban copy Excel -> created=107, updated=0, skipped=0.
  - Backup production truoc deploy/import: `backup_db/postgres/seizo0_before_equipment_excel_import_20260526_094719.dump`.
  - `docker compose build web`
  - `docker compose run --rm web python manage.py migrate setsubi_zaiko` -> applied `0010`.
  - `docker compose run --rm -v ${PWD}:/app-src web python manage.py import_equipment_list /app-src/tmp/設備リスト.xlsx` -> created=107, updated=0, skipped=0.
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - Production confirm: `EQUIPMENT-LEDGER` child categories=15, Excel items=107, `MOLD.parent_id=None`.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/` -> `302` ve login; `/` -> `200 OK`.
- Rollback:
  - Rollback migration ve `0009_mold_part_types_and_units`; neu can khoi phuc import production thi restore dump `backup_db/postgres/seizo0_before_equipment_excel_import_20260526_094719.dump`.

### [2026-05-26] Rut gon man hinh nhap master setsubi_zaiko
- Pham vi: `setsubi_zaiko/forms.py`, `templates/setsubi_zaiko/form.html`, `setsubi_zaiko/tests.py`
- Noi dung:
  - Giam form nhap/sua linh kien hang ngay, bo cac muc it dung khoi `EquipmentItemForm` de tranh ghi de rong khi field bi an.
  - Phan `詳細情報・IATF管理項目を開く` con 7 muc: ap dung may, ap dung khuon, diem dat hang, quality rank, nha cung cap, trang thai, ghi chu.
  - Du lieu cu trong DB cua cac field bo khoi form nhu Control Plan, nguoi phu trach, serial/model, ngay kiem ke van duoc giu nguyen.
- Anh huong:
  - Khong co migration moi, chi thay doi man hinh va form save.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile /app-src/setsubi_zaiko/forms.py /app-src/setsubi_zaiko/tests.py`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 8 tests OK.
- Rollback:
  - Revert cac file tren neu can mo lai toan bo field tren form.

### [2026-05-26] Mo rong setsubi_zaiko cho linh kien khuon va don vi quan ly
- Pham vi: `setsubi_zaiko/models.py`, `setsubi_zaiko/forms.py`, `setsubi_zaiko/tests.py`, `templates/setsubi_zaiko/form.html`, migration `0009`
- Noi dung:
  - Them nhom loai linh kien khuon ep nhua: inre/insert, core pin, ejector pin, slide core, guide, spring, cooling, plate, hot runner.
  - Seed them cay danh muc `MOLD` cho linh kien khuon de phan biet voi linh kien may moc/thiet bi.
  - Mo rong don vi quan ly tu `個` sang `個`, `枚`, `式`, `本`, `セット`, `その他`.
  - Rut gon man hinh nhap master linh kien: muc co ban hien san, cac truong IATF/MISUMI chi tiet nam trong vung mo rong.
- Anh huong:
  - Du lieu cu van giu nguyen, mac dinh don vi tiep tuc la `個`.
  - Can chay migration `setsubi_zaiko 0009` tren production Docker.
- Lenh da chay / can chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile ...`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py makemigrations setsubi_zaiko --check --dry-run"` -> no changes.
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 8 tests OK.
  - Backup truoc deploy: `backup_db/postgres/seizo0_before_setsubi_mold_units_20260526_084650.dump`.
  - `docker compose build web`
  - `docker compose run --rm web python manage.py migrate setsubi_zaiko` -> applied `0009`.
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check` -> OK.
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/` -> `200 OK`.
- Rollback:
  - Rollback migration ve `setsubi_zaiko 0008_iatf_item_control_fields` hoac restore dump `backup_db/postgres/seizo0_before_setsubi_mold_units_20260526_084650.dump` neu can.

### [2026-05-25] Dua setsubi_zaiko vao production Docker va nang cap upload hinh linh kien
- Pham vi: `trang_chu/settings.py`, `trang_chu/urls.py`, `templates/trang_chu/base.html`, `setsubi_zaiko/*`, `templates/setsubi_zaiko/*`, `ARCHITECTURE.md`
- Noi dung:
  - Bat `setsubi_zaiko` mac dinh trong `INSTALLED_APPS`, khong con an sau `GTECH_DEV_APPS_ENABLED`.
  - Them route production `/setsubi-zaiko/`; route cu `/dev/setsubi-zaiko/` redirect ve route moi.
  - Hien menu `設備・部品在庫` truc tiep trong sidebar.
  - Them trang chi tiet linh kien voi anh ngoai quan va anh tem/nhan phong to, link xem anh goc, thong tin IATF/MISUMI va 20 lich su nhap-xuat gan nhat.
  - Them trang sua master de upload/cap nhat anh linh kien sau khi tao.
  - Chay migration `setsubi_zaiko` tren PostgreSQL production tu `0001` den `0008`.
- Anh huong:
  - App da vao he thong Docker dang chay that; can dang nhap de truy cap.
  - Anh upload luu trong `media/setsubi_zaiko/` va duoc nginx phuc vu qua `/media/`.
  - Co backup PostgreSQL truoc deploy: `backup_db/postgres/seizo0_before_setsubi_20260525_144459.dump`.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"` -> 7 tests OK.
  - `docker exec seizo0-postgres pg_dump ...` tao backup truoc deploy.
  - `docker compose build web`
  - `docker compose run --rm web python manage.py migrate setsubi_zaiko`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check`
  - `curl.exe -k -I https://192.168.10.250/setsubi-zaiko/` -> `302` ve login.
  - `curl.exe -k -I https://192.168.10.250/dev/setsubi-zaiko/` -> `302` ve `/setsubi-zaiko/`.
  - `curl.exe -k -I https://192.168.10.250/` -> `200 OK`.
- Rollback:
  - Revert cac file tren, rollback migration `setsubi_zaiko` neu can, hoac restore dump `backup_db/postgres/seizo0_before_setsubi_20260525_144459.dump`.

### [2026-05-25] Hoan thien setsubi_zaiko buoc IATF audit/readiness
- Pham vi: `setsubi_zaiko/*`, `templates/setsubi_zaiko/*`, migration `0008`
- Noi dung:
  - Them truong master cho quan ly linh kien theo huong IATF: `quality_rank`, `control_plan_no`, `process_owner`, `supplier_name`, `supplier_part_url`, ngay kiem ke cuoi va han kiem ke tiep theo.
  - Dashboard them cac khung canh bao: ton thap hon/toi thieu, het han hieu chuan, qua han kiem ke, ledger chua cap tren xac nhan.
  - Danh sach linh kien them filter `quality_rank` va `audit alert`.
  - CSV ton kho them cot thong tin quan ly chat luong/nguon mua/kiem ke.
  - Sua form tao item de nhan `request.FILES`, giup upload anh ngoai quan va anh tem/nhan thuc su duoc luu.
- Anh huong:
  - App van dang dev-only, chi bat khi `GTECH_DEV_APPS_ENABLED=true`.
  - Can chay migrate `setsubi_zaiko` tren DB dev truoc khi dung field moi.
- Lenh da chay:
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web python -m py_compile ...`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py makemigrations setsubi_zaiko --check --dry-run"`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py check"`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_test.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py test setsubi_zaiko"`
- Rollback:
  - Revert cac file tren va rollback migration `setsubi_zaiko` ve `0007_misumi_item_master_fields`.

### [2026-05-25] Sua backup Google Drive Desktop fallback
- Pham vi: `scripts/backup_runtime_to_drive.ps1`, `scripts/install_daily_backup_task.ps1`
- Noi dung:
  - Bo mac dinh hardcode duong dan Google Drive co ky tu tieng Nhat de tranh loi encoding PowerShell.
  - Them tu dong tim Google Drive Desktop folder theo `マイドライブ`, `My Drive`, hoac `Google Drive` tren cac o dia.
  - Cai lai scheduled task `Seizo0 Daily Backup` luc `02:30`, tro den `G:\マイドライブ\seizo0-backups`.
- Anh huong:
  - Neu `rclone gdrive:` chua cau hinh, backup van copy vao Google Drive Desktop folder.
  - Upload len cloud van phu thuoc Google Drive Desktop sync neu khong cau hinh `rclone`.
- Lenh da chay:
  - Parse check PowerShell cho 2 script backup: OK.
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_daily_backup_task.ps1 -KeepBackupCount 2`
  - `Get-ScheduledTaskInfo -TaskName 'Seizo0 Daily Backup'`
- Rollback:
  - Revert 2 script tren va cai lai scheduled task bang script cu neu can.

### [2026-05-19] Chay song song IP va ten mien noi bo cho HTTPS
- Pham vi: `.env`, `.env.example`, `nginx/conf.d/seizo0.conf`, `C:/seigi-server/nginx/conf/selfsigned.crt`, `C:/seigi-server/nginx/conf/selfsigned.key`
- Noi dung:
  - Da thu them hostname noi bo `https://hayashi-techno.lab`.
  - Sau do bo hostname nay theo yeu cau, quay lai chi dung `https://192.168.10.250`.
  - Tao lai self-signed certificate co SAN: `DNS:localhost`, `IP:192.168.10.250`, `IP:127.0.0.1`.
- Anh huong:
  - Server nhan IP `192.168.10.250` voi certificate dung SAN IP.
  - Vi van la self-signed certificate, browser co the van canh bao tin cay; muon het canh bao tren moi may thi can certificate tu CA duoc client tin san hoac cai CA noi bo qua chinh sach tap trung.
- Lenh da chay / can chay:
  - `docker compose exec -T nginx nginx -t`
  - `docker compose up -d --force-recreate web nginx`
  - `docker compose exec -T web python manage.py check`
  - `curl.exe -k -I https://192.168.10.250/`
- Rollback:
  - Khoi phuc `.env`, `nginx/conf.d/seizo0.conf` va cert/key tu file backup `selfsigned.*.bak_*`, sau do recreate `web nginx`.

### [2026-05-19] Them mail canh bao ton kho nguyen lieu duoi muc an toan
- Pham vi: `quet_anh/models.py`, `quet_anh/signals.py`, `quet_anh/admin.py`, `quet_anh/migrations/0030_material_out_low_stock_alert.py`
- Noi dung:
  - Khi tao ledger xuat kho nguyen lieu lam ton kho chuyen tu tren muc an toan xuong bang/thap hon muc an toan, he thong gui email tu dong.
  - Nguoi nhan: `k_arita@hayashi-p.co.jp`, `t_miyasaka@hayashi-p.co.jp`, `giang@hayashi-p.co.jp`, `seisan_kanri@hayashi-p.co.jp`.
  - Email ghi ro nguyen lieu, ma nguyen lieu, ton hien tai, muc an toan, luong xuat cuoi, nguoi xuat cuoi, lot va so he thong.
  - Them truong `low_stock_alert_sent_at` de tranh gui lap lai cho cung mot ledger xuat kho.
- Anh huong:
  - Can chay migrate `quet_anh` tren DB runtime.
  - Can SMTP env dang hoat dong de gui mail thuc te.
- Lenh da chay / can chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/models.py /app-src/quet_anh/signals.py /app-src/quet_anh/admin.py /app-src/quet_anh/migrations/0030_material_out_low_stock_alert.py`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/quet_low_stock_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py makemigrations quet_anh --check --dry-run"`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/quet_low_stock_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py check"`
  - Can chay tren DB runtime: `python manage.py migrate quet_anh`
- Rollback:
  - Revert cac file tren va rollback migration `quet_anh` ve `0029_tablet_inspection_qr_evidence` neu can.

### [2026-05-19] Them phan loai cho dang ky phe_duyet
- Pham vi: `phe_duyet/models.py`, `phe_duyet/forms.py`, `phe_duyet/views.py`, `phe_duyet/admin.py`, `phe_duyet/migrations/0012_document_category.py`, `templates/phe_duyet/*`
- Noi dung:
  - Them truong `Document.category` voi cac loai: `保全依頼`, `資料承認`, `注文書`, `その他`.
  - Form dang ky phe duyet co them dropdown `分類`.
  - Danh sach, man hinh duyet, PDF export va CSV export hien thi/xuat phan loai.
  - Admin co list/filter theo phan loai.
- Anh huong:
  - Du lieu cu duoc gan mac dinh `その他`, khong can sua tay.
  - Can chay migrate truoc khi dung field moi tren runtime.
- Lenh da chay / can chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/phe_duyet/models.py /app-src/phe_duyet/forms.py /app-src/phe_duyet/views.py /app-src/phe_duyet/admin.py /app-src/phe_duyet/migrations/0012_document_category.py`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/phe_duyet_category_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py makemigrations phe_duyet --check --dry-run"`
  - `docker compose run --rm --no-deps -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/phe_duyet_category_check.sqlite3 -v ${PWD}:/app-src web sh -c "cd /app-src && python manage.py check"`
  - Can chay tren DB runtime: `python manage.py migrate phe_duyet`
- Rollback:
  - Revert cac file tren va rollback migration `phe_duyet` ve `0011_remove_document_status` neu can.

### [2026-05-18] Tao app dev/test quan ly xuat-nhap-ton thiet bi setsubi_zaiko
- Pham vi: `setsubi_zaiko/*`, `templates/setsubi_zaiko/*`, `trang_chu/settings.py`, `trang_chu/urls.py`, `ARCHITECTURE.md`
- Noi dung:
  - Tao app moi `setsubi_zaiko` cho quan ly thiet bi/linh kien/may moc Hayashi Techno o ban lap trinh thu nghiem.
  - Them model `EquipmentCategory`, `EquipmentItem`, `EquipmentStockLedger` voi transaction `IN`, `OUT`, `ADJ+`, `ADJ-`, `RETURN`, `SCRAP`.
  - Them UI dashboard, danh sach thiet bi, ledger, form dang ky, CSV export audit va phan trang 10 dong.
  - Seed category mac dinh: san xuat, QA, bao tri, IT, kho, an toan, tieu hao/du phong, khac.
  - Tach ro production: app chi bat khi co env `GTECH_DEV_APPS_ENABLED=true`; URL dev la `/dev/setsubi-zaiko/`.
  - Them `setsubi_zaiko/DEV_RUNBOOK.md` de chay dev/test rieng voi production.
  - Noi app voi user/session Django hien tai bang `login_required`, `request.user`, context processor va sidebar link co dieu kien.
  - Them base template rieng cho `setsubi_zaiko` dung Tailwind CDN voi preflight tat, van extend `trang_chu/base.html` de giu navbar/session he thong.
  - Them env `SQLITE_DB_NAME` de chay localhost dev bang SQLite rieng, tach khoi Docker production DB.
- Anh huong:
  - Docker production hien tai khong tu dong bat app moi neu khong set env.
  - Chua migrate/deploy production cho app nay; day la ban test de lap trinh.
- Lenh da chay / can chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/setsubi_zaiko/models.py /app-src/setsubi_zaiko/forms.py /app-src/setsubi_zaiko/views.py /app-src/setsubi_zaiko/admin.py /app-src/setsubi_zaiko/urls.py /app-src/setsubi_zaiko/apps.py /app-src/setsubi_zaiko/migrations/0001_initial.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/trang_chu/context_processors.py /app-src/setsubi_zaiko/views.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -v ${PWD}:/app-src web python /app-src/manage.py check`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -v ${PWD}:/app-src web python /app-src/manage.py makemigrations setsubi_zaiko --check --dry-run`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -v ${PWD}:/app-src web python /app-src/manage.py test setsubi_zaiko`
  - Khi test DB dev thu cong moi chay `GTECH_DEV_APPS_ENABLED=true python manage.py migrate setsubi_zaiko`.
- Rollback:
  - Tat env `GTECH_DEV_APPS_ENABLED`; xoa app/route neu khong tiep tuc phat trien.

### [2026-05-18] Buoc 1 setsubi_zaiko - nang master thiet bi/linh kien co hinh anh
- Pham vi: `setsubi_zaiko/models.py`, `setsubi_zaiko/forms.py`, `setsubi_zaiko/admin.py`, `templates/setsubi_zaiko/*`, migration `0002`
- Noi dung:
  - Bo sung `item_image` de luu anh ngoai quan thiet bi/linh kien.
  - Bo sung `nameplate_image` de luu anh tem/nhan/serial/model phuc vu nhan dien va audit.
  - Form master ho tro upload file voi `multipart/form-data`.
  - Danh sach thiet bi hien thumbnail neu co anh.
  - Admin hien cot co/khong co anh.
- Anh huong:
  - Master thiet bi/linh kien ro rang hon truoc khi lam sau workflow nhap-xuat-ton.
  - Hinh anh la optional, khong pha du lieu hien co.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/setsubi_zaiko/models.py /app-src/setsubi_zaiko/forms.py /app-src/setsubi_zaiko/admin.py /app-src/setsubi_zaiko/migrations/0002_equipmentitem_images.py /app-src/setsubi_zaiko/tests.py`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_dev_check.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py makemigrations setsubi_zaiko --check --dry-run`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -v ${PWD}:/app-src web python /app-src/manage.py test setsubi_zaiko`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/app-src/db_setsubi_dev.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py migrate setsubi_zaiko`
- Rollback:
  - Neu can bo hinh anh, revert migration `0002` trong DB dev va revert cac field/template/form/admin lien quan.

### [2026-05-18] Buoc 1 setsubi_zaiko - chuan hoa domain nha may ep nhua
- Pham vi: `setsubi_zaiko/models.py`, `setsubi_zaiko/migrations/0003_plastic_factory_categories.py`, `setsubi_zaiko/migrations/0004_alter_equipmentitem_equipment_type.py`, `setsubi_zaiko/DEV_RUNBOOK.md`
- Noi dung:
  - Chuyen huong master theo thuc te cong ty san xuat nhua: JSW射出成形機, 金型, 金型部品, ユーシン取出機, ユーシン取出機部品.
  - Them loai thiet bi/linh kien: JSW成形機部品, 金型部品, 温調機, ホッパードライヤー, コンベア, 油圧部品, 電装部品, 空圧部品.
  - Seed category domain mau cho DB dev de nhan vien chon nhanh khi dang ky master.
- Anh huong:
  - Master phu hop hon voi kho linh kien may ep nhua, khuon va robot lay san pham.
  - Chi ap dung trong app dev/test `setsubi_zaiko`; production Docker khong bi bat app neu khong set env.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/setsubi_zaiko/models.py /app-src/setsubi_zaiko/migrations/0003_plastic_factory_categories.py`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_dev_check.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py makemigrations setsubi_zaiko --check --dry-run`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/app-src/db_setsubi_dev.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py migrate setsubi_zaiko`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -v ${PWD}:/app-src web python /app-src/manage.py test setsubi_zaiko`
- Rollback:
  - Revert migration `0003` va `0004` trong DB dev neu can quay lai nhom thiet bi chung.

### [2026-05-18] Nang UI Tailwind chuyen nghiep cho setsubi_zaiko
- Pham vi: `templates/setsubi_zaiko/*`, `setsubi_zaiko/views.py`, `setsubi_zaiko/models.py`, `setsubi_zaiko/forms.py`, migration `0005`
- Noi dung:
  - Tao app shell Tailwind rieng cho `setsubi_zaiko`, van extend `trang_chu/base.html` de giu login/menu he thong.
  - Dashboard moi co KPI: so master, so hang dang hieu luc, tong so luong, so ledger.
  - Them card phan loai, quick actions, bang ledger moi, bo cuc gon cho PC/tablet.
  - Thiet ke lai danh sach master voi filter theo dai phan loai, loai thiet bi, trang thai, tu khoa.
  - Thiet ke lai ledger list va form dang ky theo style card/table chuyen nghiep.
  - Sua label tieng Nhat chinh trong model/form de tranh hien thi mojibake o UI.
- Anh huong:
  - UI dev app de thao tac hon va phu hop hon voi nhan vien cong ty san xuat nhua.
  - Production Docker khong bi anh huong neu khong bat `GTECH_DEV_APPS_ENABLED`.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/setsubi_zaiko/views.py /app-src/setsubi_zaiko/models.py /app-src/setsubi_zaiko/forms.py`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_dev_check.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py makemigrations setsubi_zaiko --check --dry-run`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/app-src/db_setsubi_dev.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py migrate setsubi_zaiko`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -v ${PWD}:/app-src web python /app-src/manage.py test setsubi_zaiko`
  - Render smoke test `/dev/setsubi-zaiko/`, `/items/`, `/ledger/`, `/items/add/` -> HTTP 200.
  - Playwright login va mo dashboard/form tren `http://127.0.0.1:8001/dev/setsubi-zaiko/`.
- Rollback:
  - Revert template Tailwind va migration `0005` neu can quay lai UI cu.

### [2026-05-18] Them phan loai cha-con kieu MISUMI cho setsubi_zaiko
- Pham vi: `setsubi_zaiko/models.py`, `setsubi_zaiko/forms.py`, `setsubi_zaiko/views.py`, `setsubi_zaiko/admin.py`, `templates/setsubi_zaiko/item_list.html`, migration `0006`
- Noi dung:
  - Them `parent` cho `EquipmentCategory` de quan ly phan loai cha-con.
  - Seed cay phan loai kieu catalog/MISUMI:
    - `成形機 > 電装部品 / 機械部品 / スクリュー関連 / ヒーター・温調部品 / 油圧・空圧部品`
    - `金型 > 入れ子・コア / ピン・エジェクタ / スライド・可動部品 / 冷却・温調部品`
    - `ユーシン取出機 > 電装部品 / 機械部品 / 吸着・チャック部品`
  - Form category co the chon `親分類`; form item hien category theo dang `親分類 > 子分類`.
  - Danh sach master them filter `分類` rieng, neu chon parent thi hien ca child.
- Anh huong:
  - Master gan hon phong cach quan ly cua MISUMI va phu hop kho linh kien may ep nhua.
  - Chi migrate DB dev/test; production Docker van khong bat app neu khong co env.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/setsubi_zaiko/models.py /app-src/setsubi_zaiko/forms.py /app-src/setsubi_zaiko/views.py /app-src/setsubi_zaiko/admin.py /app-src/setsubi_zaiko/migrations/0006_category_hierarchy_misumi_style.py`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_dev_check.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py makemigrations setsubi_zaiko --check --dry-run`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -v ${PWD}:/app-src web python /app-src/manage.py test setsubi_zaiko`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/app-src/db_setsubi_dev.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py migrate setsubi_zaiko`
  - Smoke test `/dev/setsubi-zaiko/items/` -> HTTP 200.
- Rollback:
  - Revert migration `0006` va cac thay doi parent/filter neu can quay lai phan loai phang.

### [2026-05-18] Them truong master linh kien kieu MISUMI cho setsubi_zaiko
- Pham vi: `setsubi_zaiko/models.py`, `setsubi_zaiko/forms.py`, `setsubi_zaiko/admin.py`, `setsubi_zaiko/views.py`, `templates/setsubi_zaiko/*`, migration `0007`
- Noi dung:
  - Them cac truong master chuyen cho linh kien: `社内呼称`, `メーカー品番`, `代替品番`, `適用機械No.`, `適用金型No.`, `棚番`, `最低在庫`, `発注点`.
  - Mo rong form master de nhap cac truong nay.
  - Mo rong danh sach master hien maker品番,代替品番, ap dung may/khuon va棚番.
  - Mo rong tim kiem theo code, ten,社内呼称, maker品番,代替品番,適用機械No.,適用金型No.,棚番, serial/model.
  - Mo rong CSV ton kho de xuat cac cot moi, cac ma/品番/棚番 xuat dang text Excel.
- Anh huong:
  - Master gan hon voi cach quan ly catalog/kho linh kien giong MISUMI.
  - Ho tro quan ly linh kien JSW, khuon, Yushin theo ma hang, vi tri ke va diem dat hang.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/setsubi_zaiko/models.py /app-src/setsubi_zaiko/forms.py /app-src/setsubi_zaiko/views.py /app-src/setsubi_zaiko/admin.py /app-src/setsubi_zaiko/migrations/0007_misumi_item_master_fields.py /app-src/setsubi_zaiko/tests.py`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/tmp/setsubi_dev_check.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py makemigrations setsubi_zaiko --check --dry-run`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -v ${PWD}:/app-src web python /app-src/manage.py test setsubi_zaiko`
  - `docker compose run --rm --no-deps -e GTECH_DEV_APPS_ENABLED=true -e DB_ENGINE=sqlite -e SQLITE_DB_NAME=/app-src/db_setsubi_dev.sqlite3 -v ${PWD}:/app-src web python /app-src/manage.py migrate setsubi_zaiko`
  - Smoke test `/dev/setsubi-zaiko/items/` va `/dev/setsubi-zaiko/export/items.csv` -> HTTP 200.
- Rollback:
  - Revert migration `0007` va bo cac field/UI/CSV lien quan neu chua dung.

### [2026-05-18] Tao G-TECH Codex Kit cho du an moi
- Pham vi: `gtech_codex_kit/*`
- Noi dung:
  - Tao bo rule/template/skill rieng cho Codex khi G-TECH bat dau du an moi.
  - Them template `AGENTS.md` chuan G-TECH, quy tac low-quota, Django on-prem, factory tablet UI, IATF traceability, QR/OCR/RPA va audit export.
  - Them playbook cho Django on-prem, IATF stock/tablet tenken, va mau tai lieu du an can co.
  - Them `GTECH_NEW_PROJECT_PROMPTS.md` huong dan cach dung bo kit va prompt mau de tao app quan ly nhap-xuat-ton thiet bi theo nhom thiet bi.
- Anh huong:
  - Co the copy bo `gtech_codex_kit/` sang du an moi de thiet lap cach lam viec thong nhat cho Codex.
  - Khong anh huong runtime Django hien tai.
- Lenh da chay:
  - Khong can chay test vi chi them tai lieu.
- Rollback:
  - Xoa thu muc `gtech_codex_kit/` va muc changelog nay neu khong dung.

### [2026-05-15] Tang audit trail IATF cho dieu chinh ton kho quet_anh
- Pham vi: `quet_anh/models.py`, `quet_anh/views.py`, `quet_anh/forms.py`, `quet_anh/admin.py`, `templates/quet_anh/*stock*`, migration `0027`
- Noi dung:
  - Them truong audit cho so nhap/xuat kho: `transaction_type`, `adjustment_reason_code`, `adjustment_reason`, `adjustment_note`, `stock_before_kg`, `stock_after_kg`.
  - Them `operator_name` cho so xuat kho de truy vet nguoi thao tac ca dong ADJ-.
  - Chuan hoa `ADJ+` la dieu chinh tang ton kho, `ADJ-` la dieu chinh giam ton kho; UI giai thich ro ADJ la inventory adjustment, khong phai nhap/xuat binh thuong.
  - Dieu chinh ton kho bat buoc chon ly do IATF va nhap memo chi tiet; he thong luu ton truoc/sau, nguoi thao tac, nguoi xac nhan, thoi gian va system No.
  - Backfill cac dong ADJ cu sang reason `migration` de du lieu hien co van giu nguyen va co giai thich audit.
  - Tat xoa cung tren UI va endpoint delete cua so nhap/xuat kho; neu can sua lech thi tao correction/ADJ thay vi xoa du lieu.
- Anh huong:
  - Du lieu ledger cu khong bi xoa.
  - Cac dong dieu chinh moi co traceability tot hon cho audit IATF/khach hang.
  - Nguoi dung khong con xoa cung dong nhap/xuat kho tu UI; thao tac sua lech can dung dieu chinh/correction.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/models.py /app-src/quet_anh/views.py /app-src/quet_anh/forms.py /app-src/quet_anh/admin.py /app-src/quet_anh/migrations/0027_iatf_inventory_audit_fields.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py makemigrations quet_anh --check --dry-run`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py migrate quet_anh`
  - `docker compose build web`
  - `docker compose up -d --force-recreate web`
  - `docker compose exec -T web python manage.py check`
  - Render smoke test `/quet_anh/material-inventory/`, `/quet_anh/material-stock-ledger/`, `/quet_anh/material-out-stock-ledger/` -> HTTP 200.
- Rollback:
  - Revert code/templates/admin/form changes and migrate `quet_anh` ve `0026` neu can. Can can nhac truoc vi migration 0027 them cot audit khong pha du lieu cu.

### [2026-05-15] Them CSV xuat du lieu IATF cho nhap/xuat/ton kho quet_anh
- Pham vi: `quet_anh/views.py`, `quet_anh/urls.py`, templates `material_inventory_dashboard.html`, `material_stock_ledger.html`, `material_out_stock_ledger.html`
- Noi dung:
  - Them export CSV cho 3 man hinh quan ly: nhap kho, xuat kho, ton kho.
  - CSV co header audit gom ten bieu mau, IATF management type, xac nhan dien tu, nguoi xuat, thoi gian xuat, va cam ket giu audit trail.
  - CSV dung UTF-8 BOM mot lan dau file de Excel doc tieng Nhat dung.
  - Giu filter hien tai khi xuat CSV qua query string.
- Anh huong:
  - Co the luu/in CSV lam bang chung audit; cot xac nhan gom trang thai xac nhan, nguoi xac nhan, thoi gian xac nhan.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/views.py /app-src/quet_anh/urls.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - Smoke test 3 endpoint CSV -> HTTP 200, attachment filename OK.
- Rollback:
  - Xoa 3 route CSV va nut CSV tren template neu khong dung nua.

### [2026-05-15] Chuan hoa CSV ma nguyen lieu dang text va phan trang 10 dong
- Pham vi: `quet_anh/views.py`, `templates/quet_anh/material_inventory_dashboard.html`
- Noi dung:
  - Cot `原材料コード` trong CSV nhap kho, xuat kho, ton kho duoc xuat dang text Excel (`="..."`) de tranh bi tu dong doi kieu/lam sai ma.
  - Doi phan trang nhap kho va xuat kho tu 20 ve 10 dong/trang.
  - Them phan trang 10 dong/trang cho man hinh ton kho.
- Anh huong:
  - CSV mo bang Excel giu dung ma nguyen lieu nhu `5102`, `5102-2`.
  - Ba man hinh quan ly nhap/xuat/ton kho gon hon khi du lieu nhieu.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/views.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - Smoke test CSV `material-stock-ledger/export.csv` xac nhan co `="5102"` va trang HTML tra HTTP 200.
- Rollback:
  - Doi lai Paginator ve 20 va xuat `material_code` raw neu can.

### [2026-05-15] Them workflow thu nghiem diem kiem QA tablet theo IATF
- Pham vi: `quet_anh/models.py`, `quet_anh/forms.py`, `quet_anh/views.py`, `quet_anh/urls.py`, `quet_anh/admin.py`, templates `tablet_*`, migration `0028`
- Noi dung:
  - Them model `QATabletDevice` quan ly tablet Android bang ma `QA-TAB-01` den `QA-TAB-04`.
  - Them model `QATabletInspection` ghi diem kiem: `始業前点検`, `定期点検`, `異常時点検`, `復旧確認`.
  - Hang muc diem kiem gom camera, QR sample, OCR/anh, network, lien ket may tram.
  - Co phan loai loi: QR doc khong tot, camera loi, OCR loi, network, may tram, app, hu hong/ban, khac.
  - NG se ghi tablet thanh `使用停止`, nhung day la ban thu nghiem nen khong chan luong scan.
  - Them trang `タブレット点検` tu menu `quet_anh` va trang may.
- Anh huong:
  - Co audit trail cho thiet bi doc QR/tablet truoc khi dung va khi co su co.
  - Chua bat buoc tenken moi duoc scan, dung de thu nghiem van hanh truoc.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/models.py /app-src/quet_anh/forms.py /app-src/quet_anh/views.py /app-src/quet_anh/admin.py /app-src/quet_anh/migrations/0028_tablet_device_inspection.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py makemigrations quet_anh --check --dry-run`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py migrate quet_anh`
  - `docker compose build web`
  - `docker compose up -d --force-recreate web`
  - `docker compose exec -T web python manage.py check`
  - Smoke test `/quet_anh/tablet/`, `/quet_anh/tablet/inspection/add/`, `/quet_anh/` -> HTTP 200.
- Rollback:
  - Revert code/template/admin changes va migrate `quet_anh` ve `0027` neu can xoa workflow tablet.

### [2026-05-15] Them QR doc mau vao workflow diem kiem tablet
- Pham vi: `quet_anh/models.py`, `quet_anh/forms.py`, `quet_anh/views.py`, template `tablet_inspection_form.html`, migration `0029`
- Noi dung:
  - Them field luu bang chung QR: `qr_sample_text`, `qr_sample_checked_at`.
  - Form `タブレット点検登録` co nut `QR読取開始`, dung camera doc QR mau chung.
  - Neu noi dung QR bat dau bang `QA-TABLET-CHECK` thi tu dong set QR OK va result OK.
  - Neu doc sai/noi dung khong khop thi tu dong set QR NG, result NG, problem `QR読取不良`, tablet ghi `使用停止`.
  - Van giu che do thu nghiem: NG khong chan scan thuc te.
- Anh huong:
  - Co bang chung audit ro hon: noi dung QR doc duoc va thoi diem doc.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/models.py /app-src/quet_anh/forms.py /app-src/quet_anh/views.py /app-src/quet_anh/migrations/0029_tablet_inspection_qr_evidence.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py makemigrations quet_anh --check --dry-run`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py migrate quet_anh`
  - Smoke test form GET/POST OK/NG; da xoa record test va tra tablet test ve `active`.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web`
  - `docker compose exec -T web python manage.py check`
- Rollback:
  - Revert template/code va migrate `quet_anh` ve `0028` neu khong dung QR evidence.

### [2026-05-15] Nang UI tablet tenken bang Tailwind va preset loi nhanh
- Pham vi: `templates/quet_anh/tablet_inspection_form.html`
- Noi dung:
  - Lam lai giao dien `タブレット点検登録` bang Tailwind CSS CDN rieng cho trang nay.
  - Them cac preset thao tac nhanh: `異常なし`, `QR読取不良`, `カメラ不良`, `OCR不良`, `通信不良`, `端末連携不良`, `アプリ動作不良`, `破損・汚れ`.
  - Khi bam preset NG, form tu set判定=NG, 異常分類, 異常内容, 処置内容 va bo check hang muc lien quan.
  - Giu nut QR camera scan va luu QR evidence nhu truoc.
- Anh huong:
  - Nhan vien thao tac tenken nhanh hon, du lieu nhap dong nhat hon cho audit.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - Render smoke test `/quet_anh/tablet/inspection/add/` -> HTTP 200, co Tailwind, QR button va preset.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web`
  - `docker compose exec -T web python manage.py check`
- Rollback:
  - Revert template ve giao dien Bootstrap cu neu Tailwind CDN khong phu hop mang noi bo.

### [2026-05-15] Toi uu UI tablet tenken cho trinh duyet tren tablet
- Pham vi: `templates/quet_anh/tablet_inspection_form.html`
- Noi dung:
  - Dieu chinh spacing/card/header/form control cho man hinh tablet.
  - Preset loi hien 4 cot tren tablet ngang, 2 cot tren mobile.
  - QR reader gioi han chieu rong/chieu cao hop ly de khong day trang qua dai.
  - Action bar tren tablet chuyen ve static de khong che noi dung.
- Anh huong:
  - Trang tenken gon va de thao tac hon tren tablet Android.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - Render smoke test `/quet_anh/tablet/inspection/add/` -> HTTP 200, co class tablet responsive.
  - `docker compose build web`
  - `docker compose up -d --force-recreate web`
  - `docker compose exec -T web python manage.py check`
- Rollback:
  - Revert cac style responsive trong template neu can quay lai bo cuc cu.

### [2026-05-13] Dieu chinh thang ke hoach nhan nguyen lieu theo ngay upload
- Pham vi: `iot/views_csv.py`, `iot/views_center2.py`
- Noi dung:
  - Khi upload CSV ke hoach nguyen lieu, he thong doc thang tren CSV truoc.
  - Neu thang CSV nho hon thang upload hien tai thi tu dong chuyen sang thang upload hien tai de tranh import ke hoach ve qua khu.
  - Truong hop upload truoc thang ke hoach, vi du thang 4 upload CSV thang 5, van giu thang 5 theo CSV.
  - Dong bo dashboard doc du dai may gia nguyen lieu `200-220`, khop voi luong upload CSV.
- Anh huong:
  - CSV cu ghi thang 4 neu upload trong thang 5 se tao plan_date thang 5, dashboard co the hien thi ke hoach hom nay/ngay mai.
  - Da cap nhat du lieu ke hoach nguyen lieu hien tai tu thang 4 sang thang 5 theo ngay upload hien tai.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/iot/views_csv.py /app-src/iot/views_center2.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src -w /app-src web python manage.py shell` de test `_parse_month_header`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - `docker compose exec -T web python manage.py shell` de doi 37 dong ke hoach nguyen lieu hien tai tu `2026-04` sang `2026-05`
- Lenh deploy da chay:
  - `docker compose build`
  - `docker compose --profile workers up -d --force-recreate`
  - `docker compose exec -T web python manage.py check`
- Rollback:
  - Bo tham so `upload_date` khi parse CSV nguyen lieu neu can cho phep import nguoc ve thang qua khu.

### [2026-05-13] Nhap kho nhieu lot gui tong kg mot lan
- Pham vi: `quet_anh/views.py`
- Noi dung:
  - Luong nhap kho sau buoc 品名確認 chi gui 1 lenh sang may tram voi tong kg cua tat ca lot.
  - Django van tao nhieu dong `QAMaterialStockLedger` theo tung lot, cung `注文No.` va cung ma dang ky may tram.
  - Payload job co them `lot_number` de de truy vet lot trong log/phien nhap lieu.
- Anh huong:
  - Tranh loi lot 2 bi gui tiep khi app may tram da dong/khong con dung o o kg.
  - Du lieu ton kho Django van quan ly duoc tung lot, con may tram nhan dung tong kg cua 1 lan nhap kho.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/views.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - `docker compose build web`
  - `docker compose up -d --force-recreate web`
  - `docker compose exec -T web python manage.py check`
- Rollback:
  - Co the quay lai cach lap tung lot trong `stock_in_start`, nhung khong khuyen nghi vi da gay loi HTTP 500/khong cong lot sau.

### [2026-05-13] Hien thi nguoi thao tac nhap kho va so bao ton kho
- Pham vi: `quet_anh/models.py`, `quet_anh/views.py`, `quet_anh/signals.py`, `quet_anh/forms.py`, `templates/quet_anh/material_stock_ledger.html`, `templates/quet_anh/material_inventory_dashboard.html`, migration `0026`
- Noi dung:
  - Them `operator_name` vao `QAMaterialStockLedger`.
  - Luu ten user dang dang nhap khi tao dong nhap kho thu cong va dong dieu chinh ADJ nhap kho.
  - Backfill `operator_name` tu `qa_result.operator_name` cho cac dong co lien ket anh kiem tra.
  - Bang nhap kho hien `operator_name`, fallback ve `qa_result.operator_name` neu co.
  - Bang ton kho hien them so bao hien tai, so bao nhap, so bao xuat tinh theo `bag_weight_kg` cua master.
- Anh huong:
  - Luong nhap kho hien dung nguoi thao tac cho cac phien moi sau migration.
  - Dashboard ton kho co du lieu so bao nguyen lieu ben canh kg.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/views.py /app-src/quet_anh/models.py /app-src/quet_anh/signals.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py makemigrations quet_anh --check --dry-run`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`

### [2026-05-12] Them dieu chinh ton kho bang superuser
- Pham vi: `quet_anh/views.py`, `quet_anh/urls.py`, `templates/quet_anh/material_inventory_dashboard.html`
- Noi dung:
  - Gioi han quyen dieu chinh ton kho ve `is_superuser`.
  - Them nut `調整` tren dashboard ton kho cho superuser.
  - Superuser co the nhap ton kho dung hoac chenhlech kg; he thong tu tao but toan `ADJ` dang nhap kho neu tang, xuat kho neu giam.
  - Dong dieu chinh duoc danh dau supervisor confirmed va giu trong ledger de truy vet, khong sua mat dau du lieu cu.
  - Cho trang xuat kho hien ca dong dieu chinh `auto_input_ledger=None`.
- Anh huong:
  - Co the can thiep cac ma ton kho dang lech ma van giu audit trail.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python -m py_compile /app-src/quet_anh/views.py`
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`

### [2026-05-12] Toi uu man hinh nhap kho cho tablet
- Pham vi: `templates/quet_anh/stock_in_start.html`
- Noi dung:
  - O nhap lot nguyen lieu chuyen sang `readonly`/`inputmode=none` de khong bat ban phim mac dinh tren tablet.
  - Them modal ban phim rieng co so, chu cai A-Z va ky tu lot thong dung (`-`, `/`, `.`), dung duoc cho ca dong lot tao moi.
  - Dieu chinh bo cuc tablet: thu nho nut/phim, giam padding, gioi han chieu cao modal theo man hinh va cho modal-body cuon khi can.
- Anh huong:
  - Nguoi thao tac nhap so lot bang phim noi bo giong cach nhap kg, giam loi cham nham tren tablet.
  - Man hinh nhap kg/lot hien duoc day du hon tren tablet dung ngang/doc, khong bi che mat nut xac nhan.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - `docker compose build web`
  - `docker compose up -d --force-recreate web`

### [2026-05-12] Dong bo modal nhap lot cho luong xuat kho tren tablet
- Pham vi: `templates/quet_anh/upload.html`
- Noi dung:
  - Doi o `ロット番号` cua luong xuat kho sang `readonly`/`inputmode=none` de khong bat ban phim mac dinh tren tablet.
  - Them modal ban phim lot gom so, chu cai A-Z va ky tu `-`, `/`, `.`.
  - Lam gon modal kg va bo cuc tablet cua man hinh xuat kho: giam padding, thu nho phim/nut, gioi han chieu cao modal va cho modal-body cuon khi can.
- Anh huong:
  - Thao tac nhap lot/so kg dong nhat giua nhap kho va xuat kho, hien thi day du hon tren tablet.
- Lenh da chay:
  - `docker compose run --rm --no-deps -v ${PWD}:/app-src web python /app-src/manage.py check`
  - Chua rebuild/recreate `web` theo yeu cau can hoi y kien truoc khi cap nhat Docker runtime.

### [2026-05-12] Sua loi callback quet_anh tren PostgreSQL
- Pham vi: `quet_anh/views.py`, `trang_chu/settings.py`, `nginx/conf.d/seizo0.conf`, Docker runtime `web`/`nginx`
- Noi dung:
  - Bo `select_related("chuong_trinh", "may_tinh")` khoi query `select_for_update()` khi finalize job nhap lieu tu app quet anh.
  - Doi mac dinh `POSTGRES_CONN_MAX_AGE` tu 60 ve 0 de giam nguy co day ket noi PostgreSQL khi dashboard polling day.
  - Tang nginx proxy timeout len 300s de request `/quet_anh/upload/` khong bi 504 khi OCR/may tram xu ly lau.
  - Sua buoc nhap kho `品名確認`: may tram tra ve 品名 va 注文No dang xu ly de nguoi thao tac kiem tra; Django khong tu dong so khop/chan theo ten nguyen lieu.
- Anh huong:
  - Tranh loi PostgreSQL `FOR UPDATE cannot be applied to the nullable side of an outer join`.
  - Callback may tram it bi 500 do `too many clients already` hon, doi lai moi request se mo/dong connection DB.
  - Request upload anh co them thoi gian cho OCR/callback; model OCR nen duoc cai san bang script neu rebuild container sach.
  - Cac nguyen lieu co ten gan nhau nhu `HNI-B625 第一` / `HNI-B625 第二` van dung duoc; quyet dinh dung/sai do nguoi thao tac xac nhan tren man hinh.
- Lenh da chay / can chay:
  - `docker compose build web`
  - `docker compose up -d --force-recreate web`
  - `docker compose exec -T nginx nginx -s reload`
  - `docker compose exec -T web python manage.py check`
- Rollback:
  - Co the revert 2 dong code neu can quay lai hanh vi cu; khong khuyen nghi tren PostgreSQL hien tai.

### [2026-05-11] Chuyen DB runtime tu SQLite sang PostgreSQL
- Pham vi: `docker-compose.yml`, `settings.py`, `requirements.txt`, `iot`, `xu_ly_anh`, Docker runtime, `ARCHITECTURE.md`, `.env.example`
- Noi dung:
  - Them service Docker `postgres` dung image `postgres:16-alpine`, volume `postgres-data`.
  - Them cau hinh Django chon DB qua env `DB_ENGINE`; Docker web mac dinh dung PostgreSQL.
  - Them dependency `psycopg2-binary==2.9.11`.
  - Export SQLite sach thanh `backup_db/postgres_migration/sqlite_dump_20260511_172616.json`.
  - Tao snapshot SQLite truoc migration: `backup_db/postgres_migration/db_before_postgres_20260511_172616.sqlite3`.
  - Migrate schema sang PostgreSQL va import thanh cong 47249 object.
  - Sua migration `xu_ly_anh.0002` de chi chay SQL SQLite khi backend la SQLite.
  - Sua signal `UserProfile` bo qua `raw=True` de `loaddata` khong tao profile trung.
  - Noi `iot.MailLog` (`mail_uid`, `sender`, `subject`) de nhap du lieu mail cu hop le tren PostgreSQL.
  - Bat lai `iot-worker-serial` tren PostgreSQL, giu cac worker IoT rieng le disabled.
  - Tao backup PostgreSQL sau migration: `backup_db/postgres/seizo0_postgres_20260511_174911.dump`.
- Anh huong:
  - Runtime chinh khong con ghi vao SQLite `db.sqlite3`, giam nguy co `database disk image is malformed`.
  - `iot-worker-serial` va dashboard dang chay tren PostgreSQL.
  - Backup van hanh da duoc cap nhat de tao PostgreSQL dump, khong dua vao `db.sqlite3`.
- Lenh da chay:
  - `docker compose build web`
  - `docker compose up -d postgres redis`
  - `python manage.py dumpdata ... sqlite_dump_20260511_172616.json`
  - `python manage.py migrate`
  - `python manage.py loaddata backup_db/postgres_migration/sqlite_dump_20260511_172616.json`
  - `docker compose up -d web nginx`
  - `docker compose --profile workers up -d --force-recreate iot-worker-serial fax-reminder-daily`
- Rollback:
  - Set `DB_ENGINE=sqlite`, stop PostgreSQL-dependent containers, and restore `db.sqlite3` tu snapshot/backup neu can quay lai tam thoi.

### [2026-05-11] Cap nhat backup tu dong sang PostgreSQL
- Pham vi: `Dockerfile`, `iot/management/commands/backup_runtime_data.py`, `scripts/backup_runtime_to_drive.ps1`, `PROJECT_CHANGELOG.md`, `SERVER_HANDOFF.md`
- Noi dung:
  - Cai `postgresql-client` trong Docker image de co `pg_dump`/`pg_restore`.
  - `backup_runtime_data` tu nhan backend DB: PostgreSQL thi tao `postgres/seizo0_postgres.dump`, SQLite thi giu co che backup SQLite cu.
  - Script PowerShell backup runtime chay container backup trong Docker network cua project de ket noi duoc service `postgres`.
  - File zip backup moi co `manifest.json` ghi `database_kind=postgresql`.
- Anh huong:
  - Backup tu dong hang ngay se la du lieu PostgreSQL runtime hien tai.
  - Khong nen xem `db.sqlite3` la nguon backup chinh sau moc 2026-05-11.
- Lenh da chay:
  - `docker compose build web`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_runtime_to_drive.ps1 -SkipUpload -KeepBackupCount 3`
  - `pg_restore -l postgres/seizo0_postgres.dump`
- Ket qua:
  - Tao thanh cong `backup_db/daily/seizo0_runtime_backup_20260511_181452.zip`.
  - Zip chua `postgres/seizo0_postgres.dump`, manifest ghi `database_kind=postgresql`, `pg_restore -l` doc duoc 707 TOC entries.

### [2026-05-11] Kiem tra lai nguy co mat du lieu khi chuyen PostgreSQL
- Pham vi: `db.sqlite3`, `db.sqlite3.malformed_20260511_171737`, PostgreSQL runtime
- Noi dung:
  - Xac minh `db.sqlite3` hien tai con doc duoc, `PRAGMA integrity_check = ok`.
  - Xac minh `backup_db/postgres_migration/db_before_postgres_20260511_172616.sqlite3` co SHA256 trung voi `db.sqlite3` tai moc migration.
  - Doc file malformed bang che do cuu ho read-only `PRAGMA writable_schema=ON` de so sanh count/ID cac bang chinh.
- Ket qua:
  - PostgreSQL khong thieu ID nao so voi file malformed trong cac bang da doi chieu: `iot_chatworkmessage`, `iot_net100cycleshot`, `iot_productmonthlyshot`, `menu_order`, `menu_faxstatus`, `iot_maillog`.
  - PostgreSQL hien co them record moi do worker chay sau migration: `iot_chatworkmessage` +3, `iot_net100cycleshot` +11 so voi file malformed.

### [2026-05-11] Cuu bu du lieu app quet_anh hom nay tu SQLite malformed
- Pham vi: PostgreSQL runtime, `db.sqlite3.malformed_20260511_171737`, `backup_db/quetanh_recovery/`, `backup_db/postgres/`
- Noi dung:
  - Kiem tra rieng cac bang `quet_anh_*`, `xu_ly_anh_*`, va `nhap_lieu_*` lien quan luong quet anh.
  - Phat hien PostgreSQL thieu du lieu `quet_anh` hom nay trong file SQLite malformed luc 17:17.
  - Tao backup truoc khi cuu: `backup_db/postgres/seizo0_before_quetanh_recover_20260511_184335.dump`.
  - Tao SQLite recovered sach tu file malformed: `backup_db/quetanh_recovery/recovered_20260511_171737.sqlite3`.
  - Import bu vao PostgreSQL:
    - `quet_anh_qaresult`: ID 2370-2376
    - `nhap_lieu_phiennhaplieu`: ID 118-119
    - `nhap_lieu_ketquanhaplieu`: ID 106-107
    - `quet_anh_qaautoinputledger`: ID 96-97, dung lai tu `PhienNhapLieu` + `QAResult` vi phan nay trong SQLite malformed khong recover duoc day du cot.
    - `quet_anh_qamaterialoutstockledger`: ID 66-67
  - Xac minh media cua 7 QA result hom nay van con day du trong `media/quet_anh2/` va `media/quet_anh2/processed/`.
  - Tao backup sau khi cuu: `backup_db/postgres/seizo0_after_quetanh_recover_20260511_184758.dump`.
- Ket qua:
  - PostgreSQL hien co 7 `QAResult` ngay 2026-05-11, ID 2370-2376.
  - `QAMaterialOutStockLedger` hom nay co 2 dong, ID 66-67.
  - `nhap_lieu` lien quan co 2 phien va 2 ket qua callback hom nay.
  - So sanh sau cuu: khong con ID thieu trong cac bang `quet_anh`/`nhap_lieu` da recover duoc.
- Lenh kiem tra:
  - `docker compose exec -T web python manage.py check` -> OK.

### [2026-05-11] Them handoff doc cho doi server
- Pham vi: `SERVER_HANDOFF.md`, `ARCHITECTURE.md`, `DOCKER_DEPLOY.md`, `RESTORE_FROM_DRIVE.md`
- Noi dung:
  - Them doc tom tat nhanh tinh trang runtime PostgreSQL, container can chay, worker policy, backup/restore va lenh check.
  - Cap nhat Docker/restore docs de tranh hieu nham `db.sqlite3` la DB chinh.
- Anh huong:
  - Khi doi server, chi can doc `SERVER_HANDOFF.md` truoc de biet cach start/restore/kiem tra.
- Lenh can chay:
  - Khong co.
- Rollback:
  - Revert cac thay doi tai lieu neu co quy trinh handoff khac.

### [2026-05-11] Dieu chinh worker IoT tuan tu, bo fetch mail notify
- Pham vi: `docker-compose.yml`, `iot/management/commands/run_iot_workers_serial.py`, `ARCHITECTURE.md`
- Noi dung:
  - Loai `fetch_mail_notify` khoi `run_iot_workers_serial`.
  - Doi cac service worker IoT rieng le sang profile `disabled` de tranh chay song song khi bat nham profile `iot-workers`.
  - Giam tan suat worker IoT tuan tu: nhom nhanh 30 giay, nhom cham 180 giay.
  - Them SQLite `quick_check` dinh ky 300 giay trong worker tuan tu; neu DB bao loi thi worker dung ghi tiep va thoat sau 60 giay de Docker restart.
- Anh huong:
  - Cac job IoT quan trong van chay tuan tu, giam ap luc ghi SQLite.
  - Mail notify tu command `fetch_mail_notify` se khong tu chay.
- Lenh can chay:
  - `docker compose up -d --force-recreate iot-worker-serial`
- Rollback:
  - Them lai `fetch_mail_notify` vao slow commands va doi interval/profile ve gia tri cu neu can.

### [2026-05-11] Restore SQLite lan 2 va tam dung IoT worker
- Pham vi: `db.sqlite3`, `trang_chu/signals.py`, Docker runtime
- Noi dung:
  - `/iot/dashboard/` lai bao `database disk image is malformed` luc 2026-05-11 17:16 JST.
  - Dung `iot-worker-serial` va `web`, luu DB hong thanh `db.sqlite3.malformed_20260511_171737`.
  - Restore DB tu `backup_db/db_backup_20260511_025040.sqlite3` sau khi kiem tra `integrity_check=ok`, `foreign_key_check=0`.
  - Doi `iot-worker-serial` runtime restart policy thanh `no` va giu worker IoT dung.
  - Doi `iot-worker-serial` trong compose sang profile `disabled` de `docker compose --profile workers up -d` khong bat lai IoT worker.
  - Bo auto `PRAGMA journal_mode=WAL` trong `trang_chu/signals.py`; giu SQLite o che do bao thu voi `synchronous=FULL` va `busy_timeout=30000`.
- Anh huong:
  - Web va `/iot/dashboard/` chay lai bang DB backup sach.
  - Du lieu phat sinh sau moc backup co the khong nam trong DB hien tai.
  - IoT worker tam dung de uu tien on dinh DB; can chuyen DB/worker an toan hon truoc khi bat lai.
- Lenh da chay:
  - `docker stop trang_chu-iot-worker-serial-1 seizo0-django`
  - `Copy-Item backup_db\db_backup_20260511_025040.sqlite3 db.sqlite3 -Force`
  - `docker update --restart=no trang_chu-iot-worker-serial-1`
- Rollback:
  - Co the doi `db.sqlite3.malformed_20260511_171737` ve lai ten tam de dieu tra/cuu du lieu, khong ghi de file nay.

### [2026-05-11] Khoi phuc OCR Paddle cho app quet_anh
- Pham vi: `requirements.txt`, Docker runtime `seizo0-django`, `scripts/install_paddleocr_models.sh`
- Noi dung:
  - Dieu tra loi OCR khong tao du lieu trong log/mail cua app quet anh.
  - Phat hien `paddleocr 3.5.0` khong tuong thich code cu `PaddleOCR(..., rec=True, det=True)`.
  - Ha ve bo OCR on dinh: `paddleocr==2.7.3`, `paddlepaddle==2.6.2`, `numpy==1.26.4`, `opencv-python==4.6.0.66`.
  - Khoa them cac dependency phu de tranh crash native khi import/chay OCR.
  - Tai va giai nen san model PaddleOCR trong container de tranh loi tu dong giai nen model bang Python.
  - Them script `scripts/install_paddleocr_models.sh` de chuan bi model OCR khi restore/rebuild server.
  - Giu nguyen logic so sanh trong `quet_anh/views.py`; chi sua moi truong plugin OCR.
- Anh huong:
  - OCR da doc duoc text tu anh thuc te trong `media/quet_anh2`.
  - Neu rebuild image, can cai theo `requirements.txt` moi de giu dung version.
- Lenh da chay:
  - `docker exec seizo0-django pip install ...`
  - `docker exec seizo0-django bash /app/scripts/install_paddleocr_models.sh`
  - `docker exec seizo0-django python manage.py check`
  - OCR smoke test voi `media/quet_anh2/captured_1eQWa14.png`.
- Rollback:
  - Revert cac pin OCR trong `requirements.txt` neu chuyen sang engine OCR khac.

### [2026-05-11] Phuc hoi SQLite sau loi malformed va dung worker IoT song song
- Pham vi: `db.sqlite3`, Docker runtime, `backup_db/`, `nginx/conf.d/seizo0.conf`, `SERVER_RECOVERY_RUNBOOK.md`
- Noi dung:
  - `/iot/dashboard/` bao `database disk image is malformed`.
  - Dung cac container worker ghi DB song song: `update-net100-shots`, `fetch-mail-notify`, `sync-chatwork`, `update-machine-counter`, `update-esp32-shot`, `update-mold-shot`, `iot-worker-serial`.
  - Luu DB hong thanh `db.sqlite3.malformed_20260511_114903`.
  - Restore `db.sqlite3` tu full backup `backup_db/daily/seizo0_runtime_backup_20260511_103348.zip`.
  - Kiem tra sau restore: `PRAGMA integrity_check = ok`, `foreign_key_check = 0`.
  - `/iot/dashboard/` tra HTTP 200 sau restore.
  - Doi restart policy cac worker ghi DB da dung sang `no` de tranh tu bat lai sau Docker restart.
  - Sua nginx proxy dung Docker DNS dong (`resolver 127.0.0.11`) de tranh 502 khi container web restart va doi IP.
  - Tao `SERVER_RECOVERY_RUNBOOK.md` ghi lai quy trinh xu ly SQLite malformed va nginx 502.
- Anh huong:
  - Du lieu trong DB quay ve moc backup 2026-05-11 10:33:48.
  - Cac thao tac sau moc backup co the khong con trong DB hien tai.
  - Cac worker IoT nen khong tu chay; can can nhac chien luoc DB/worker an toan truoc khi bat lai.
- Lenh da chay:
  - `docker stop ...worker...`
  - Restore DB tu zip backup.
  - `docker update --restart=no ...worker...`
  - `python backup_sqlite.py`
- Rollback:
  - File DB hong van duoc giu tai `db.sqlite3.malformed_20260511_114903` de dieu tra/cuu du lieu neu can.

### [2026-05-11] Them backup du lieu hang ngay va upload Google Drive
- Pham vi: `iot/management/commands/backup_runtime_data.py`, `backup_sqlite.py`, `scripts/backup_runtime_to_drive.ps1`, `scripts/install_daily_backup_task.ps1`, `BACKUP_DRIVE.md`, `RESTORE_FROM_DRIVE.md`, `ARCHITECTURE.md`
- Noi dung:
  - Them command `backup_runtime_data` tao zip backup gom SQLite DB bang SQLite backup API, `media/`, va mot so file van hanh nho.
  - Backup DB duoc chay `PRAGMA integrity_check` truoc khi dong goi.
  - Cap nhat `backup_sqlite.py` cu de chi giu 2 file `db_backup_*.sqlite3` moi nhat.
  - Them PowerShell script tao backup local va upload Google Drive qua `rclone` neu da cau hinh.
  - Mac dinh chi giu 2 file backup moi nhat o local va Google Drive de tranh ton dung luong.
  - PowerShell script mac dinh backup full runtime: source code, DB, `media/`, `staticfiles/`, `logs/`, `nginx/`, `.env` va file deploy.
  - Khi khong co `rclone`, script copy backup vao Google Drive Desktop folder `G:\マイドライブ\seizo0-backups`.
  - Them `RESTORE_FROM_DRIVE.md` huong dan khoi phuc server moi tu file backup tren Drive.
  - Them script cai Windows Task Scheduler de chay hang ngay.
- Anh huong:
  - Co the khoi phuc server moi bang source code + zip backup runtime.
  - `.env` va source code duoc gom trong backup PowerShell mac dinh de phuc hoi server gan nhu y nguyen; can bao ve file backup tren Google Drive.
- Lenh can chay:
  - Test local: `.\scripts\backup_runtime_to_drive.ps1 -SkipUpload`
  - Sau khi cau hinh `rclone`: `.\scripts\backup_runtime_to_drive.ps1 -RcloneRemote "gdrive:seizo0-backups"`
  - Cai lich: `.\scripts\install_daily_backup_task.ps1 -RcloneRemote "gdrive:seizo0-backups"`
- Rollback:
  - Xoa scheduled task `Seizo0 Daily Backup`, xoa cac script/file command neu khong dung nua.

### [2026-05-11] Ho tro lai WebSocket path cu cua ESP32
- Pham vi: `iot/esp32_bridge.py`, `ARCHITECTURE.md`
- Noi dung:
  - Them alias WebSocket `ws://192.168.10.250:9000/ws/esp32/buttons/` dung voi firmware ESP32 hien tai.
  - Giu nguyen cac path moi `/esp32/ws/` va `/ws/`.
- Anh huong:
  - ESP32 cu co the ket noi lai port `9000` ma khong can nap lai firmware.
- Lenh can chay:
  - `docker compose build web`
  - `docker compose up -d --force-recreate esp32-bridge`
- Rollback:
  - Xoa route `/ws/esp32/buttons/` trong `iot/esp32_bridge.py` va recreate service.

### [2026-05-06] Them ESP32 bridge WebSocket/HTTP tren port 9000
- Pham vi: `iot/esp32_bridge.py`, `docker-compose.yml`, `requirements.txt`, `ARCHITECTURE.md`
- Noi dung:
  - Tao service `esp32-bridge` chay tren port `9000` de thay service ESP32 cu khong con trong server moi.
  - Ho tro HTTP:
    - `GET /esp32/api/button_status/` tra ve `{"devices": [...]}`
    - `POST /esp32/api/button_status/` nhan JSON cap nhat trang thai thiet bi.
  - Ho tro WebSocket:
    - `ws://192.168.10.250:9000/esp32/ws/`
    - `ws://192.168.10.250:9000/ws/`
  - Luu trang thai cuoi vao `logs/esp32_bridge_state.json`.
  - Them dependency `aiohttp` va rebuild image `seizo0-django:latest`.
- Anh huong:
  - `/iot/api/esp32_machines/` khong con loi connection refused toi port 9000.
  - Hien tai state test da duoc xoa; API se rong cho den khi ESP32 that gui data.
- Lenh can chay:
  - `docker compose build web`
  - `docker compose up -d --force-recreate web esp32-bridge`
  - `docker compose --profile workers up -d --force-recreate iot-worker-serial fax-reminder-daily`
- Rollback:
  - Stop bridge: `docker compose stop esp32-bridge`
  - Neu co service ESP32 cu, dam bao no bind lai port `9000`.

### [2026-05-06] Chay worker IoT theo kieu tuan tu cho SQLite
- Pham vi: `iot/management/commands/run_iot_workers_serial.py`, `docker-compose.yml`
- Noi dung:
  - Them command `run_iot_workers_serial` de chay cac command IoT lan luot trong mot process.
  - Nhom 10 giay: `update_machine_counter`, `update_mold_shot`, `update_esp32_shot`.
  - Nhom 60 giay: `update_net100_shots`, `sync_chatwork`, `fetch_mail_notify`.
  - Them service Docker `iot-worker-serial` trong profile `workers`.
  - Rebuild image `seizo0-django:latest` de dua command moi vao container.
- Anh huong:
  - Du lieu realtime IoT co the cap nhat tu dong ma khong can bat 6 container ghi DB song song.
  - Sau hon 2 phut theo doi, `iot-worker-serial` chay on dinh va SQLite `integrity_check` van OK.
- Lenh can chay:
  - `docker compose build web`
  - `docker compose --profile workers up -d iot-worker-serial fax-reminder-daily`
- Rollback:
  - Stop worker tuan tu: `docker compose stop iot-worker-serial`.
  - Khong khuyen nghi bat lai profile `iot-workers` khi van dung SQLite tren Windows bind mount.

### [2026-05-06] Kiem tra mail va tach worker IoT tan suat cao
- Pham vi: `docker-compose.yml`, SMTP/runtime workers
- Noi dung:
  - Kiem tra SMTP Gmail trong Docker: co user/password, mo ket noi SMTP thanh cong.
  - Gui mail test bang Django `send_mail`: ket qua `send_result=1`.
  - Sau khi bat cac worker tan suat cao, `update-mold-shot` lam SQLite bao `database disk image is malformed`.
  - Da dung toan bo worker ghi DB, luu file loi thanh `db.sqlite3.malformed_after_iot_workers_20260506_122744`, restore lai DB sach tu `backup_db/db_before_workers_20260506_031920.sqlite3`.
  - Tách cac worker IoT/mail/chatwork tan suat cao sang profile `iot-workers`; profile `workers` chi giu `fax-reminder-daily`.
- Anh huong:
  - Mail cho `menu`, `quet_anh`, `learn` co the gui qua SMTP hien tai.
  - Khong nen bat `iot-workers` tren SQLite Windows bind mount neu chua doi chien luoc DB/worker, vi co nguy co lam hong DB.
  - `/iot/api/esp32_machines/` hien tra loi 500 vi service ESP32 ngoai tai `192.168.10.250:9000` dang khong ket noi duoc.
- Lenh can chay:
  - Auto FAX an toan: `docker compose --profile workers up -d fax-reminder-daily`
  - Chi bat worker IoT khi chap nhan rui ro/da sua DB: `docker compose --profile iot-workers up -d`
- Rollback:
  - Doi profile cac worker IoT ve `workers` neu muon hanh vi cu, nhung khong khuyen nghi khi dung SQLite.

### [2026-05-06] Tu dong chay nhac FAX com trua luc 14:50
- Pham vi: `docker-compose.yml`
- Noi dung:
  - Them service `fax-reminder-daily` trong profile `workers`.
  - Service kiem tra gio Nhat (`JST-9`) va moi ngay luc `14:50` chay `python manage.py fax_reminder --force`.
  - Giu service `fax-reminder` profile `manual` de van co the chay tay khi can.
- Anh huong:
  - Khi `docker compose --profile workers up -d` dang chay, he thong se tu dong nhac mail FAX com trua mot lan moi ngay luc 14:50.
- Lenh can chay:
  - `docker compose --profile workers up -d fax-reminder-daily`
- Rollback:
  - Stop service: `docker compose stop fax-reminder-daily`

### [2026-05-06] Tam dung worker Docker de bao ve SQLite
- Pham vi: `docker-compose.yml`, `db.sqlite3`
- Noi dung:
  - Khi test `/quet_anh/` va luong nhap kho tren iPhone, Django bao `DatabaseError: database disk image is malformed`.
  - Dung cac worker nen co kha nang ghi DB, luu file loi thanh `db.sqlite3.malformed_20260506_121302`.
  - Phuc hoi lai `db.sqlite3` tu `backup_db/db_backup_20260428_163203.sqlite3`.
  - Kiem tra `PRAGMA integrity_check`: OK; `PRAGMA foreign_key_check`: 0 loi; hash DB trung backup 2026-04-28.
  - Dua cac service nen ghi DB vao Docker profile `workers`, de `docker compose up -d` mac dinh chi chay `web`, `nginx`, `redis`.
- Anh huong:
  - Web va app `/quet_anh/` chay lai binh thuong; request chua login tra `302` ve `/login/` thay vi `500`.
  - Cac tac vu nen nhu mail, machine counter, mold shot, esp32, net100, chatwork tam thoi khong tu chay de tranh SQLite hong lai.
- Lenh can chay:
  - Mac dinh: `docker compose up -d web nginx redis`
  - Chi bat worker khi chap nhan rui ro SQLite/concurrency: `docker compose --profile workers up -d`
- Rollback:
  - Xoa `profiles: [workers]` o cac service nen neu muon quay lai hanh vi cu.
- Ghi chu:
  - Nen uu tien backup SQLite bang SQLite backup API va can nhac chuyen DB khoi Windows bind mount neu can chay nhieu worker ghi lien tuc.

### [2026-05-06] Kiem tra va phuc hoi SQLite sach cho Docker
- Pham vi: `db.sqlite3`, `backup_db/`
- Noi dung:
  - Khi chay Docker, SQLite hien tai bao loi `database disk image is malformed`.
  - Da dung cac container co kha nang ghi DB truoc khi thao tac.
  - Doi file DB hong thanh `db.sqlite3.corrupt_20260506_115717`.
  - Phuc hoi `db.sqlite3` tu backup sach `backup_db/db_backup_20260428_163203.sqlite3`.
  - Chay `PRAGMA integrity_check`, `PRAGMA quick_check`, va `PRAGMA foreign_key_check`: tat ca OK, foreign key error = 0.
  - Tao backup verified moi bang SQLite backup API: `backup_db/db_verified_20260506_115907.sqlite3`.
- Anh huong:
  - DB hien tai khong con bi corrupt theo kiem tra SQLite.
  - Du lieu sau thoi diem backup 2026-04-28 co the khong nam trong DB hien tai; file corrupt cu van duoc giu de phuc hoi neu can.
- Lenh can chay:
  - `docker compose run --rm web python manage.py check`
  - `docker compose up -d` chi sau khi xac nhan muon chay lai worker ghi DB.
- Rollback:
  - Dung file `db.sqlite3.corrupt_20260506_115717` de dieu tra/cuu du lieu, khong ghi de len file nay.

### [2026-05-06] Dat DB chinh ve dung backup 2026-04-28
- Pham vi: `db.sqlite3`, `backup_db/db_backup_20260428_163203.sqlite3`
- Noi dung:
  - Theo yeu cau van hanh, lay `backup_db/db_backup_20260428_163203.sqlite3` lam nguon du lieu chinh xac nhat.
  - Luu DB truoc khi restore thanh `db.sqlite3.before_restore_20260428_20260506_120220`.
  - Copy lai backup 2026-04-28 vao `db.sqlite3`.
  - Kiem tra `PRAGMA integrity_check`: OK.
  - Kiem tra `PRAGMA foreign_key_check`: 0 loi.
  - Hash SHA256 cua `db.sqlite3` trung 100% voi backup 2026-04-28.
- Anh huong:
  - DB hien tai la ban byte-for-byte cua backup ngay 2026-04-28 16:32:03.
  - Du lieu sau backup nay khong nam trong DB chinh hien tai.
- Lenh can chay:
  - Chi chay lai Docker sau khi chap nhan moc du lieu 2026-04-28.
- Rollback:
  - Co the doi `db.sqlite3.before_restore_20260428_20260506_120220` ve lai `db.sqlite3` neu can quay lai trang thai truoc restore.

### [2026-05-06] Them Docker deploy cho laptop server
- Pham vi: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `DOCKER_DEPLOY.md`, `settings.py`, `requirements.txt`, `iot/management/commands/fetch_device_batch.py`
- Noi dung:
  - Them Docker image cho Django va compose service gom `web` + `redis`.
  - Mount runtime data tu host: `db.sqlite3`, `media/`, `staticfiles/`, `dashboard.log`.
  - Chuyen cac cau hinh deploy chinh sang env var: secret key, debug, allowed hosts, CSRF origins, email, Redis URL.
  - Bo sung package thieu cho Docker/runtime: `django-redis`, `django-widget-tweaks`, `gunicorn`.
  - Sua command `fetch_device_batch` dung `trang_chu.settings`.
- Anh huong:
  - Co the chay app bang `docker compose up -d --build` tu thu muc `trang_chu`.
  - Email se can set lai qua `.env`; khong con dua vao gia tri hardcode trong settings.
- Lenh can chay:
  - `Copy-Item .env.example .env`
  - `docker compose up -d --build`
- Rollback:
  - Xoa cac file Docker moi, revert thay doi `settings.py`, `requirements.txt`, va `fetch_device_batch.py`.
- Ghi chu:
  - Van dung SQLite local; can backup `db.sqlite3` va `media/` rieng.

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
