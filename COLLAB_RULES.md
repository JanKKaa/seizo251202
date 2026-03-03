# Collaboration Rules (Codex + Team)

## Muc tieu
- Dam bao moi thay doi lon deu duoc ghi lai de co the tiep tuc nhanh o phien sau.
- Giu thong tin ngan gon, de tim, de handoff.

## Quy tac bat buoc
1. Khi co thay doi lon (kien truc, model, route, command, quy trinh deploy/git), cap nhat `PROJECT_CHANGELOG.md` ngay sau khi xong.
2. Moi thay doi lon phai co:
- `Ngay` (YYYY-MM-DD)
- `Pham vi` (app/file)
- `Noi dung thay doi`
- `Anh huong/rui ro`
- `Lenh can chay`
- `Rollback`
3. Neu thay doi lien quan van hanh, cap nhat them `ARCHITECTURE.md` neu can.
4. Moi phien lam viec moi, doc 2 file truoc:
- `ARCHITECTURE.md`
- `PROJECT_CHANGELOG.md`

## Dinh nghia "thay doi lon"
- Doi URL/luong chuc nang chinh.
- Doi model/database/migration.
- Doi command cron/management.
- Doi auth, permission, settings, secret, cache.
- Doi quy trinh Git/deploy/backup.

## Cau nhac de bat dau nhanh
Khi mo lai VS Code, gui:
"Doc `ARCHITECTURE.md` va `PROJECT_CHANGELOG.md`, tom tat 5 dong nhung gi moi nhat roi tiep tuc task ..."
