# -*- coding: utf-8 -*-
"""Page: RFI Management — Request for Inspection."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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
from streamlit_qc.services import rfi_service
from streamlit_qc.services.rfi_service import (
    INSPECTION_TYPES,
    RFI_STATUSES,
    STATUS_LABEL,
    TYPE_LABEL,
)

st.set_page_config(
    page_title=f"RFI · {APP_NAME}",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("rfi")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav()
render_page_header(
    "📨 RFI — Request for Inspection",
    "Phiếu yêu cầu kiểm tra nghiệm thu — workflow SUBMITTED→CONFIRMED→COMPLETED→CLOSED",
)
project_info_strip()

pid = get_current_project_id()
if not pid:
    st.warning("⚠️ Vui lòng chọn dự án ở Tổng quan trước.")
    st.stop()

proj = db.get_project(pid)
project_code = proj["code"] if proj else "PROJ"

# Metrics
cnt = rfi_service.counts(db, pid)
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("📨 SUBMITTED", cnt.get("SUBMITTED", 0))
m2.metric("✅ CONFIRMED", cnt.get("CONFIRMED", 0))
m3.metric("🔧 IN PROGRESS", cnt.get("IN_PROGRESS", 0))
m4.metric("🏁 COMPLETED", cnt.get("COMPLETED", 0))
m5.metric("⚫ CLOSED", cnt.get("CLOSED", 0))
m6.metric("❌ REJECTED", cnt.get("REJECTED", 0))

st.divider()

tab_new, tab_list, tab_action = st.tabs([
    "✏️ Gửi RFI mới",
    "📋 Danh sách RFI",
    "🔧 Xác nhận / Đóng phiếu",
])

# ====================================================================
# TAB 1 — Submit RFI
# ====================================================================
with tab_new:
    st.subheader("Gửi RFI mới")
    st.caption(
        f"Hệ thống tự sinh số RFI dạng `RFI-{project_code}-YYYYMMDD-NNN`. "
        "Nếu là **Hold Point**, CĐT/Tư vấn BẮT BUỘC có mặt khi kiểm tra."
    )

    with st.form("form_new_rfi", clear_on_submit=True):
        c1, c2 = st.columns(2)
        comp_code = c1.text_input(
            "Mã cấu kiện *", placeholder="VD: BM-001",
        )
        ins_type = c2.selectbox(
            "Loại nghiệm thu *",
            INSPECTION_TYPES,
            format_func=lambda t: TYPE_LABEL.get(t, t),
        )

        c3, c4 = st.columns(2)
        proposed = c3.date_input("Ngày đề xuất KT *", value=date.today())
        submitter = c4.text_input("Người gửi *", value=get_current_user())

        is_hold = st.checkbox(
            "🛑 Hold Point — CĐT/Tư vấn phải có mặt",
            help="Khi tick, kiểm tra này sẽ bị dừng nếu không có witness từ CĐT.",
        )
        witness_req = ""
        if is_hold:
            witness_req = st.text_input(
                "Tên CĐT/Tư vấn cần witness",
                placeholder="VD: A. Nguyễn Văn B - CĐT",
            )

        submitted = st.form_submit_button(
            "📨 Gửi RFI", type="primary", use_container_width=True,
        )
        if submitted:
            if not comp_code.strip():
                st.error("❌ Vui lòng nhập mã cấu kiện.")
            elif not submitter.strip():
                st.error("❌ Vui lòng nhập người gửi.")
            else:
                try:
                    rid, rno = rfi_service.submit_rfi(
                        db=db, pid=pid, project_code=project_code,
                        component_code=comp_code.strip(),
                        inspection_type=ins_type,
                        proposed_date=proposed.isoformat(),
                        submitted_by=submitter.strip(),
                        is_hold_point=is_hold,
                        witness_required=witness_req.strip() or None,
                    )
                    st.success(
                        f"✅ Đã gửi RFI **#{rid}** — Số: **{rno}**. "
                        "Sang tab **Xác nhận** để inspector phản hồi."
                    )
                except Exception as e:
                    st.error(f"Lỗi: {e}")

# ====================================================================
# TAB 2 — List
# ====================================================================
with tab_list:
    st.subheader("Danh sách RFI")
    flt = st.multiselect(
        "Lọc trạng thái",
        RFI_STATUSES,
        default=["SUBMITTED", "CONFIRMED", "IN_PROGRESS"],
        format_func=lambda s: STATUS_LABEL.get(s, s),
    )
    df_all = rfi_service.list_rfis_df(db, pid)
    if df_all.empty:
        st.info("Chưa có RFI nào. Sang tab **Gửi RFI mới**.")
    else:
        if flt:
            labels = [STATUS_LABEL[s] for s in flt]
            df_view = df_all[df_all["Trạng thái"].isin(labels)]
        else:
            df_view = df_all
        st.caption(f"**{len(df_view)} / {len(df_all)}** RFI")
        st.dataframe(df_view, use_container_width=True, hide_index=True, height=400)

        # Export
        import io
        bio = io.BytesIO()
        df_view.to_excel(bio, index=False, sheet_name="RFI")
        bio.seek(0)
        st.download_button(
            "⬇️ Xuất Excel danh sách RFI",
            data=bio.getvalue(),
            file_name=f"RFI_{project_code}_{date.today():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ====================================================================
# TAB 3 — Confirm / Action
# ====================================================================
with tab_action:
    st.subheader("Xác nhận / Cập nhật RFI")
    df = rfi_service.list_rfis_df(db, pid)
    if df.empty:
        st.info("Chưa có RFI nào.")
    else:
        # Chỉ hiện RFI chưa CLOSED
        df_open = df[~df["Trạng thái"].str.contains("Đóng|Hoàn tất|Từ chối", regex=True)]
        if df_open.empty:
            st.info("Tất cả RFI đã đóng hoặc hoàn tất.")
        else:
            sel_id = st.selectbox(
                "Chọn RFI",
                df_open["ID"].tolist(),
                format_func=lambda i: (
                    f"#{i} — {df_open[df_open['ID']==i]['Số RFI'].iloc[0]} "
                    f"({df_open[df_open['ID']==i]['Trạng thái'].iloc[0]})"
                ),
            )
            row = df_open[df_open["ID"] == sel_id].iloc[0]
            st.info(
                f"**{row['Số RFI']}** · CK: {row['Cấu kiện']} · "
                f"Loại: {row['Loại KT']} · Hold: {row['Hold Point']} · "
                f"Ngày đề xuất: {row['Ngày đề xuất']}"
            )

            new_status = st.selectbox(
                "Hành động",
                ["CONFIRMED", "REJECTED", "IN_PROGRESS", "COMPLETED", "CLOSED"],
                format_func=lambda s: STATUS_LABEL.get(s, s),
            )
            note = st.text_area("Ghi chú phản hồi", value="")
            user = st.text_input("Người thực hiện", value=get_current_user())

            confirmed_date = None
            if new_status == "CONFIRMED":
                conf_d = st.date_input("Ngày xác nhận", value=date.today())
                confirmed_date = conf_d.isoformat()

            if st.button(
                f"💾 Cập nhật → {STATUS_LABEL.get(new_status)}",
                type="primary", use_container_width=True,
            ):
                try:
                    if new_status == "CONFIRMED":
                        rfi_service.confirm_rfi(db, int(sel_id), confirmed_date or "",
                                                user, note)
                    elif new_status == "REJECTED":
                        rfi_service.reject_rfi(db, int(sel_id), user, note or "(không nêu lý do)")
                    elif new_status == "COMPLETED":
                        rfi_service.complete_rfi(db, int(sel_id), user)
                    elif new_status == "CLOSED":
                        rfi_service.close_rfi(db, int(sel_id), user)
                    else:
                        db.update_rfi_status(int(sel_id), new_status, response_note=note)
                        db.conn.commit()
                    st.success(f"✅ Đã cập nhật RFI #{sel_id}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")
