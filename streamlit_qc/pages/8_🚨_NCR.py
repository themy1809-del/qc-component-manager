# -*- coding: utf-8 -*-
"""Page: NCR Management — Non-Conformance Report.

Workflow: OPEN → IN_REVIEW → RESOLVED → CLOSED.
3 tab: Tạo NCR mới / Danh sách / Tổng hợp.
"""
from __future__ import annotations

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
from streamlit_qc.services import ncr_service
from streamlit_qc.services.ncr_service import (
    NCR_SEVERITIES,
    NCR_STATUSES,
    SEVERITY_LABEL,
    STATUS_LABEL,
)

st.set_page_config(
    page_title=f"NCR · {APP_NAME}",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("ncr")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav()
render_page_header(
    "🚨 NCR Management",
    "Quản lý phiếu Non-Conformance Report — báo cáo lỗi & xử lý",
)
project_info_strip()

pid = get_current_project_id()
if not pid:
    st.warning("⚠️ Vui lòng chọn dự án ở Tổng quan trước.")
    st.stop()

# ====================================================================
# METRICS
# ====================================================================
cnt = ncr_service.counts(db, pid)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("🔴 OPEN", cnt.get("OPEN", 0), help="Phiếu mới — chưa xử lý")
m2.metric("🟡 IN_REVIEW", cnt.get("IN_REVIEW", 0), help="Đang xem xét / phân tích")
m3.metric("🟢 RESOLVED", cnt.get("RESOLVED", 0), help="Đã xử lý — chờ đóng phiếu")
m4.metric("⚫ CLOSED", cnt.get("CLOSED", 0), help="Đã đóng phiếu hoàn tất")
m5.metric("📊 Tổng", sum(cnt.values()))

st.divider()

# ====================================================================
# TABS
# ====================================================================
tab_new, tab_list, tab_export = st.tabs([
    "✏️ Tạo NCR mới",
    "📋 Danh sách + Xử lý",
    "📤 Xuất Excel",
])

# ====================================================================
# TAB 1 — Tạo NCR mới
# ====================================================================
with tab_new:
    st.subheader("Tạo phiếu NCR mới")
    st.caption("Hệ thống tự sinh số phiếu dạng `NCR-{năm}-{seq:03d}`.")

    with st.form("form_new_ncr", clear_on_submit=True):
        title = st.text_input(
            "Tiêu đề lỗi *",
            placeholder="VD: Mối hàn cấu kiện BM-001 không đạt MT",
            max_chars=200,
        )

        c1, c2 = st.columns(2)
        comp_code = c1.text_input(
            "Mã cấu kiện (tuỳ chọn)",
            placeholder="BM-001",
            help="Để trống nếu lỗi không gắn với 1 cấu kiện cụ thể",
        )
        severity = c2.selectbox(
            "Mức độ nghiêm trọng *",
            NCR_SEVERITIES,
            index=1,  # MEDIUM
            format_func=lambda s: SEVERITY_LABEL.get(s, s),
        )

        c3, c4 = st.columns(2)
        deadline_in = c3.date_input(
            "Deadline xử lý *", value=date.today(),
            help="Ngày bắt buộc phải xử lý xong",
        )
        raised_by = c4.text_input(
            "Người báo lỗi *", value=get_current_user(),
        )

        description = st.text_area(
            "Mô tả chi tiết lỗi",
            height=120,
            placeholder=(
                "Mô tả rõ vị trí lỗi, hiện trạng, ảnh hưởng nghiệp vụ...\n"
                "VD: 3 vị trí mối hàn ở mặt đầu CK BM-001 phát hiện rỗ khí qua kiểm tra MT,"
                " cần mài lại và hàn lại."
            ),
        )

        submitted = st.form_submit_button(
            "🚨 Tạo phiếu NCR", type="primary", use_container_width=True
        )
        if submitted:
            if not title.strip():
                st.error("❌ Vui lòng nhập tiêu đề.")
            else:
                try:
                    nid, ncr_no = ncr_service.create_ncr(
                        db=db,
                        pid=pid,
                        title=title.strip(),
                        description=description.strip(),
                        component_code=comp_code.strip() or None,
                        severity=severity,
                        deadline=deadline_in.isoformat(),
                        raised_by=raised_by.strip() or None,
                    )
                    st.success(
                        f"✅ Đã tạo NCR **#{nid}** — Số phiếu: **{ncr_no}**. "
                        f"Vào tab **Danh sách + Xử lý** để theo dõi."
                    )
                except Exception as e:
                    st.error(f"Lỗi: {e}")

# ====================================================================
# TAB 2 — Danh sách + Xử lý
# ====================================================================
with tab_list:
    st.subheader("Danh sách NCR & xử lý")

    f1, f2 = st.columns([1.5, 1.5])
    flt_status = f1.multiselect(
        "Lọc trạng thái",
        NCR_STATUSES,
        default=["OPEN", "IN_REVIEW"],
        format_func=lambda s: STATUS_LABEL.get(s, s),
    )
    flt_sev = f2.multiselect(
        "Lọc mức độ",
        NCR_SEVERITIES,
        default=[],
        format_func=lambda s: SEVERITY_LABEL.get(s, s),
    )

    # Load all then filter Python-side để giữ UI đơn giản
    df_all = ncr_service.list_ncrs_df(db, pid)
    if df_all.empty:
        st.info("Chưa có NCR nào trong dự án này. Sang tab **Tạo NCR mới**.")
    else:
        df_view = df_all.copy()
        if flt_status:
            keep_labels = [STATUS_LABEL[s] for s in flt_status]
            df_view = df_view[df_view["Trạng thái"].isin(keep_labels)]
        if flt_sev:
            keep_sev = [SEVERITY_LABEL[s] for s in flt_sev]
            df_view = df_view[df_view["Mức độ"].isin(keep_sev)]

        st.caption(f"**{len(df_view)} / {len(df_all)}** NCR sau lọc")
        st.dataframe(df_view, use_container_width=True, hide_index=True, height=300)

        # === Xử lý 1 NCR ===
        st.markdown("##### 🔧 Chuyển trạng thái 1 NCR")
        col1, col2 = st.columns([1, 3])
        ncr_ids = df_view["ID"].tolist()
        if ncr_ids:
            sel_id = col1.selectbox(
                "Chọn ID NCR",
                ncr_ids,
                format_func=lambda i: f"#{i} — {df_view[df_view['ID']==i]['Số NCR'].iloc[0]}",
            )
            with col2:
                sel_row = df_view[df_view["ID"] == sel_id].iloc[0]
                st.caption(
                    f"**{sel_row['Số NCR']}** — {sel_row['Tiêu đề']} · "
                    f"hiện tại: **{sel_row['Trạng thái']}**"
                )

            new_status = st.selectbox(
                "Trạng thái mới",
                NCR_STATUSES,
                format_func=lambda s: STATUS_LABEL.get(s, s),
            )
            cc1, cc2 = st.columns(2)
            root_cause = cc1.text_area(
                "Nguyên nhân gốc (root cause)",
                height=80,
                placeholder="Ghi rõ nguyên nhân để rút kinh nghiệm...",
            )
            corrective = cc2.text_area(
                "Hành động khắc phục",
                height=80,
                placeholder="Mô tả hành động đã thực hiện...",
            )
            resolved_by = st.text_input(
                "Người xử lý", value=get_current_user(),
            )

            cbt1, cbt2 = st.columns(2)
            if cbt1.button(
                f"💾 Cập nhật → {STATUS_LABEL.get(new_status)}",
                type="primary",
                use_container_width=True,
            ):
                try:
                    ncr_service.update_status(
                        db, int(sel_id), new_status,
                        resolved_by=resolved_by,
                        root_cause=root_cause,
                        corrective_action=corrective,
                    )
                    st.success(f"✅ Đã cập nhật NCR #{sel_id}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

            if cbt2.button(
                f"🗑️ Xoá NCR #{sel_id}",
                type="secondary",
                use_container_width=True,
            ):
                confirm = st.checkbox(f"Xác nhận xoá vĩnh viễn NCR #{sel_id}?")
                if confirm:
                    try:
                        ncr_service.delete(db, int(sel_id))
                        st.success(f"Đã xoá NCR #{sel_id}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

# ====================================================================
# TAB 3 — Xuất Excel
# ====================================================================
with tab_export:
    st.subheader("Xuất Excel danh sách NCR")
    st.caption("File Excel có conditional formatting theo trạng thái — tiện báo cáo Sếp/CĐT.")

    proj = db.get_project(pid)
    pcode = proj["code"] if proj else "PROJ"

    if st.button("📥 Tạo file Excel", type="primary"):
        try:
            xlsx = ncr_service.export_to_excel(db, pid, pcode)
            fname = f"NCR_List_{pcode}_{date.today():%Y%m%d}.xlsx"
            st.download_button(
                f"⬇️ Tải {fname}",
                data=xlsx,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.success(f"✅ Đã tạo file ({len(xlsx):,} bytes).")
        except Exception as e:
            st.error(f"Lỗi: {e}")
