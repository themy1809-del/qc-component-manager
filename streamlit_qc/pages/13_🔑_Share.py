# -*- coding: utf-8 -*-
"""Page: Client Portal — quản lý share tokens cho CĐT view-only.

Hai chế độ:
- Admin mode (mặc định): tạo / quản lý / revoke token
- Client mode: khi URL có query param ?token=... → hiển thị dashboard view-only
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
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
from streamlit_qc.services import share_token_service

st.set_page_config(
    page_title=f"Share · {APP_NAME}",
    page_icon="🔑",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

# ====================================================================
# DETECT MODE — Client (có token) vs Admin
# ====================================================================
qp = st.query_params
client_token = qp.get("token", "")
if isinstance(client_token, list):
    client_token = client_token[0] if client_token else ""

if client_token:
    # ============================================================
    # CLIENT VIEW (read-only)
    # ============================================================
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#0F1E40,#1E3A8A);"
        f"padding:18px;border-radius:10px;color:#fff;margin-bottom:14px;'>"
        f"<div style='font-size:18px;font-weight:700;'>🏢 Cổng thông tin Khách hàng / Tư vấn</div>"
        f"<div style='font-size:13px;color:#FCE7A1;margin-top:4px;'>"
        f"Đại Dũng Steel — QC Component Manager · View-only</div></div>",
        unsafe_allow_html=True,
    )

    # Password gate?
    pwd_input = None
    pid_ok, msg = share_token_service.validate_token(db, client_token, None)
    if msg == "need_password":
        st.warning("🔒 Link này yêu cầu mật khẩu.")
        pwd_input = st.text_input("Nhập mật khẩu", type="password")
        if st.button("Mở khoá"):
            pid_ok, msg = share_token_service.validate_token(db, client_token, pwd_input)
        else:
            st.stop()

    if msg == "not_found":
        st.error("❌ Token không tồn tại hoặc đã bị thu hồi.")
        st.stop()
    elif msg == "expired":
        st.error("⏰ Link đã hết hạn. Vui lòng yêu cầu Đại Dũng cấp link mới.")
        st.stop()
    elif msg == "wrong_password":
        st.error("❌ Sai mật khẩu. Thử lại.")
        st.stop()
    elif msg != "ok" or not pid_ok:
        st.error(f"Lỗi: {msg}")
        st.stop()

    # === VIEW MODE ===
    proj = db.get_project(pid_ok)
    if not proj:
        st.error("Dự án không tồn tại.")
        st.stop()

    st.success(f"✅ Đã xác thực · Bạn đang xem dự án: **{proj['code']} — {proj['name']}**")

    # Stats
    cnt_row = db.conn.execute(
        "SELECT COUNT(*) c, "
        "SUM(CASE WHEN status='ACCEPTED' THEN 1 ELSE 0 END) acc, "
        "SUM(CASE WHEN status='PASSED' THEN 1 ELSE 0 END) pass, "
        "SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) inp, "
        "SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) fail "
        "FROM components WHERE project_id=?",
        (pid_ok,),
    ).fetchone()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📦 Tổng CK", f"{cnt_row['c']:,}")
    m2.metric("✅ ACCEPTED", f"{cnt_row['acc'] or 0:,}")
    m3.metric("🏁 PASSED", f"{cnt_row['pass'] or 0:,}")
    m4.metric("🔧 IN PROGRESS", f"{cnt_row['inp'] or 0:,}")
    m5.metric("❌ FAILED", f"{cnt_row['fail'] or 0:,}")

    total = cnt_row["c"] or 0
    done = (cnt_row["acc"] or 0) + (cnt_row["pass"] or 0)
    if total:
        pct = done * 100 / total
        st.progress(min(pct / 100, 1.0), text=f"Tiến độ tổng thể: {pct:.1f}% ({done:,}/{total:,})")

    # Component list (read-only)
    st.markdown("##### 📋 Danh sách cấu kiện")
    rows = db.conn.execute(
        "SELECT code, status, data_json FROM components "
        "WHERE project_id=? ORDER BY code LIMIT 500",
        (pid_ok,),
    ).fetchall()
    if rows:
        items = []
        for r in rows:
            try:
                d = json.loads(r["data_json"])
            except (json.JSONDecodeError, TypeError):
                d = {}
            items.append({
                "Mã cấu kiện": r["code"],
                "Trạng thái": r["status"],
                "Xưởng": d.get("workshop", ""),
                "Bản vẽ": d.get("manual_drawing") or d.get("drawing") or "",
                "Khối lượng (kg)": d.get("weight_kg", ""),
            })
        st.dataframe(pd.DataFrame(items), use_container_width=True,
                     hide_index=True, height=400)
    else:
        st.info("Dự án này chưa có cấu kiện nào.")

    # Footer
    st.divider()
    st.caption(
        f"🔒 View-only · "
        f"Liên hệ Đại Dũng QC: themy1809@gmail.com · "
        f"Token: `{client_token[:8]}...`"
    )
    st.stop()


# ====================================================================
# ADMIN MODE — quản lý token
# ====================================================================
from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("share_admin")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav()
render_page_header(
    "🔑 Client Portal — Share Tokens",
    "Tạo link view-only cho CĐT / Tư vấn xem dự án từ xa",
)
project_info_strip()

pid = get_current_project_id()
if not pid:
    st.warning("⚠️ Vui lòng chọn dự án ở Tổng quan trước.")
    st.stop()

tab_new, tab_list = st.tabs(["➕ Tạo token mới", "📋 Quản lý token"])

with tab_new:
    st.subheader("Tạo link share cho dự án")
    st.caption(
        "Link sẽ cho phép CĐT/Tư vấn xem dự án **read-only** mà không cần login. "
        "Có thể đặt mật khẩu + thời hạn hết hạn."
    )

    c1, c2 = st.columns([3, 1])
    label = c1.text_input(
        "Mô tả (cho admin nhớ)",
        placeholder="VD: Link cho CĐT San bay Phú Quốc — 30 ngày",
    )
    days = c2.number_input("Số ngày hiệu lực", 1, 365, 30, key="days_v")

    c3, c4 = st.columns(2)
    use_pwd = c3.checkbox("Đặt mật khẩu (bảo mật cao hơn)", value=True)
    password = ""
    if use_pwd:
        password = c4.text_input(
            "Mật khẩu", type="password",
            placeholder="Ít nhất 6 ký tự",
        )

    if st.button("🔑 Tạo link", type="primary", use_container_width=True):
        if use_pwd and len(password) < 6:
            st.error("Mật khẩu cần ít nhất 6 ký tự.")
        else:
            try:
                token = share_token_service.create_token(
                    db=db, pid=pid, label=label,
                    days_valid=int(days),
                    password=password if use_pwd else None,
                    created_by=get_current_user(),
                )
                base_url = st.text_input(
                    "Base URL của app",
                    value="https://qc-daidung.streamlit.app",
                    key="base_url_show",
                )
                share_url = share_token_service.build_share_url(base_url, token)
                st.success("✅ Đã tạo link share!")
                st.code(share_url, language=None)
                st.caption(
                    f"📋 Copy link trên gửi cho CĐT. "
                    f"{'🔒 Đã đặt mật khẩu — gửi mật khẩu riêng qua kênh khác.' if use_pwd else '⚠️ Không có mật khẩu — ai có link đều xem được.'}"
                )
            except Exception as e:
                st.error(f"Lỗi: {e}")

with tab_list:
    st.subheader("Danh sách token đang hoạt động")
    df = share_token_service.list_tokens_df(db, pid)
    if df.empty:
        st.info("Chưa có token nào.")
    else:
        st.dataframe(
            df.drop(columns=["Token đầy đủ"]),
            use_container_width=True, hide_index=True,
        )

        st.markdown("##### 🗑️ Thu hồi token")
        sel_token = st.selectbox(
            "Chọn token để thu hồi",
            df["Token đầy đủ"].tolist(),
            format_func=lambda t: f"{t[:8]}... · {df[df['Token đầy đủ']==t]['Mô tả'].iloc[0]}",
        )
        if st.button(f"🗑️ Thu hồi token {sel_token[:8]}...",
                     type="secondary", use_container_width=True):
            try:
                share_token_service.revoke_token(db, sel_token, by_user=get_current_user())
                st.success(f"✅ Đã thu hồi token {sel_token[:8]}...")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")
