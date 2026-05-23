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

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("caukien")
from streamlit_qc.core.state import require_login
require_login()
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
    # Pre-set search query nếu user click từ Global Search ở Trang chủ
    _preset_search = st.session_state.pop("preset_search_query", None)
    search = st.text_input(
        "🔎 Tìm mã cấu kiện",
        value=_preset_search or "",
        placeholder="vd: 01BTG hoặc TB001",
    )
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
        "✓": False,  # Checkbox cho bulk update
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
        "✓": st.column_config.CheckboxColumn(
            "✓", width="small",
            help="Tick để chọn cấu kiện cho bulk update / xóa hàng loạt",
        ),
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

# ============================================================
# BULK UPDATE PANEL — hiện khi có row được tick checkbox
# ============================================================
selected_ids = edited[edited["✓"] == True]["id"].tolist()
n_selected = len(selected_ids)

# ============================================================
# 💬 COMMENT PANEL — hiện khi chọn ĐÚNG 1 cấu kiện
# ============================================================
if n_selected == 1:
    from streamlit_qc.services import comment_service
    single_cid = int(selected_ids[0])
    single_row = edited[edited["id"] == single_cid].iloc[0]
    single_code = single_row["Tên cấu kiện"]

    with st.expander(f"💬 Comment cho cấu kiện **{single_code}**", expanded=True):
        # Form thêm comment
        new_comment = st.text_area(
            "Thêm comment", placeholder="Ghi chú QC, mô tả vấn đề, tag đồng nghiệp...",
            height=80, key=f"new_comment_{single_cid}",
        )
        cc1, cc2, _ = st.columns([2, 2, 4])
        with cc1:
            if st.button("💾 Lưu comment", type="primary", use_container_width=True,
                         disabled=(not new_comment.strip())):
                try:
                    user = st.session_state[S_CURRENT_USER]
                    comment_service.add_comment(db, single_cid, user, new_comment.strip())
                    st.success("Đã lưu comment")
                    # Clear via counter pattern
                    if f"new_comment_counter_{single_cid}" not in st.session_state:
                        st.session_state[f"new_comment_counter_{single_cid}"] = 0
                    st.session_state[f"new_comment_counter_{single_cid}"] += 1
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

        # Hiển thị comment history
        comments = comment_service.list_comments(db, single_cid, limit=50)
        if comments:
            st.markdown(f"**{len(comments)} comment(s):**")
            for c in comments:
                ts = str(c.get("ts", ""))[:16].replace("T", " ")
                user = c.get("user_name") or "anonymous"
                st.markdown(
                    f"<div style='background:#f8fafc;border-left:3px solid #D4A744;"
                    f"padding:8px 12px;margin:6px 0;border-radius:6px;font-size:13px;'>"
                    f"<div style='color:#64748b;font-size:11px;margin-bottom:4px;'>"
                    f"<b style='color:#0F1E40;'>{user}</b> · {ts}"
                    f"</div>"
                    f"<div style='color:#0F172A;white-space:pre-wrap;'>{c['text']}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("_Chưa có comment nào._")

if n_selected > 0:
    st.markdown(
        f'<div style="background:#fffdf7;border:2px solid #D4A744;border-radius:10px;'
        f'padding:14px 18px;margin:10px 0;">'
        f'<div style="font-weight:700;color:#0F1E40;font-size:14px;margin-bottom:8px;">'
        f'🎯 Đã chọn <b style="color:#D4A744;font-size:18px;">{n_selected}</b> cấu kiện · Sửa hàng loạt:'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    bk1, bk2, bk3, bk4, bk5 = st.columns([2, 2, 2, 1.5, 1.5])
    with bk1:
        bulk_field = st.selectbox(
            "Cột cần đổi",
            ["Xưởng", "Bản vẽ", "Revision"],
            key="bulk_field",
        )
    with bk2:
        bulk_value = st.text_input(
            "Giá trị mới",
            placeholder=f"Đổi thành...",
            key="bulk_value",
        )
    with bk3:
        st.write("")
        st.write("")
        if st.button(
            f"💾 Áp dụng cho {n_selected} cấu kiện",
            type="primary", use_container_width=True,
            disabled=(not bulk_value.strip()),
        ):
            UI_TO_FLD = {"Xưởng": "workshop", "Bản vẽ": "name", "Revision": "rev_no"}
            fld = UI_TO_FLD[bulk_field]
            user = st.session_state[S_CURRENT_USER]
            n_ok, n_fail = 0, 0
            errors = []
            with st.spinner(f"Đang cập nhật {n_selected} cấu kiện..."):
                for cid in selected_ids:
                    try:
                        component_service.update_component_field(
                            db, int(cid), fld, bulk_value.strip(), user_name=user
                        )
                        n_ok += 1
                    except Exception as e:
                        n_fail += 1
                        if len(errors) < 5:
                            errors.append(f"ID {cid}: {e}")
            if n_ok:
                st.success(f"✅ Đã cập nhật **{n_ok}** cấu kiện. Cột `{bulk_field}` = `{bulk_value.strip()}`")
            if n_fail:
                st.error(f"❌ {n_fail} thất bại. Lỗi mẫu:\n" + "\n".join(errors))
            st.session_state.pop(SNAP_KEY, None)
            st.rerun()
    with bk4:
        st.write("")
        st.write("")
        if st.button("✗ Bỏ chọn hết", use_container_width=True):
            st.session_state.pop(SNAP_KEY, None)
            st.rerun()
    with bk5:
        st.write("")
        st.write("")
        if st.button(
            f"🗑 Xóa {n_selected}",
            use_container_width=True,
            help="Xóa cấu kiện khỏi DB (cascade xóa luôn inspection). KHÔNG hoàn tác được.",
        ):
            # Confirm 2 lần qua session_state
            st.session_state["bulk_delete_confirm"] = True

    # Confirm dialog xóa
    if st.session_state.get("bulk_delete_confirm"):
        st.error(
            f"⚠️ **XÁC NHẬN XÓA {n_selected} CẤU KIỆN?** "
            f"Hành động này KHÔNG hoàn tác được. Inspection liên quan cũng bị xóa."
            f"⚠️ **XÁC NHẬN XÓA {n_selected} CẤU KIỆN?** "
            f"Hành động này KHÔNG hoàn tác được. Inspection liên quan cũng bị xóa."
        )
        confirm_col1, confirm_col2, _ = st.columns([2, 2, 4])
        with confirm_col1:
            if st.button("✅ Xác nhận XÓA", type="primary", use_container_width=True):
                user = st.session_state[S_CURRENT_USER]
                placeholders = ",".join("?" * len(selected_ids))
                db.conn.execute(
                    f"DELETE FROM components WHERE id IN ({placeholders})",
                    selected_ids,
                )
                db.conn.commit()
                db.log(user, "BULK_DELETE", "component", None,
                       f"deleted={n_selected}, ids={selected_ids[:10]}")
                st.success(f"Đã xóa {n_selected} cấu kiện.")
                st.session_state.pop("bulk_delete_confirm", None)
                st.session_state.pop(SNAP_KEY, None)
                st.rerun()
        with confirm_col2:
            if st.button("❌ Hủy", use_container_width=True):
                st.session_state.pop("bulk_delete_confirm", None)
                st.rerun()

    st.write("")

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
exp_col1, exp_col2, exp_col3, _ = st.columns([2, 2, 3, 3])
with exp_col1:
    csv_data = edited.drop(columns=["id", "✓"]).to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 Tải CSV", csv_data,
                       file_name=f"cau_kien_{proj['code']}.csv",
                       mime="text/csv", use_container_width=True)

with exp_col2:
    accepted_ids = [r.id for r in data.rows if r.status == "ACCEPTED"]
    n_accepted = len(accepted_ids)
    gen_pdf = st.button(
        f"📄 PDF biên bản ({n_accepted} ACCEPTED)",
        use_container_width=True,
        disabled=(n_accepted == 0),
        help="Xuất PDF biên bản nghiệm thu cho TẤT CẢ cấu kiện ACCEPTED đang hiển thị.",
    )

with exp_col3:
    pdf_limit = st.number_input(
        "Giới hạn số cấu kiện / PDF", min_value=1, max_value=200, value=50,
    )

if gen_pdf and accepted_ids:
    try:
        from streamlit_qc.services import pdf_service
        ids_to_export = accepted_ids[:int(pdf_limit)]
        with st.spinner(f"Đang tạo PDF cho {len(ids_to_export)} cấu kiện..."):
            pdf_bytes = pdf_service.generate_certificate(
                db, pid=pid, component_ids=ids_to_export,
                inspector_signoff=st.session_state.get(S_CURRENT_USER, ""),
                customer_signoff="",
            )
        st.success(f"✅ Đã tạo PDF với {len(ids_to_export)} cấu kiện.")
        from datetime import datetime as _dt
        st.download_button(
            "💾 Tải PDF",
            pdf_bytes,
            file_name=f"BBNT_{proj['code']}_{_dt.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    except ImportError:
        st.error("Chưa cài reportlab.")
    except Exception as e:
        st.error(f"Lỗi: {e}")
