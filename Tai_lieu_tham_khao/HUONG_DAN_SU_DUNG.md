# Hướng dẫn sử dụng QC Component Manager

## 1. Cài đặt lần đầu

1. Cài Python 3.10+ tại https://www.python.org/downloads/ (nhớ tick **Add Python to PATH**)
2. Mở thư mục này → double-click `RUN_APP.bat` để chạy. Lần đầu sẽ tự cài thư viện cần thiết.

## 2. Luồng làm việc cơ bản

### Bước 1 — Tạo dự án
Nhấn **+ Dự án mới** ở góc trên phải, nhập:
- **Mã dự án**: ví dụ `VIOLA`, `MEPS25`, `BT-PHASE3`
- **Tên dự án**: tên đầy đủ
- Địa điểm, chủ đầu tư, ghi chú (tùy chọn)

### Bước 2 — Import danh sách tổng (PKL/Master List)
Vào tab **📥 Import Danh sách Tổng**:
1. Chọn file Excel danh sách tổng (.xlsb / .xlsx / .xlsm / .xls / .csv)
2. Chọn **Sheet** (mặc định `PKL`) và **dòng tiêu đề** (PKL VIOLA = dòng 4)
3. Nhấn **Đọc tiêu đề**
4. Nhấn **🔁 Auto-mapping VIOLA (PKL)** nếu file theo template Đại Dũng - hệ thống tự ánh xạ.  
   Nếu form khác, chọn thủ công cột Excel cho từng trường (chỉ trường `code` là bắt buộc).
5. Nhấn **💾 Lưu Mapping & Import**

> Mapping được lưu theo từng dự án, lần sau không cần map lại.

### Bước 3 — Hàng ngày: Import file kiểm tra
Vào tab **📤 Import File Kiểm tra Hàng ngày**:
1. Chọn **Loại kiểm tra** (FUR / DIR / VIR / NDT / TAIR / PRE / MB / MTR / **DGRP**)
2. Chọn file Excel kiểm tra hôm đó
3. Chọn Sheet (mặc định trùng tên loại KT) và dòng tiêu đề
4. Nhấn **Đọc tiêu đề**
5. Nhấn nút Auto-mapping phù hợp:
   - **🔁 Auto-mapping NDT VIOLA** cho file kiểm tra mối hàn (sheet NDT)
   - **🔁 Auto-mapping DGRP VIOLA (Bàn giao)** cho **Biên bản nghiệm thu và bàn giao sản phẩm** (vd `16.05.2026__10725-009 DGRP VIOLA - STRUCTURAL STEEL.xlsx`)
6. Nhấn **▶ Import và cập nhật trạng thái**

> **Đặc biệt cho DGRP**: App sẽ tự động (a) lấy **ngày kiểm tra** từ tên file (định dạng `DD.MM.YYYY`), (b) phân tích cột Remark như `"Dim,Visual,NDT"` thành nhiều bản ghi inspection (DIR + VIR + NDT) cho cùng 1 cấu kiện. Bạn không cần map cột ngày.

App tự động:
- Match cấu kiện theo mã (tự bóc đuôi `-J1`, `-J2-R1`… để lấy mã gốc)
- Nhận diện FAIL nếu Remark có chữ "REJ", "FAIL", "NG"
- Cập nhật trạng thái: cấu kiện được đánh dấu **ACCEPTED** khi đã PASS đủ DIR + VIR + NDT

### Bước 4 — Theo dõi & xuất báo cáo
- Tab **📊 Tổng quan**: 6 chỉ số PENDING / IN_PROGRESS / PASSED / FAILED / ACCEPTED và lịch sử kiểm tra gần nhất
- Tab **🔧 Danh sách Cấu kiện**: lọc theo trạng thái, tìm theo mã, double-click 1 dòng để xem chi tiết và toàn bộ lịch sử kiểm tra của cấu kiện đó
- Nhấn **📊 Xuất Excel báo cáo** để xuất file tổng hợp 3 sheet (Components / Inspections / Summary)

## 3. Dùng chung nhiều QC

App lưu dữ liệu trong file `qc_components.db` (SQLite) cùng thư mục.  
Để **nhiều QC dùng chung**, copy app lên ổ mạng chung (ví dụ `Z:\PHONG QC\...`), tất cả mở từ đó.

> ⚠ Hiện tại SQLite không hỗ trợ ghi đồng thời mạnh. Nếu cần >5 QC ghi cùng lúc, đề xuất nâng cấp lên PostgreSQL/MySQL (xem mục Roadmap trong SRS).

## 4. Quy tắc trạng thái

| Trạng thái | Khi nào |
|---|---|
| PENDING | Mới import từ PKL, chưa có inspection nào |
| IN_PROGRESS | Đã có ≥1 inspection PASS nhưng chưa đủ DIR+VIR+NDT |
| PASSED | Đã PASS một trong DIR/VIR/NDT |
| FAILED | Có ≥1 inspection FAIL |
| ACCEPTED | Đã PASS đủ DIR + VIR + NDT → coi như nghiệm thu xong |

## 5. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|