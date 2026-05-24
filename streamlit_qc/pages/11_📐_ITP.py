# -*- coding: utf-8 -*-
"""Page: ITP Templates + Engine — Inspection Test Plan."""
from __future__ import annotations

import sys
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
from streamlit_qc.services import itp_service
from streamlit_qc.services.itp_service import (
    CP_RESULT_LABEL,
    DEFAULT_TEMPLATES,
    HOLD_TYPE_LABEL,
    HOLD_TYPES,
)

st.set_page_config(
    page_title=f"ITP · {APP_NAME}",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("itp")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav()
render_page_header(
    "📐 ITP — Inspection Test Plan",
    "Quy trình kiểm tra checkpoints với Hold Point + witness từ CĐT",
)
project_info_strip()

pid = get_current_project_id()
if not pid:
    st.warning("⚠️ Vui lòng chọn dự án ở Tổng quan trước.")
    st.stop()

tab_tpl, tab_run = st.tabs([
    "📋 Quản lý Template",
    "▶️ Chạy ITP cho cấu kiện",
])

# ====================================================================
# TAB 1 — Templates
# ====================================================================
with tab_tpl:
    st.subheader("Danh sách template ITP")
    df = itp_service.list_templates_df(db, pid)
    if df.empty:
        st.info("Chưa có template nào. Bấm **Tạo template mới** bên dưới.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("##### ➕ Tạo template mới")

    use_preset = st.checkbox(
        "Dùng preset mẫu (ngành thép VN)", value=True,
        help="3 preset có sẵn: Dầm thép H / Cột ống tròn / Tấm thép phẳng",
    )

    if use_preset:
        preset_name = st.selectbox(
            "Chọn preset",
            list(DEFAULT_TEMPLATES.keys()),
        )
        tpl_name = st.text_input("Tên template", value=preset_name)
        comp_type = st.text_input("Loại cấu kiện (component_type, optional)",
                                   placeholder="VD: BEAM, COLUMN, PLATE")

        # Preview checkpoints
        cps_preview = DEFAULT_TEMPLATES[preset_name]
        st.markdown("**Preview checkpoints:**")
        df_prev = pd.DataFrame([{
            "Seq": c["seq"],
            "Tên checkpoint": c["name"],
            "Loại": HOLD_TYPE_LABEL.get(c["hold_type"], c["hold_type"]),
            "Bắt buộc": "✅" if c.get("required", True) else "❌",
        } for c in cps_preview])
        st.dataframe(df_prev, use_container_width=True, hide_index=True)

        if st.button("💾 Tạo template từ preset", type="primary"):
            try:
                tid = itp_service.create_template(
                    db, pid, tpl_name, comp_type or None, cps_preview,
                )
                db.conn.commit()
                st.success(f"✅ Đã tạo template #{tid}: {tpl_name}")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")
    else:
        # Custom template
        tpl_name = st.text_input("Tên template", placeholder="VD: ITP Dầm tổ hợp")
        comp_type = st.text_input("Loại cấu kiện (optional)")
        st.markdown("**Nhập checkpoints (mỗi dòng 1 CP, format: `tên | hold_type | required`):**")
        st.caption("hold_type ∈ {HOLD, WITNESS, REVIEW}. required ∈ {true, false}")
        custom_text = st.text_area(
            "Checkpoints",
            value=(
                "Dimension Check | WITNESS | true\n"
                "Fit-up Inspection | HOLD | true\n"
                "NDT (VT/MT/UT) | WITNESS | true\n"
                "Paint DFT | REVIEW | true\n"
                "Final Inspection | HOLD | true"
            ),
            height=160,
        )
        if st.button("💾 Tạo template custom", type="primary"):
            try:
                cps = []
                for i, line in enumerate(custom_text.split("\n"), 1):
                    line = line.strip()
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 1:
                        continue
                    name = parts[0]
                    ht = parts[1].upper() if len(parts) > 1 else "REVIEW"
                    if ht not in HOLD_TYPES:
                        ht = "REVIEW"
                    req = True
                    if len(parts) > 2:
                        req = parts[2].lower() in ("true", "yes", "1")
                    cps.append({"seq": i, "name": name, "hold_type": ht, "required": req})
                tid = itp_service.create_template(
                    db, pid, tpl_name or "ITP", comp_type or None, cps,
                )
                db.conn.commit()
                st.success(f"✅ Đã tạo template #{tid} với {len(cps)} checkpoint")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")


# ====================================================================
# TAB 2 — Run ITP
# ====================================================================
with tab_run:
    st.subheader("Chạy ITP cho 1 cấu kiện")

    rows = db.conn.execute(
        "SELECT id, code, status FROM components "
        "WHERE project_id=? ORDER BY code LIMIT 500", (pid,),
    ).fetchall()
    if not rows:
        st.info("Chưa có cấu kiện nào.")
        st.stop()

    c1, c2 = st.columns([2, 2])
    comp_options = [(r["id"], r["code"], r["status"]) for r in rows]
    sel_comp = c1.selectbox(
        "Chọn cấu kiện",
        comp_options,
        format_func=lambda x: f"{x[1]} ({x[2]})",
    )
    sel_cid = sel_comp[0]

    tpl_rows = db.list_itp_templates(pid)
    if not tpl_rows:
        st.warning("Chưa có template ITP. Tạo template ở tab trên trước.")
        st.stop()

    tpl_options = [(r["id"], r["name"]) for r in tpl_rows]
    sel_tpl = c2.selectbox(
        "Chọn template ITP",
        tpl_options,
        format_func=lambda x: x[1],
    )
    sel_tid = sel_tpl[0]

    cps = itp_service.get_template_checkpoints(db, sel_tid)
    if not cps:
        st.error("Template không có checkpoint nào.")
        st.stop()

    progress = itp_service.get_progress(db, sel_cid)
    st.caption(
        f"Tiến độ: **{progress['passed']}**/{progress['total']} PASS · "
        f"{progress['failed']} FAIL · {progress['hold_waiting']} chờ witness"
    )

    # Build progress table
    records_by_seq = {r["checkpoint_seq"]: r for r in progress["records"]}
    table_data = []
    for cp in cps:
        seq = int(cp["seq"])
        rec = records_by_seq.get(seq)
        cur_result = rec["result"] if rec else "PENDING"
        table_data.append({
            "Seq": seq,
            "Checkpoint": cp["name"],
            "Loại": HOLD_TYPE_LABEL.get(cp.get("hold_type", "REVIEW"), ""),
            "Bắt buộc": "✅" if cp.get("required", True) else "—",
            "Kết quả": CP_RESULT_LABEL.get(cur_result, cur_result),
            "Người KT": rec["inspector"] if rec else "",
            "Witness": rec["witness_by"] if rec and rec["witness_by"] else "—",
        })
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    st.markdown("##### ⬇️ Nhập kết quả checkpoint")
    cc1, cc2 = st.columns([1.5, 1.5])
    cp_seq = cc1.selectbox(
        "Checkpoint",
        [c["seq"] for c in cps],
        format_func=lambda s: f"#{s} — {next(c['name'] for c in cps if c['seq']==s)}",
    )
    result = cc2.selectbox("Kết quả", ["PASS", "FAIL"])
    inspector = st.text_input("Người KT", value=get_current_user())
    remarks = st.text_area("Ghi chú", value="", height=80)

    if st.button("💾 Lưu checkpoint", type="primary"):
        try:
            res = itp_service.submit_checkpoint(
                db, sel_cid, sel_tid, int(cp_seq), result, inspector, remarks,
            )
            if not res["ok"]:
                st.error(f"Lỗi: {res.get('error')}")
            elif res["next_action"] == "hold_waiting":
                st.warning(
                    f"🛑 HOLD POINT — checkpoint **{res['checkpoint']}** đang chờ "
                    f"witness từ **{res['witness_required']}**. "
                    "Xuống mục **Witness** bên dưới khi CĐT có mặt."
                )
            elif res["next_action"] == "all_passed":
                st.success("🏆 TẤT CẢ CHECKPOINT PASS! Cấu kiện đã ACCEPTED.")
                st.balloons()
            else:
                st.success("✅ Đã lưu. Sang checkpoint tiếp theo.")
            st.rerun()
        except Exception as e:
            st.error(f"Lỗi: {e}")

    # Witness section
    waiting = [r for r in progress["records"] if r["result"] == "HOLD_WAITING"]
    if waiting:
        st.divider()
        st.markdown("##### 🛑 Hold Point đang chờ witness")
        for r in waiting:
            st.warning(
                f"CP #{r['checkpoint_seq']} — **{r['checkpoint_name']}** · "
                f"Inspector: {r['inspector']}"
            )
            w_name = st.text_input(
                f"Tên người witness (CĐT/Tư vấn) — CP {r['checkpoint_seq']}",
                key=f"witness_{r['checkpoint_seq']}",
            )
            if st.button(f"✍️ Ký witness CP {r['checkpoint_seq']}",
                         key=f"btn_witness_{r['checkpoint_seq']}"):
                if not w_name.strip():
                    st.error("Cần nhập tên người witness.")
                else:
                    ok = itp_service.witness_checkpoint(
                        db, sel_cid, int(r["checkpoint_seq"]), w_name.strip(),
                    )
                    if ok:
                        st.success(f"✅ Đã ký witness bởi {w_name}.")
                        st.rerun()
                    else:
                        st.error("Lỗi: không update được.")
