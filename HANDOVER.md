# BÀN GIAO DỰ ÁN: Chuyển QC Component Manager từ Tkinter → Streamlit Web App

## 0. ĐỌC PHẦN NÀY TRƯỚC

Đây là tài liệu chuyển giao **đầy đủ context** giữa 2 phiên làm việc với Claude. Phiên trước đã hoàn thiện bản **Tkinter desktop**, phiên mới (đang đọc tài liệu này) sẽ xây dựng lại bằng **Streamlit web app** để phục vụ nhiều QC dùng đồng thời.

**Yêu cầu của chủ đầu tư (oke - QC specialist Đại Dũng):**
- Web app cho phòng QC, mở bằng trình duyệt từ mọi máy
- Tận dụng 100% logic Python đã có, chỉ thay UI Tkinter → Streamlit
- Triển khai trên 1 PC cũ làm server, các QC vào bằng Chrome qua mạng nội bộ
- Miễn phí 100%, không phụ thuộc Microsoft

---

## 1. BỐI CẢNH NGHIỆP VỤ

**Người dùng:** oke - chuyên gia QC tại Đại Dũng, quản lý nghiệm thu cấu kiện thép cho nhiều dự án (VIOLA, PVF Hưng Yên, sân vận động, nhà xưởng...).

**Bài toán cốt lõi:**
1. Mỗi dự án có 1 file Excel **PKL (Packing List / Master List)** chứa toàn bộ cấu kiện (~8.000-50.000 dòng × 50-92 cột)
2. Mỗi ngày QC làm việc, sinh ra 1 file Excel **DGRP (Biên bản nghiệm thu bàn giao)** chứa các cấu kiện kiểm tra hôm đó
3. App phải đối chiếu daily ↔ master, cập nhật trạng thái + lưu lịch sử
4. Form Excel **khác nhau giữa các dự án** → cần mapping linh hoạt

**Thực tế:**
- Phòng QC chia ra các nhà máy AH1-AH9 (An Hạ - Đại Dũng)
- Mỗi cấu kiện có mã định danh duy nhất kiểu `01BTG3008-001` (VIOLA), `TB001-1/1` (PVF)
- File daily có cấu kiện được prefix với số module: `1-01BTG3008-001`, `2-01USC3011-001` → cần tách prefix `\d+-` khi match
- File NDT có suffix mối hàn `-J1`, `-J3-R1` → cần tách `-J` khi match
- 8 loại nghiệm thu: **FUR / DIR / VIR / NDT / TAIR / PRE / MB / MTR**
- Loại đặc biệt **DGRP** = bàn giao, 1 dòng → tạo nhiều inspection records dựa vào Remark "Dim,Visual,NDT"

---

## 2. KIẾN TRÚC DỮ LIỆU (đã chốt, GIỮ NGUYÊN cho Streamlit)

### Bảng `projects`
```sql
id INTEGER PRIMARY KEY
code TEXT UNIQUE        -- VIOLA, PVF-HY...
name TEXT               -- Tên dự án
location, owner, note TEXT
created_at TEXT
```

### Bảng `components`
```sql
id INTEGER PRIMARY KEY
project_id INTEGER (FK)
code TEXT               -- 01BTG3008-001
data_json TEXT          -- JSON tất cả field: name, zone, phase, material, workshop, section, weight_kg, manual_nfi, manual_insp_date, manual_drawing...
status TEXT             -- PENDING / IN_PROGRESS / PASSED / FAILED / ACCEPTED
UNIQUE(project_id, code)
```

### Bảng `inspections`
```sql
id INTEGER PRIMARY KEY
project_id, component_id (FK)
inspection_type TEXT    -- FUR/DIR/VIR/NDT/TAIR/PRE/MB/MTR
inspection_date TEXT    -- YYYY-MM-DD (ISO chuẩn)
inspector, result, report_no, rfi_no, note TEXT
source_file, imported_at TEXT
```

### Bảng `column_mappings`
```sql
project_id, mapping_type (MASTER/DAILY_*), mapping_json, header_row, sheet_name
```

### Bảng `audit_log`
```sql
user_name, action, entity, entity_id, detail, ts
```

### Quy tắc trạng thái (đã chốt)
- PASS DIR/VIR/NDT → PASSED
- PASS đủ DIR + VIR + NDT → **ACCEPTED**
- FAIL → FAILED
- Còn lại → IN_PROGRESS / PENDING

---

## 3. CHỨC NĂNG ĐÃ XÂY (bản Tkinter v1.0.2)

### 3.1 Quản lý dự án
- Tạo / chuyển dự án bằng dropdown trên top bar

### 3.2 Import Master List (tab "Import Danh sách Tổng")
- Chọn file (.xlsb/.xlsx/.xlsm/.xls/.csv)
- Chọn sheet + dòng tiêu đề
- Auto-detect THÔNG MINH (dò header row + match cột bằng SMART_KEYWORDS)
- Auto-mapping VIOLA / Auto-mapping PVF Hưng Yên (cứng cho 2 template)
- Save/Load template mapping (file `mapping_templates.json`)
- Upsert vào DB - thread-safe với lock

### 3.3 Import Daily (tab "Import File Kiểm tra Hàng ngày")
- 9 loại NT: FUR/DIR/VIR/NDT/TAIR/PRE/MB/MTR/**DGRP**
- Auto-mapping NDT VIOLA (sheet NDT, header row 2)
- Auto-mapping DGRP VIOLA (sheet "BIÊN BẢN BÀN GIAO", header 11, code = "Tên - Mã số")
- **Ô nhập tay**: Số NFI + Ngày kiểm tra → áp cho cả file
- Auto-extract ngày từ tên file (regex `DD.MM.YYYY` → `YYYY-MM-DD`)
- **Logic match cấu kiện**: thử nhiều biến thể
  - Mã gốc
  - Tách prefix `^\d+-` (vd `1-01BTG3008-001` → `01BTG3008-001`)
  - Tách suffix `-J` (vd `01USC3020-001-J1` → `01USC3020-001`)
- **DGRP mode**: parse Remark "Dim,Visual,NDT" → tạo nhiều inspection records
- Nút **🔍 Debug Match**: in 10 mã master vs 10 mã daily đầu (kèm ✅/❌)

### 3.4 Danh sách Cấu kiện
- 7 cột (đã chốt): **Tên cấu kiện | Bản vẽ | Revision | Xưởng | Tình trạng | Số NFI | Ngày kiểm tra**
- Tất cả cột căn giữa
- Ngày hiển thị **DD/MM/YYYY** (helper `format_date_vn`)
- Click header để sort tăng/giảm
- Filter dropdown cho từng cột: Zone, Phase, Material, Xưởng, Type
- Lọc theo trạng thái + tìm theo mã
- **Inline edit** bằng double-click ô:
  - Bản vẽ → lưu `manual_drawing`
  - Revision → lưu `rev_no`
  - Xưởng → lưu `workshop`
  - Số NFI → lưu `manual_nfi`
  - Ngày kiểm tra → lưu `manual_insp_date` (accept cả DD/MM/YYYY và YYYY-MM-DD)
- Double-click cột Tên cấu kiện → mở popup chi tiết + lịch sử kiểm tra

### 3.5 Dashboard (tab Tổng quan)
- 6 thẻ chỉ số: Tổng / Chưa KT / Đang KT / Đạt / Không đạt / Đã NT
- **Dropdown lọc Xưởng** (mới) - cập nhật cả 6 thẻ + lịch sử
- **Bảng thống kê theo Xưởng** (mới): Xưởng | Tổng | từng trạng thái | % Hoàn thành
- Bảng "Lịch sử kiểm tra gần nhất" (200 inspection mới nhất)

### 3.6 Xuất báo cáo
- File Excel 3 sheet: Components / Inspections / Summary

### 3.7 Đã sửa các bug
- SQLite threading: `check_same_thread=False` + `Lock`
- File path có dấu tiếng Việt → BAT dùng `chcp 65001`

---

## 4. HƯỚNG STREAMLIT - GỢI Ý KIẾN TRÚC

### 4.1 Cấu trúc thư mục
```
streamlit_qc/
├── app.py                  # Entry point + sidebar navigation
├── pages/
│   ├── 1_📊_Tổng_quan.py
│   ├── 2_📥_Import_Master.py
│   ├── 3_📤_Import_Daily.py
│   ├── 4_🔧_Cấu_kiện.py
│   └── 5_⚙_Cấu_hình.py
├── core/
│   ├── db.py               # SQLAlchemy / sqlite3 wrapper
│   ├── excel.py            # Helpers đọc xlsb/xlsx, format date
│   ├── mapping.py          # Smart auto-detect + templates
│   └── auth.py             # Login (optional)
├── data/
│   ├── qc_components.db    # SQLite (hoặc dùng PostgreSQL nếu nhiều user)
│   └── mapping_templates.json
└── requirements.txt
```

### 4.2 Thư viện chính
```
streamlit>=1.30
pandas>=2.0
openpyxl
pyxlsb
sqlalchemy (optional, để dễ chuyển sang PostgreSQL sau)
```

### 4.3 Bí kíp Streamlit cho bài toán này
- **`st.data_editor`** thay cho Tkinter Treeview → inline edit miễn phí
- **`st.session_state`** để giữ project hiện tại, mapping cache
- **`@st.cache_data`** cho master list (8000 dòng) - quan trọng
- **`st.file_uploader`** + accept `.xlsb` cần config `accept_multiple_files=False, type=["xlsx","xlsb","xls","csv"]`
- **`st.dataframe`** với column_config cho format ngày, status badge
- **`st.tabs`** thay cho ttk.Notebook
- **Phân trang** với `st.dataframe(height=600)` (Streamlit tự virtual scroll)

### 4.4 Phần CÓ THỂ COPY-PASTE 90% từ Tkinter
- Toàn bộ class `DB` (chỉ bỏ `_lock` vì Streamlit chạy single-thread per session)
- Hàm `read_excel_any`, `list_sheet_names`, `excel_date_to_iso`
- Hàm `format_date_vn`, `parse_date_input`
- Hàm `extract_date_from_filename`, `parse_remark_types`
- Hàm `smart_detect_header_row`, `smart_match_columns`
- Logic match cấu kiện (strip prefix, suffix)
- Logic upsert component, add_inspection

### 4.5 Phần PHẢI VIẾT LẠI
- UI (file `pages/*.py` + `app.py`) - dùng Streamlit components
- Inline edit (dùng `st.data_editor` thay `_inline_edit_cell`)
- Multi-user: cần thêm login (st-pages hoặc streamlit-authenticator)

---

## 5. FILES TRONG THƯ MỤC NÀY

### `Tai_lieu_tham_khao/`
- **`QCComponentManager_Tkinter_v1.py`** - code Python desktop hoàn chỉnh, 1458 dòng. ĐỌC FILE NÀY ĐỂ HIỂU LOGIC.
- **`UML_HeThong_QuanLy_CauKien.html`** - Use Case + Class Diagram (mở bằng trình duyệt)
- **`SRS_QC_Component_Manager.docx`** - Đặc tả yêu cầu chính thức
- **`HUONG_DAN_SU_DUNG.md`** - Hướng dẫn dùng app Tkinter (tham khảo UX)

### `Sample_files/`
- **`PKL - VIOLA-STRUCTURAL STEEL - 2026.05.09.xlsb`** (5MB) - Master VIOLA: 8.217 dòng × 92 cột, sheet "PKL", header row 4
- **`PKL - SÂN VẬN ĐỘNG PVF HƯNG YÊN - 2026.05.05.xlsx`** - Master PVF: 73 dòng × 50 cột, sheet "PKL", header row 3
- **`16.05.2026__10725-009 DGRP VIOLA.xlsx`** - Daily DGRP: 46 cấu kiện, sheet "BIÊN BẢN BÀN GIAO", header row 11
- **`15.5.2026_10725-009 DGRP VIOLA.xlsx`** - Daily DGRP cấu trúc khác chút (cùng header row 11 nhưng cột [3] là type, không phải code)

---

## 6. PROMPT MẪU ĐỂ START CHAT MỚI

Khi mở chat mới, attach folder này và gửi prompt sau:

```
Tôi muốn chuyển app QC Component Manager từ Python Tkinter (desktop) sang Streamlit (web app).
Hãy đọc file HANDOVER.md trong folder này để hiểu toàn bộ context, sau đó:
1. Khẳng định bạn đã đọc và tóm tắt 3 quy tắc quan trọng nhất
2. Đề xuất cấu trúc thư mục streamlit_qc
3. Bắt đầu với app.py + 1 page (Tổng quan) để tôi review trước
4. Test với 2 file mẫu trong Sample_files/

Code hiện tại trong Tai_lieu_tham_khao/QCComponentManager_Tkinter_v1.py - hãy tận dụng tối đa.
```

---

## 7. NHỮNG ĐIỀU CẦN GIỮ NGUYÊN (KHÔNG ĐƯỢC ĐỔI)

1. **Schema DB** - vì có thể migrate dữ liệu hiện tại sang Streamlit
2. **Logic match cấu kiện** - 2 quy tắc tách prefix/suffix đã verify với dữ liệu thực
3. **8 loại inspection + DGRP** - đúng nghiệp vụ Đại Dũng
4. **Quy tắc status ACCEPTED** = PASS đủ DIR + VIR + NDT
5. **Format ngày hiển thị** DD/MM/YYYY, lưu YYYY-MM-DD
6. **Smart keywords** trong `SMART_KEYWORDS` dict
7. **Cấu trúc 7 cột bảng cấu kiện** - đã chốt với user

## 8. NHỮNG ĐIỀU CÓ THỂ CẢI THIỆN

1. **Multi-user authentication** (streamlit-authenticator)
2. **Phân quyền 3 vai trò**: Inspector / Manager / Admin
3. **Comment/Note** trên từng cấu kiện
4. **Upload ảnh** kèm inspection (Streamlit dễ hơn Tkinter)
5. **Chart Plotly** cho dashboard (tiến độ theo tuần)
6. **Mobile-friendly** layout (Streamlit responsive)
7. **Migrate SQLite → PostgreSQL** khi >5 user đồng thời

---

## 9. THÔNG TIN LIÊN HỆ NGHIỆP VỤ

- **Người dùng chính:** oke (QC Đại Dũng)
- **Dự án mẫu:** VIOLA Energy Center (8.217 cấu kiện), PVF Hưng Yên (73 cấu kiện)
- **Form Excel:** Đại Dũng VIOLA dùng "Member Punch No\nTên hồ sơ", PVF dùng "Tên cấu kiện"
- **Ngôn ngữ:** giao diện Tiếng Việt, code có thể bilingual

---

**Cập nhật lần cuối:** 18/05/2026
**Phiên bản Tkinter tham khảo:** v1.0.2
**Sẵn sàng bắt đầu Streamlit project!**
