# -*- coding: utf-8 -*-
"""Page: Tổng quan (Dashboard) — v2.1 Premium visual."""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from streamlit_qc.core.constants import (
    APP_NAME,
    STATUS_COLORS,
    STATUS_LABELS,
    STATUS_ACCEPTED,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    STATUS_PASSED,
    STATUS_PENDING,
)
from streamlit_qc.core.date_utils import format_date_vn
from streamlit_qc.core.state import get_current_project_id, get_db, init_session_state
from streamlit_qc.core.theme import apply_theme
from streamlit_qc.core.ui import project_info_strip, render_page_header, render_top_nav
from streamlit_qc.services import dashboard_service

st.set_page_config(
    page_title=f"Tổng quan · {APP_NAME}",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("tongquan")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav(active_page="tongquan")

proj = render_page_header(
    "Tổng quan",
    subtitle="Tiến độ nghiệm thu cấu kiện theo dự án",
    page_icon="📊",
)
pid = get_current_project_id()
if pid is None or proj is None:
    st.warning("Chưa có dự án. Bấm **+ Dự án mới** ở header trên.")
    st.stop()

# ============================================================
# CSS cho dashboard v2.1 — premium look
# ============================================================
st.markdown("""
<style>
/* Hero progress section */
.hero-progress {
    background: linear-gradient(135deg, #0F1E40 0%, #1E3A8A 100%);
    border-radius: 14px;
    padding: 28px 32px;
    color: #FFFFFF;
    box-shadow: 0 6px 24px rgba(15, 30, 64, 0.18);
    margin-bottom: 6px;
}
.hero-progress .label {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #FCE7A1;
    margin-bottom: 6px;
    font-weight: 600;
}
.hero-progress .sub-label {
    font-size: 13px;
    color: rgba(255,255,255,0.78);
    margin-bottom: 16px;
}
.hero-progress .big-number {
    font-size: 56px;
    font-weight: 800;
    line-height: 1.0;
    color: #FFFFFF;
    letter-spacing: -1px;
    margin-bottom: 4px;
}
.hero-progress .ratio {
    font-size: 15px;
    color: rgba(255,255,255,0.85);
    margin-bottom: 18px;
}
.hero-progress .bar-track {
    width: 100%;
    height: 16px;
    background: rgba(255,255,255,0.16);
    border-radius: 10px;
    overflow: hidden;
}
.hero-progress .bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #D4A744 0%, #FCE7A1 100%);
    border-radius: 10px;
    box-shadow: 0 0 12px rgba(212, 167, 68, 0.5);
    transition: width 0.6s ease;
}

/* KPI cards */
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 18px 20px 14px 20px;
    box-shadow: 0 1px 3px rgba(15, 30, 64, 0.05);
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
    height: 138px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.kpi-card:hover {
    box-shadow: 0 8px 24px rgba(15, 30, 64, 0.10);
    transform: translateY(-2px);
}
.kpi-card .accent-bar {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
}
.kpi-card .icon-circle {
    width: 34px; height: 34px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    margin-bottom: 4px;
}
.kpi-card .label {
    color: #475569;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.3px;
}
.kpi-card .value {
    font-size: 30px;
    font-weight: 800;
    line-height: 1.0;
    letter-spacing: -1px;
    margin-top: 2px;
}
.kpi-card .sub {
    color: #94a3b8;
    font-size: 12px;
    margin-top: 6px;
}

/* Section title */
.section-title {
    font-size: 16px;
    font-weight: 700;
    color: #0F1E40;
    margin: 14px 0 12px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title::before {
    content: "";
    width: 4px;
    height: 16px;
    background: #D4A744;
    border-radius: 2px;
}
</style>
""", unsafe_allow_html=True)

n_comp = db.conn.execute(
    "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,)
).fetchone()["c"]
project_info_strip(proj, n_comp=n_comp)

# ============================================================
# Filter xưởng
# ============================================================
workshop_list = dashboard_service.get_workshop_list(db, pid)
col_filter, col_refresh = st.columns([4, 1])
with col_filter:
    options = ["(Tất cả xưởng)"] + workshop_list
    selected = st.selectbox("🏭 Lọc theo xưởng", options, index=0)
with col_refresh:
    st.write("")
    st.write("")
    if st.button("🔄 Làm mới", use_container_width=True):
        st.rerun()

ws_filter = None if selected == "(Tất cả xưởng)" else selected

with st.spinner("Đang tính số liệu..."):
    data = dashboard_service.compute_dashboard(db, pid, workshop_filter=ws_filter)

counts = data.counts
total = counts.get("TOTAL", 0)
done = counts.get(STATUS_PASSED, 0) + counts.get(STATUS_ACCEPTED, 0)
progress_pct = round(done * 100 / total, 1) if total else 0.0

# ============================================================
# HERO: Tiến độ tổng thể — Navy gradient + Gold progress bar
# ============================================================
st.markdown(f"""
<div class="hero-progress">
    <div class="label">Tiến độ tổng thể</div>
    <div class="sub-label">PASSED + ACCEPTED · {selected}</div>
    <div class="big-number">{progress_pct}%</div>
    <div class="ratio">{done:,} / {total:,} cấu kiện đã hoàn thành</div>
    <div class="bar-track">
        <div class="bar-fill" style="width: {min(progress_pct, 100)}%;"></div>
    </div>
</div>
""", unsafe_allow_html=True)

# === Quick-nav chips: nhảy nhanh đến section ===
st.markdown(
    """
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 0 0;">
      <a href="#chi-so-kiem-tra" style="background:#F1F5F9;color:#0F1E40;
         padding:5px 14px;border-radius:14px;font-size:13px;font-weight:600;
         text-decoration:none;border:1px solid #CBD5E1;">📊 KPI</a>
      <a href="#thong-ke-chi-tiet-theo-xuong" style="background:#FEF3C7;color:#7C2D12;
         padding:5px 14px;border-radius:14px;font-size:13px;font-weight:600;
         text-decoration:none;border:1px solid #FCD34D;">🏭 Theo xưởng</a>
      <a href="#nang-suat-inspection-theo-thoi-gian" style="background:#DBEAFE;color:#1E40AF;
         padding:5px 14px;border-radius:14px;font-size:13px;font-weight:600;
         text-decoration:none;border:1px solid #93C5FD;">📈 Chart trend</a>
      <a href="#hieu-suat-inspector" style="background:#DCFCE7;color:#166534;
         padding:5px 14px;border-radius:14px;font-size:13px;font-weight:600;
         text-decoration:none;border:1px solid #86EFAC;">👤 Inspector</a>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# ============================================================
# ⚖️ KHỐI LƯỢNG (TẤN) + PHỄU CÁC KHÂU — kiểm soát không bỏ sót
# ============================================================
st.markdown('<div class="section-title">⚖️ Khối lượng &amp; phễu các khâu</div>',
            unsafe_allow_html=True)

@st.cache_data(ttl=120, show_spinner=False, max_entries=32)
def _weight_cached(_db, pid_in: int) -> dict:
    return dashboard_service.get_weight_stats(_db, pid_in)

try:
    _w = _weight_cached(db, pid)
    _t_ton = _w["total_kg"] / 1000.0
    _f_ton = _w["fitup_kg"] / 1000.0
    _d_ton = _w["final_kg"] / 1000.0
    _pf = (100.0 * _f_ton / _t_ton) if _t_ton else 0.0
    _pd = (100.0 * _d_ton / _t_ton) if _t_ton else 0.0

    wcol1, wcol2, wcol3, wcol4 = st.columns(4)
    wcol1.metric(
        "📦 Tổng khối lượng",
        f"{_t_ton:,.1f} tấn",
        f"{_w['total_n']:,} cấu kiện",
        delta_color="off",
        help="Tổng Weight [kg] của toàn bộ cấu kiện trong master (quy ra tấn).",
    )
    wcol2.metric(
        "🔧 Đã Fit-up",
        f"{_f_ton:,.1f} tấn",
        f"{_pf:.1f}% khối lượng · {_w['fitup_n']:,} CK",
        delta_color="off",
        help="Khối lượng các cấu kiện đã có Fit-up PASS.",
    )
    wcol3.metric(
        "✅ Đã nghiệm thu (Final)",
        f"{_d_ton:,.1f} tấn",
        f"{_pd:.1f}% khối lượng · {_w['final_n']:,} CK",
        delta_color="off",
        help="Khối lượng các cấu kiện đã có Final/DGRP PASS.",
    )
    wcol4.metric(
        "🕳 Chưa kiểm khâu nào",
        f"{_w['never_inspected']:,} CK",
        "cần đưa vào kế hoạch",
        delta_color="off",
        help="Cấu kiện chưa có bất kỳ inspection nào — dễ bỏ sót nhất.",
    )

    # Phễu các khâu — nhìn 1 phát biết tồn ở đâu
    _tot_n = max(_w["total_n"], 1)
    st.progress(min(_w["fitup_n"] / _tot_n, 1.0),
                text=f"Khâu Fit-up: {_w['fitup_n']:,}/{_w['total_n']:,} cấu kiện")
    st.progress(min(_w["final_n"] / _tot_n, 1.0),
                text=f"Khâu Final (nghiệm thu): {_w['final_n']:,}/{_w['total_n']:,} cấu kiện")

    if _w["final_no_fitup"] and _w["fitup_n"] > 0:
        st.warning(
            f"⚠️ **{_w['final_no_fitup']:,} cấu kiện CÓ Final nhưng THIẾU Fit-up** — "
            "dấu hiệu bỏ sót khâu hoặc thiếu hồ sơ Fit-up. "
            "Vào tab Cấu kiện → lọc «Có Final, thiếu Fit-up» để xem danh sách."
        )
    elif _w["fitup_n"] == 0 and _w["final_n"] > 0:
        st.caption(
            "ℹ️ Dự án này theo dõi nghiệm thu 1 bước (không có khâu Fit-up riêng) "
            "— thanh Fit-up = 0 là bình thường."
        )
except Exception as _w_err:
    st.caption(f"⚠️ Khối lượng: {_w_err}")

st.write("")

# ============================================================
# KPI CARDS — icon + accent + drill-down
# ============================================================
st.markdown('<div class="section-title">Chỉ số kiểm tra</div>', unsafe_allow_html=True)

KPI_ICONS = {
    "TOTAL": ("📦", "#dbeafe"),
    STATUS_PENDING: ("⏳", "#f1f5f9"),
    STATUS_IN_PROGRESS: ("🔧", "#fef3c7"),
    STATUS_ACCEPTED: ("✅", "#d1fae5"),
    STATUS_FAILED: ("⚠️", "#fee2e2"),
    STATUS_PASSED: ("🏆", "#dcfce7"),
}

card_specs = [
    ("TOTAL", STATUS_LABELS["TOTAL"], STATUS_COLORS["TOTAL"]),
    (STATUS_PENDING, STATUS_LABELS[STATUS_PENDING], STATUS_COLORS[STATUS_PENDING]),
    (STATUS_IN_PROGRESS, STATUS_LABELS[STATUS_IN_PROGRESS], STATUS_COLORS[STATUS_IN_PROGRESS]),
    (STATUS_ACCEPTED, STATUS_LABELS[STATUS_ACCEPTED], STATUS_COLORS[STATUS_ACCEPTED]),
]
if counts.get(STATUS_FAILED, 0) > 0:
    card_specs.append((STATUS_FAILED, STATUS_LABELS[STATUS_FAILED], STATUS_COLORS[STATUS_FAILED]))
if counts.get(STATUS_PASSED, 0) > 0:
    card_specs.append((STATUS_PASSED, STATUS_LABELS[STATUS_PASSED], STATUS_COLORS[STATUS_PASSED]))

cols = st.columns(len(card_specs))
for col, (key, label, color) in zip(cols, card_specs):
    with col:
        value = counts.get(key, 0)
        icon, icon_bg = KPI_ICONS.get(key, ("•", "#f1f5f9"))
        pct_of_total = (value * 100 / total) if total and key != "TOTAL" else None
        sub_html = (
            f'<div class="sub">{pct_of_total:.1f}% tổng</div>' if pct_of_total is not None
            else f'<div class="sub">cấu kiện trong dự án</div>'
        )
        st.markdown(
            f"""<div class="kpi-card">
                <div class="accent-bar" style="background:{color};"></div>
                <div>
                    <span class="icon-circle" style="background:{icon_bg};">{icon}</span>
                    <div class="label">{label}</div>
                    <div class="value" style="color:{color};">{value:,}</div>
                </div>
                {sub_html}
            </div>""",
            unsafe_allow_html=True,
        )
        if value > 0:
            btn_label = "🔎 Xem danh sách" if key != "TOTAL" else "🔎 Xem tất cả"
            if st.button(btn_label, key=f"drill_{key}", use_container_width=True):
                st.session_state["preset_status_filter"] = key
                st.switch_page("pages/4_🔧_Cấu_kiện.py")

st.write("")

# ============================================================
# CHARTS: Donut + Bar
# ============================================================
if total > 0:
    col_pie, col_bar = st.columns([1, 2], gap="medium")
    with col_pie:
        st.markdown('<div class="section-title">Tỉ lệ trạng thái</div>', unsafe_allow_html=True)
        pie_data = pd.DataFrame([
            {"Trạng thái": STATUS_LABELS[s], "Số lượng": counts.get(s, 0)}
            for s in [STATUS_ACCEPTED, STATUS_IN_PROGRESS, STATUS_PENDING, STATUS_FAILED, STATUS_PASSED]
            if counts.get(s, 0) > 0
        ])
        if not pie_data.empty:
            color_map = {STATUS_LABELS[s]: STATUS_COLORS[s] for s in STATUS_COLORS}
            fig_pie = px.pie(pie_data, names="Trạng thái", values="Số lượng",
                            color="Trạng thái", color_discrete_map=color_map, hole=0.58)
            fig_pie.update_traces(
                textposition="outside",
                textinfo="percent+label",
                textfont=dict(size=12, color="#0F172A"),
                marker=dict(line=dict(color="#FFFFFF", width=2)),
                pull=[0.02] * len(pie_data),
            )
            fig_pie.update_layout(
                showlegend=False,
                height=340,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                annotations=[dict(
                    text=f"<b>{progress_pct}%</b><br><span style='font-size:11px;color:#64748b'>hoàn thành</span>",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=22, color="#0F1E40"),
                )],
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    with col_bar:
        st.markdown('<div class="section-title">% Hoàn thành theo xưởng</div>', unsafe_allow_html=True)
        if data.workshop_stats:
            bar_df = pd.DataFrame(data.workshop_stats).sort_values("percent", ascending=True)
            # Phân ngưỡng màu rõ ràng theo % hoàn thành
            def _bar_color(p):
                if p < 30:   return "#DC2626"   # đỏ — chậm
                if p < 50:   return "#EA580C"   # cam đậm — cần đẩy
                if p < 70:   return "#F59E0B"   # vàng cam — trung bình
                if p < 85:   return "#16A34A"   # xanh — khá
                return "#0F766E"                # teal đậm — tốt
            bar_df = bar_df.copy()
            bar_df["color"] = bar_df["percent"].apply(_bar_color)
            # Dùng go.Bar để gán màu từng bar độc lập (không qua color mapping)
            import plotly.graph_objects as go
            fig_bar = go.Figure(go.Bar(
                x=bar_df["percent"],
                y=bar_df["workshop"],
                orientation="h",
                text=bar_df["percent"].apply(lambda v: f"<b>{v}%</b>"),
                textposition="outside",
                textfont=dict(size=13, color="#0F172A"),
                marker=dict(
                    color=bar_df["color"].tolist(),
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{y}</b><br>%{x}%<extra></extra>",
            ))
            fig_bar.update_layout(
                height=340,
                margin=dict(l=10, r=30, t=10, b=10),
                xaxis=dict(
                    range=[0, 110],
                    showgrid=True, gridcolor="#f1f5f9",
                    tickfont=dict(size=11, color="#64748b"),
                    title=dict(text="% Hoàn thành", font=dict(size=12, color="#64748b")),
                ),
                yaxis=dict(tickfont=dict(size=13, color="#0F172A", family="Segoe UI")),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                bargap=0.35,
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            # Legend màu nhỏ ở dưới chart
            st.markdown(
                """<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:11px;
                           color:#64748b;margin-top:-8px;justify-content:center;">
                    <span><span style="display:inline-block;width:10px;height:10px;background:#DC2626;border-radius:2px;vertical-align:middle;"></span> &lt; 30% Chậm</span>
                    <span><span style="display:inline-block;width:10px;height:10px;background:#EA580C;border-radius:2px;vertical-align:middle;"></span> 30-50% Cần đẩy</span>
                    <span><span style="display:inline-block;width:10px;height:10px;background:#F59E0B;border-radius:2px;vertical-align:middle;"></span> 50-70% Trung bình</span>
                    <span><span style="display:inline-block;width:10px;height:10px;background:#16A34A;border-radius:2px;vertical-align:middle;"></span> 70-85% Khá</span>
                    <span><span style="display:inline-block;width:10px;height:10px;background:#0F766E;border-radius:2px;vertical-align:middle;"></span> ≥ 85% Tốt</span>
                </div>""",
                unsafe_allow_html=True,
            )

st.write("")

# ============================================================
# THỐNG KÊ THEO XƯỞNG
# ============================================================
st.markdown('<div class="section-title">Thống kê chi tiết theo Xưởng</div>', unsafe_allow_html=True)
if data.workshop_stats:
    ws_df = pd.DataFrame(data.workshop_stats).rename(columns={
        "workshop": "🏭 Xưởng", "TOTAL": "Tổng",
        "PENDING": "Chưa KT", "IN_PROGRESS": "Đã Fit-up",
        "PASSED": "Đạt", "FAILED": "K.đạt", "ACCEPTED": "Đã NT",
        "percent": "% Hoàn thành",
    })
    if "Đạt" in ws_df.columns and ws_df["Đạt"].sum() == 0:
        ws_df = ws_df.drop(columns=["Đạt"])
    if "K.đạt" in ws_df.columns and ws_df["K.đạt"].sum() == 0:
        ws_df = ws_df.drop(columns=["K.đạt"])

    st.dataframe(
        ws_df, use_container_width=True, hide_index=True,
        column_config={
            "% Hoàn thành": st.column_config.ProgressColumn(
                "% Hoàn thành", format="%.1f%%",
                min_value=0.0, max_value=100.0),
            "Tổng": st.column_config.NumberColumn(format="%d"),
            "Chưa KT": st.column_config.NumberColumn(format="%d"),
            "Đã Fit-up": st.column_config.NumberColumn(format="%d"),
            "Đã NT": st.column_config.NumberColumn(format="%d"),
        },
    )

st.write("")

# ============================================================
# 🔮 FORECAST & S-CURVE (P2.8) — velocity + ETA + cumulative chart
# ============================================================
try:
    from streamlit_qc.services import forecast_service as _fc

    @st.cache_data(ttl=120, show_spinner=False, max_entries=16)
    def _forecast_cached(_db, pid_in: int):
        return _fc.get_forecast(_db, pid_in)

    @st.cache_data(ttl=120, show_spinner=False, max_entries=16)
    def _scurve_cached(_db, pid_in: int, days: int):
        return _fc.get_scurve(_db, pid_in, days)

    forecast = _forecast_cached(db, pid)

    st.markdown(
        '<div class="section-title">🔮 Dự báo tiến độ & S-Curve</div>',
        unsafe_allow_html=True,
    )

    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric(
        "⚡ Velocity (tuần)",
        f"{forecast.velocity_per_week:.1f} CK",
        help="Trung bình số CK ACCEPTED/tuần trong 4 tuần qua",
    )
    eta_label = f"{forecast.eta_days} ngày" if forecast.eta_days is not None else "—"
    eta_delta = forecast.eta_date if forecast.eta_date else None
    fc2.metric(
        "🎯 ETA hoàn thành",
        eta_label,
        delta=eta_delta,
        delta_color="off",
        help=(
            "Số ngày dự kiến hoàn thành toàn bộ project theo velocity hiện tại."
            "Để 0 nghĩa là đã hoàn thành 100%."
        ),
    )
    lead = forecast.avg_lead_time_days
    fc3.metric(
        "⏱️ Lead time TB",
        f"{lead:.1f} ngày" if lead is not None else "—",
        help="Trung bình ngày từ Fit-up PASS → Final PASS (cấu kiện ACCEPTED)",
    )
    fc4.metric(
        "📦 Còn lại",
        f"{forecast.total_components - forecast.done_components:,} CK",
        help="Số cấu kiện chưa ACCEPTED",
    )

    # S-curve chart
    sdata = _scurve_cached(db, pid, 90)
    if sdata:
        import plotly.graph_objects as _pgo
        dates = [d["date"] for d in sdata]
        pcts = [d["cum_pct"] for d in sdata]
        nbrs = [d["cumulative"] for d in sdata]

        fig_s = _pgo.Figure()
        fig_s.add_trace(_pgo.Scatter(
            x=dates, y=pcts, mode="lines+markers", name="Actual %",
            line=dict(color="#0F1E40", width=3),
            marker=dict(size=6, color="#D4A744"),
            fill="tozeroy", fillcolor="rgba(15,30,64,0.08)",
            customdata=nbrs,
            hovertemplate="<b>%{x}</b><br>%{y:.1f}%<br>%{customdata} CK<extra></extra>",
        ))
        # Today marker
        import datetime as _dtdt
        fig_s.add_vline(
            x=_dtdt.date.today().isoformat(),
            line_dash="dash", line_color="#94A3B8",
            annotation_text="Hôm nay", annotation_position="top",
        )
        fig_s.update_layout(
            title="S-Curve: % ACCEPTED tích luỹ theo ngày (90 ngày qua)",
            xaxis_title="Ngày", yaxis_title="% Hoàn thành",
            height=320, margin=dict(l=10, r=10, t=40, b=10),
            yaxis=dict(range=[0, 100]),
            showlegend=False,
        )
        st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.caption("Chưa đủ dữ liệu inspection để vẽ S-curve.")
except Exception as _fc_err:
    st.caption(f"⚠️ Forecast service: {_fc_err}")

st.write("")

# ============================================================
# LỊCH SỬ KIỂM TRA GẦN NHẤT
# ============================================================
st.markdown(
    '<div class="section-title">Lịch sử kiểm tra gần nhất '
    '<span style="font-weight:400;color:#94a3b8;font-size:13px;">· 200 record gần nhất</span></div>',
    unsafe_allow_html=True
)
if data.recent_inspections:
    recent_df = pd.DataFrame(data.recent_inspections)
    recent_df["date"] = recent_df["date"].apply(format_date_vn)
    recent_df = recent_df.rename(columns={
        "date": "📅 Ngày KT", "code": "🔧 Mã cấu kiện",
        "type": "Loại", "result": "KQ",
        "inspector": "👤 Người KT", "report": "📋 Số báo cáo",
    })
    st.dataframe(recent_df, use_container_width=True, hide_index=True, height=380)
else:
    st.info("Chưa có inspection nào. Vào **Import Daily** để nạp file kiểm tra.")


# ============================================================
# 📈 TREND CHART — năng suất inspection theo thời gian
# ============================================================
st.write("")
st.markdown('<div class="section-title">📈 Năng suất inspection theo thời gian</div>', unsafe_allow_html=True)

tcol1, tcol2 = st.columns([3, 1])
with tcol1:
    trend_days = st.radio(
        "Khoảng thời gian",
        [7, 30, 90],
        format_func=lambda d: f"{d} ngày qua",
        horizontal=True,
        index=1,
        key="trend_days_radio",
    )
with tcol2:
    trend_scope = st.radio(
        "Phạm vi",
        ["Dự án này", "Toàn công ty"],
        horizontal=True,
        key="trend_scope_radio",
    )

@st.cache_data(ttl=60, show_spinner=False, max_entries=32)
def _trend_cached(_db, pid_in: int | None, days: int) -> list[dict]:
    return dashboard_service.get_inspection_trend(_db, pid_in, days)

trend_pid = pid if trend_scope == "Dự án này" else None
trend_data = _trend_cached(db, trend_pid, trend_days)

if trend_data:
    import datetime as dt
    # Build daily series
    today = dt.date.today()
    days_list = [(today - dt.timedelta(days=i)).isoformat() for i in range(trend_days - 1, -1, -1)]
    series_fitup = {d: 0 for d in days_list}
    series_final = {d: 0 for d in days_list}
    series_other = {d: 0 for d in days_list}
    for r in trend_data:
        d = r["date"]
        if d not in series_fitup:
            continue
        if r["type"] == "FUR":
            series_fitup[d] += r["count"]
        elif r["type"] == "DGRP":
            series_final[d] += r["count"]
        else:
            series_other[d] += r["count"]

    date_labels = [dt.date.fromisoformat(d).strftime("%d/%m") for d in days_list]
    fit_vals = list(series_fitup.values())
    fin_vals = list(series_final.values())
    other_vals = list(series_other.values())
    total_vals = [a + b + c for a, b, c in zip(fit_vals, fin_vals, other_vals)]

    import plotly.graph_objects as _go
    fig_trend = _go.Figure()
    fig_trend.add_trace(_go.Bar(
        x=date_labels, y=fit_vals, name="Fit-up",
        marker_color="#F59E0B",
        hovertemplate="<b>%{x}</b><br>Fit-up: %{y}<extra></extra>",
    ))
    fig_trend.add_trace(_go.Bar(
        x=date_labels, y=fin_vals, name="Final / DGRP",
        marker_color="#0F766E",
        hovertemplate="<b>%{x}</b><br>Final: %{y}<extra></extra>",
    ))
    if sum(other_vals) > 0:
        fig_trend.add_trace(_go.Bar(
            x=date_labels, y=other_vals, name="Khác (NDT/DIR/VIR)",
            marker_color="#94A3B8",
            hovertemplate="<b>%{x}</b><br>Khác: %{y}<extra></extra>",
        ))
    # Line tổng
    fig_trend.add_trace(_go.Scatter(
        x=date_labels, y=total_vals,
        mode="lines+markers+text", name="Tổng",
        line=dict(color="#0F1E40", width=2.5),
        marker=dict(size=7, color="#FCE7A1", line=dict(color="#0F1E40", width=2)),
        text=total_vals,
        textposition="top center",
        textfont=dict(size=10, color="#0F1E40"),
        hovertemplate="<b>%{x}</b><br>Tổng: %{y}<extra></extra>",
    ))
    fig_trend.update_layout(
        barmode="stack",
        height=380, margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#475569")),
        yaxis=dict(gridcolor="#f1f5f9", tickfont=dict(size=10, color="#94A3B8")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        bargap=0.3,
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    # Stats tổng
    total_week = sum(total_vals)
    avg_day = total_week / trend_days if trend_days else 0
    max_day = max(total_vals) if total_vals else 0
    max_day_idx = total_vals.index(max_day) if max_day else 0
    max_date = date_labels[max_day_idx] if max_day else "—"
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.metric(f"Tổng {trend_days} ngày", f"{total_week:,}")
    with sc2:
        st.metric("Trung bình/ngày", f"{avg_day:.1f}")
    with sc3:
        st.metric(f"Ngày cao nhất ({max_date})", f"{max_day:,}")
else:
    st.info(f"Chưa có inspection nào trong {trend_days} ngày qua.")


# ============================================================
# 👤 INSPECTOR PERFORMANCE
# ============================================================
st.write("")
st.markdown('<div class="section-title">👤 Hiệu suất Inspector</div>', unsafe_allow_html=True)

@st.cache_data(ttl=60, show_spinner=False, max_entries=32)
def _inspector_perf_cached(_db, pid_in: int | None, days: int) -> list[dict]:
    return dashboard_service.get_inspector_performance(_db, pid_in, days)

insp_perf = _inspector_perf_cached(db, trend_pid, trend_days)

if insp_perf:
    perf_df = pd.DataFrame(insp_perf)
    perf_df["fail_rate"] = (perf_df["n_fail"] * 100 / perf_df["total"]).round(1)
    perf_df = perf_df.rename(columns={
        "inspector": "Inspector",
        "total": "Tổng",
        "n_pass": "✅ Pass",
        "n_fail": "❌ Fail",
        "n_recheck": "🔁 Recheck",
        "fail_rate": "% Fail",
    })
    st.dataframe(
        perf_df, use_container_width=True, hide_index=True,
        column_config={
            "Tổng": st.column_config.NumberColumn(format="%d"),
            "✅ Pass": st.column_config.NumberColumn(format="%d"),
            "❌ Fail": st.column_config.NumberColumn(format="%d"),
            "🔁 Recheck": st.column_config.NumberColumn(format="%d"),
            "% Fail": st.column_config.ProgressColumn(
                "% Fail", format="%.1f%%", min_value=0.0, max_value=50.0,
            ),
        },
    )
    st.caption(f"Top 20 inspector trong **{trend_days} ngày qua** · {'Dự án này' if trend_pid else 'Toàn công ty'}")
else:
    st.info(f"Chưa có inspection nào trong {trend_days} ngày qua.")
