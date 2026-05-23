# -*- coding: utf-8 -*-
"""Page: Báo cáo & Phân tích."""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import datetime as dt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from streamlit_qc.core.constants import APP_NAME, STATUS_COLORS
from streamlit_qc.core.state import get_current_project_id, get_db, init_session_state
from streamlit_qc.core.theme import apply_theme
from streamlit_qc.core.ui import project_info_strip, render_page_header, render_top_nav
from streamlit_qc.services import report_service

st.set_page_config(
    page_title=f"Báo cáo · {APP_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()
render_top_nav(active_page="baocao")

proj = render_page_header(
    "Báo cáo & Phân tích",
    subtitle="Chart tiến độ tuần · Xuất Excel 4 sheet",
    page_icon="📈",
)
pid = get_current_project_id()
if pid is None or proj is None:
    st.warning("Chưa có dự án.")
    st.stop()

project_info_strip(proj)

min_d, max_d = report_service.get_inspection_date_range(db, pid)

if min_d is None:
    st.info("Chưa có inspection nào. Vào **Import Daily** để nạp file.")
    try:
        excel_bytes = report_service.export_to_excel(db, pid, proj["code"])
        st.download_button("📊 Tải báo cáo Excel", excel_bytes,
                           file_name=f"BaoCao_{proj['code']}_{dt.date.today():%Y%m%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.error(f"Lỗi: {e}")
    st.stop()

default_from = max(min_d, dt.date.today() - dt.timedelta(days=90))
c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    date_from = st.date_input("Từ ngày", value=default_from,
                               min_value=min_d, max_value=max_d, format="DD/MM/YYYY")
with c2:
    date_to = st.date_input("Đến ngày", value=max_d,
                             min_value=min_d, max_value=max_d, format="DD/MM/YYYY")
with c3:
    st.write("")
    st.write("")
    st.caption(f"📅 Dữ liệu: **{min_d.strftime('%d/%m/%Y')}** → **{max_d.strftime('%d/%m/%Y')}**")

if date_from > date_to:
    st.error("⚠ Từ ngày phải ≤ Đến ngày.")
    st.stop()

with st.spinner("Đang tính báo cáo..."):
    data = report_service.compute_report(db, pid, date_from=date_from, date_to=date_to)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Tổng cấu kiện", f"{data.total_components:,}")
m2.metric("Inspection trong kỳ", f"{data.total_inspections:,}")
m3.metric("Đã nghiệm thu", f"{data.accepted:,}")
m4.metric("Đạt (PASSED)", f"{data.passed:,}")
m5.metric("Không đạt", f"{data.failed:,}")

st.divider()
st.markdown("### 📅 Tiến độ theo tuần")
if data.weekly:
    weekly_df = pd.DataFrame([
        {"Tuần": w.week_label, "Inspection": w.inspections,
         "Cộng dồn": w.cumulative, "_sort": w.week_start}
        for w in data.weekly
    ]).sort_values("_sort")

    col_line, col_bar = st.columns(2)
    with col_line:
        st.markdown("##### Cộng dồn")
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=weekly_df["Tuần"], y=weekly_df["Cộng dồn"],
            mode="lines+markers",
            line=dict(color=STATUS_COLORS["ACCEPTED"], width=3),
            fill="tozeroy", fillcolor="rgba(15, 118, 110, 0.1)",
        ))
        fig_line.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                               showlegend=False)
        st.plotly_chart(fig_line, use_container_width=True)
    with col_bar:
        st.markdown("##### Theo tuần")
        fig_bar = px.bar(weekly_df, x="Tuần", y="Inspection", text="Inspection",
                        color_discrete_sequence=[STATUS_COLORS["PASSED"]])
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)

st.divider()
col_type, col_ws = st.columns(2)
with col_type:
    st.markdown("### 🏷 Theo loại NT")
    if data.by_type:
        type_df = pd.DataFrame([{"Loại": k, "Số": v} for k, v in data.by_type.items()])
        fig_t = px.bar(type_df, x="Số", y="Loại", orientation="h", text="Số", color="Loại")
        fig_t.update_traces(textposition="outside")
        fig_t.update_layout(height=350, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_t, use_container_width=True)

with col_ws:
    st.markdown("### 🏭 Top xưởng % đã KT")
    if data.workshop_progress:
        ws_df = pd.DataFrame(data.workshop_progress).sort_values("percent_in_range", ascending=True)
        fig_ws = px.bar(ws_df.tail(10), x="percent_in_range", y="workshop", orientation="h",
                       text="percent_in_range", color="percent_in_range",
                       color_continuous_scale=["#fee2e2", "#fef3c7", "#dcfce7", "#bbf7d0"],
                       range_color=[0, 100])
        fig_ws.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_ws.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10),
                              coloraxis_showscale=False, xaxis=dict(range=[0, 110]))
        st.plotly_chart(fig_ws, use_container_width=True)

st.divider()
st.markdown("### 📥 Xuất báo cáo Excel")
try:
    excel_bytes = report_service.export_to_excel(db, pid, proj["code"])
    st.download_button("📊 Tải báo cáo Excel", excel_bytes,
                       file_name=f"BaoCao_{proj['code']}_{dt.date.today():%Y%m%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       type="primary")
except Exception as e:
    st.error(f"Lỗi: {e}")
