# -*- coding: utf-8 -*-
"""Page: Hồ sơ — Dimension / Welding / Paint Report + Thư mời nghiệm thu."""
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

from streamlit_qc.core.constants import APP_NAME, ALL_STATUSES, STATUS_LABELS
from streamlit_qc.core.state import (
    get_current_project_id,
    get_current_user,
    get_db,
    init_session_state,
)
from streamlit_qc.core.theme import apply_theme
from streamlit_qc.core.ui import project_info_strip, render_page_header, render_top_nav
from streamlit_qc.services import (
    component_service,
    invitation_service,
    qc_report_service,
)
from streamlit_qc.services.qc_report_service import (
    DIMENSION_FIELDS,
    FIELDS_BY_TYPE,
    PAINT_FIELDS,
    RESULT_OPTIONS,
    WELDING_FIELDS,
)
from streamlit_qc.services.invitation_service import STAGE_LABELS, InvitationData

st.set_page_config(
    page_title=f"Hồ sơ · {APP_NAME}",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()

render_top_nav()
render_page_header(
    "📋 Hồ sơ nghiệm thu",
    "Báo cáo Dimension / Welding / Paint + Thư mời nghiệm thu",
)
project_info_strip()

db = get_db()
pid = get_current_project_id()

if not pid:
    st.warning("⚠️ Vui lòng chọn dự án ở trang Tổng quan trước.")
    st.stop()

# ====================================================================
# HEADER METRICS
# ====================================================================
counts = qc_report_service.count_by_type(db, pid)
c1, c2, c3, c4 = st.columns(4)
c1.metric("📐 Dimension", counts.get("DIMENSION", 0))
c2.metric("🔥 Welding", counts.get("WELDING", 0))
c3.metric("🎨 Paint", counts.get("PAINT", 0))
c4.metric("📦 Tổng", sum(counts.values()))

st.divider()

# ====================================================================
# TABS
# ====================================================================
tab_dim, tab_weld, tab_paint, tab_inv = st.tabs([
    "📐 Dimension Report",
    "🔥 Welding Report",
    "🎨 Paint Report",
    "✉️ Thư mời nghiệm thu",
])


# ====================================================================
# Helper: render 1 report tab (dùng cho cả 3 loại)
# ====================================================================
def render_report_tab(report_type: str, fields: list, emoji: str, label: str) -> None:
    st.subheader(f"{emoji} Nhập / Import {label} Report")

    # === Tabs nội bộ: Nhập tay | Import Excel | Danh sách ===
    sub_input, sub_import, sub_list = st.tabs(
        ["✏️ Nhập tay", "📤 Import Excel", "📋 Danh sách"]
    )

    # --- 1. Nhập tay ---
    with sub_input:
        st.caption("Nhập 1 báo cáo trực tiếp cho 1 cấu kiện.")

        # Lấy danh sách cấu kiện để dropdown
        rows = db.conn.execute(
            "SELECT id, code FROM components WHERE project_id=? ORDER BY code LIMIT 500",
            (pid,),
        ).fetchall()
        if not rows:
            st.info("Dự án chưa có cấu kiện. Hãy Import Master trước.")
        else:
            options = ["— Chọn cấu kiện —"] + [r["code"] for r in rows]
            with st.form(f"form_{report_type}", clear_on_submit=True):
                colA, colB, colC = st.columns([2, 1.5, 1])
                code_sel = colA.selectbox("Mã cấu kiện", options, key=f"code_{report_type}")
                date_in = colB.date_input("Ngày KT", value=date.today(), key=f"date_{report_type}")
                result_in = colC.selectbox(
                    "Kết quả", RESULT_OPTIONS, key=f"result_{report_type}"
                )

                col1, col2 = st.columns(2)
                inspector_in = col1.text_input(
                    "Người KT", value=get_current_user(), key=f"insp_{report_type}"
                )
                rfi_in = col2.text_input("Số RFI", key=f"rfi_{report_type}")

                st.markdown("**Chi tiết kết quả đo:**")
                # Render dynamic fields
                data_inputs = {}
                cols_grid = st.columns(2)
                for i, (fld, lbl) in enumerate(fields):
                    target_col = cols_grid[i % 2]
                    if "mm" in fld or "um" in fld or "mpa" in fld or "pct" in fld or "_c" in fld:
                        val = target_col.text_input(lbl, key=f"{report_type}_{fld}")
                    else:
                        val = target_col.text_input(lbl, key=f"{report_type}_{fld}")
                    if val:
                        data_inputs[fld] = val

                submitted = st.form_submit_button(
                    f"💾 Lưu {label} Report", type="primary", use_container_width=True
                )
                if submitted:
                    if code_sel.startswith("—"):
                        st.error("Vui lòng chọn cấu kiện.")
                    else:
                        try:
                            rid = qc_report_service.add_report(
                                db=db,
                                pid=pid,
                                report_type=report_type,
                                component_code=code_sel,
                                report_date=date_in.isoformat(),
                                inspector=inspector_in or None,
                                result=result_in,
                                data=data_inputs,
                                rfi_no=rfi_in or None,
                                created_by=get_current_user(),
                            )
                            db.conn.commit()
                            st.success(f"✅ Đã lưu báo cáo #{rid} cho cấu kiện {code_sel}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi: {e}")

    # --- 2. Import Excel ---
    with sub_import:
        st.caption(
            "Tải file Excel chứa danh sách báo cáo. "
            "Cột bắt buộc: `code`. Cột tuỳ chọn: `date`, `inspector`, `result`, `rfi`."
        )

        # Template download
        tpl_df = qc_report_service.get_template_df(report_type)
        tpl_buf = pd.ExcelWriter("/tmp/_tpl.xlsx", engine="openpyxl")
        # Simple: use to_excel via BytesIO
        import io
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as w:
            tpl_df.to_excel(w, sheet_name=label, index=False)
        bio.seek(0)
        st.download_button(
            f"⬇️ Tải template {label} Report",
            data=bio.getvalue(),
            file_name=f"Template_{report_type}_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"tpl_{report_type}",
        )

        up = st.file_uploader(
            f"Chọn file Excel {label} Report",
            type=["xlsx", "xls"],
            key=f"up_{report_type}",
        )
        if up:
            try:
                df_up = pd.read_excel(up, sheet_name=0)
            except Exception as e:
                st.error(f"Không đọc được file: {e}")
                df_up = None
            if df_up is not None:
                st.write(f"📄 File có **{len(df_up)} dòng** và **{len(df_up.columns)} cột**.")
                st.dataframe(df_up.head(20), use_container_width=True, hide_index=True)
                if st.button(
                    f"🚀 Import {len(df_up)} dòng vào {label} Report",
                    type="primary",
                    key=f"go_{report_type}",
                ):
                    res = qc_report_service.import_reports_from_excel(
                        db=db,
                        pid=pid,
                        report_type=report_type,
                        df=df_up,
                        created_by=get_current_user(),
                        source_file=up.name,
                    )
                    if res.errors:
                        st.warning(f"⚠️ {len(res.errors)} lỗi:")
                        for err in res.errors[:10]:
                            st.text(err)
                    st.success(
                        f"✅ Import xong: {res.success} thành công / "
                        f"{res.skipped} bỏ qua / tổng {res.total} dòng."
                    )
                    st.rerun()

    # --- 3. Danh sách ---
    with sub_list:
        df_rep = qc_report_service.list_reports(db, pid, report_type=report_type)
        if df_rep.empty:
            st.info(f"Chưa có {label} Report nào.")
        else:
            st.write(f"**{len(df_rep)} báo cáo** {label}")
            st.dataframe(df_rep, use_container_width=True, hide_index=True)

            # Download
            bio = io.BytesIO()
            with pd.ExcelWriter(bio, engine="openpyxl") as w:
                df_rep.to_excel(w, sheet_name=label, index=False)
            bio.seek(0)
            st.download_button(
                f"⬇️ Xuất Excel danh sách {label}",
                data=bio.getvalue(),
                file_name=f"{label}_Reports_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_list_{report_type}",
            )

            # Xoá 1 báo cáo
            with st.expander("🗑️ Xoá báo cáo"):
                del_id = st.number_input(
                    "Nhập ID báo cáo cần xoá",
                    min_value=0, value=0, step=1, key=f"del_{report_type}",
                )
                if st.button(f"Xoá #{del_id}", key=f"btn_del_{report_type}"):
                    if del_id > 0:
                        qc_report_service.delete_report(db, int(del_id))
                        st.success(f"Đã xoá báo cáo #{del_id}.")
                        st.rerun()


# ====================================================================
# TAB 1 — DIMENSION
# ====================================================================
with tab_dim:
    render_report_tab("DIMENSION", DIMENSION_FIELDS, "📐", "Dimension")

# ====================================================================
# TAB 2 — WELDING
# ====================================================================
with tab_weld:
    render_report_tab("WELDING", WELDING_FIELDS, "🔥", "Welding")

# ====================================================================
# TAB 3 — PAINT
# ====================================================================
with tab_paint:
    render_report_tab("PAINT", PAINT_FIELDS, "🎨", "Paint")

# ====================================================================
# TAB 4 — THƯ MỜI NGHIỆM THU
# ====================================================================
with tab_inv:
    st.subheader("✉️ Tạo thư mời nghiệm thu (Excel)")

    proj = db.get_project(pid)
    project_code = proj["code"] if proj else ""
    project_name = proj["name"] if proj else ""

    colA, colB, colC = st.columns([1.2, 1.2, 1])
    stage = colA.selectbox(
        "Công đoạn nghiệm thu",
        list(STAGE_LABELS.keys()),
        format_func=lambda s: f"{s} — {STAGE_LABELS[s]}",
    )
    insp_date = colB.date_input("Ngày dự kiến nghiệm thu", value=date.today())
    rfi_no = colC.text_input("Số RFI", value="")

    col1, col2 = st.columns(2)
    recipient = col1.text_input(
        "Kính gửi", value="Kính gửi: Quý Giám sát chủ đầu tư"
    )
    location = col2.text_input("Địa điểm", value="Nhà máy Đại Dũng — Long An")

    note = st.text_area(
        "Ghi chú (tuỳ chọn)", value="", height=70,
        placeholder="VD: Xin Quý giám sát có mặt lúc 08:00, mang theo dụng cụ kiểm tra..."
    )

    st.markdown("##### Chọn cấu kiện đưa vào thư mời")
    selection_mode = st.radio(
        "Cách chọn cấu kiện:",
        ["Theo trạng thái", "Nhập danh sách mã"],
        horizontal=True,
    )

    components = []
    if selection_mode == "Theo trạng thái":
        status_pick = st.multiselect(
            "Lọc trạng thái",
            ALL_STATUSES,
            default=["IN_PROGRESS", "PASSED"],
            format_func=lambda s: STATUS_LABELS.get(s, s),
        )
        if status_pick:
            components = invitation_service.get_components_for_stage(
                db, pid, status_filter=status_pick, limit=2000
            )
    else:
        codes_text = st.text_area(
            "Danh sách mã cấu kiện (mỗi dòng 1 mã)",
            height=120,
            placeholder="ABC-001\nABC-002\n...",
        )
        codes = [c.strip() for c in codes_text.split("\n") if c.strip()]
        if codes:
            placeholders = ",".join("?" * len(codes))
            rows_ids = db.conn.execute(
                f"SELECT id FROM components WHERE project_id=? AND code IN ({placeholders})",
                (pid, *codes),
            ).fetchall()
            cids = [r["id"] for r in rows_ids]
            if cids:
                components = invitation_service.get_components_for_stage(
                    db, pid, component_ids=cids, limit=2000
                )

    if components:
        st.success(f"✅ Đã chọn **{len(components)} cấu kiện**.")
        df_preview = pd.DataFrame(components)
        st.dataframe(df_preview, use_container_width=True, hide_index=True, height=240)

        if st.button("📥 Tạo & tải file thư mời (.xlsx)", type="primary"):
            inv = InvitationData(
                project_code=project_code,
                project_name=project_name,
                stage=stage,
                inspection_date=insp_date.isoformat(),
                location=location,
                rfi_no=rfi_no,
                recipient=recipient,
                sender="Phòng QC — Đại Dũng Steel",
                note=note,
                components=components,
            )
            try:
                xlsx_bytes = invitation_service.build_invitation_excel(inv)
                fname = invitation_service.default_filename(inv)
                st.download_button(
                    "⬇️ Tải file thư mời",
                    data=xlsx_bytes,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
                st.balloons()
            except Exception as e:
                st.error(f"Lỗi tạo file: {e}")
    else:
        st.info("Hãy chọn cấu kiện ở trên để sinh thư mời.")
