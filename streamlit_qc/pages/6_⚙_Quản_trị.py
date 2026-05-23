# -*- coding: utf-8 -*-
"""Page: Quản trị."""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import datetime as dt
import pandas as pd
import streamlit as st

from streamlit_qc.core.constants import APP_NAME, APP_VERSION
from streamlit_qc.core.state import (
    S_CURRENT_USER,
    get_current_project_id,
    get_db,
    init_session_state,
    set_current_project_id,
)
from streamlit_qc.core.theme import apply_theme
from streamlit_qc.core.ui import render_page_header, render_top_nav
from streamlit_qc.services import admin_service, project_service

st.set_page_config(
    page_title=f"Quản trị · {APP_NAME}",
    page_icon="⚙",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("quantri")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav(active_page="quantri")

user = st.session_state[S_CURRENT_USER]
render_page_header(
    "Quản trị hệ thống",
    subtitle=f"Audit log · Quản lý dự án · Backup/Restore · v{APP_VERSION}",
    page_icon="⚙",
    show_project_picker=False,
)
st.caption(f"👤 Đang thao tác: **{user}**")

tab_audit, tab_proj, tab_backup = st.tabs([
    "📋 Lịch sử thao tác",
    "🏗 Quản lý dự án",
    "💾 Backup / Restore",
])

with tab_audit:
    stats = admin_service.get_audit_stats(db)
    m1, m2, m3 = st.columns(3)
    m1.metric("Tổng records", f"{stats['total']:,}")
    m2.metric("Số action", len(stats["by_action"]))
    m3.metric("Số user", len(stats["by_user"]))

    st.divider()
    f1, f2, f3 = st.columns(3)
    with f1:
        flt_user = st.text_input("User", placeholder="vd: themy")
    with f2:
        flt_action = st.selectbox("Action",
            ["", "CREATE_PROJECT", "UPDATE_PROJECT", "DELETE_PROJECT",
             "IMPORT_MASTER", "IMPORT_DAILY", "EDIT_COMPONENT",
             "CLEAR_COMPONENTS", "RESET_INSPECTIONS", "EXPORT_REPORT"])
    with f3:
        flt_entity = st.text_input("Entity", placeholder="vd: project")

    d1, d2, d3 = st.columns(3)
    with d1:
        flt_from = st.date_input("Từ ngày", value=dt.date.today() - dt.timedelta(days=30), format="DD/MM/YYYY")
    with d2:
        flt_to = st.date_input("Đến ngày", value=dt.date.today(), format="DD/MM/YYYY")
    with d3:
        st.write("")
        st.write("")
        do_search = st.button("🔎 Tìm", type="primary", use_container_width=True)

    if do_search or "audit_query_run" in st.session_state:
        st.session_state["audit_query_run"] = True
        df_log = admin_service.query_audit_log(db, user=flt_user, action=flt_action,
                                                entity=flt_entity, date_from=flt_from,
                                                date_to=flt_to, limit=1000)
        st.caption(f"Tìm thấy **{len(df_log)}** records.")
        if not df_log.empty:
            st.dataframe(df_log, hide_index=True, use_container_width=True, height=500)

with tab_proj:
    projects = project_service.list_projects(db)
    if not projects:
        st.info("Chưa có dự án.")
    else:
        proj_df = pd.DataFrame([
            {"ID": p["id"], "Mã": p["code"], "Tên": p["name"],
             "Địa điểm": p["location"] or "", "Owner": p["owner"] or "",
             "Tạo lúc": p["created_at"],
             "Số cấu kiện": db.conn.execute(
                 "SELECT COUNT(*) c FROM components WHERE project_id=?", (p["id"],)
             ).fetchone()["c"],
             "Số inspection": db.conn.execute(
                 "SELECT COUNT(*) c FROM inspections WHERE project_id=?", (p["id"],)
             ).fetchone()["c"]}
            for p in projects
        ])
        st.dataframe(proj_df, hide_index=True, use_container_width=True)

        st.divider()
        proj_options = {f"[{p['code']}] {p['name']}": p["id"] for p in projects}
        picked_label = st.selectbox("Chọn dự án để sửa/xoá", list(proj_options.keys()))
        picked_pid = proj_options[picked_label]
        proj = next(p for p in projects if p["id"] == picked_pid)

        with st.form(f"edit_proj_{picked_pid}"):
            e1, e2 = st.columns(2)
            with e1:
                new_name = st.text_input("Tên dự án", value=proj["name"])
                new_location = st.text_input("Địa điểm", value=proj["location"] or "")
            with e2:
                new_owner = st.text_input("Owner", value=proj["owner"] or "")
                new_note = st.text_area("Ghi chú", value=proj["note"] or "", height=68)
            if st.form_submit_button("💾 Lưu", type="primary"):
                try:
                    admin_service.update_project(db, picked_pid,
                        name=new_name, location=new_location,
                        owner=new_owner, note=new_note, user_name=user)
                    st.success("Đã lưu.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

        st.divider()
        d1, d2 = st.columns(2)
        with d1:
            if st.button("🔄 Reset Inspections", use_container_width=True):
                n = admin_service.reset_inspections(db, picked_pid, user_name=user)
                st.success(f"Đã xoá {n} inspections.")
                st.rerun()
        with d2:
            if st.button("🗑 Xoá dự án", use_container_width=True):
                st.session_state["_confirm_del"] = picked_pid

        if st.session_state.get("_confirm_del") == picked_pid:
            st.error(f"**XÁC NHẬN XOÁ [{proj['code']}]?**")
            code_input = st.text_input(f"Gõ `{proj['code']}` để xác nhận", key="del_confirm")
            if st.button("⚠ XOÁ VĨNH VIỄN", type="primary",
                         disabled=(code_input != proj["code"])):
                info = admin_service.delete_project(db, picked_pid, user_name=user)
                st.session_state.pop("_confirm_del", None)
                if get_current_project_id() == picked_pid:
                    set_current_project_id(None)
                st.success(f"Đã xoá [{proj['code']}].")
                st.rerun()

with tab_backup:
    db_path = Path(db.path)
    db_size_kb = db_path.stat().st_size / 1024 if db_path.exists() else 0

    bcol1, bcol2 = st.columns([2, 4])
    with bcol1:
        if st.button("📦 Tạo backup", type="primary", use_container_width=True):
            try:
                backup_bytes = admin_service.backup_db(db)
                st.session_state["_backup_bytes"] = backup_bytes
                st.session_state["_backup_ts"] = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            except Exception as e:
                st.error(f"Lỗi: {e}")
    with bcol2:
        st.caption(f"DB hiện tại: **{db_size_kb:.1f} KB**")

    if "_backup_bytes" in st.session_state:
        st.download_button("⬇ Tải backup .zip",
                           st.session_state["_backup_bytes"],
                           file_name=f"qc_backup_{st.session_state['_backup_ts']}.zip",
                           mime="application/zip")

    st.divider()
    st.warning("⚠ Restore sẽ ghi đè DB hiện tại. File cũ được backup .bak.")
    uploaded = st.file_uploader("Upload file backup (.db hoặc .zip)", type=["db", "zip"])
    if uploaded is not None:
        if st.button("⚠ Restore NGAY", type="primary"):
            result = admin_service.restore_db(db, uploaded.getbuffer().tobytes(), user_name=user)
            if result["success"]:
                st.success(f"Restore xong. RESTART Streamlit để load DB mới.")
                try:
                    st.cache_resource.clear()
                except Exception:
                    pass
            else:
                st.error(result.get("error", "Unknown"))


# ============================================================
# 📊 THỐNG KÊ TRUY CẬP — visitor tracking
# ============================================================
st.divider()
st.markdown("### 📊 Thống kê truy cập")
st.caption("Theo dõi các session truy cập app (anonymous tracking — không bắt login)")

from streamlit_qc.services import access_tracker

stats = access_tracker.get_stats_summary(db)
ms1, ms2, ms3, ms4 = st.columns(4)
ms1.metric("Hôm nay", f"{stats['sessions_today']}", help="Session duy nhất hôm nay")
ms2.metric("7 ngày qua", f"{stats['sessions_7d']}", help="Session duy nhất 7 ngày")
ms3.metric("Tất cả", f"{stats['total_sessions']:,}", help="Tổng session toàn thời gian")
ms4.metric("Tổng pageviews", f"{stats['total_page_views']:,}", help="Tổng số lần xem page")

# Chart daily visits 14 ngày
daily = access_tracker.get_daily_visits(db, days=14)
if daily:
    import plotly.graph_objects as _go
    import datetime as _dt
    date_labels = []
    for r in daily:
        try:
            date_labels.append(_dt.date.fromisoformat(r["date"]).strftime("%d/%m"))
        except Exception:
            date_labels.append(r["date"])

    fig_visits = _go.Figure()
    fig_visits.add_trace(_go.Bar(
        x=date_labels, y=[r["sessions"] for r in daily],
        name="Session", marker_color="#0F766E",
        text=[r["sessions"] for r in daily], textposition="outside",
    ))
    fig_visits.add_trace(_go.Scatter(
        x=date_labels, y=[r["page_views"] for r in daily],
        name="Pageview", mode="lines+markers",
        line=dict(color="#D97706", width=2), yaxis="y2",
    ))
    fig_visits.update_layout(
        height=280, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Session", gridcolor="#f1f5f9"),
        yaxis2=dict(title="Pageview", overlaying="y", side="right"),
        xaxis=dict(showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
        bargap=0.3,
    )
    st.plotly_chart(fig_visits, use_container_width=True)

# 2 cột: Top pages + Recent visitors
vc1, vc2 = st.columns([1, 2])
with vc1:
    st.markdown("##### 🔥 Top page (7 ngày)")
    top_pages = access_tracker.get_top_pages(db, days=7, limit=10)
    if top_pages:
        page_labels = {
            "home": "🏠 Trang chủ",
            "tongquan": "📊 Tổng quan",
            "master": "📥 Import Master",
            "daily": "📤 Import Daily",
            "caukien": "🔧 Cấu kiện",
            "baocao": "📈 Báo cáo",
            "quantri": "⚙️ Quản trị",
        }
        df_top = pd.DataFrame([{
            "Page": page_labels.get(p["page"], p["page"]),
            "Views": p["views"],
        } for p in top_pages])
        st.dataframe(df_top, hide_index=True, use_container_width=True,
                     column_config={"Views": st.column_config.NumberColumn(format="%d")})
    else:
        st.caption("_Chưa có data._")

with vc2:
    st.markdown("##### 🕒 Recent visitors (50 session mới nhất)")
    recent = access_tracker.get_recent_visitors(db, limit=50)
    if recent:
        df_rec = pd.DataFrame([{
            "Session": r["session_id"],
            "Lần cuối": r["last_seen"],
            "Pageviews": r["page_views"],
            "IP": r["ip"],
            "Trình duyệt": r["ua"][:50] + ("..." if len(r["ua"]) > 50 else ""),
        } for r in recent])
        st.dataframe(df_rec, hide_index=True, use_container_width=True, height=400,
                     column_config={"Pageviews": st.column_config.NumberColumn(format="%d")})
    else:
        st.caption("_Chưa có visitor nào._")
