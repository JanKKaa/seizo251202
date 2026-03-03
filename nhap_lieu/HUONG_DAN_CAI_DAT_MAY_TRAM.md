# NHAP LIEU - HUONG DAN CAI DAT MAY TRAM (FLASK INPUT API)

File nay huong dan cai thu vien va chay script Flask tren may tram nhap lieu.

## 1) Yeu cau
- Windows 10/11
- Python 3.10+ (khuyen nghi 3.11)
- Quyen chay app desktop (WINNC/SK5030)

## 2) Tao moi truong ao (venv)
Mo PowerShell tai thu muc chua script Flask, sau do chay:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## 3) Cai thu vien can thiet

```powershell
pip install flask pyautogui pyperclip requests
```

Neu pyautogui bao loi thieu dependency, cai them:

```powershell
pip install pillow pygetwindow pymsgbox pyscreeze pytweening mouseinfo pyrect
```

## 4) Kiem tra thu vien

```powershell
python -c "import flask,pyautogui,pyperclip,requests; print('OK')"
```

Neu in ra `OK` la dat.

## 5) Cau hinh bien moi truong (khuyen nghi)
Script ho tro doc bien moi truong:
- `INPUT_EXE_PATH`
- `INPUT_WORKING_DIR`
- `DJANGO_CALLBACK_URL`
- `SELECT_START_X`, `SELECT_START_Y`, `SELECT_END_X`, `SELECT_END_Y`
- `APP_BOOT_WAIT`, `PRE_SELECT_WAIT`, `CALLBACK_TIMEOUT`, `CALLBACK_RETRIES`

Vi du:

```powershell
$env:INPUT_EXE_PATH="\\Jimusyoserver\d\WINNC_V10\HAYASHITC\SK5030.EXE"
$env:INPUT_WORKING_DIR="\\Jimusyoserver\d\WINNC_V10\HAYASHITC"
$env:DJANGO_CALLBACK_URL="http://192.168.10.71:8000/nhap-lieu/api/cap-nhat-ket-qua/"
```

## 6) Chay Flask API tren may tram

```powershell
python workstation_flask_api.py
```

Mac dinh service lang nghe tai:
- `http://0.0.0.0:5000/send_input`

## 7) Test nhanh endpoint

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/send_input" -Method Post -ContentType "application/json" -Body '{"quy_tac":["TEST","ENTER"],"delay":0.1}'
```

## 8) Loi thuong gap
- `python is not recognized`: chua cai Python hoac chua add PATH.
- Loi thieu thu vien: cai lai bang `pip install ...`.
- Khong callback ve Django: kiem tra `DJANGO_CALLBACK_URL`, firewall, IP route.
- Chon sai vung copy: dieu chinh `SELECT_START_*`, `SELECT_END_*`.

## 9) Van hanh on dinh
- Moi may tram chi nen chay 1 instance Flask.
- Neu doi man hinh/do phan giai, can calibrate lai toa do select.
- Theo doi log console de biet trang thai callback.
