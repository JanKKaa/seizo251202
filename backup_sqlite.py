import shutil
import datetime
import os

# Đường dẫn tới file database
db_path = "db.sqlite3"
# Thư mục lưu backup
backup_dir = "backup_db"
os.makedirs(backup_dir, exist_ok=True)

# Tạo tên file backup theo ngày
today = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = os.path.join(backup_dir, f"db_backup_{today}.sqlite3")

# Sao lưu file
shutil.copy2(db_path, backup_file)
print(f"Đã backup: {backup_file}")