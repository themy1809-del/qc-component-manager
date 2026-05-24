# -*- coding: utf-8 -*-
"""Page: Bulk Inspection Entry — nhập kết quả inspection cho nhiều cấu kiện cùng lúc.

Workflow:
  1. Chọn filter (status: PENDING/IN_PROGRESS, workshop, search)
  2. Tick checkbox các cấu kiện cần nhập
  3. Chọn inspection type + result + date + RFI
  4. Preview confirm → Submit
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from streamlit_qc.core.constants import APP_NAME
from streamlit_qc.core.state import (
    get_current_project_id,
    get_current_user,
    get_db,
    init_session_state,
)
from streamlit_qc.core.theme import apply_theme
from streamlit_qc.core.ui import project_info_strip, render_page_header, render_top_nav

st.set_page_config(
    page_title=f"Bulk KT · {APP_NAME}",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("bulk_kt")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav()
render_page_header(
    "⚡ Bulk Inspection Entry",
    "Nhập kết quả nghiệm thu HÀNG LOẠT — chọn nhiều cấu kiện 1 lần",
)
project_info_strip()

pid = get_current_project_id()
if not pid:
    st.warning("⚠️ Vui lòng chọn dự án ở Tổng quan trước.")
    st.stop()

# ====================================================================
# 1. FILTER cấu kiện
# ====================================================================
st.markdown("##### 1️⃣ Lọc cấu kiện cần nghiệm thu")

f1, f2, f3, f4 = st.columns([1.2, 1.2, 2, 1])
status_pick = f1.multiselect(
    "Trạng thái",
    ["PENDING", "IN_PROGRESS", "PASSED", "ACCEPTED", "FAILED"],
    default=["PENDING", "IN_PROGRESS"],
)
# Lấy danh sách workshop từ DB
ws_rows = db.conn.execute(
    "SELECT DISTINCT json_extract(data_json, '$.workshop') AS ws "
    "FROM components WHERE project_id=?"
    if not db.is_postgres else
    "SELECT DISTINCT data_json::json->>'workshop' AS ws "
    "FROM components WHERE project_id=%s",
    (pid,),
).fetchall()
workshops = sorted({r["ws"] for r in ws_rows if r["ws"]})
ws_pick = f2.multiselect("Xưởng", workshops, default=[])
search = f3.text_input("🔎 Tìm mã cấu kiện chứa", value="")
limit = f4.number_input("Tối đa", 10, 1000, 200, step=50)

# Build query
where = ["project_id=?"]
params: list = [pid]
if status_pick:
    placeholders = ",".join("?" * len(status_pick))
    where.append(f"status IN ({placeholders})")
    params.extend(status_pick)
if search.strip():
    where.append("LOWER(code) LIKE ?")
    params.append(f"%{search.strip().lower()}%")

q = (
    f"SELECT id, code, status, data_json FROM components "
    f"WHERE {' AND '.join(where)} ORDER BY code LIMIT ?"
)
params.append(int(limit))

rows = db.conn.execute(q, tuple(params)).fetchall()

# Filter by workshop python-side (vì JSON extract khác cú pháp giữa SQLite/Postgres)
records = []
for r in rows:
    try:
        d = json.loads(r["data_json"]) if r["data_json"] else {}
    except (json.JSONDecodeError, TypeError):
        d = {}
    ws = d.get("workshop", "")
    if ws_pick and ws not in ws_pick:
        continue
    records.append({
        "✓": False,
        "ID": r["id"],
        "Mã cấu kiện": r["code"],
        "Xưởng": ws,
        "Bản vẽ": d.get("manual_drawing") or d.get("drawing") or "",
        "Trạng thái": r["status"],
    })

if not records:
    st.warning("⚠️ Không có cấu kiện nào khớp bộ lọc.")
    st.stop()

st.caption(f"Tìm thấy **{len(records)}** cấu kiện. Tick checkbox cột **✓** để chọn.")

df_pick = pd.DataFrame(records)

edited = st.data_editor(
    df_pick,
    use_container_width=True,
    height=380,
    hide_index=True,
    column_config={
        "✓": st.column_config.CheckboxColumn("✓", width="small"),
        "ID": None,
        "Mã cấu kiện": st.column_config.TextColumn(disabled=True),
        "Xưởng": st.column_config.TextColumn(disabled=True),
        "Bản vẽ": st.column_config.TextColumn(disabled=True),
        "Trạng thái": st.column_config.TextColumn(disabled=True),
    },
    key="bulk_pick_table",
)

selected = edited[edited["✓"] == True]
n_sel = len(selected)
st.markdown(f"**Đã chọn: {n_sel} cấu kiện**")

if n_sel == 0:
    st.info("👆 Tick checkbox để chọn cấu kiện trước khi tiếp tục.")
    st.stop()

st.divider()

# ====================================================================
# 2. CHỌN inspection params
# ====================================================================
st.markdown("##### 2️⃣ Thông số nghiệm thu áp dụng cho TẤT CẢ cấu kiện đã chọn")

c1, c2, c3 = st.columns(3)
ins_type = c1.selectbox(
    "Loại nghiệm thu",
    ["FUR", "DIR", "VIR", "NDT", "DGRP"],
    format_func=lambda t: {
        "FUR": "FUR — Fit-up",
        "DIR": "DIR — Dimension",
        "VIR": "VIR — Visual",
        "NDT": "NDT — Kiểm tra không phá huỷ",
        "DGRP": "DGRP — Final / Đóng gói",
    }.get(t, t),
)
result = c2.selectbox("Kết quả", ["PASS", "FAIL", "RECHECK"])
ins_date = c3.date_input("Ngày KT", value=date.today())

c4, c5, c6 = st.columns(3)
inspector = c4.text_input("Người KT", value=get_current_user())
rfi_no = c5.text_input("Số RFI", placeholder="VD: RFI-2026-001")
report_no = c6.text_input("Số báo cáo", placeholder="VD: R-001")

note = st.text_input("Ghi chú chung (áp cho tất cả)", value="")

# ====================================================================
# 3. PREVIEW + COMMIT
# ====================================================================
st.divider()
st.markdown("##### 3️⃣ Xem trước & xác nhận")

preview_df = selected[["Mã cấu kiện", "Xưởng", "Trạng thái"]].copy()
preview_df["Loại KT mới"] = ins_type
preview_df["Kết quả"] = result
preview_df["Ngày KT"] = ins_date.isoformat()
preview_df["Người KT"] = inspector
st.dataframe(preview_df, use_container_width=True, hide_index=True, height=200)

st.warning(
    f"⚠️ Sẽ thêm **{n_sel} record** vào bảng inspections với "
    f"`type={ins_type}`, `result={result}`, `date={ins_date}`. "
    "Hành động này KHÔNG thể undo qua UI."
)

confirm = st.checkbox(f"✅ Tôi xác nhận nhập {n_sel} inspection")

if st.button(
    f"🚀 Submit {n_sel} inspection",
    type="primary",
    disabled=(not confirm),
    use_container_width=True,
):
    n_ok = 0
    n_err = 0
    errors = []
    progress = st.progress(0.0)
    for i, row in enumerate(selected.itertuples(index=False)):
        try:
            db.add_inspection(
                pid=pid,
                cid=int(row.ID),
                itype=ins_type,
                idate=ins_date.isoformat(),
                inspector=inspector or "",
                result=result,
                rep=report_no or "",
                rfi=rfi_no or "",
                note=note or "",
                src="BULK",
            )
            n_ok += 1
        except Exception as e:
            n_err += 1
            errors.append(f"{row._asdict().get('Mã cấu kiện', '?')}: {e}")
        progress.progress((i + 1) / n_sel)

    db.conn.commit()
    db.log(
        get_current_user(), "BULK_INSPECTION", "components", None,
        f"type={ins_type} result={result} n_ok={n_ok} n_err={n_err}",
    )
    progress.empty()

    if n_err == 0:
        st.success(f"✅ Hoàn tất: đã nhập **{n_ok}** inspection.")
        st.balloons()
    else:
        st.warning(f"⚠️ Có lỗi: {n_ok} OK / {n_err} FAIL")
        for e in errors[:10]:
            st.text(f"  • {e}")
    st.info("👉 Vào trang **Cấu kiện** để xem kết quả cập nhật, hoặc **Báo cáo** để xuất file.")
