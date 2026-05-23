# QC Component Manager — Web v2.0

Phiên bản Streamlit của QC Component Manager, kế thừa logic từ bản Tkinter v1.0.2.

Dành cho phòng QC Đại Dũng (10-50 người dùng đồng thời).

## Hiện trạng (Milestone 1)

Đã có:

- Sidebar chọn dự án + nhập tên QC (audit log)
- Tạo dự án mới
- Page Tổng quan: 6 KPI cards, progress bar, 2 chart Plotly, bảng thống kê xưởng, 200 inspection mới nhất
- DB schema giữ nguyên từ v1 (5 bảng: projects, components, inspections, column_mappings, audit_log)

Sắp có (các milestone tiếp):

- M2: Import Master (PKL) với smart auto-detect
- M3: Import Daily + DGRP + Debug Match
- M4: Bảng cấu kiện 7 cột với inline edit
- M5: Báo cáo Excel + chart tiến độ tuần
- M6: Auth login + Admin

## Cài đặt

```bash
pip install -r requirements.txt
```

## Chạy

```bash
cd streamlit_qc
streamlit run app.py
```

Mặc định mở ở [http://localhost:8501](http://localhost:8501). Trong LAN nội bộ các máy QC vào bằng `http://<server-ip>:8501`.

## Cấu trúc thư mục

```
streamlit_qc/
├── app.py                  # Entry point + sidebar
├── pages/
│   └── 1_📊_Tổng_quan.py   # Dashboard
├── services/               # Business logic
│   ├── project_service.py
│   └── dashboard_service.py
├── core/                   # Infrastructure
│   ├── constants.py        # SMART_KEYWORDS, INSPECTION_TYPES, ...
│   ├── date_utils.py       # format_date_vn, parse_date_input, ...
│   ├── excel_engine.py     # read_excel_any, smart_detect_header_row
│   ├── db.py               # SQLite wrapper
│   └── state.py            # session_state helpers
├── data/                   # SQLite DB (auto-tạo)
└── .streamlit/config.toml  # theme + port
```

## Quy tắc nghiệp vụ (KHÔNG ĐỔI)

1. **Match mã cấu kiện**: thử mã gốc → strip `^\d+-` (prefix) → strip `-J.*$` (suffix)
2. **Trạng thái ACCEPTED**: chỉ khi PASS đủ cả 3 loại DIR + VIR + NDT
3. **DGRP**: 1 dòng Excel sinh nhiều inspection records theo cột Remark
4. **Format ngày**: hiển thị `DD/MM/YYYY`, lưu DB `YYYY-MM-DD`

## Quyết định kiến trúc

**Tại sao Milestone 1 dùng `sqlite3` trực tiếp thay vì SQLAlchemy?**

- Schema cũ dùng `data_json TEXT` → ORM không có lợi nhiều, vẫn phải parse JSON
- Copy logic Tkinter nhanh hơn (95% reuse)
- SQLite WAL mode đủ cho 10-50 user
- SQLAlchemy có thể add ở Milestone 5+ khi cần migrate PostgreSQL

Khi nào cần đổi sang SQLAlchemy:

- Số user vượt 50 đồng thời (cần PostgreSQL)
- Cần migration phức tạp (Alembic)
- Cần ORM relationships cho tính năng mới (vd: comment, attachment)
