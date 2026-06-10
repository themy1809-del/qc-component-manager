# TỰ ĐỘNG IMPORT HẰNG ĐÊM BẰNG GITHUB ACTIONS

Từ nay **không cần chạy IMPORT_ALL.bat thủ công nữa**. Mỗi đêm ~1h sáng (giờ VN),
server của GitHub tự tải file mới nhất từ Drive và import vào DB. Sáng vào web là có số liệu mới.

Server GitHub đặt ở Mỹ — cùng vùng với DB Supabase — nên import **nhanh hơn nhiều**
so với chạy từ mạng văn phòng.

## Cài đặt 1 lần duy nhất (2 bước)

### Bước 1 — Thêm mật khẩu DB vào GitHub
1. Mở repo trên github.com → **Settings** → **Secrets and variables** → **Actions**
2. Bấm **New repository secret**
3. Name: `DATABASE_URL`
4. Secret: dán nguyên dòng `postgresql://...` trong file `supabase_new.txt` trên máy anh
5. Bấm **Add secret**

### Bước 2 — Push code lên
Double-click `PUSH.bat` (workflow + config sẽ được đẩy lên cùng).

Xong. Đêm nay nó tự chạy.

## Cách dùng hằng ngày
- **Không phải làm gì cả.** Số liệu tự cập nhật mỗi đêm.
- Muốn cập nhật NGAY (không đợi đêm): vào repo → tab **Actions** →
  "Auto import master (hang dem)" → **Run workflow**.
  - Ô "Ma du an": gõ mã để chạy riêng (vd `10725-009`), để trống = tất cả.
  - Tick "Ep import lai" nếu đổi cách map mà file không đổi.
- IMPORT_ALL.bat trên máy vẫn dùng được như cũ (dự phòng).

## Theo dõi / xử lý lỗi
- Tab **Actions** hiện lịch sử từng đêm: xanh = OK, đỏ = có dự án lỗi.
- Chạy lỗi GitHub sẽ gửi email cho chủ repo.
- Log từng dự án xem trong run → job "import" → bước "Chay import".

## Lưu ý
- File `AUTO_IMPORT_CONFIG.json` giờ ĐƯỢC commit lên repo (chỉ chứa Drive ID
  của link công khai, không có mật khẩu). Sửa cấu hình dự án = sửa file này rồi PUSH.bat.
- Mật khẩu DB chỉ nằm trong GitHub Secret + supabase_new.txt (vẫn gitignore).
- Dự án nào file không đổi sẽ tự bỏ qua nên mỗi đêm thường chỉ mất vài phút.
- Đổi giờ chạy: sửa dòng `cron: "0 18 * * *"` trong
  `.github/workflows/auto-import.yml` (giờ UTC = giờ VN trừ 7).
