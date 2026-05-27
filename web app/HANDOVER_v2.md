# BÀN GIAO DỰ ÁN v2.0 — QC Component Manager Web (Streamlit)

> **Tiếp nối HANDOVER.md** — tài liệu này tổng kết phiên bản **Streamlit Web v2.0** đã hoàn thành.
> Dành cho các phiên Claude / dev tiếp theo + chính oke khi cần refresh.

---

## 0. STATUS HIỆN TẠI

**Phiên bản:** `v2.0.0` (May 2026)
**Status:** 6/6 milestone hoàn thành, tested với data thực VIOLA + PVF
**Tổng code:** ~4.500 dòng Python, 31 file
**Performance:** Vượt tất cả Definition of Done

| Milestone | Trạng thái | Test |
|---|---|---|
| M1 — Scaffold + Tổng quan | ✅ | DB schema + logic ACCEPTED |
| M2 — Import Master | ✅ | VIOLA 8.212 dòng × 92 cột → 1.2s |
| M3 — Import Daily + DGRP + Debug | ✅ | 2 file DGRP thật + DGRP synthetic ACCEPTED |
| M4 — Bảng Cấu kiện | ✅ | Load 8.211 rows < 100ms (target 3s) |
| M5 — Báo cáo + Chart | ✅ | Export Excel 4 sheet 849KB |
| M6 — Quản trị + Docs | ✅ | Backup/Restore + audit log + 2 guide |

---

## 1. KIẾN TRÚC

**4 lớp Layered Architecture** (theo MASTER_PROMPT):

```
┌─────────────────────────────────────────────────┐
│  Presentation Layer    pages/*.py               │
│  (chỉ render UI)        + app.py (sidebar)      │
├─────────────────────────────────────────────────┤
│  Service Layer         services/*.py            │
│  (business logic, 95%   - project_service       │
│   copy từ Tkinter)      - dashboard_service     │
│                         - master_import_service │
│                         - daily_import_service  │
│                         - mapping_service       │
│                         - component_service     │
│                         - debug_match_service   │
│                         - report_service        │
│                         - admin_service         │
├─────────────────────────────────────────────────┤
│  Repository = embedded trong DB class           │
│  (đơn giản hoá - schema dùng data_json TEXT)    │
├─────────────────────────────────────────────────┤
│  Infrastructure Layer  core/*.py                │
│  - constants.py        SMART_KEYWORDS, types    │
│  - date_utils.py       format/parse date        │
│  - excel_engine.py     read xlsb/xlsx, smart    │
│  - db.py               SQLite WAL + schema      │
│  - state.py            session_state helpers    │
└─────────────────────────────────────────────────┘
```

## 2. CẤU TRÚC THƯ MỤC FINAL

```
streamlit_qc/                          (31 file Python + 3 doc + 2 config)
├── app.py                              Entry + sidebar
├── pages/                              6 page tự động render từ tên file
│   ├── 1_📊_Tổng_quan.py               KPI + chart + bảng xưởng
│   ├── 2_📥_Import_Master.py            Upload + auto-detect + VIOLA/PVF + template
│   ├── 3_📤_Import_Daily.py             9 loại NT + DGRP + Debug Match
│   ├── 4_🔧_Cấu_kiện.py                7 cột + inline edit + filter + modal
│   ├── 5_📈_Báo_cáo.py                 4 chart Plotly + xuất Excel 4 sheet
│   └── 6_⚙_Quản_trị.py                Audit + project CRUD + Backup/Restore
├── services/
│   ├── __init__.py
│   ├── project_service.py
│   ├── dashboard_service.py
│   ├── master_import_service.py
│   ├── daily_import_service.py
│   ├── mapping_service.py              VIOLA/PVF hardcoded + template JSON
│   ├── component_service.py            list + filter + inline edit
│   ├── debug_match_service.py
│   ├── report_service.py
│   └── admin_service.py                audit + backup/restore + project delete
├── core/
│   ├── __init__.py
│   ├── constants.py                    SMART_KEYWORDS, STANDARD_FIELDS (24)
│   ├── date_utils.py                   format_date_vn, parse_date_input
│   ├── excel_engine.py                 read_excel_any, smart_detect/match
│   ├── db.py                           DB class, schema, logic ACCEPTED
│   └── state.py                        session_state + DB singleton
├── data/                               (auto-tạo)
│   ├── qc_components.db                SQLite WAL
│   └── mapping_templates.json
├── docs/
│   ├── user_guide.md                   Cho QC trong phòng
│   └── admin_guide.md                  Cho IT vận hành
├── .streamlit/config.toml              theme + port + maxUploadSize
├── .gitignore
├── requirements.txt
├── README.md
└── __init__.py
```

## 3. CÁC QUYẾT ĐỊNH KIẾN TRÚC

### 3.1 Tại sao SQLite thay vì SQLAlchemy?

**Quyết định:** Dùng `sqlite3` trực tiếp, KHÔNG SQLAlchemy ORM.

**Lý do:**
- Schema cũ dùng `data_json TEXT` → ORM không có lợi (vẫn phải parse JSON)
- Copy logic Tkinter nhanh hơn 3-5x
- SQLite WAL mode đủ cho 10-50 user (Đại Dũng quy mô này)
- Tránh over-engineering cho phase 1

**Khi nào migrate SQLAlchemy?** Xem `docs/admin_guide.md` mục 8.

### 3.2 Tại sao tạm bỏ Login?

**Quyết định:** Milestone 1 không cài `streamlit-authenticator`.

**Thay vào đó:** Sidebar có dropdown "Người thao tác" → ghi vào `audit_log.user_name`.

**Khi nào add Login?** Khi:
- Phòng QC mở rộng > 50 người
- Cần phân quyền Inspector/Manager/Admin
- Cần audit từng user chi tiết hơn

**Cách add sau này:** Chỉ cần sửa `core/state.py` và `app.py`. Service layer không cần đổi.

### 3.3 Filter logic ở Python thay vì SQL

`component_service.list_components` query toàn bộ rows rồi filter dropdown ở Python.

**Lý do:** Các trường filter (zone/phase/material/workshop/type) nằm trong `data_json` → khó query SQL hiệu quả.

**Verified performance:** 8.211 rows filter trong 153ms — chấp nhận được.

**Tương lai:** Nếu DB > 50K rows, cân nhắc:
- Tách các trường filter ra cột riêng (denormalize)
- Hoặc dùng JSON_EXTRACT của SQLite

---

## 4. QUY TẮC NGHIỆP VỤ ĐÃ VERIFY

Tất cả copy NGUYÊN XI từ Tkinter v1.0.2, đã test với data thực:

### 4.1 Match mã cấu kiện (3 candidates)

File: `services/daily_import_service.py::_generate_match_candidates`

```python
candidates = [code]                          # 1. mã gốc
m = re.match(r"^(\d+)-(.+)$", code)
if m: candidates.append(m.group(2))          # 2. strip prefix "1-"
m_j = re.match(r"^(.+?)-J\d", code, re.I)
if m_j: candidates.append(m_j.group(1))      # 3. strip suffix "-J1"
```

**Verified:** `1-01ERC3001-001` → match `01ERC3001-001` trong master ✅

### 4.2 Logic ACCEPTED

File: `core/db.py::add_inspection`

- PASS DIR/VIR/NDT đơn lẻ → status = `PASSED`
- PASS đủ cả 3 (DIR + VIR + NDT) → status = `ACCEPTED`
- FAIL → `FAILED`
- Còn lại → `IN_PROGRESS`

**Verified với synthetic data:** ACCEPTED logic chạy đúng.

### 4.3 DGRP đặc biệt

File: `services/daily_import_service.py` (block `if inspection_type == "DGRP"`)

- Parse cột Remark với `core/date_utils.py::parse_remark_types`
- "Dim,Visual,NDT" → tạo 3 inspection (DIR + VIR + NDT)
- Remark rỗng/không parse được → fallback `["DIR"]`

**Lưu ý nghiệp vụ:** File DGRP thực tế của Đại Dũng hiện chỉ có "MAIN STRUCTURE" trong Remark → tất cả tạo DIR only. Cần QC nhập Remark đúng chuẩn `Dim,Visual,NDT` để auto-ACCEPTED.

### 4.4 Format ngày

| Tình huống | Format |
|---|---|
| Hiển thị UI | `DD/MM/YYYY` (`format_date_vn`) |
| Lưu DB | `YYYY-MM-DD` (ISO) |
| Input accept | Cả 2 (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, ...) |
| Tên file | `DD.MM.YYYY` → auto extract bằng regex |

---

## 5. PERFORMANCE — KẾT QUẢ TEST

| Test case | Target | Actual | Note |
|---|---|---|---|
| Import master VIOLA 8.212 dòng | < 30s | **1.2s** | 6.675 rows/sec |
| Import master PVF 73 dòng | < 5s | < 0.1s | — |
| Import DGRP 753 dòng → 46 inspection | < 10s | < 1s | — |
| Load bảng cấu kiện 8.211 rows | < 3s | **100ms** | 30x faster than target |
| Filter status PASSED | — | 10ms | — |
| Filter workshop AH4 (418 rows) | — | 153ms | — |
| Export Excel 4 sheet 8K rows | < 30s | 5.2s | 849 KB output |
| Compute report (92 inspections) | — | 92ms | — |

**Kết luận:** App responsive với data thực, gấp 10-30x target.

---

## 6. CONTRACT GIỮ NGUYÊN TỪ V1

**KHÔNG được đổi** khi maintain v2:

1. **Schema DB** (5 bảng: `projects`, `components`, `inspections`, `column_mappings`, `audit_log`)
2. **`SMART_KEYWORDS` dict** trong `core/constants.py`
3. **Logic 3 candidates match** trong `daily_import_service`
4. **Logic ACCEPTED** trong `core/db.py::add_inspection`
5. **Hardcoded VIOLA_MAPPING + PVF_MAPPING** trong `mapping_service.py`
6. **7 cột bảng cấu kiện** trong `COMPONENT_DISPLAY_COLUMNS`
7. **24 trường STANDARD_FIELDS**

Nếu cần đổi: hỏi anh oke (QC Đại Dũng) trước.

---

## 7. ĐIỂM CHƯA HOÀN HẢO / CẢI TIẾN TƯƠNG LAI

### 7.1 Phase 7 — Auth (đã skip ở M1)
- streamlit-authenticator + bcrypt
- 3 role: Inspector / Manager / Admin
- Page Admin → CRUD users

### 7.2 Phase 8 — Optimization
- Add cột riêng cho zone/phase/material/workshop/type (denormalize) nếu DB > 50K rows
- Migrate sang PostgreSQL nếu > 50 user đồng thời
- Cache @st.cache_data cho query master list

### 7.3 Phase 9 — Tính năng mở rộng
- Upload ảnh kèm inspection (Streamlit dễ hơn Tkinter)
- Comment/Note trên từng cấu kiện
- Notification khi PASSED → ACCEPTED
- Export PDF báo cáo (hiện chỉ có Excel)
- Mobile-friendly UI tweaks

### 7.4 Phase 10 — Testing
- pytest cho 9 service module
- Coverage target 70%
- Integration test với 4 file Excel mẫu
- CI/CD GitHub Actions

### 7.5 Phase 11 — i18n
- Hiện tại 100% tiếng Việt hardcode
- Tách string ra file `locales/vi.json` để dễ dịch sang EN

---

## 8. FILES THAM CHIẾU TRONG FOLDER

```
web app/                               (root — folder Cowork đã mount)
├── HANDOVER.md                         File bàn giao GỐC từ phiên Tkinter
├── HANDOVER_v2.md                      <-- File này (phiên Web)
├── MASTER_PROMPT.md                    Prompt yêu cầu chất lượng
├── UML_Streamlit_WebApp.html           5 diagram kiến trúc
├── Tai_lieu_tham_khao/
│   ├── QCComponentManager_Tkinter_v1.py  Source Tkinter 1457 dòng — GOLDEN TRUTH
│   ├── HUONG_DAN_SU_DUNG.md            UX guide Tkinter (tham khảo)
│   ├── SRS_QC_Component_Manager.docx   SRS chính thức
│   └── UML_HeThong_QuanLy_CauKien.html  UML hệ thống chung
├── Sample_files/                       4 file Excel mẫu để test
│   ├── PKL - VIOLA-STRUCTURAL STEEL - 2026.05.09.xlsb       (5MB, 8217 dòng)
│   ├── PKL - SÂN VẬN ĐỘNG PVF HƯNG YÊN - 2026.05.05.xlsx    (73 dòng)
│   ├── 15.5.2026_10725-009 DGRP VIOLA - STRUCTURAL STEEL.xlsx
│   └── 16.05.2026__10725-009 DGRP VIOLA - STRUCTURAL STEEL.xlsx
└── streamlit_qc/                       <-- DỰ ÁN CHÍNH
    └── ... (xem mục 2 ở trên)
```

---

## 9. RUN BOOK

### 9.1 Chạy local (dev)

```bat
cd "web app"
pip install -r streamlit_qc\requirements.txt
cd streamlit_qc
streamlit run app.py
```

### 9.2 Deploy production

Xem `streamlit_qc/docs/admin_guide.md` — đầy đủ 11 mục.

### 9.3 Restore khi mất data

1. Page **⚙ Quản trị → 💾 Restore** → upload file `.db` hoặc `.zip`
2. App backup file cũ thành `.bak` trước
3. Restart Streamlit để load DB mới

---

## 10. PROMPT BÀN GIAO CHO PHIÊN CLAUDE TIẾP

Khi mở chat mới, attach folder này và gửi:

```
Tôi muốn maintain/cải tiến app QC Component Manager Web v2.0 (Streamlit).
Hãy đọc HANDOVER_v2.md để hiểu toàn bộ context, sau đó:

1. Confirm đã đọc + tóm tắt 3 quy tắc nghiệp vụ trong mục 4
2. Tôi sẽ nói task cụ thể (vd: thêm tính năng X, fix bug Y, optimize Z)
3. Bạn đề xuất giải pháp + hỏi clarification nếu cần
4. Code theo layered architecture đã chốt (pages → services → core)
5. KHÔNG đổi schema DB + 7 contract trong mục 6 nếu không hỏi tôi trước

Source Tkinter golden truth ở Tai_lieu_tham_khao/QCComponentManager_Tkinter_v1.py
Files mẫu test ở Sample_files/
```

---

**Cập nhật lần cuối:** 2026-05-18
**Tác giả phiên này:** Claude + oke (QC Đại Dũng)
**Phiên bản:** v2.0.0
**Trạng thái:** Sẵn sàng deploy lên PC server LAN phòng QC
