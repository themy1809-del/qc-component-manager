# AUTO IMPORT — Tự động lấy dữ liệu mới nhất từ Google Drive

## Dùng hằng ngày (1 bước)

Double-click **`IMPORT_ALL.bat`**. Xong.

Tool sẽ tự động, cho từng dự án:
1. Tải bản **mới nhất** từ Google Drive (link công khai, không cần mật khẩu)
2. Import thẳng vào DB cloud (Supabase)
3. Dữ liệu không đổi so với lần trước → tự bỏ qua
4. In tổng kết: dự án nào OK / bỏ qua / lỗi

Không cần tải file tay, không cần mở web. Cần máy có internet.

## Đã cấu hình sẵn 18 dự án

File `AUTO_IMPORT_CONFIG.json` đã khai báo sẵn, lấy từ thư mục Drive anh gửi:
- **5 dự án dạng Google Sheets** (team sửa trực tiếp online): Cầu đi bộ, Igarashi,
  APEC bao che, Hậu Giang, BISON Unit 1 → ID cố định, **luôn lấy bản mới nhất** tự động.
- **13 dự án dạng file Excel** trên Drive: VIOLA, BISON Unit 2 + SDM, APEC S3, PVF,
  3× Mỹ Thủy, EVAPCO, cao tốc VIN, VIOLA Ducting, GT1, Phú Quốc sàn thép.

## Lưu ý quan trọng

1. **Mã dự án (`code`)** đặt theo số dự án (vd `10725-009`, `10725-003-U1`).
   Nếu trên web app anh đã có dự án với mã KHÁC, tool sẽ tạo dự án mới.
   → Mở `AUTO_IMPORT_CONFIG.json`, sửa `code` cho khớp dự án đang có (nếu cần).

2. **Dự án dạng file Excel**: nếu team **upload đè file mới** (xóa file cũ, tải file
   khác lên) thì link ID đổi → cần cập nhật lại `drive_id`. Cách bền nhất: bảo team
   **giữ nguyên file Google Sheets và sửa trực tiếp** (như 5 dự án trên) → ID không
   bao giờ đổi, tự động mãi mãi. Khi cần cập nhật ID, nhắn tôi.

3. Muốn ép import lại tất cả: chạy `IMPORT_ALL.bat --force` (qua PowerShell).

4. Tạm bỏ qua 1 dự án: mở config, đổi `"bat": false`.

## Tự chạy tự động trên CLOUD (không cần bật máy)

App đã có sẵn **GitHub Actions** chạy auto-import tự động, **không cần máy anh bật**.
File: `.github/workflows/auto-import.yml`.

**Lịch chạy** (giờ Việt Nam, Thứ 2 – Thứ 7): **08:00, 11:00, 13:00, 15:00**.

Mỗi lần chạy: tự dò file mới nhất trên Drive → file nào không đổi thì bỏ qua →
file đổi thì tải + import vào Supabase. Dữ liệu trên `qc-daidung.streamlit.app`
tự cập nhật theo, không phải double-click `IMPORT_ALL.bat` nữa.

### Cần làm 1 lần duy nhất: thêm "khóa" DATABASE_URL trên GitHub

Để Actions kết nối được DB Supabase, phải lưu chuỗi kết nối vào GitHub (an toàn, ẩn):

1. Mở repo trên GitHub → **Settings** (tab trên cùng).
2. Menu trái: **Secrets and variables → Actions**.
3. Bấm **New repository secret**.
4. **Name**: `DATABASE_URL`
5. **Secret**: dán **nguyên nội dung file `supabase_new.txt`** (chuỗi `postgresql://...` — bản Session pooler).
6. Bấm **Add secret**.

> Nếu chưa thêm secret này, các lần chạy theo lịch sẽ **báo lỗi đỏ** với dòng
> "Chua cau hinh secret DATABASE_URL".

### Chạy tay / kiểm tra ngay (không đợi tới giờ)

1. Repo GitHub → tab **Actions** → chọn workflow **"Auto import master (theo lich)"**.
2. Bấm **Run workflow** (góc phải).
   - Ô **projects**: gõ mã dự án muốn import (vd `10725-009`), để trống = tất cả.
   - Tick **force** nếu muốn ép import lại cả file không đổi.
3. Bấm nút **Run workflow** xanh → đợi → bấm vào lần chạy để xem log từng dự án.
   Log cuối in: `XONG: N OK, N bỏ qua, N lỗi`.

### Đổi lịch chạy

Mở `.github/workflows/auto-import.yml`, sửa các dòng `cron` (giờ **UTC**, VN = UTC+7).
Vd muốn thêm mốc 09:00 VN → thêm dòng `- cron: "0 2 * * 1-6"`.

## Tự chạy trên MÁY theo lịch (tuỳ chọn, nếu không muốn dùng cloud)

Dùng **Task Scheduler** của Windows, trỏ tới `IMPORT_ALL.bat`, đặt giờ (vd 7:00).

---

## Nếu thấy import LÂU

Lần chạy **đầu tiên** luôn lâu nhất vì phải tải + nạp HẾT 18 dự án, trong đó có
file rất lớn (BISON Unit 2 ~94MB, VIOLA ~52MB). Đây là điều không tránh được ở
lần đầu. Những lần sau sẽ **nhanh hơn nhiều** vì:

- Tool **kiểm tra dung lượng trước (HEAD)** — dự án nào trên Drive không đổi so với
  lần trước → **bỏ qua, không tải lại, không import lại**.

### Cách chạy nhanh khi chỉ cần vài dự án

Mở PowerShell tại thư mục web app, gõ tên 1 hoặc vài mã dự án:

```powershell
.\IMPORT_ALL.bat 10725-009
.\IMPORT_ALL.bat 10626-030 10725-008
```

→ Chỉ import đúng dự án đó, bỏ qua 17 cái còn lại. Rất nhanh.

### Mẹo giảm tải

- Dự án nào ít thay đổi: mở `AUTO_IMPORT_CONFIG.json` đổi `"bat": false` để
  tạm tắt, khi cần mới bật lại.
- Vì DB đặt ở Mỹ, mỗi lần import dự án lớn (vài chục nghìn cấu kiện) sẽ mất ít phút
  do khoảng cách mạng — đây là giới hạn của bản miễn phí, không phải lỗi.

## Dự án Google Sheets trên cloud — cần Google API key

5 dự án dạng Google Sheets (team sửa online) **không tải được từ máy chủ GitHub**
nếu không có API key. Làm 1 lần:

1. Vào https://console.cloud.google.com → tạo 1 Project (hoặc dùng project sẵn).
2. Menu → **APIs & Services → Library** → tìm **Google Drive API** → **Enable**.
3. Menu → **APIs & Services → Credentials** → **Create credentials → API key** → copy chuỗi key.
4. Trên GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - Name: `GOOGLE_API_KEY`
   - Secret: dán chuỗi key vừa tạo.
5. **Chia sẻ 5 Google Sheets**: mở từng sheet → Share → "Anyone with the link" → **Viewer**.
   (API key chỉ đọc được file đã chia sẻ công khai dạng xem.)

Sau đó workflow sẽ tự đọc cả 5 Google Sheets → đủ 18/18. Không có key thì 13 dự án
dạng file vẫn tự động bình thường, chỉ 5 Sheets là bỏ qua.
