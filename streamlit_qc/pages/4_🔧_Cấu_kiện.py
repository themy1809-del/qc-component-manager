# -*- coding: utf-8 -*-
"""Page: Bảng Cấu kiện."""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from streamlit_qc.core.constants import (
    ALL_STATUSES,
    APP_NAME,
    COMPONENT_FILTER_FIELDS,
    STATUS_LABELS,
)
from streamlit_qc.core.date_utils import format_date_vn
from streamlit_qc.core.state import (
    S_CURRENT_USER,
    get_current_project_id,
    get_db,
    init_session_state,
)
from streamlit_qc.core.theme import apply_theme
from streamlit_qc.core.ui import project_info_strip, render_page_header, render_top_nav
from streamlit_qc.services import component_service

st.set_page_config(
    page_title=f"Cấu kiện · {APP_NAME}",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()
render_top_nav(active_page="caukien")

proj = render_page_header(
    "Danh sách Cấu kiện",
    subtitle="Bảng 7 cột với inline edit, filter và sort",
    page_icon="🔧",
)
pid = get_current_project_id()
if pid is None or proj is None:
    st.warning("Chưa có dự án. Bấm **+ Dự án mới** ở header.")
    st.stop()

project_info_strip(proj)

# Pre-set overdue filter từ Trang chủ (nếu có)
_preset_overdue = st.session_state.pop("preset_overdue_filter", False)

flt_col1, flt_col2, flt_col3, flt_col4, flt_col5 = st.columns([2, 3, 1.2, 1.2, 1.3])
with flt_col1:
    # Pre-set status nếu user click từ KPI trang Tổng quan
    _status_options = ["ALL"] + ALL_STATUSES
    _preset = st.session_state.pop("preset_status_filter", None)
    _default_idx = _status_options.index(_preset) if _preset in _status_options else 0
    status = st.selectbox(
        "Trạng thái", _status_options,
        index=_default_idx,
        format_func=lambda s: "Tất cả" if s == "ALL" else STATUS_LABELS.get(s, s),
    )
with flt_col2:
    search = st.text_input("🔎 Tìm mã cấu kiện", placeholder="vd: 01BTG hoặc TB001")
with flt_col3:
    st.write("")
    st.write("")
    if st.button("🧹 Xoá lọc", use_container_width=True):
        for key in ["status", "search", "only_overdue"] + [f"flt_{f}" for f, _ in COMPONENT_FILTER_FIELDS]:
            st.session_state.pop(key, None)
        st.rerun()
with flt_col4:
    st.write("")
    st.write("")
    show_filters = st.toggle("🎚 Lọc cột", value=False)
with flt_col5:
    st.write("")
    st.write("")
    only_overdue = st.toggle(
        "⚠️ Chỉ overdue",
        value=_preset_overdue,
        key="only_overdue",
        help="Chỉ hiển thị cấu kiện đã Fit-up nhưng quá 7 ngày chưa Final",
    )

# Tính set ID overdue nếu filter bật (cache 60s)
@st.cache_data(ttl=60, show_spinner=False)
def _get_overdue_cached(_db, pid_in: int, threshold: int = 7) -> list[dict]:
    return component_service.get_overdue_components(_db, pid_in, threshold)

overdue_ids: set[int] = set()
if only_overdue:
    overdue_list = _get_overdue_cached(db, pid, 7)
    overdue_ids = {o["id"] for o in overdue_list}
    if not overdue_ids:
        st.success("🎉 Không có cấu kiện nào overdue! (Fit-up > 7 ngày chưa Final)")
        st.stop()

dropdown_filters = {}
if show_filters:
    pre_query = component_service.list_components(db, pid, status=status, search=search)
    uv = pre_query.unique_values
    cols = st.columns(len(COMPONENT_FILTER_FIELDS))
    for col, (field, label) in zip(cols, COMPONENT_FILTER_FIELDS):
        with col:
            values = ["(Tất cả)"] + uv.get(field, [])
            chosen = st.selectbox(label, values, key=f"flt_{field}")
            if chosen and chosen != "(Tất cả)":
                dropdown_filters[field] = chosen

with st.spinner("Đang tải..."):
    data = component_service.list_components(db, pid, status=status,
                                              search=search, dropdown_filters=dropdown_filters)

# Áp filter overdue (sau khi đã load list)
if only_overdue and overdue_ids:
    data.rows = [r for r in data.rows if r.id in overdue_ids]

status_label = "tất cả trạng thái" if status == "ALL" else STATUS_LABELS.get(status, status)
caption_parts = [
    f"Tổng dự án: **{data.total_in_db:,}**",
    f"Sau lọc {status_label}: **{data.after_status_search:,}**",
]
if dropdown_filters:
    caption_parts.append(f"Sau filter cột: **{data.after_dropdown_filter:,}**")
if only_overdue:
    caption_parts.append(f"⚠️ Chỉ overdue: **{len(data.rows):,}**")
st.caption(" · ".join(caption_parts))

if not data.rows:
    st.info("Không có cấu kiện nào khớp bộ lọc.")
    st.stop()

# Emoji cho từng inspection result
def _result_label(result: str) -> str:
    """Convert PASS/FAIL/RECHECK → emoji + text. '' = chưa KT."""
    if not result:
        return "⚪ Chưa"
    r = result.upper()
    if r == "PASS":
        return "🟢 Đạt"
    if r == "FAIL":
        return "🔴 K.đạt"
    if r == "RECHECK":
        return "🟡 Recheck"
    return f"⚪ {result}"


df_table = pd.DataFrame([
    {
        "id": r.id,
        "Tên cấu kiện": r.code,
        "Bản vẽ": r.name,
        "Revision": r.rev_no,
        "Xưởng": r.workshop,
        "Fit-up": _result_label(getattr(r, "fitup_status", "")),
        "Ngày Fit-up": getattr(r, "fitup_date", ""),
        "Final": _result_label(getattr(r, "final_status", "")),
        "Ngày Final": getattr(r, "final_date", ""),
    }
    for r in data.rows
])

SNAP_KEY = f"comp_snapshot_{pid}_{status}_{search}_{'_'.join(dropdown_filters.values())}"
if SNAP_KEY not in st.session_state:
    st.session_state[SNAP_KEY] = df_table.copy()

st.markdown(
    "💡 *Click ô Bản vẽ / Revision / Xưởng để sửa. "
    "Fit-up + Final + ngày tự động cập nhật từ Import Daily.*"
)

edited = st.data_editor(
    df_table, use_container_width=True, height=600, hide_index=True,
    column_config={
        "id": None,
        "Tên cấu kiện": st.column_config.TextColumn("Tên cấu kiện", disabled=True, width="medium"),
        "Bản vẽ": st.column_config.TextColumn("Bản vẽ", width="medium"),
        "Revision": st.column_config.TextColumn("Revision", width="small"),
        "Xưởng": st.column_config.TextColumn("Xưởng", width="small"),
        "Fit-up": st.column_config.TextColumn(
            "Fit-up", disabled=True, width="small",
            help="Kết quả Fit-up mới nhất từ file daily.",
        ),
        "Ngày Fit-up": st.column_config.TextColumn(
            "Ngày Fit-up", disabled=True, width="small",
            help="Ngày kiểm tra Fit-up.",
        ),
        "Final": st.column_config.TextColumn(
            "Final", disabled=True, width="small",
            help="Kết quả Final (nghiệm thu) mới nhất. PASS → ACCEPTED.",
        ),
        "Ngày Final": st.column_config.TextColumn(
            "Ngày Final", disabled=True, width="small",
            help="Ngày kiểm tra Final.",
        ),
    },
    key=f"editor_{pid}_{status}_{search}",
)

snapshot = st.session_state[SNAP_KEY]
edited_indexed = edited.set_index("id")
snap_indexed = snapshot.set_index("id")
changes = []
EDITABLE_COLS = ["Bản vẽ", "Revision", "Xưởng"]
UI_COL_TO_SERVICE = {
    "Bản vẽ": "name", "Revision": "rev_no", "Xưởng": "workshop",
}

for cid in edited_indexed.index:
    if cid not in snap_indexed.index:
        continue
    for col in EDITABLE_COLS:
        old_v = str(snap_indexed.at[cid, col] or "").strip()
        new_v = str(edited_indexed.at[cid, col] or "").strip()
        if old_v != new_v:
            changes.append((cid, UI_COL_TO_SERVICE[col], new_v))

btn_col1, btn_col2, _ = st.columns([2, 2, 4])
with btn_col1:
    save_btn = st.button(f"💾 Lưu thay đổi ({len(changes)})",
                         type="primary", use_container_width=True,
                         disabled=(len(changes) == 0))

if save_btn and changes:
    user = st.session_state[S_CURRENT_USER]
    n_ok = 0
    for cid, col, val in changes:
        try:
            component_service.update_component_field(db, cid, col, val, user_name=user)
            n_ok += 1
        except Exception as e:
            st.error(f"Lỗi {cid}: {e}")
    st.success(f"Đã lưu {n_ok} thay đổi.")
    st.session_state.pop(SNAP_KEY, None)
    st.rerun()

st.divider()
exp_col1, _ = st.columns([2, 6])
with exp_col1:
    csv_data = edited.drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 Tải CSV", csv_data,
                       file_name=f"cau_kien_{proj['code']}.csv",
                       mime="text/csv", use_container_width=True)
