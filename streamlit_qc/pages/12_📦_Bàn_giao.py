# -*- coding: utf-8 -*-
"""Page: Batch Handover — gom lô + QR + Packing List + Material Traceability."""
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
from streamlit_qc.services import batch_service, material_service
from streamlit_qc.services.batch_service import BATCH_STATUSES, STATUS_LABEL

st.set_page_config(
    page_title=f"Bàn giao · {APP_NAME}",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("bangiao")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav()
render_page_header(
    "📦 Bàn giao + Vật liệu",
    "Gom lô cấu kiện ACCEPTED · QR code · Packing List · Mill Cert traceability",
)
project_info_strip()

pid = get_current_project_id()
if not pid:
    st.warning("⚠️ Vui lòng chọn dự án ở Tổng quan trước.")
    st.stop()

proj = db.get_project(pid)
project_code = proj["code"] if proj else "PROJ"

tab_new, tab_list, tab_qr, tab_mat = st.tabs([
    "📦 Tạo lô bàn giao",
    "📋 Danh sách lô",
    "📲 QR code cấu kiện",
    "🔗 Vật liệu (Heat No)",
])

# ====================================================================
# TAB 1 — Create batch
# ====================================================================
with tab_new:
    st.subheader("Tạo lô bàn giao mới")
    st.caption(
        f"Hệ thống tự sinh số lô: `BG-{project_code}-YYYYMMDD-NNN`. "
        "Chỉ gom được cấu kiện đang ACCEPTED (đã nghiệm thu xong)."
    )

    # Lấy CK ACCEPTED chưa thuộc batch nào
    rows = db.conn.execute(
        """SELECT c.id, c.code, c.data_json
           FROM components c
           WHERE c.project_id=? AND c.status='ACCEPTED'
             AND c.id NOT IN (SELECT component_id FROM batch_items)
           ORDER BY c.code LIMIT 1000""",
        (pid,),
    ).fetchall()

    if not rows:
        st.info("Không có cấu kiện ACCEPTED chưa gom lô. Hãy hoàn tất nghiệm thu trước.")
    else:
        st.success(f"Có **{len(rows)} cấu kiện** ACCEPTED sẵn sàng gom lô.")

        import json
        records = []
        for r in rows:
            try:
                d = json.loads(r["data_json"])
            except (json.JSONDecodeError, TypeError):
                d = {}
            records.append({
                "✓": False,
                "ID": r["id"],
                "Mã CK": r["code"],
                "Xưởng": d.get("workshop", ""),
                "Khối lượng (kg)": float(d.get("weight_kg") or 0),
                "Bản vẽ": d.get("manual_drawing") or d.get("drawing") or "",
            })
        df = pd.DataFrame(records)
        edited = st.data_editor(
            df, use_container_width=True, height=320, hide_index=True,
            column_config={
                "✓": st.column_config.CheckboxColumn(width="small"),
                "ID": None,
                "Khối lượng (kg)": st.column_config.NumberColumn(format="%.1f"),
            },
            key="batch_picker",
        )
        sel = edited[edited["✓"] == True]
        st.caption(
            f"**Đã chọn: {len(sel)} CK** · "
            f"Tổng KL: **{sel['Khối lượng (kg)'].sum():,.1f} kg**"
        )

        notes = st.text_input("Ghi chú lô (optional)", value="")

        if st.button(
            f"📦 Tạo lô gồm {len(sel)} CK", type="primary",
            disabled=(len(sel) == 0), use_container_width=True,
        ):
            try:
                bid, bno, n = batch_service.create_batch_from_components(
                    db=db, pid=pid, project_code=project_code,
                    component_ids=sel["ID"].tolist(),
                    created_by=get_current_user(),
                    notes=notes,
                )
                st.success(f"✅ Đã tạo lô **{bno}** (#{bid}) với {n} cấu kiện.")
                st.session_state["_last_batch_id"] = bid
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")

# ====================================================================
# TAB 2 — List
# ====================================================================
with tab_list:
    st.subheader("Danh sách lô bàn giao")
    flt = st.multiselect(
        "Lọc trạng thái",
        BATCH_STATUSES,
        default=[],
        format_func=lambda s: STATUS_LABEL.get(s, s),
    )
    df_all = batch_service.list_batches_df(db, pid)
    if df_all.empty:
        st.info("Chưa có lô nào.")
    else:
        df_view = df_all
        if flt:
            labels = [STATUS_LABEL[s] for s in flt]
            df_view = df_all[df_all["Trạng thái"].isin(labels)]
        st.dataframe(df_view, use_container_width=True, hide_index=True, height=300)

        st.markdown("##### 🔧 Cập nhật trạng thái lô")
        ids = df_view["ID"].tolist()
        if ids:
            sel_id = st.selectbox(
                "Chọn lô",
                ids,
                format_func=lambda i: (
                    f"#{i} — {df_view[df_view['ID']==i]['Số lô'].iloc[0]} "
                    f"({df_view[df_view['ID']==i]['Trạng thái'].iloc[0]})"
                ),
            )

            # Show items
            items = db.list_batch_items(int(sel_id))
            if items:
                df_items = pd.DataFrame([{
                    "Mã CK": it["component_code"],
                    "Trạng thái": it["status"],
                    "Số lượng": it["quantity"],
                } for it in items])
                st.caption(f"**{len(items)} cấu kiện trong lô:**")
                st.dataframe(df_items, use_container_width=True, hide_index=True, height=200)

            # Action
            cu1, cu2 = st.columns(2)
            new_status = cu1.selectbox(
                "Chuyển trạng thái",
                ["READY", "DELIVERED", "CONFIRMED"],
                format_func=lambda s: STATUS_LABEL.get(s, s),
            )
            handover_d = cu2.date_input(
                "Ngày bàn giao", value=date.today(),
                key=f"handover_{sel_id}",
            )
            cu3, cu4 = st.columns(2)
            recv_name = cu3.text_input(
                "Người nhận", key=f"recv_{sel_id}",
            )
            recv_co = cu4.text_input(
                "Công ty nhận", key=f"recv_co_{sel_id}",
            )

            cb1, cb2 = st.columns(2)
            if cb1.button(
                f"💾 Cập nhật → {STATUS_LABEL[new_status]}",
                type="primary", use_container_width=True,
                key=f"upd_{sel_id}",
            ):
                try:
                    batch_service.transition_status(
                        db, int(sel_id), new_status,
                        by_user=get_current_user(),
                        handover_date=handover_d.isoformat(),
                        receiver_name=recv_name or None,
                        receiver_company=recv_co or None,
                    )
                    st.success(f"✅ Đã cập nhật lô #{sel_id}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

            # Packing list
            if cb2.button(
                f"📥 Xuất Packing List Excel",
                use_container_width=True,
                key=f"pl_{sel_id}",
            ):
                try:
                    xlsx = batch_service.build_packing_list_excel(db, int(sel_id))
                    bno = df_view[df_view["ID"] == sel_id]["Số lô"].iloc[0]
                    st.download_button(
                        f"⬇️ Tải PackingList_{bno}.xlsx",
                        data=xlsx,
                        file_name=f"PackingList_{bno}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_pl_{sel_id}",
                    )
                except Exception as e:
                    st.error(f"Lỗi: {e}")

# ====================================================================
# TAB 3 — QR codes
# ====================================================================
with tab_qr:
    st.subheader("📲 Tạo QR code cho cấu kiện")
    st.caption(
        "QR chứa link app + mã CK. Erection team scan QR để xem thông tin nhanh."
    )

    rows = db.conn.execute(
        "SELECT id, code, status FROM components "
        "WHERE project_id=? AND status='ACCEPTED' ORDER BY code LIMIT 100",
        (pid,),
    ).fetchall()
    if not rows:
        st.info("Chưa có CK ACCEPTED. Cần nghiệm thu trước khi tạo QR.")
    else:
        opts = [(r["id"], r["code"]) for r in rows]
        sel = st.selectbox(
            "Chọn cấu kiện",
            opts,
            format_func=lambda x: x[1],
        )
        png = batch_service.gen_qr_for_component(sel[0], sel[1])
        if png:
            st.image(png, caption=f"QR code: {sel[1]}", width=200)
            st.download_button(
                "⬇️ Tải PNG",
                data=png,
                file_name=f"QR_{sel[1]}.png",
                mime="image/png",
            )
        else:
            st.warning(
                "Cần cài `qrcode` package. Thêm `qrcode[pil]` vào requirements.txt."
            )

# ====================================================================
# TAB 4 — Materials (heat_no)
# ====================================================================
with tab_mat:
    st.subheader("🔗 Vật liệu — Mill Certificate")
    st.caption("Quản lý heat number, gắn vật liệu vào cấu kiện để truy xuất nguồn gốc.")

    sub_new, sub_list = st.tabs(["➕ Thêm lô vật liệu", "📋 Danh sách + Assign"])

    with sub_new:
        with st.form("form_new_mat", clear_on_submit=True):
            c1, c2 = st.columns(2)
            heat_no = c1.text_input("Heat No *", placeholder="H12345A")
            grade = c2.text_input("Grade *", placeholder="Q345B / SS400 / S355JR")

            c3, c4 = st.columns(2)
            supplier = c3.text_input("Nhà cung cấp", placeholder="POSCO / Hoà Phát")
            origin = c4.text_input("Xuất xứ", placeholder="Hàn Quốc / VN")

            c5, c6 = st.columns(2)
            cert_no = c5.text_input("Cert No", placeholder="MTC-001/2026")
            test_date = c6.date_input("Ngày test", value=date.today())

            st.markdown("**Thành phần hoá học (%):**")
            cch1, cch2, cch3, cch4, cch5 = st.columns(5)
            c_pct = cch1.text_input("C", value="")
            mn_pct = cch2.text_input("Mn", value="")
            si_pct = cch3.text_input("Si", value="")
            p_pct = cch4.text_input("P", value="")
            s_pct = cch5.text_input("S", value="")

            st.markdown("**Cơ tính:**")
            cme1, cme2, cme3 = st.columns(3)
            yld = cme1.text_input("Yield (MPa)", value="")
            tens = cme2.text_input("Tensile (MPa)", value="")
            elong = cme3.text_input("Elongation (%)", value="")

            submitted = st.form_submit_button("💾 Lưu lô vật liệu", type="primary")
            if submitted:
                if not heat_no.strip():
                    st.error("Cần nhập Heat No.")
                else:
                    try:
                        chem = {}
                        for k, v in [("C", c_pct), ("Mn", mn_pct), ("Si", si_pct),
                                     ("P", p_pct), ("S", s_pct)]:
                            if v.strip():
                                try: chem[k] = float(v)
                                except ValueError: pass
                        mech = {}
                        for k, v in [("yield_mpa", yld), ("tensile_mpa", tens),
                                     ("elongation_pct", elong)]:
                            if v.strip():
                                try: mech[k] = float(v)
                                except ValueError: pass
                        mid = material_service.create_material(
                            db=db, pid=pid, heat_no=heat_no.strip(),
                            grade=grade.strip() or None,
                            supplier=supplier or None,
                            origin=origin or None,
                            cert_no=cert_no or None,
                            test_date=test_date.isoformat(),
                            chemical=chem, mechanical=mech,
                        )
                        st.success(f"✅ Đã tạo lô vật liệu #{mid} — {heat_no}.")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

    with sub_list:
        df = material_service.list_materials_df(db, pid)
        if df.empty:
            st.info("Chưa có lô vật liệu nào.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True, height=260)

            st.markdown("##### 🔗 Gắn lô vật liệu vào cấu kiện")
            mid_sel = st.selectbox(
                "Chọn lô vật liệu",
                df["ID"].tolist(),
                format_func=lambda i: (
                    f"#{i} — {df[df['ID']==i]['Heat No'].iloc[0]} "
                    f"({df[df['ID']==i]['Grade'].iloc[0]})"
                ),
            )
            codes_text = st.text_area(
                "Danh sách mã cấu kiện (mỗi dòng 1 mã)",
                height=120,
                placeholder="BM-001\nBM-002\n...",
            )
            if st.button("🔗 Gắn vật liệu vào CK", type="primary"):
                codes = [c.strip() for c in codes_text.split("\n") if c.strip()]
                if not codes:
                    st.error("Cần nhập ít nhất 1 mã CK.")
                else:
                    n_ok, nf = material_service.assign_to_components(
                        db=db, material_id=int(mid_sel),
                        component_codes=codes, pid=pid,
                        assigned_by=get_current_user(),
                    )
                    st.success(f"✅ Gắn thành công {n_ok}/{len(codes)} cấu kiện.")
                    if nf:
                        st.warning(f"❌ Không tìm thấy mã: {', '.join(nf[:10])}")

            # Show CK using this material
            comps = material_service.get_components_for_material(db, int(mid_sel))
            if not comps.empty:
                st.caption(f"**{len(comps)} cấu kiện đang dùng heat này:**")
                st.dataframe(comps, use_container_width=True, hide_index=True, height=200)
