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

# === MỞ RỘNG block-container + THU GỌN BẢNG CHO TRANG NÀY ===
st.markdown(
    """
    <style>
    /* Mở rộng main container */
    [data-testid="stMain"] .block-container,
    .block-container {
        max-width: 100% !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
    }
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
        width: 100% !important;
    }
    [data-testid="stDataEditor"] table {
        width: 100% !important;
        min-width: 1500px;
    }
    /* Header bảng — chữ đậm + nền nhạt */
    [data-testid="stDataEditor"] thead th {
        text-align: center !important;
        font-weight: 600 !important;
        background: #F1F5F9 !important;
        color: #0F1E40 !important;
        padding: 6px 4px !important;
    }
    [data-testid="stDataEditor"] tbody td {
        padding: 4px 8px !important;
        font-size: 13px !important;
    }
    /* ===== THU GỌN 3 CỘT ĐẦU "PHỤ" ===== */
    /* Cột 1 = index (icon ✏️ + ⋮ của Streamlit) — ẨN hoàn toàn */
    [data-testid="stDataEditor"] thead th:nth-child(1),
    [data-testid="stDataEditor"] tbody td:nth-child(1) {
        max-width: 0 !important;
        width: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        border: 0 !important;
    }
    /* Cột 2 = ✓ checkbox bulk select — siêu gọn */
    [data-testid="stDataEditor"] thead th:nth-child(2),
    [data-testid="stDataEditor"] tbody td:nth-child(2) {
        max-width: 42px !important;
        width: 42px !important;
        padding: 2px !important;
        text-align: center !important;
    }
    /* Cột 3 = Stt — gọn */
    [data-testid="stDataEditor"] thead th:nth-child(3),
    [data-testid="stDataEditor"] tbody td:nth-child(3) {
        max-width: 50px !important;
        width: 50px !important;
        text-align: center !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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

flt_col1, flt_col2, flt_col_btn, flt_col3, flt_col4, flt_col5 = st.columns([2, 2.6, 0.8, 1.2, 1.2, 1.3])
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
        "🔎 Tìm mã / bản vẽ",
        value=_preset_search or "",
        placeholder="vd: 01BTG · hoặc dán nhiều mã: TB001, TB002, TB003",
        key="search_input",
        help="1 từ khoá = tìm trong Mã + Bản vẽ + Member No (không phân biệt hoa thường). "
             "Dán NHIỀU mã cách nhau bởi dấu phẩy / dấu cách / xuống dòng = lọc đúng các mã đó.",
    )
with flt_col_btn:
    st.write("")
    st.write("")
    if st.button("🔍 Tìm", use_container_width=True,
                 help="Bấm để áp filter (hoặc Enter trong ô)"):
        # Trigger rerun với giá trị search hiện tại — Streamlit tự rerun khi text_input đổi,
        # nhưng nút này giúp UX rõ ràng + force-refresh khi cần.
        st.rerun()
with flt_col3:
    st.write("")
    st.write("")
    if st.button("🧹 Xoá lọc", use_container_width=True):
        for key in ["status", "search", "search_input", "only_overdue", "flt_daily"] + [f"flt_{f}" for f, _ in COMPONENT_FILTER_FIELDS]:
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

# Hàng 2: filter "có / chưa có file daily"
flt2_col1, flt2_col2, _ = st.columns([2, 2, 6])
with flt2_col1:
    daily_filter = st.selectbox(
        "🗂 Lọc theo file daily",
        ["Tất cả", "Đã có Fit-up", "Chưa có Fit-up",
         "Đã có Final", "Chưa có Final", "⚠ Có Final, thiếu Fit-up"],
        key="flt_daily",
        help="Lọc theo trạng thái import file daily (cột Import Fit-up / Import Final).",
    )

# Tính set ID overdue nếu filter bật (cache 60s)
@st.cache_data(ttl=60, show_spinner=False, max_entries=10)
def _get_overdue_cached(_db, pid_in: int, threshold: int = 7) -> list[dict]:
    return component_service.get_overdue_components(_db, pid_in, threshold)


@st.cache_data(ttl=60, show_spinner=False, max_entries=6)
def _list_components_cached(_db, pid_in: int, status_in: str, search_in: str, filters_key: tuple):
    """Cache 60s, max 6 bản — tránh load lại + tránh phình RAM gói free."""
    return component_service.list_components(
        _db, pid_in, status=status_in, search=search_in,
        dropdown_filters=dict(filters_key) if filters_key else None,
    )

@st.cache_data(ttl=300, show_spinner=False, max_entries=20)
def _filter_options_cached(_db, pid_in: int) -> dict[str, list[str]]:
    """Dropdown options bằng SQL DISTINCT — không tải cả bảng như trước."""
    return component_service.get_filter_options(_db, pid_in)


overdue_ids: set[int] = set()
if only_overdue:
    overdue_list = _get_overdue_cached(db, pid, 7)
    overdue_ids = {o["id"] for o in overdue_list}
    if not overdue_ids:
        st.success("🎉 Không có cấu kiện nào overdue! (Fit-up > 7 ngày chưa Final)")
        st.stop()

dropdown_filters = {}
if show_filters:
    uv = _filter_options_cached(db, pid)
    cols = st.columns(len(COMPONENT_FILTER_FIELDS))
    for col, (field, label) in zip(cols, COMPONENT_FILTER_FIELDS):
        with col:
            values = ["(Tất cả)"] + uv.get(field, [])
            chosen = st.selectbox(label, values, key=f"flt_{field}")
            if chosen and chosen != "(Tất cả)":
                dropdown_filters[field] = chosen

# === Loading skeleton: shimmer placeholder cho 7K+ rows ===
_load_placeholder = st.empty()
_load_placeholder.markdown(
    """
    <style>
    @keyframes _qc_shimmer {
      0%{background-position:200% 0;} 100%{background-position:-200% 0;}
    }
    .qc-skel{background:linear-gradient(90deg,#f1f5f9 25%,#e2e8f0 50%,#f1f5f9 75%);
        background-size:200% 100%;animation:_qc_shimmer 1.5s infinite;
        border-radius:6px;margin:6px 0;}
    </style>
    <div class="qc-skel" style="height:32px;"></div>
    <div class="qc-skel" style="height:200px;"></div>
    <div style="text-align:center;color:#64748b;font-size:13px;margin-top:8px;">
      ⏳ Đang tải dữ liệu cấu kiện... (dự án lớn có thể mất 2–5 giây)
    </div>
    """,
    unsafe_allow_html=True,
)
data = _list_components_cached(
    db, pid, status, search, tuple(sorted(dropdown_filters.items())),
)
_load_placeholder.empty()

# Áp filter overdue (sau khi đã load list)
if only_overdue and overdue_ids:
    data.rows = [r for r in data.rows if r.id in overdue_ids]

# Áp filter file daily
if daily_filter == "Đã có Fit-up":
    data.rows = [r for r in data.rows if getattr(r, "fitup_imported_at", "")]
elif daily_filter == "Chưa có Fit-up":
    data.rows = [r for r in data.rows if not getattr(r, "fitup_imported_at", "")]
elif daily_filter == "Đã có Final":
    data.rows = [r for r in data.rows if getattr(r, "final_imported_at", "")]
elif daily_filter == "Chưa có Final":
    data.rows = [r for r in data.rows if not getattr(r, "final_imported_at", "")]
elif daily_filter == "⚠ Có Final, thiếu Fit-up":
    # Bỏ sót khâu: đã nghiệm thu Final nhưng không có hồ sơ Fit-up
    data.rows = [r for r in data.rows
                 if getattr(r, "final_status", "") and not getattr(r, "fitup_status", "")]

status_label = "tất cả trạng thái" if status == "ALL" else STATUS_LABELS.get(status, status)
caption_parts = [
    f"Tổng dự án: **{data.total_in_db:,}**",
    f"Sau lọc {status_label}: **{data.after_status_search:,}**",
]
if dropdown_filters:
    caption_parts.append(f"Sau filter cột: **{data.after_dropdown_filter:,}**")
if daily_filter and daily_filter != "Tất cả":
    caption_parts.append(f"🗂 {daily_filter}: **{len(data.rows):,}**")
if only_overdue:
    caption_parts.append(f"⚠️ Chỉ overdue: **{len(data.rows):,}**")
st.caption(" · ".join(caption_parts))

if not data.rows:
    st.info("Không có cấu kiện nào khớp bộ lọc.")
    st.stop()

# === PHÂN TRANG: chỉ render 1 trang để bảng nhẹ (18k dòng → ì trình duyệt) ===
_total_rows = len(data.rows)
_pgc1, _pgc2, _pgc3 = st.columns([1.2, 1.2, 3])
with _pgc1:
    _page_size = st.selectbox(
        "Số dòng / trang", [200, 500, 1000, 2000], index=1, key="comp_page_size"
    )
_n_pages = max(1, -(-_total_rows // _page_size))
with _pgc2:
    _page = st.number_input(
        f"Trang (1–{_n_pages})", min_value=1, max_value=_n_pages, value=1, step=1
    )
_start = (int(_page) - 1) * _page_size
_end = min(_start + _page_size, _total_rows)
with _pgc3:
    st.markdown(
        f"<div style='padding-top:34px;color:#64748b;'>Hiển thị "
        f"<b>{_start + 1:,}–{_end:,}</b> / <b>{_total_rows:,}</b> dòng</div>",
        unsafe_allow_html=True,
    )
_page_rows = data.rows[_start:_end]

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


def _short_guid(g: str) -> str:
    """Rút gọn GUID: '2ad18b07-b471-4cc6-...' → '2ad18b07…' (8 ký tự + dấu ellipsis)."""
    s = str(g or "").strip()
    if not s:
        return ""
    if len(s) > 10:
        return s[:8] + "…"
    return s


df_table = pd.DataFrame([
    {
        "id": r.id,
        "✓": False,  # Checkbox cho bulk update
        "Stt": _start + idx + 1,
        "Tên cấu kiện": r.code,
        "Bản vẽ": r.name,
        "Rev": r.rev_no,
        "Xưởng": r.workshop,
        "Mã Gui": _short_guid(getattr(r, "guid", "")),
        "Kiểm tra fitup": _result_label(getattr(r, "fitup_status", "")),
        "Ngày Fit-up": getattr(r, "fitup_date", ""),
        "Người KT Fit-up": getattr(r, "fitup_inspector", ""),
        "Kiểm tra final": _result_label(getattr(r, "final_status", "")),
        "Ngày Final": getattr(r, "final_date", ""),
        "Người KT Final": getattr(r, "final_inspector", ""),
        "Ghi chú": getattr(r, "note", ""),
    }
    for idx, r in enumerate(_page_rows)
])

SNAP_KEY = f"comp_snapshot_{pid}_{status}_{search}_{'_'.join(dropdown_filters.values())}_{_page}_{_page_size}"
if SNAP_KEY not in st.session_state:
    st.session_state[SNAP_KEY] = df_table.copy()

st.markdown(
    "💡 *Click ô Bản vẽ / Revision / Xưởng / Ghi chú để sửa. "
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
        "Stt": st.column_config.NumberColumn(
            "Stt", disabled=True, width="small",
            help="Số thứ tự dòng hiện tại.",
        ),
        # Tên cấu kiện vừa đủ (mã ~13 ký tự)
        "Tên cấu kiện": st.column_config.TextColumn(
            "Tên cấu kiện", disabled=True, width="medium",
        ),
        # Bản vẽ thu nhỏ vì thường ngắn (vd: BLB3001, BTG3005)
        "Bản vẽ": st.column_config.TextColumn(
            "Bản vẽ", width="small",
            help="Số bản vẽ kỹ thuật. Nếu thấy sai → vào Import Master → Tinh chỉnh mapping → "
                 "đổi cột 'name' sang cột Excel chứa số bản vẽ đúng.",
        ),
        "Rev": st.column_config.TextColumn("Rev", width="small"),
        "Xưởng": st.column_config.TextColumn("Xưởng", width="small"),
        "Mã Gui": st.column_config.TextColumn(
            "Mã Gui", disabled=True, width="small",
            help="Mã GUID rút gọn (8 ký tự đầu + …). Tích chọn 1 cấu kiện để xem GUID đầy đủ trong panel comment.",
        ),
        "Kiểm tra fitup": st.column_config.TextColumn(
            "Kiểm tra fitup", disabled=True, width="small",
            help="Kết quả Fit-up mới nhất từ file daily.",
        ),
        "Ngày Fit-up": st.column_config.TextColumn(
            "Ngày Fit-up", disabled=True, width="small",
            help="Ngày kiểm tra Fit-up.",
        ),
        "Người KT Fit-up": st.column_config.TextColumn(
            "Người KT Fit-up", disabled=True, width="medium",
            help="Người kiểm tra Fit-up của lần gần nhất.",
        ),
        "Kiểm tra final": st.column_config.TextColumn(
            "Kiểm tra final", disabled=True, width="small",
            help="Kết quả Final (nghiệm thu) mới nhất. PASS → ACCEPTED.",
        ),
        "Ngày Final": st.column_config.TextColumn(
            "Ngày Final", disabled=True, width="small",
            help="Ngày kiểm tra Final.",
        ),
        "Ghi chú": st.column_config.TextColumn(
            "Ghi chú", width="medium",
            help="Ghi chú QC — gõ trực tiếp vào ô rồi bấm 💾 Lưu thay đổi.",
        ),
        "Người KT Final": st.column_config.TextColumn(
            "Người KT Final", disabled=True, width="medium",
            help="Người kiểm tra Final của lần gần nhất.",
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

    # === Copy link cấu kiện để share ===
    try:
        from urllib.parse import urlencode
        share_params = urlencode({"pid": pid, "code": single_code})
        share_link = f"?{share_params}"
        st.code(share_link, language=None)
        st.caption(
            f"📎 Link share cấu kiện **{single_code}** — paste sau URL gốc của app, "
            "hoặc copy thẳng để dán vào Zalo/email."
        )
    except Exception:
        pass

    # === 📅 TIMELINE VIEW — lịch sử inspection của 1 cấu kiện ===
    with st.expander(f"📅 Timeline kiểm tra **{single_code}**", expanded=True):
        timeline_rows = db.conn.execute(
            """SELECT inspection_type, inspection_date, inspector, result,
                      report_no, rfi_no, source_file, imported_at
               FROM inspections WHERE component_id=?
               ORDER BY inspection_date ASC, id ASC""",
            (single_cid,),
        ).fetchall()

        if not timeline_rows:
            st.info("Cấu kiện này chưa có inspection nào. Vào **Bulk KT** hoặc **Import Daily**.")
        else:
            # Vertical timeline với màu theo loại
            TYPE_COLOR = {
                "FUR": "#F59E0B",   # amber — Fit-up
                "DIR": "#3B82F6",   # blue — Dimension
                "VIR": "#0EA5E9",   # sky — Visual
                "NDT": "#A855F7",   # purple — NDT
                "DGRP": "#10B981",  # emerald — Final
            }
            RESULT_ICON = {"PASS": "✅", "FAIL": "❌", "RECHECK": "🔁"}
            timeline_html = '<div style="border-left:3px solid #D4A744;padding-left:18px;margin:8px 0;">'
            for r in timeline_rows:
                itype = r["inspection_type"] or "?"
                color = TYPE_COLOR.get(itype, "#94A3B8")
                idate = (r["inspection_date"] or "(chưa có ngày)")[:10]
                result = r["result"] or ""
                icon = RESULT_ICON.get(result, "⚪")
                inspector = r["inspector"] or ""
                rfi = r["rfi_no"] or ""
                report = r["report_no"] or ""
                src = r["source_file"] or ""
                timeline_html += f"""
                <div style="margin-bottom:14px;position:relative;">
                  <div style="position:absolute;left:-26px;top:2px;width:14px;height:14px;
                       border-radius:50%;background:{color};
                       border:3px solid white;box-shadow:0 0 0 2px {color};"></div>
                  <div style="font-weight:700;color:{color};font-size:14px;">
                    {icon} {itype} — {result} <span style="color:#64748B;font-weight:400;">({idate})</span>
                  </div>
                  <div style="color:#475569;font-size:12px;margin-top:2px;">
                    👤 {inspector or '—'} · 📋 RFI: <code>{rfi or '—'}</code>
                    · 🔖 Report: <code>{report or '—'}</code>
                    · 📁 <code>{src}</code>
                  </div>
                </div>
                """
            timeline_html += "</div>"
            st.markdown(timeline_html, unsafe_allow_html=True)

            # Mini stats
            from collections import Counter
            type_counts = Counter(r["inspection_type"] for r in timeline_rows)
            result_counts = Counter(r["result"] for r in timeline_rows if r["result"])
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Tổng inspection", len(timeline_rows))
            mc2.metric(
                "Loại nhiều nhất",
                f"{type_counts.most_common(1)[0][0]} ({type_counts.most_common(1)[0][1]})"
                if type_counts else "—",
            )
            mc3.metric(
                "PASS rate",
                f"{result_counts.get('PASS', 0) * 100 / max(1, sum(result_counts.values())):.0f}%",
            )

    with st.expander(f"💬 Comment cho cấu kiện **{single_code}**", expanded=False):
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

    # ============================================================
    # 📋 EXPORT NFI THEO TEMPLATE CHUẨN
    # ============================================================
    from streamlit_qc.services import rfi_export_service as rfi_exp

    with st.expander(
        f"📋 Xuất NFI cho {n_selected} cấu kiện đã chọn (theo template chuẩn dự án)",
        expanded=False,
    ):
        has_tpl = rfi_exp.has_template(pid)
        ec1, ec2 = st.columns([2, 3])
        with ec1:
            st.markdown("**Template chuẩn của dự án:**")
            if has_tpl:
                tpl_prefix, tpl_counter = rfi_exp.get_template_rfi_seed(pid)
                st.success(
                    f"✅ Đã có template — prefix `{tpl_prefix}`, counter cuối `{tpl_counter}`"
                )
                if st.button("🔄 Thay template khác", key="reload_tpl"):
                    st.session_state["show_upload_tpl"] = True
            else:
                st.warning("⚠️ Dự án chưa có template. Upload file mẫu RFI trước.")
                st.session_state["show_upload_tpl"] = True

        with ec2:
            if st.session_state.get("show_upload_tpl") or not has_tpl:
                up = st.file_uploader(
                    "Upload file Excel template RFI (giữ format gốc)",
                    type=["xlsx"],
                    key=f"upload_tpl_{pid}",
                    help="App sẽ lưu template này riêng cho dự án. Sheet bắt buộc: "
                         "'RFI' + 'MEMBER LIST'. RFI No. lấy từ C7 sheet RFI.",
                )
                if up is not None:
                    try:
                        path = rfi_exp.save_template(pid, up.getvalue())
                        st.success(f"✅ Đã lưu template: `{path.name}`")
                        st.session_state.pop("show_upload_tpl", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi lưu template: {e}")

        if has_tpl:
            st.markdown("---")
            st.markdown("**🎨 Nội dung trang bìa RFI** *(điền sẵn vào sheet RFI)*")
            cb1, cb2, cb3, cb4 = st.columns([1.5, 1.5, 1.5, 1.5])
            with cb1:
                stage_choice = st.selectbox(
                    "Inspection Stage",
                    ["Fit-Up", "Final"],
                    key="rfi_stage",
                    help="Điền vào cột 'Inspection Stage' của MEMBER LIST.",
                )
            with cb2:
                from datetime import date as _date
                rfi_date = st.date_input(
                    "Ngày RFI", value=_date.today(), key="rfi_date",
                    help="Ngày đề nghị kiểm tra (ô F64 sheet RFI).",
                )
            with cb3:
                itp_doc_input = st.text_input(
                    "ITP Doc. Reference No.",
                    value="DDC-QAQC-VIO20025-ITP-001",
                    key="rfi_itp_doc",
                    help="Mã văn bản ITP (ô C19).",
                )
            with cb4:
                itp_item_input = st.text_input(
                    "Item no (ITP)", value="3.2", key="rfi_itp_item",
                    help="Số mục trong ITP (ô H14). Vd: 3.2",
                )

            # Discipline checkboxes
            st.markdown("**🔖 Discipline** *(tick các loại sẽ kiểm tra)*")
            disc_options = list(rfi_exp.DISCIPLINES)
            default_disc = ["Welding", "Dimension"] if stage_choice == "Fit-Up" else ["Dimension", "Coating"]
            disciplines_sel = st.multiselect(
                "Loại kiểm tra (Discipline)",
                disc_options,
                default=default_disc,
                key="rfi_disciplines",
                label_visibility="collapsed",
            )

            st.markdown("---")
            ex1, ex2, ex3 = st.columns([2, 2, 3])
            with ex1:
                try:
                    preview_no = rfi_exp.get_next_rfi_no_by_template(db, pid)
                    st.info(f"**RFI No. sẽ sinh:**\n\n`{preview_no}`")
                except Exception as e:
                    st.error(f"Lỗi preview RFI No.: {e}")
                    preview_no = None
            with ex2:
                mtype_override = st.text_input(
                    "Member Type (override)",
                    value="",
                    placeholder="Để trống = auto-detect",
                    key="rfi_mtype_override",
                    help="Ô C22. Để trống thì app tự lấy loại chiếm đa số.",
                )
            with ex3:
                st.write("")
                st.write("")
                if st.button(
                    f"📥 Xuất NFI cho {n_selected} cấu kiện",
                    type="primary",
                    use_container_width=True,
                    key="export_nfi_btn",
                ):
                    try:
                        with st.spinner(f"Đang tạo file NFI cho {n_selected} cấu kiện..."):
                            file_bytes, rfi_no = rfi_exp.export_rfi_file(
                                db=db,
                                pid=pid,
                                project_code=proj["code"],
                                component_ids=[int(c) for c in selected_ids],
                                user_name=st.session_state.get(S_CURRENT_USER, ""),
                                inspection_stage=stage_choice,
                                disciplines=disciplines_sel,
                                itp_doc=itp_doc_input or None,
                                itp_item_no=itp_item_input or None,
                                member_type_override=mtype_override or None,
                                proposed_date=rfi_date.isoformat() if rfi_date else None,
                            )
                        st.session_state["last_nfi_bytes"] = file_bytes
                        st.session_state["last_nfi_no"] = rfi_no
                        st.success(
                            f"✅ Đã tạo file NFI **{rfi_no}** "
                            f"({n_selected} cấu kiện) — bấm Tải xuống bên dưới."
                        )
                    except FileNotFoundError as e:
                        st.error(f"❌ {e}")
                    except Exception as e:
                        st.exception(e)

            # Show download button nếu vừa export xong
            if st.session_state.get("last_nfi_bytes"):
                st.download_button(
                    f"💾 Tải file: {st.session_state['last_nfi_no']}.xlsx",
                    data=st.session_state["last_nfi_bytes"],
                    file_name=f"{st.session_state['last_nfi_no']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    bk1, bk2, bk3, bk4, bk5 = st.columns([2, 2, 2, 1.5, 1.5])
    with bk1:
        bulk_field = st.selectbox(
            "Cột cần đổi",
            ["Xưởng", "Bản vẽ", "Rev", "Ghi chú"],
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
            UI_TO_FLD = {"Xưởng": "workshop", "Bản vẽ": "name",
                         "Rev": "rev_no", "Ghi chú": "note"}
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
EDITABLE_COLS = ["Bản vẽ", "Rev", "Xưởng", "Ghi chú"]
UI_COL_TO_SERVICE = {
    "Bản vẽ": "name", "Rev": "rev_no", "Xưởng": "workshop", "Ghi chú": "note",
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

# ============================================================
# 📜 LỊCH SỬ NFI ĐÃ XUẤT
# ============================================================
st.divider()
from streamlit_qc.services import rfi_export_service as _rfi_exp_h
_nfi_history = _rfi_exp_h.list_exported_nfis(pid)
with st.expander(
    f"📜 Lịch sử NFI đã xuất ({len(_nfi_history)} file)", expanded=False,
):
    if not _nfi_history:
        st.info(
            "Chưa có file NFI nào được xuất cho dự án này. "
            "Tick chọn cấu kiện ở bảng trên + bấm 📋 **Xuất NFI** để tạo file đầu tiên."
        )
    else:
        for nfi in _nfi_history[:50]:
            hc1, hc2, hc3, hc4 = st.columns([2.5, 2, 1.5, 1])
            with hc1:
                st.markdown(
                    f"**`{nfi['rfi_no']}`**  \n"
                    f"<span style='color:#64748B;font-size:12px;'>"
                    f"📅 {nfi['ts'].strftime('%d/%m/%Y %H:%M')}"
                    f"</span>",
                    unsafe_allow_html=True,
                )
            with hc2:
                rfi_db = db.conn.execute(
                    "SELECT response_note, inspection_type, submitted_by, "
                    "       proposed_date, status "
                    "FROM rfis WHERE project_id=? AND rfi_no=?",
                    (pid, nfi['rfi_no']),
                ).fetchone()
                if rfi_db:
                    note = rfi_db["response_note"] or ""
                    n_codes = note.count(",") + 1 if note else 0
                    st.caption(
                        f"📋 {rfi_db['inspection_type']} · "
                        f"{n_codes} cấu kiện · "
                        f"👤 {rfi_db['submitted_by'] or '—'} · "
                        f"📌 {rfi_db['status']}"
                    )
                else:
                    st.caption(f"📦 {nfi['size_bytes']:,} bytes")
            with hc3:
                try:
                    file_bytes_h = _rfi_exp_h.read_exported_nfi(pid, nfi['rfi_no'])
                    if file_bytes_h:
                        st.download_button(
                            "💾 Tải lại",
                            file_bytes_h,
                            file_name=f"{nfi['rfi_no']}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"redl_{nfi['rfi_no']}",
                        )
                except Exception:
                    st.caption("⚠️ file lỗi")
            with hc4:
                if st.button(
                    "🗑", key=f"del_nfi_{nfi['rfi_no']}",
                    help=f"Xóa file {nfi['rfi_no']}.xlsx",
                ):
                    if _rfi_exp_h.delete_exported_nfi(pid, nfi['rfi_no']):
                        db.conn.execute(
                            "DELETE FROM rfis WHERE project_id=? AND rfi_no=?",
                            (pid, nfi['rfi_no']),
                        )
                        db.conn.commit()
                        st.success(f"Đã xóa {nfi['rfi_no']}")
                        st.rerun()
            st.markdown(
                "<hr style='margin:6px 0;border:0;border-top:1px solid #E2E8F0;'>",
                unsafe_allow_html=True,
            )
        if len(_nfi_history) > 50:
            st.caption(f"_Chỉ hiển thị 50 file mới nhất / tổng {len(_nfi_history)}._")
