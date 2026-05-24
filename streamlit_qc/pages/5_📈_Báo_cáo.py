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

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("baocao")
from streamlit_qc.core.state import require_login
require_login()
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

# ============================================================
# 📊 EXCEL BÁO CÁO TỔNG HỢP PRO — 6 sheet đa chiều
# ============================================================
st.markdown(
    '<div style="background:linear-gradient(135deg,#0F1E40,#1E3A8A);'
    'padding:14px 18px;border-radius:10px;color:#fff;margin-bottom:10px;">'
    '<div style="font-size:14px;font-weight:700;">📊 Báo cáo Excel chuyên nghiệp</div>'
    '<div style="font-size:12px;color:rgba(255,255,255,0.78);margin-top:4px;">'
    '6 sheet: Tổng quan · Cấu kiện · Overdue · FAIL · Inspector · Inspections — Format đẹp cho khách/sếp'
    '</div></div>',
    unsafe_allow_html=True,
)

ec1, ec2, ec3 = st.columns([2, 2, 3])
with ec1:
    overdue_threshold_export = st.number_input(
        "Ngưỡng overdue (ngày)",
        min_value=1, max_value=90, value=7,
        help="Số ngày sau Fit-up coi là overdue trong sheet Overdue.",
    )
with ec2:
    st.write("")
    if st.button("📊 Tạo báo cáo Excel PRO", type="primary", use_container_width=True):
        try:
            with st.spinner("Đang tạo Excel 6 sheet..."):
                excel_bytes = report_service.export_to_excel_pro(
                    db, pid, proj["code"], proj["name"],
                    overdue_threshold=int(overdue_threshold_export),
                )
            st.session_state["_excel_pro_bytes"] = excel_bytes
            st.session_state["_excel_pro_name"] = (
                f"BaoCao_PRO_{proj['code']}_{dt.date.today():%Y%m%d}.xlsx"
            )
            st.success("✅ Đã tạo báo cáo!")
        except Exception as e:
            st.error(f"Lỗi: {e}")
            import traceback
            with st.expander("Chi tiết"):
                st.code(traceback.format_exc())
with ec3:
    if "_excel_pro_bytes" in st.session_state:
        st.write("")
        st.download_button(
            f"💾 Tải file {st.session_state.get('_excel_pro_name', 'BaoCao.xlsx')}",
            st.session_state["_excel_pro_bytes"],
            file_name=st.session_state["_excel_pro_name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

st.divider()

# ============================================================
# 📄 PDF BIÊN BẢN NGHIỆM THU — chọn cấu kiện và xuất hàng loạt
# ============================================================
st.markdown(
    '<div style="background:linear-gradient(135deg,#7B1E1E,#A02828);'
    'padding:14px 18px;border-radius:10px;color:#fff;margin-bottom:10px;">'
    '<div style="font-size:14px;font-weight:700;">📄 PDF Biên bản nghiệm thu</div>'
    '<div style="font-size:12px;color:rgba(255,255,255,0.85);margin-top:4px;">'
    'Xuất biên bản nghiệm thu (đơn lẻ hoặc bulk) — định dạng PDF in giấy ký tay'
    '</div></div>',
    unsafe_allow_html=True,
)

from streamlit_qc.services import pdf_service as _pdf

pdf_mode = st.radio(
    "Cách chọn cấu kiện:",
    ["Theo trạng thái", "Nhập danh sách mã", "Top N gần nhất"],
    horizontal=True,
    key="_pdf_mode",
)

pdf_comp_ids: list[int] = []

if pdf_mode == "Theo trạng thái":
    from streamlit_qc.core.constants import ALL_STATUSES, STATUS_LABELS
    cps1, cps2 = st.columns([2, 1])
    sts_pick = cps1.multiselect(
        "Lọc trạng thái",
        ALL_STATUSES,
        default=["ACCEPTED", "PASSED"],
        format_func=lambda s: STATUS_LABELS.get(s, s),
        key="_pdf_sts",
    )
    pdf_limit = cps2.number_input("Tối đa", 1, 500, 50, key="_pdf_limit_s")
    if sts_pick:
        placeholders = ",".join("?" * len(sts_pick))
        rows = db.conn.execute(
            f"SELECT id FROM components WHERE project_id=? AND status IN ({placeholders}) "
            f"ORDER BY code LIMIT ?",
            (pid, *sts_pick, int(pdf_limit)),
        ).fetchall()
        pdf_comp_ids = [r["id"] for r in rows]

elif pdf_mode == "Nhập danh sách mã":
    codes_text = st.text_area(
        "Danh sách mã (mỗi dòng 1 mã)",
        height=100,
        placeholder="ABC-001\nABC-002\n...",
        key="_pdf_codes",
    )
    codes = [c.strip() for c in codes_text.split("\n") if c.strip()]
    if codes:
        placeholders = ",".join("?" * len(codes))
        rows = db.conn.execute(
            f"SELECT id FROM components WHERE project_id=? AND code IN ({placeholders})",
            (pid, *codes),
        ).fetchall()
        pdf_comp_ids = [r["id"] for r in rows]

else:  # Top N
    pdf_topn = st.number_input("Số cấu kiện gần nhất", 1, 200, 20, key="_pdf_topn")
    rows = db.conn.execute(
        "SELECT id FROM components WHERE project_id=? ORDER BY id DESC LIMIT ?",
        (pid, int(pdf_topn)),
    ).fetchall()
    pdf_comp_ids = [r["id"] for r in rows]

cpdf1, cpdf2, cpdf3 = st.columns(3)
qc_signoff = cpdf1.text_input(
    "Nhà thầu (QC Đại Dũng) ký",
    value="", placeholder="Nguyễn Văn A", key="_pdf_qc",
)
consult_signoff = cpdf2.text_input(
    "Tư vấn giám sát ký",
    value="", placeholder="(tuỳ chọn)", key="_pdf_consult",
)
cust_signoff = cpdf3.text_input(
    "Chủ đầu tư ký",
    value="", placeholder="(tuỳ chọn)", key="_pdf_cust",
)

cbtn1, cbtn2 = st.columns([2, 3])
if cbtn1.button(
    f"📄 Tạo PDF ({len(pdf_comp_ids)} cấu kiện)",
    type="primary",
    disabled=(len(pdf_comp_ids) == 0),
    use_container_width=True,
    key="_btn_make_pdf",
):
    try:
        with st.spinner(f"Đang tạo PDF cho {len(pdf_comp_ids)} cấu kiện..."):
            pdf_bytes = _pdf.generate_certificate(
                db, pid, pdf_comp_ids,
                inspector_signoff=qc_signoff,
                customer_signoff=cust_signoff,
                consultant_signoff=consult_signoff,
            )
        st.session_state["_pdf_bytes"] = pdf_bytes
        st.session_state["_pdf_name"] = (
            f"BienBanNT_{proj['code']}_{len(pdf_comp_ids)}cks_"
            f"{dt.date.today():%Y%m%d}.pdf"
        )
        st.success(f"✅ PDF {len(pdf_bytes):,} bytes — {len(pdf_comp_ids)} cấu kiện.")
    except Exception as e:
        st.error(f"Lỗi tạo PDF: {e}")

if "_pdf_bytes" in st.session_state:
    cbtn2.download_button(
        f"⬇️ Tải PDF — {st.session_state.get('_pdf_name', 'BienBanNT.pdf')}",
        st.session_state["_pdf_bytes"],
        file_name=st.session_state["_pdf_name"],
        mime="application/pdf",
        use_container_width=True,
        key="_btn_dl_pdf",
    )

st.divider()

min_d, max_d = report_service.get_inspection_date_range(db, pid)
has_any = report_service.has_any_inspection(db, pid)

if not has_any:
    st.info("Chưa có inspection nào. Vào **Import Daily** để nạp file.")
    try:
        excel_bytes = report_service.export_to_excel(db, pid, proj["code"])
        st.download_button("📊 Tải báo cáo Excel", excel_bytes,
                           file_name=f"BaoCao_{proj['code']}_{dt.date.today():%Y%m%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.error(f"Lỗi: {e}")
    st.stop()

# BUG FIX: nếu có inspection nhưng date không parseable → fallback today
if min_d is None:
    min_d = max_d = dt.date.today()
    st.warning(
        "⚠️ Dự án có inspection nhưng phần lớn chưa có ngày kiểm tra. "
        "Báo cáo có thể không đầy đủ — hãy bổ sung ngày cho các record."
    )

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


# ============================================================
# 🆚 SO SÁNH DỰ ÁN SIDE-BY-SIDE
# ============================================================
st.divider()
st.markdown("### 🆚 So sánh dự án")
st.caption("Chọn các dự án để so sánh KPI side-by-side · tìm dự án nào tốt/chậm/cần đẩy")

from streamlit_qc.services import dashboard_service, project_service
all_projects = project_service.list_projects(db)
if len(all_projects) < 2:
    st.info("Cần ≥ 2 dự án để so sánh. Hiện tại chỉ có 1 dự án.")
else:
    proj_options = {f"[{p['code']}] {p['name']}": p["id"] for p in all_projects}
    selected_labels = st.multiselect(
        "Chọn dự án so sánh (≥ 2)",
        list(proj_options.keys()),
        default=list(proj_options.keys())[:min(4, len(proj_options))],
        help="Chọn 2-5 dự án để so sánh trực quan.",
    )
    selected_pids = [proj_options[lbl] for lbl in selected_labels]

    if len(selected_pids) >= 2:
        with st.spinner("Đang so sánh..."):
            compare_data = dashboard_service.compare_projects(db, selected_pids)

        if compare_data:
            # Bảng so sánh
            import pandas as _pd
            df_cmp = _pd.DataFrame(compare_data)
            df_cmp["pct_str"] = df_cmp["pct"].astype(str) + "%"
            df_cmp_show = df_cmp.rename(columns={
                "code": "Mã dự án",
                "name": "Tên dự án",
                "total": "Tổng CK",
                "accepted": "Đã NT",
                "backlog": "Tồn đọng",
                "failed": "FAIL",
                "overdue": "Overdue (>7d)",
                "inspections_7d": "Insp 7 ngày",
                "pct": "% Hoàn thành",
            })[["Mã dự án", "Tên dự án", "Tổng CK", "Đã NT", "Tồn đọng",
                "FAIL", "Overdue (>7d)", "Insp 7 ngày", "% Hoàn thành"]]
            st.dataframe(
                df_cmp_show, use_container_width=True, hide_index=True,
                column_config={
                    "Đã NT": st.column_config.NumberColumn(format="%d"),
                    "Tồn đọng": st.column_config.NumberColumn(format="%d"),
                    "FAIL": st.column_config.NumberColumn(format="%d"),
                    "Overdue (>7d)": st.column_config.NumberColumn(format="%d"),
                    "Insp 7 ngày": st.column_config.NumberColumn(format="%d"),
                    "% Hoàn thành": st.column_config.ProgressColumn(
                        "% Hoàn thành", format="%.1f%%",
                        min_value=0.0, max_value=100.0,
                    ),
                },
            )

            # Grouped bar chart
            st.markdown("##### 📊 So sánh trực quan")
            import plotly.graph_objects as _go
            codes = [c["code"] for c in compare_data]

            fig_cmp = _go.Figure()
            fig_cmp.add_trace(_go.Bar(
                x=codes, y=[c["pending"] for c in compare_data],
                name="Chưa KT", marker_color="#94A3B8",
            ))
            fig_cmp.add_trace(_go.Bar(
                x=codes, y=[c["in_progress"] for c in compare_data],
                name="Đã Fit-up", marker_color="#D97706",
            ))
            fig_cmp.add_trace(_go.Bar(
                x=codes, y=[c["accepted"] for c in compare_data],
                name="Đã NT", marker_color="#0F766E",
            ))
            if any(c["failed"] for c in compare_data):
                fig_cmp.add_trace(_go.Bar(
                    x=codes, y=[c["failed"] for c in compare_data],
                    name="FAIL", marker_color="#DC2626",
                ))
            fig_cmp.update_layout(
                barmode="stack",
                height=380,
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="#f1f5f9", title="Số cấu kiện"),
                xaxis=dict(title=None, tickfont=dict(size=13, color="#0F1E40")),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                bargap=0.25,
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

            # Chart % hoàn thành riêng
            st.markdown("##### 🎯 % Hoàn thành")
            fig_pct = _go.Figure()
            colors_pct = []
            for p in compare_data:
                pct_v = p["pct"]
                if pct_v < 30:   c = "#DC2626"
                elif pct_v < 50: c = "#EA580C"
                elif pct_v < 70: c = "#F59E0B"
                elif pct_v < 85: c = "#16A34A"
                else:            c = "#0F766E"
                colors_pct.append(c)
            fig_pct.add_trace(_go.Bar(
                x=codes,
                y=[c["pct"] for c in compare_data],
                marker_color=colors_pct,
                text=[f"<b>{c['pct']}%</b>" for c in compare_data],
                textposition="outside",
                textfont=dict(size=13, color="#0F172A"),
            ))
            fig_pct.update_layout(
                height=300, showlegend=False,
                margin=dict(l=10, r=10, t=20, b=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(range=[0, 110], gridcolor="#f1f5f9", title="% Hoàn thành"),
                xaxis=dict(title=None, tickfont=dict(size=13, color="#0F1E40")),
                bargap=0.4,
            )
            st.plotly_chart(fig_pct, use_container_width=True)

            # Highlight insights
            best = max(compare_data, key=lambda x: x["pct"])
            worst = min(compare_data, key=lambda x: x["pct"])
            most_active = max(compare_data, key=lambda x: x["inspections_7d"])
            most_overdue = max(compare_data, key=lambda x: x["overdue"])

            ic1, ic2, ic3, ic4 = st.columns(4)
            with ic1:
                st.metric("🏆 Tốt nhất", f"{best['code']}", f"{best['pct']}%")
            with ic2:
                st.metric("📉 Chậm nhất", f"{worst['code']}", f"{worst['pct']}%", delta_color="inverse")
            with ic3:
                st.metric("⚡ Năng suất tuần", f"{most_active['code']}",
                          f"{most_active['inspections_7d']:,} insp")
            with ic4:
                st.metric("⚠ Nhiều overdue", f"{most_overdue['code']}",
                          f"{most_overdue['overdue']} CK", delta_color="inverse")
    elif len(selected_pids) == 1:
        st.info("Chọn thêm dự án để so sánh (≥ 2).")
ids) == 1:
        st.info("Chọn thêm dự án để so sánh (≥ 2).")
