# -*- coding: utf-8 -*-
"""Reusable UI components: top nav, page header, KPI cards, badges, empty state."""
from __future__ import annotations

import streamlit as st

from streamlit_qc.core.theme import (
    BORDER,
    GOLD,
    GOLD_SOFT,
    NAVY,
    NAVY_DARK,
    NAVY_LIGHT,
    SURFACE,
    TEXT,
    TEXT_MUTED,
)


def render_top_nav(active_page: str = "") -> None:
    """Top horizontal navigation bar với logo + 7 page links + user."""
    from streamlit_qc.core.constants import APP_NAME, APP_VERSION
    from streamlit_qc.core.state import S_CURRENT_USER

    PAGES = [
        ("home", "🏠 Trang chủ", "app.py"),
        ("tongquan", "📊 Tổng quan", "pages/1_📊_Tổng_quan.py"),
        ("master", "📥 Master", "pages/2_📥_Import_Master.py"),
        ("daily", "📤 Daily", "pages/3_📤_Import_Daily.py"),
        ("caukien", "🔧 Cấu kiện", "pages/4_🔧_Cấu_kiện.py"),
        ("baocao", "📈 Báo cáo", "pages/5_📈_Báo_cáo.py"),
        ("quantri", "⚙ Quản trị", "pages/6_⚙_Quản_trị.py"),
    ]

    user = st.session_state.get(S_CURRENT_USER, "qc_user")
    initial = (user[:1] or "Q").upper()

    top_html = (
        f'<div style="background:linear-gradient(135deg,{NAVY_DARK} 0%,{NAVY} 100%);'
        f'border-radius:12px;padding:10px 18px;margin:-10px 0 14px 0;'
        f'display:flex;align-items:center;justify-content:space-between;'
        f'box-shadow:0 4px 16px rgba(15,30,64,.12);">'
        f'<div style="display:flex;align-items:center;gap:14px;">'
        f'<div style="background:linear-gradient(135deg,{GOLD},#9F7B1F);'
        f'width:34px;height:34px;border-radius:8px;line-height:34px;text-align:center;'
        f'color:{NAVY_DARK};font-weight:800;font-size:14px;">QC</div>'
        f'<div>'
        f'<div style="color:white;font-weight:700;font-size:14px;line-height:1.1;">{APP_NAME}</div>'
        f'<div style="color:rgba(255,255,255,.55);font-size:10px;">v{APP_VERSION}</div>'
        f'</div></div>'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<div style="width:30px;height:30px;border-radius:50%;'
        f'background:linear-gradient(135deg,{GOLD},#9F7B1F);'
        f'color:{NAVY_DARK};font-weight:700;line-height:30px;'
        f'text-align:center;font-size:13px;">{initial}</div>'
        f'<div style="color:white;font-size:13px;font-weight:500;">{user}</div>'
        f'</div></div>'
    )
    st.markdown(top_html, unsafe_allow_html=True)

    cols = st.columns(len(PAGES))
    for i, (key, label, path) in enumerate(PAGES):
        with cols[i]:
            try:
                st.page_link(path, label=label, use_container_width=True)
            except Exception:
                st.button(label, key=f"nav_{key}", use_container_width=True)

    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)


def render_page_header(page_title, subtitle="", page_icon="", show_project_picker=True, page_subtitle=""):
    """Header chuẩn mỗi page: title bên trái, project picker bên phải."""
    from streamlit_qc.core.state import get_current_project_id, get_db, set_current_project_id
    from streamlit_qc.services import project_service

    if page_subtitle and not subtitle:
        subtitle = page_subtitle

    db = get_db()
    projects = project_service.list_projects(db)
    current_proj = None

    col_title, col_picker = st.columns([3, 2])

    with col_title:
        icon_html = f"<span style='margin-right:8px;'>{page_icon}</span>" if page_icon else ""
        sub_html = (
            f"<div style='color:{TEXT_MUTED};font-size:14px;margin-top:2px;'>{subtitle}</div>"
            if subtitle else ""
        )
        title_html = (
            f'<div style="margin:0 0 12px 0;">'
            f'<div style="display:flex;align-items:center;">'
            f'<div style="width:4px;height:28px;background:{GOLD};border-radius:2px;margin-right:12px;"></div>'
            f'<h2 style="margin:0;color:{NAVY};font-size:22px;font-weight:700;">{icon_html}{page_title}</h2>'
            f'</div>{sub_html}</div>'
        )
        st.markdown(title_html, unsafe_allow_html=True)

    with col_picker:
        if show_project_picker:
            current_proj = _render_inline_project_picker(db, projects)

    st.divider()
    return current_proj


def _render_inline_project_picker(db, projects):
    from streamlit_qc.core.state import get_current_project_id, set_current_project_id

    current_pid = get_current_project_id()
    current_proj = None

    if not projects:
        c_lbl, c_btn = st.columns([2, 3])
        with c_lbl:
            st.markdown(
                f"<div style='color:{TEXT_MUTED};font-size:13px;margin-top:8px;'>Chưa có dự án</div>",
                unsafe_allow_html=True,
            )
        with c_btn:
            if st.button("+ Tạo dự án mới", key="hdr_new_proj_btn",
                         type="primary", use_container_width=True):
                st.session_state["_show_new_proj_dialog"] = True
        _maybe_show_new_project_dialog(db)
        return None

    options = {f"[{p['code']}] {p['name']}": p["id"] for p in projects}
    labels = list(options.keys())

    if current_pid is None or current_pid not in options.values():
        set_current_project_id(projects[0]["id"])
        current_pid = projects[0]["id"]

    idx = next((i for i, p in enumerate(projects) if p["id"] == current_pid), 0)

    c_label, c_select, c_new = st.columns([1.2, 4, 2])
    with c_label:
        st.markdown(
            f"<div style='color:{TEXT_MUTED};font-size:12px;font-weight:600;"
            f"text-transform:uppercase;letter-spacing:.05em;margin-top:8px;'>Dự án:</div>",
            unsafe_allow_html=True,
        )
    with c_select:
        sel = st.selectbox("Dự án", labels, index=idx,
                          label_visibility="collapsed", key="page_hdr_proj_select")
        if sel:
            new_pid = options[sel]
            if new_pid != current_pid:
                set_current_project_id(new_pid)
                st.rerun()
            current_proj = dict(next(p for p in projects if p["id"] == new_pid))
    with c_new:
        if st.button("+ Dự án mới", key="hdr_new_proj_btn", use_container_width=True):
            st.session_state["_show_new_proj_dialog"] = True

    _maybe_show_new_project_dialog(db)
    return current_proj


@st.dialog("Tạo dự án mới", width="large")
def _new_project_dialog(db):
    from streamlit_qc.core.state import S_CURRENT_USER, set_current_project_id
    from streamlit_qc.services import project_service

    with st.form("new_project_form_dialog", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            code = st.text_input("Mã dự án *", placeholder="VD: VIOLA")
        with c2:
            name = st.text_input("Tên dự án *", placeholder="VD: VIOLA Energy Center")
        location = st.text_input("Địa điểm")
        owner = st.text_input("Chủ đầu tư")
        note = st.text_area("Ghi chú", height=68)

        c_submit, c_cancel = st.columns([1, 1])
        with c_submit:
            submitted = st.form_submit_button("Tạo dự án", type="primary", use_container_width=True)
        with c_cancel:
            cancel = st.form_submit_button("Huỷ", use_container_width=True)

        if submitted:
            try:
                new_pid = project_service.create_project(
                    db, code=code, name=name, location=location,
                    owner=owner, note=note,
                    user_name=st.session_state.get(S_CURRENT_USER, "qc_user"),
                )
                set_current_project_id(new_pid)
                st.session_state.pop("_show_new_proj_dialog", None)
                st.success(f"Đã tạo dự án [{code}]")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Lỗi: {e}")

        if cancel:
            st.session_state.pop("_show_new_proj_dialog", None)
            st.rerun()


def _maybe_show_new_project_dialog(db):
    if st.session_state.get("_show_new_proj_dialog"):
        _new_project_dialog(db)


def project_info_strip(proj=None, n_comp=None):
    """
    Dải info compact cho dự án.

    Nếu proj=None → tự tra cứu từ session state (pid hiện tại).
    """
    if proj is None:
        try:
            from streamlit_qc.core.state import get_current_project_id, get_db
            pid = get_current_project_id()
            if pid is None:
                return
            db_inst = get_db()
            row = db_inst.get_project(pid)
            if not row:
                return
            proj = dict(row) if not isinstance(row, dict) else row
        except Exception:
            return

    code = proj["code"] if "code" in proj else "—"
    name = proj["name"] if "name" in proj else "—"
    parts = [f"<b>[{code}]</b> {name}"]
    if n_comp is not None:
        parts.append(f"📦 <b>{n_comp:,}</b> cấu kiện")
    loc = proj["location"] if "location" in proj else None
    owner = proj["owner"] if "owner" in proj else None
    if loc:
        parts.append(f"📍 {loc}")
    if owner:
        parts.append(f"🏢 {owner}")
    st.markdown(
        f"<div style='background:{GOLD_SOFT};border:1px solid {GOLD};color:{NAVY_DARK};"
        f"padding:8px 14px;border-radius:8px;font-size:13px;line-height:1.6;"
        f"margin:-8px 0 16px 0;'>{' &nbsp;·&nbsp; '.join(parts)}</div>",
        unsafe_allow_html=True,
    )


def section_header(title, subtitle="", icon=""):
    """Header section với dải gold bên trái."""
    icon_html = f"<span style='margin-right:8px;'>{icon}</span>" if icon else ""
    sub_html = (
        f"<div style='color:{TEXT_MUTED};font-size:14px;margin-top:2px;'>{subtitle}</div>"
        if subtitle else ""
    )
    html = (
        f'<div style="margin:8px 0 20px 0;">'
        f'<div style="display:flex;align-items:center;">'
        f'<div style="width:4px;height:24px;background:{GOLD};border-radius:2px;margin-right:12px;"></div>'
        f'<h3 style="margin:0;color:{NAVY};font-size:20px;font-weight:600;">{icon_html}{title}</h3>'
        f'</div>{sub_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def hero_banner(title, subtitle="", badge=""):
    """Hero banner gradient navy."""
    badge_html = ""
    if badge:
        badge_html = (
            f"<span style='background:{GOLD};color:{NAVY_DARK};padding:4px 12px;"
            f"border-radius:999px;font-size:12px;font-weight:600;margin-left:12px;"
            f"display:inline-block;'>{badge}</span>"
        )
    sub_html = (
        f"<div style='color:rgba(255,255,255,0.85);font-size:15px;margin-top:6px;'>{subtitle}</div>"
        if subtitle else ""
    )
    html = (
        f'<div style="background:linear-gradient(135deg,{NAVY_DARK} 0%,{NAVY_LIGHT} 100%);'
        f'border-radius:14px;padding:26px 30px;margin-bottom:24px;'
        f'box-shadow:0 4px 20px rgba(15,30,64,0.15);position:relative;overflow:hidden;">'
        f'<div style="position:absolute;top:-30px;right:-30px;width:160px;height:160px;'
        f'background:radial-gradient(circle,{GOLD}22 0%,transparent 70%);border-radius:50%;"></div>'
        f'<h1 style="margin:0;color:white;font-size:28px;font-weight:700;display:inline;">{title}</h1>'
        f'{badge_html}{sub_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def kpi_card(label, value, color=NAVY, icon="", delta=""):
    """1 KPI card. HTML viết 1 dòng để tránh Streamlit markdown parse indent thành code block."""
    icon_html = f"<div style='font-size:20px;margin-bottom:4px;opacity:.7;'>{icon}</div>" if icon else ""
    delta_html = f"<div style='font-size:12px;color:{TEXT_MUTED};margin-top:6px;'>{delta}</div>" if delta else ""
    val_str = f"{value:,}" if isinstance(value, int) else str(value)
    html = (
        f'<div style="background:{SURFACE};border:1px solid {BORDER};'
        f'border-radius:12px;padding:16px 18px;box-shadow:0 1px 3px rgba(0,0,0,.04);height:100%;">'
        f'{icon_html}'
        f'<div style="color:{TEXT_MUTED};font-size:12px;font-weight:500;'
        f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;">{label}</div>'
        f'<div style="color:{color};font-size:30px;font-weight:700;line-height:1.1;">{val_str}</div>'
        f'{delta_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def status_badge(status):
    """HTML inline status badge."""
    from streamlit_qc.core.constants import STATUS_BG, STATUS_COLORS, STATUS_LABELS
    bg = STATUS_BG.get(status, "#F1F5F9")
    color = STATUS_COLORS.get(status, NAVY)
    label = STATUS_LABELS.get(status, status)
    return (
        f"<span style='background:{bg};color:{color};padding:3px 10px;"
        f"border-radius:999px;font-size:12px;font-weight:600;display:inline-block;'>{label}</span>"
    )


def info_pill(text, color=NAVY):
    """Pill nhỏ chứa info."""
    st.markdown(
        f"<span style='display:inline-block;background:{GOLD_SOFT};color:{color};"
        f"padding:4px 12px;border-radius:999px;font-size:13px;font-weight:500;"
        f"border:1px solid {GOLD};'>{text}</span>",
        unsafe_allow_html=True,
    )


def quick_action_card(icon, title, description, page_path=None):
    """Card quick action."""
    html = (
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:12px;'
        f'padding:20px;height:100%;">'
        f'<div style="font-size:32px;margin-bottom:10px;">{icon}</div>'
        f'<div style="font-size:16px;font-weight:600;color:{NAVY};margin-bottom:4px;">{title}</div>'
        f'<div style="font-size:13px;color:{TEXT_MUTED};line-height:1.45;">{description}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def empty_state(icon, title, description, action_hint=""):
    """Empty state khi chưa có data."""
    hint_html = (
        f"<div style='margin-top:14px;display:inline-block;background:{GOLD_SOFT};"
        f"color:{NAVY_DARK};padding:8px 16px;border-radius:8px;font-size:13px;'>"
        f"{action_hint}</div>"
        if action_hint else ""
    )
    html = (
        f'<div style="text-align:center;padding:48px 24px;background:{SURFACE};'
        f'border:1px dashed {BORDER};border-radius:12px;margin:20px 0;">'
        f'<div style="font-size:48px;opacity:.4;margin-bottom:14px;">{icon}</div>'
        f'<div style="font-size:17px;font-weight:600;color:{NAVY};margin-bottom:6px;">{title}</div>'
        f'<div style="font-size:14px;color:{TEXT_MUTED};max-width:480px;margin:0 auto;line-height:1.5;">{description}</div>'
        f'{hint_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
