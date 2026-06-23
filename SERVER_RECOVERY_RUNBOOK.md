# Server Recovery Runbook

Tai lieu nay ghi thao tac nhanh khi server gap cac loi da tung xay ra.

## 1) Loi `database disk image is malformed`

Dau hieu:

```text
DatabaseError at /iot/dashboard/
database disk image is malformed
```

Nguyen nhan co kha nang cao:
- Nhieu worker IoT ghi SQLite cung luc.
- SQLite dang nam tren Windows bind mount, khong an toan khi co nhieu tien trinh ghi lien tuc.

### Buoc 1: Dung worker ghi DB

Chay trong `C:\seigi-server\seizo0\trang_chu`:

```powershell
docker stop trang_chu-update-net100-shots-1 trang_chu-fetch-mail-notify-1 trang_chu-sync-chatwork-1 trang_chu-update-machine-counter-1 trang_chu-update-esp32-shot-1 trang_chu-update-mold-shot-1 trang_chu-iot-worker-serial-1
```

Khong dung cac container chinh:

```text
seizo0-django
seizo0-nginx
seizo0-redis
seizo0-esp32-bridge
trang_chu-fax-reminder-daily-1
```

### Buoc 2: Kiem tra DB hien tai

```powershell
docker run --rm -v ${PWD}:/app -w /app seizo0-django:latest python -c "import sqlite3; c=sqlite3.connect('db.sqlite3'); print(c.execute('PRAGMA integrity_check').fetchone()); c.close()"
```

Neu ket qua khong phai `('ok',)` thi DB dang hong.

### Buoc 3: Luu lai DB hong

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
Copy-Item db.sqlite3 "db.sqlite3.malformed_$stamp" -Force
```

Khong xoa file malformed, vi co the can dieu tra hoac cuu du lieu sau.

### Buoc 4: Lay DB tu full backup moi nhat

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$zip = Get-ChildItem backup_db\daily\seizo0_runtime_backup_*.zip | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$restoreDir = "backup_db\restore_tmp_$stamp"
New-Item -ItemType Directory -Force -Path $restoreDir | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($zip.FullName)
$entry = $archive.GetEntry('db.sqlite3')
[IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $restoreDir 'db.sqlite3'), $true)
$archive.Dispose()
```

### Buoc 5: Kiem tra DB trong backup

```powershell
docker run --rm -v ${PWD}:/app -w /app seizo0-django:latest python -c "import sqlite3; p='backup_db/restore_tmp_$stamp/db.sqlite3'; c=sqlite3.connect(p); print(c.execute('PRAGMA integrity_check').fetchone()); print(c.execute('PRAGMA foreign_key_check').fetchall()); c.close()"
```

Chi restore neu:

```text
integrity_check = ok
foreign_key_check = []
```

### Buoc 6: Thay DB va restart web

```powershell
docker stop seizo0-django
Copy-Item "backup_db\restore_tmp_$stamp\db.sqlite3" db.sqlite3 -Force
Remove-Item -Force db.sqlite3-shm,db.sqlite3-wal -ErrorAction SilentlyContinue
docker start seizo0-django
```

### Buoc 7: Kiem tra lai

```powershell
docker run --rm -v ${PWD}:/app -w /app seizo0-django:latest python -c "import sqlite3; c=sqlite3.connect('db.sqlite3'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(len(c.execute('PRAGMA foreign_key_check').fetchall())); c.close()"
curl.exe -k -I --max-time 30 https://192.168.10.250/iot/dashboard/
```

Ket qua tot:

```text
ok
0
HTTP/1.1 200 OK
```

### Buoc 8: Chan worker tu bat lai

```powershell
docker update --restart=no trang_chu-update-net100-shots-1 trang_chu-fetch-mail-notify-1 trang_chu-sync-chatwork-1 trang_chu-update-machine-counter-1 trang_chu-update-esp32-shot-1 trang_chu-update-mold-shot-1 trang_chu-iot-worker-serial-1
```

Chi bat lai worker sau khi da co chien luoc DB/worker an toan hon.

## 2) Loi `502 Bad Gateway` sau khi restart Django

Dau hieu:

```text
502 Bad Gateway
nginx/1.27.5
```

Nguyen nhan thuong gap:
- Nginx da resolve IP container `web` cu.
- Sau khi `seizo0-django` restart, IP noi bo Docker doi.

### Kiem tra nhanh

```powershell
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
curl.exe -I --max-time 30 http://127.0.0.1:8000/iot/dashboard/
curl.exe -k -I --max-time 30 https://192.168.10.250/iot/dashboard/
```

Neu port `8000` OK nhung HTTPS qua nginx 502, restart nginx:

```powershell
docker restart seizo0-nginx
```

Kiem tra:

```powershell
curl.exe -k -I --max-time 30 https://192.168.10.250/iot/dashboard/
```

Ket qua tot:

```text
HTTP/1.1 200 OK
```

## 3) Sua nginx de tranh 502 lap lai

Trong `nginx/conf.d/seizo0.conf`, server SSL nen co:

```nginx
resolver 127.0.0.11 valid=10s ipv6=off;
set $django_upstream http://web:8000;

location / {
    proxy_pass $django_upstream;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Sau khi sua:

```powershell
docker exec seizo0-nginx nginx -t
docker exec seizo0-nginx nginx -s reload
```

## 4) Tao backup sach sau khi restore

Sau khi restore thanh cong:

```powershell
docker run --rm -v ${PWD}:/app -w /app seizo0-django:latest python backup_sqlite.py
.\scripts\backup_runtime_to_drive.ps1 -DriveFolder "G:\マイドライブ\seizo0-backups" -KeepBackupCount 2
```

## 5) Loi OCR `quet_anh` xuat kho deu ra 0%

Dau hieu:
- Man hinh xuat kho OCR/so sanh hien 0% lien tuc.
- DB `QAResult` gan nhat co the van binh thuong, vi ket qua mismatch thuong khong duoc luu.
- Log co the co `PaddleOCR failed`, `Cannot parse tensor desc`, hoac container bi native segfault.

Nguyen nhan da tung gap:
- Model PaddleOCR trong `/root/.paddleocr/whl` bi hong hoac khong tuong thich.
- Runtime container khong co `curl`, nen script tai model cu khong chay duoc.
- Cau hinh `use_angle_cls=True` va goi `ocr.ocr(..., cls=True)` co the gay segfault voi bo PaddleOCR/Paddle hien tai.

Kiem tra nhanh PaddleOCR import:

```powershell
docker compose exec -T web python -c "from paddleocr import PaddleOCR; print('import ok')"
```

Kiem tra OCR tren anh mau da luu trong container:

```powershell
docker compose exec -T web python manage.py shell -c "from paddleocr import PaddleOCR; import cv2; path='/app/media/quet_anh2/processed/processed_new_bduTRQ2.png'; ocr=PaddleOCR(use_angle_cls=False, lang='japan', rec=True, det=True, use_gpu=False, enable_mkldnn=False, show_log=False); img=cv2.imread(path); res=ocr.ocr(img, cls=False); text=''.join([line[1][0] for line in (res[0] or [])]) if res and res[0] else ''; print(text[:120]); print('LEN', len(text))"
```

Ket qua tot: `LEN` lon hon 0 va co text OCR in ra.

Cach fix on dinh:
- Dam bao `scripts/install_paddleocr_models.sh` co the tai model ke ca khi container khong co `curl`.
- Bake model vao image bang build moi:

```powershell
docker compose build web
docker compose up -d --force-recreate web nginx
```

Neu chi can sua cache model de debug nhanh trong container hien tai:

```powershell
docker compose exec -T web sh -c "rm -rf /root/.paddleocr/whl/det /root/.paddleocr/whl/rec /root/.paddleocr/whl/cls && bash scripts/install_paddleocr_models.sh"
```

Luu y: cache sua truc tiep trong container co the mat khi recreate; nen build image moi de dung production.

Cau hinh OCR nen giu trong code:

```python
PaddleOCR(
    use_angle_cls=False,
    lang="japan",
    rec=True,
    det=True,
    use_gpu=False,
    enable_mkldnn=False,
    show_log=False,
)
ocr.ocr(img_np, cls=False)
```

Kiem tra sau deploy:

```powershell
docker compose exec -T web python manage.py check
curl.exe -k -I --max-time 60 https://192.168.10.250/quet_anh/
```

Neu vua recreate web ma nginx tra 502, doi Django khoi dong xong roi thu lai. Neu 502 van lap lai nhung port 8000 OK, xem muc 2.

## 6) Ghi nhat ky

Sau moi su co lon, cap nhat:

```text
PROJECT_CHANGELOG.md
```

Can ghi:
- Thoi diem.
- File DB hong da luu ten gi.
- Backup da restore tu file nao.
- Lenh da chay.
- Rui ro mat du lieu tu moc thoi gian nao.
