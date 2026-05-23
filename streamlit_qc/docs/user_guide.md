# Hướng dẫn sử dụng — QC Component Manager Web v2.0

> Dành cho QC trong phòng. Đọc 1 lần là dùng được.

## 1. Mở app

- Mở trình duyệt Chrome / Edge.
- Vào địa chỉ: `http://<IP-server>:8501` (anh IT cấp).
- Nếu chạy trên máy mình: `http://localhost:8501`.

## 2. Lần đầu sử dụng — tạo dự án

1. Ở sidebar trái → mục **"➕ Tạo dự án mới"**
2. Nhập:
   - **Mã dự án**: viết hoa, không dấu, vd `VIOLA`, `PVF-HY`, `STADIUM-2026`
   - **Tên dự án**: viết đầy đủ
3. Bấm **"Tạo"**

## 3. Hằng ngày — quy trình chuẩn

```
Lần đầu:    Tạo dự án → Import Master (PKL)
Hằng ngày:  Import Daily (DGRP/NDT/...) → Xem Tổng quan
Hằng tuần:  Vào Báo cáo → tải Excel cho sếp
```

### 3.1 Import Master List (PKL) — chỉ cần làm 1 lần mỗi dự án

1. Vào page **"📥 Import Master"**
2. Kéo thả file PKL (`.xlsb`/`.xlsx`)
3. Bấm 1 trong các nút:
   - **"🤖 Smart Auto-detect"** — dùng cho mọi form PKL lạ
   - **"🔁 VIOLA"** — nếu là form VIOLA Structural Steel
   - **"🔁 PVF Hưng Yên"** — nếu là form PVF
4. Xem mapping có đúng không (cột "code" phải có)
5. Bấm **"💾 Lưu Mapping & Import"**
6. Chờ ~2-5 giây → có thông báo "Hoàn tất"

### 3.2 Import Daily (file kiểm tra hằng ngày)

1. Vào page **"📤 Import Daily"**
2. Chọn loại kiểm tra:
   - **FUR/DIR/VIR/NDT/...** — 1 file = 1 loại
   - **DGRP** — biên bản bàn giao, tự tạo nhiều inspection theo cột Remark
3. Upload file
4. Bấm **"🔁 Auto-mapping DGRP VIOLA"** hoặc **"🔁 Auto-mapping NDT VIOLA"**
5. Điền **Số NFI** + **Ngày kiểm tra** (tự lấy từ tên file)
6. (Tuỳ chọn) Bấm **"🔍 Debug Match"** để xem mã có khớp master không
7. Bấm **"▶ Import"**

### 3.3 Xem & sửa bảng cấu kiện

Vào page **"🔧 Cấu kiện"**:

- **Tìm mã**: gõ vào ô "🔎 Tìm mã cấu kiện"
- **Lọc trạng thái**: dropdown đầu trang
- **Lọc Zone/Phase/Material/Xưởng/Type**: bật toggle "🎚 Lọc cột"
- **Sort**: click vào tên cột
- **Sửa nhanh** (Bản vẽ / Revision / Xưởng / Số NFI / Ngày KT):
  - Double-click vào ô → sửa → Enter
  - Sửa nhiều ô liền → bấm nút **"💾 Lưu thay đổi"** ở cuối
- **Xem chi tiết + lịch sử kiểm tra**: gõ mã vào ô bên dưới → **"👁 Xem chi tiết"**

### 3.4 Xem tổng quan & xuất báo cáo

- **📊 Tổng quan**: KPI cards, % hoàn thành theo xưởng, lịch sử 200 inspection mới nhất
- **📈 Báo cáo**: chọn date range → xem chart tiến độ tuần + tải Excel 4 sheet

## 4. Hiểu các trạng thái

| Trạng thái | Khi nào |
|---|---|
| **PENDING** (Chưa KT) | Cấu kiện mới import từ master, chưa có inspection nào |
| **IN_PROGRESS** (Đang KT) | Có inspection nhưng chưa đủ điều kiện PASSED |
| **PASSED** (Đạt) | Đã có ít nhất 1 inspection PASS thuộc DIR/VIR/NDT |
| **FAILED** (Không đạt) | Có inspection FAIL |
| **ACCEPTED** (Đã nghiệm thu) | **PASS đủ cả 3 loại DIR + VIR + NDT** trên cùng cấu kiện |

## 5. Mẹo dùng nhanh

- **Tên file daily phải có ngày**: `15.5.2026_DGRP_VIOLA.xlsx` → app tự lấy ngày
- **Mã có prefix `1-`**: vd `1-01BTG3008-001` → app tự khớp với `01BTG3008-001` trong master
- **Mã có suffix `-J1`**: vd `01USC3020-001-J1` (file NDT mối hàn) → app tự khớp với `01USC3020-001`
- **Cột Remark DGRP** có chữ `Dim,Visual,NDT` → app tạo 3 inspection từ 1 dòng → tự thành ACCEPTED
- **Số NFI ô trên cùng** áp cho cả file — đỡ phải nhập từng dòng
- **Chọn người thao tác** ở sidebar — tên sẽ ghi vào audit log

## 6. Gặp lỗi

### "Không có cấu kiện match"
- Vào **🔍 Debug Match** trong page Import Daily → xem 10 mã master vs 10 mã daily
- Nếu mã master sai (vd import nhầm cột) → xoá rồi import lại Master

### "App chậm, treo"
- Refresh trang (F5)
- Nếu vẫn chậm: báo IT restart server

### "Mất dữ liệu"
- Vào **⚙ Quản trị → 💾 Backup/Restore** → upload file backup gần nhất
- Nếu không có backup: hỏi IT (database file `data/qc_components.db`)

## 7. Liên hệ
- IT phòng QC Đại Dũng
- File này được cập nhật khi có tính năng mới
