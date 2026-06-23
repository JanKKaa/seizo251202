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
5. Neu task lien quan doi server, Docker, DB, restore, backup, worker, doc them:
- `SERVER_HANDOFF.md`

## Che do tiet kiem quota
- Uu tien doc `AGENTS.md` o root truoc, sau do chi doc file lien quan truc tiep den task.
- Dung `rg` de tim dung file/ham truoc khi mo file.
- Khong quet cac thu muc lon neu khong can: `.venv/`, `staticfiles/`, `media/`, `backup_db/`, `seizo0_backup/`.
- Sua nho, dung pham vi; khong refactor ngoai yeu cau.
- Test nho nhat co ich truoc: syntax/import check, command Django lien quan, hoac view/URL lien quan.
- Bao cao cuoi ngan gon: file da sua, noi dung, lenh da chay, rui ro con lai.

## Dinh nghia "thay doi lon"
- Doi URL/luong chuc nang chinh.
- Doi model/database/migration.
- Doi command cron/management.
- Doi auth, permission, settings, secret, cache.
- Doi quy trinh Git/deploy/backup.

## Cau nhac de bat dau nhanh
Khi mo lai VS Code, gui:
"Doc `ARCHITECTURE.md` va `PROJECT_CHANGELOG.md`, tom tat 5 dong nhung gi moi nhat roi tiep tuc task ..."

Neu dang doi server/restore, gui:
"Doc `SERVER_HANDOFF.md` truoc, sau do kiem tra `docker compose ps` va xac nhan DB dang la PostgreSQL ..."
