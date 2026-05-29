# BÀN GIAO PHIÊN CHAT — 2026-05-29

> **Mục đích**: Tài liệu này tổng kết toàn bộ phiên chat ngày 27-29/05/2026. Dán nội dung vào chat mới để Claude tiếp tục công việc mượt mà.

---

## 🚨 CÔNG VIỆC ĐANG DỞ — ƯU TIÊN CAO NHẤT

### 1. RESTORE DATA TRÊN CLOUD (chưa hoàn thành)
**Tình trạng**: Streamlit Cloud bị reset DB → app cloud trống hoàn toàn. DB local trên máy còn nguyên:
- 4 dự án: **Viola** (3.079 ck), **PVF** (73), **PQA Phú Quốc** (11.405), **THẢO CHECK-VIOLA** (1.896)
- Tổng **16.453 cấu kiện + 11.116 inspections + 118 audit log**
- File: `streamlit_qc/data/qc_components.db` (11.6 MB)

**Việc cần làm — chạy 6 lệnh git tuần tự**:
```bat
cd /d "D:\Workshop AH6-AH9\Cải tiến hồ sơ\Phần mềm hồ sơ\Streamlit_Web_App\web app"
git add -f streamlit_qc/data/qc_components.db
git status
git commit -m "restore: backup DB 4 du an, 16k cau kien, 11k inspections"
git push
```
Đợi 2 phút → vào `qc-daidung.streamlit.app` → phải thấy 4 dự án trong dropdown.

### 2. MIGRATE SANG POSTGRES (Supabase) — KHẨN
Vì SQLite trên Streamlit Cloud reset mỗi lần redeploy → push code = mất data. File `migrate_sqlite_to_postgres.py` đã có sẵn skeleton trong folder gốc.

User đã chọn: **"Plan backup tự động hourly lên Drive/S3"** (option 2) — nhưng mình recommend migrate Postgres luôn vì backup không cứu được data giữa các interval.

---

## ✅ NHỮNG VIỆC ĐÃ HOÀN THÀNH TRONG SESSION

### Bug fixes
1. **`DB.add_inspection() missing 'src'`** — Thêm `src="MASTER"` thiếu ở `master_import_service.py` dòng 247 (DGRP/Final block).
2. **`UNIQUE constraint failed: components.project_id, code`** — Đổi `upsert_component` từ SELECT-then-INSERT (race condition) sang try-INSERT-except-UPDATE atomic. Thêm normalize ký tự vô hình trong `code` (zero-width space, NBSP, BOM, bidi marks).
3. **Smart-detect mapping sai** cho file Bison: cột `code` map nhầm "Tên cấu kiện cũ" (46 unique) → fix thắng "Member Punch No" (43.640 unique). Cột `name` map nhầm "KIỂM TRA TÊN CẤU KIỆN" → fix thắng "Tên bản vẽ".

### Features mới
4. **Cột "Import Fit-up" + "Import Final"** trong bảng Cấu kiện — hiện timestamp file daily import (DD/MM/YYYY HH:MM).
5. **Nút 🔍 Tìm** bên cạnh ô search cấu kiện.
6. **Xuất NFI theo template Excel chuẩn** — service mới `rfi_export_service.py`:
   - Lưu template per-project tại `streamlit_qc/data/templates/project_{pid}/`
   - Auto sinh RFI No. từ prefix template (vd `200POR241141-VIOLA-RFI-A033` → A034)
   - Điền sheet RFI (C7, C19 ITP Doc, H14 Item no, C22 Member Type, F64 Date, G59 Inspector, các ô X discipline) + MEMBER LIST (N rows)
   - INSERT OR IGNORE vào bảng `rfis`
   - Lưu file đã xuất vào `streamlit_qc/data/exports/project_{pid}/`
7. **Form custom trang bìa NFI** trong page Cấu kiện — Discipline multiselect, ITP Doc, Item no, Date, Member Type override.
8. **Lịch sử NFI đã xuất** — panel ở cuối trang Cấu kiện, có nút Tải lại + Xóa từng file.
9. **Toggle "🔒 Lấy HẾT mọi cột Excel khi import"** (mặc định BẬT) trong Import Master — auto map cột chưa map thành field `extra_<slug>` để không mất dữ liệu.
10. **Nút "✨ Map HẾT các cột"** trong panel Tinh chỉnh mapping + helper `_auto_map_all_columns` + `_slugify_col`.
11. **Banner "Sẽ lấy HẾT N cột"** trong Preview Import Master.
12. **Filter "Có file daily / Chưa có file daily"** trong bảng Cấu kiện.

### UI/UX
13. Bảng Cấu kiện cấu trúc mới (11 cột): Stt, Tên cấu kiện, Bản vẽ, Rev, Xưởng, Mã Gui, Kiểm tra fitup, Ngày Fit-up, Người KT Fit-up, Kiểm tra final, Ngày Final, Người KT Final.
14. Mở rộng bảng full chiều rộng màn hình (CSS override `block-container` max-width: 100%).
15. Rút gọn Mã Gui hiển thị 8 ký tự + "…".
16. Ẩn cột index Streamlit (✏️ ⋮) + thu hẹp cột ✓ checkbox + cột Stt.

---

## 📋 ĐÁNH GIÁ TỔNG QUAN APP — VIỆC CẦN XỬ LÝ

### 🔴 P0 (rủi ro vận hành — phải làm sớm)
1. **`core/db.py` quá lớn (1.348 dòng / 18 bảng)** — God class, tách thành `core/db/` package
2. **Schema `data_json TEXT`** không scale — denormalize zone/phase/material/workshop/type/weight/length thành cột riêng (đặc biệt khi dự án Bison 43K dòng)
3. **Bảng Cấu kiện load 33-43K row vào `st.data_editor`** — không pagination, sẽ chậm/treo
4. **Không có test tự động** — 0 file pytest, bug đã từng lộ ở production
5. **Auth bị skip** — `streamlit-authenticator` chưa enable, ai có URL đều vào được
6. **Streamlit Cloud + SQLite không bền** — cần migrate Postgres (Supabase free tier)

### 🟠 P1 (UX / maintainability)
7. Page `4_🔧_Cấu_kiện.py` 38KB / 900+ dòng — làm quá nhiều việc, tách components
8. **5 chỗ f-string trong UPDATE SQL** — risk thấp nhưng cần whitelist field names
9. **Mapping hardcode 4 dự án** — chuyển sang user templates dynamic
10. **`rfis.rfi_no UNIQUE`** + 1 component_id — không support 1 RFI = N cấu kiện đúng cách. Cần bảng `rfi_components` many-to-many.
11. **34 chỗ `except Exception:`** — cần audit + log proper
12. HANDOVER_v2.md outdated — cần HANDOVER_v3 cho features mới

### 🟡 P2 (cải tiến)
13. Chỉ 14 chỗ `@st.cache_data` — thêm cho dashboard / project list / count queries
14. CSS injection per-page bừa bộn — gom vào `core/theme.py`
15. Magic numbers (min-width: 1600px, limit=50000, threshold_days=7…) — đẩy vào constants
16. UI mobile responsive chưa kiểm chứng cho pages mới (RFI, Bàn giao, NCR)
17. i18n — 100% tiếng Việt hardcode, tách `locales/vi.json` + `en.json`

### 🟢 P3 (nice-to-have)
18. Đa upload file daily cùng lúc
19. Notification (email/Zalo bot) khi cấu kiện ACCEPTED hoặc RFI REJECTED
20. Excel export đa-format
21. Audit log viewer cải tiến (filter/search/export)
22. Bulk import multiple projects từ thư mục

---

## ⚠️ LƯU Ý KỸ THUẬT QUAN TRỌNG

### Vấn đề Edit/Write tool truncate file
Trong session này, Edit/Write tool của Cowork **truncate file giữa chừng nhiều lần** (db.py, master_import_service.py, constants.py, excel_engine.py, page files). Triệu chứng: file mất phần đuôi, có null bytes, hoặc duplicate dòng.

**Workaround đã dùng**:
- Viết file lớn / mới: dùng `cat <<EOF > file.py` qua bash thay vì Write tool
- Sửa nhỏ: dùng `sed -i` qua bash thay vì Edit tool
- Sau mỗi sửa: chạy `python3 -c "import ast; ast.parse(open(f).read())"` để verify

### Cấu trúc DB hiện tại (18 bảng)
```
projects, components, inspections, audit_log, column_mappings,
users, comments, ncrs, qc_reports, rfis,
itp_records, itp_templates, materials, material_assignments,
batches, batch_items, share_tokens, access_log
```
Bảng `components` có `UNIQUE (project_id, code)` + `status DEFAULT 'PENDING'` + `data_json TEXT`. Bảng `rfis` có `rfi_no TEXT UNIQUE NOT NULL` (hiện chưa support many-to-many với components).

### Quy tắc nghiệp vụ ACCEPTED (giữ nguyên, KHÔNG đổi)
- DGRP (Final) PASS → status = `ACCEPTED`
- DGRP (Final) FAIL → `FAILED`
- FUR (Fit-up) PASS → `IN_PROGRESS`
- FUR (Fit-up) FAIL → `FAILED`
- PASS đủ DIR+VIR+NDT → `ACCEPTED` (backward compat)

### Mapping smart-detect mới (sau fix Bison)
`SMART_KEYWORDS["code"]` priority: `tên hồ sơ` → `member punch no` → `punch no` → ... → `tên cấu kiện` (xuống cuối).
`SMART_KEYWORDS["name"]` priority: `tên bản vẽ` → `drawing no` → `drawing number` → ... → `drawing`.
`smart_match_columns` loại header có suffix `cũ/old/backup/mới/new/version/history` + prefix `kiểm tra/check/ktra` cho các field nhận diện chính.

---

## 📂 FILE STRUCTURE (15.700 dòng / 13 pages / 24 services)

```
web app/
├── streamlit_qc/
│   ├── app.py
│   ├── pages/  (13 files: 1_Tổng_quan → 13_Share)
│   ├── services/ (24 files, lớn nhất: report 22K, component 21K, pdf 14K, rfi_export 12K)
│   ├── core/
│   │   ├── db.py        (1.348 dòng — god class, cần tách)
│   │   ├── constants.py (SMART_KEYWORDS, STANDARD_FIELDS, STATUS_*)
│   │   ├── excel_engine.py (smart_match_columns, smart_detect_header_row)
│   │   ├── date_utils.py
│   │   ├── state.py
│   │   ├── theme.py     (CSS apply_theme — max-width 1400px global)
│   │   ├── ui.py        (render_page_header, project_info_strip, render_top_nav)
│   │   └── sidebar.py
│   ├── data/
│   │   ├── qc_components.db  (DB chính — gitignored)
│   │   ├── mapping_templates.json (user-saved templates)
│   │   ├── templates/project_{pid}/rfi_template.xlsx
│   │   └── exports/project_{pid}/{rfi_no}.xlsx
│   ├── docs/  (user_guide.md, admin_guide.md)
│   └── .streamlit/config.toml
├── Sample_files/ (PKL VIOLA xlsb, PKL PVF xlsx, DGRP VIOLA xlsx ×2)
├── Tai_lieu_tham_khao/ (Tkinter source, SRS, UML)
├── HANDOVER.md, HANDOVER_v2.md, HANDOFF_SESSION_2026-05-29.md ← FILE NÀY
├── MASTER_PROMPT.md
├── migrate_sqlite_to_postgres.py (skeleton — chưa chạy)
└── *.bat (START_SERVER, START_TUNNEL, PUSH, DEPLOY, GET_MY_IP)
```

---

## 📝 PROMPT ĐỂ DÁN VÀO CHAT MỚI

```
Tôi muốn tiếp tục dự án QC Component Manager Web (Streamlit) ở folder này.

Đọc file HANDOFF_SESSION_2026-05-29.md để hiểu context đầy đủ:
- Status hiện tại + việc đang dở
- 22 features + 7 bug fixes đã làm phiên trước
- Đánh giá P0-P3 các vấn đề cần xử lý
- Lưu ý kỹ thuật quan trọng (đặc biệt: Edit/Write tool hay truncate file, dùng bash heredoc thay thế)

Sau khi đọc xong, hãy:
1. Tóm tắt 2 việc đang DỞ ưu tiên cao nhất
2. Hỏi tôi muốn làm việc nào trước

Quy ước giao tiếp: tôi nói "Plan tính năng X" / "Lập kế hoạch cho X" = chỉ phân tích kế hoạch, không code.
Câu khác = code luôn.
```

---

## 🗓 LỊCH SỬ COMMIT GỢI Ý (sau khi user push)
```
HEAD → "restore: backup DB 4 du an, 16k cau kien, 11k inspections"
    ↑
"fix: atomic upsert components + normalize code invisible chars"
"fix: smart-detect uu tien Member Punch No + Ten ban ve, loai cot cu/check"
"ui: an cot index Streamlit + thu gon checkbox + Stt"
"ui: rut gon Ma Gui 8 ky tu + Ten cau kien medium"
"ui: dieu chinh width cot bang Cau kien + CSS header dam"
"ui: bang cau kien rong toan man hinh (100% width)"
"feat: bang cau kien moi (Stt, Ma Gui, Nguoi KT Fit-up/Final)"
"feat: Import Master luon lay het cot Excel (auto-map extra_*)"
"feat: NFI export custom trang bia + lich su + filter daily"
"feat: NFI export theo template + cot Ngay Import + nut Tim"
"fix: add missing src='MASTER' in DGRP/Final import"
```

---

**Tác giả phiên này**: Claude + oke (QC Đại Dũng)
**Ngày kết phiên**: 2026-05-29
**Tổng task đã hoàn thành**: 29
**Status**: 🟡 Đang chờ user push DB restore lên GitHub
