# Hướng dẫn migrate dữ liệu sang Supabase (Postgres)

Mục tiêu: chuyển 4 dự án / 16.453 cấu kiện / 11.116 inspections từ SQLite sang
Supabase Postgres để **không mất dữ liệu mỗi lần Streamlit Cloud redeploy/ngủ dậy**.

## Bước 1 — Tạo project Supabase (miễn phí)
1. Vào https://supabase.com → đăng ký (GitHub hoặc email).
2. **New project**: đặt tên (vd `qc-daidung`), region **Singapore**, đặt **Database Password** và LƯU LẠI.
3. Chờ ~2 phút cho project sẵn sàng.

## Bước 2 — Lấy connection string
- **Project Settings → Database → Connection string → tab URI**.
- Copy chuỗi dạng:
  `postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-...pooler.supabase.com:5432/postgres`
- Thay `[YOUR-PASSWORD]` bằng mật khẩu DB ở Bước 1.

## Bước 3 — Chạy migrate (trên máy bạn, password không rời máy)
1. Double-click **`MIGRATE_SUPABASE.bat`**.
2. Lần đầu nó mở Notepad `supabase_url.txt` → dán chuỗi (đã thay password) → **Lưu**.
3. Chạy lại `MIGRATE_SUPABASE.bat`. Thấy dòng **`HOAN TAT MIGRATION!`** là xong.

## Bước 4 — Bật Postgres cho app trên Cloud
- Streamlit Cloud → app → **Settings → Secrets**, thêm:
  ```
  DATABASE_URL = "postgresql://postgres.xxxx:MATKHAU@...pooler.supabase.com:5432/postgres"
  ```
- App tự reboot → giờ đọc/ghi thẳng Supabase, dữ liệu bền vĩnh viễn.
- Xoá `supabase_url.txt` trên máy sau khi xong (không cần giữ mật khẩu).

> File `supabase_url.txt` đã được .gitignore nên không bị commit lên GitHub.
