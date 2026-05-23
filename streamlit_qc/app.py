# -*- coding: utf-8 -*-
"""QC Component Manager Web v2.4 — Minimal Workshop Dashboard.

Triết lý: ít KPI, nhiều visual, dễ click.
- Hero compact 1 dòng
- Workshop grid: chỉ tên + % + thanh tiến độ
- Click workshop → panel chi tiết với donut + activity
- Nav tiles cuối trang
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_PARENT = _THIS.parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from streamlit_qc.core.constants import (
    APP_NAME,
    APP_VERSION,
    COMPANY,
    STATUS_ACCEPTED,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    STATUS_PASSED,
    STATUS_PENDING,
)
from streamlit_qc.core.state import get_current_project_id, get_db, init_session_state
from streamlit_qc.core.theme import apply_theme
from streamlit_qc.core.ui import empty_state, render_page_header, render_top_nav
from streamlit_qc.services import project_service

st.set_page_config(
    page_title=f"{APP_NAME} v{APP_VERSION}",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()
render_top_nav(active_page="home")

proj = render_page_header(
    "Trang chủ",
    subtitle=f"Dashboard tương tác · {COMPANY}",
    page_icon="🏠",
)


def emit(html: str) -> None:
    cleaned = re.sub(r"^[ \t]+", "", html, flags=re.MULTILINE)
    st.markdown(cleaned, unsafe_allow_html=True)


emit("""
<style>
/* Hero — 1 dòng, gọn */
.hero {
  background: linear-gradient(135deg, #0F1E40 0%, #1E3A8A 100%);
  border-radius: 12px; padding: 16px 22px; color: #fff;
  display: flex; align-items: center; justify-content: space-between; gap: 14px;
  flex-wrap: wrap; margin-bottom: 18px;
  box-shadow: 0 4px 16px rgba(15, 30, 64, 0.16);
}
.hero .name {font-size: 18px; font-weight: 700; margin: 0;}
.hero .meta {color: rgba(255,255,255,0.72); font-size: 12px; margin-top: 3px;}
.hero .pct {font-size: 30px; font-weight: 800; color: #FCE7A1; line-height: 1; letter-spacing: -0.5px;}
.hero .ratio {color: rgba(255,255,255,0.72); font-size: 11px; margin-top: 2px;}

/* Section title minimal */
.sec {
  font-size: 14px; font-weight: 700; color: #0F1E40;
  margin: 14px 0 10px 0;
  display: flex; align-items: center; gap: 8px;
}
.sec::before {content: ""; width: 3px; height: 14px; background: #D4A744; border-radius: 2px;}
.sec .sub {font-weight: 400; color: #94A3B8; font-size: 12px;}

/* Workshop card — VERY MINIMAL */
.ws {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 14px 16px; min-height: 90px;
  transition: all 0.18s ease; position: relative; overflow: hidden;
}
.ws:hover {box-shadow: 0 6px 16px rgba(15, 30, 64, 0.10); border-color: #D4A744;}
.ws.active {border: 2px solid #D4A744; background: #fffdf7; box-shadow: 0 4px 14px rgba(212, 167, 68, 0.15);}
.ws .row {display: flex; justify-content: space-between; align-items: baseline;}
.ws .nm {font-size: 17px; font-weight: 800; color: #0F1E40; letter-spacing: -0.3px;}
.ws .pc {font-size: 24px; font-weight: 800; line-height: 1; letter-spacing: -0.5px;}
.ws .bar {height: 7px; background: #f1f5f9; border-radius: 4px; overflow: hidden; margin-top: 8px;}
.ws .bar .fill {height: 100%; border-radius: 4px; transition: width 0.6s ease;}
.ws .tot {font-size: 11px; color: #94A3B8; margin-top: 6px;}

/* Workshop detail panel */
.panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-left: 5px solid #D4A744;
  border-radius: 12px;
  padding: 18px 22px;
  margin-top: 10px;
  box-shadow: 0 4px 14px rgba(15, 30, 64, 0.06);
}
.panel-head {display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 10px;}
.panel-head .nm {font-size: 22px; font-weight: 800; color: #0F1E40; margin: 0;}
.panel-head .sub {font-size: 12px; color: #64748B;}
.panel-head .pct {font-size: 38px; font-weight: 800; line-height: 1; letter-spacing: -1px;}

/* Activity feed */
.act-feed {background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden;}
.act-row {
  border-bottom: 1px solid #f1f5f9; padding: 10px 14px;
  display: flex; gap: 10px; align-items: center; font-size: 12px;
}
.act-row:last-child {border-bottom: none;}
.act-row:hover {background: #fafbfc;}
.act-row .typ {padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 700; background: #f1f5f9; color: #475569;}
.act-row .res {padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 10px;}
.res-pass {background: #dcfce7; color: #166534;}
.res-fail {background: #fee2e2; color: #991b1b;}
.res-rec {background: #fef3c7; color: #92400e;}

/* Nav tile minimal */
.nav {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 12px 8px; text-align: center; height: 78px;
  display: flex; flex-direction: column; justify-content: center; gap: 2px;
  transition: all .15s ease;
}
.nav:hover {border-color: #D4A744; box-shadow: 0 4px 12px rgba(15,30,64,.08); transform: translateY(-2px);}
.nav .ic {font-size: 18px;}
.nav .lbl {font-weight: 700; color: #0F1E40; font-size: 11px;}

/* Multi-project mini card */
.proj-mini {
  background:#fff; border:1px solid #e2e8f0; border-radius:10px;
  padding: 10px 12px; transition: all .15s ease;
  height: 100%; display: flex; flex-direction: column; gap: 4px;
  position: relative; overflow: hidden;
}
.proj-mini:hover {border-color:#D4A744; box-shadow:0 4px 12px rgba(15,30,64,.08); transform:translateY(-2px);}
.proj-mini.active {border:2px solid #D4A744; background:#fffdf7;}
.proj-mini .pm-strip {position:absolute; top:0; left:0; right:0; height:3px;}
.proj-mini .pm-code {font-size:11px; color:#FCE7A1; background:#0F1E40; padding:2px 8px; border-radius:4px; font-weight:700; align-self:flex-start;}
.proj-mini .pm-name {font-size:12px; font-weight:600; color:#0F172A; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:4px;}
.proj-mini .pm-pct {font-size:22px; font-weight:800; line-height:1; margin-top:2px;}
.proj-mini .pm-bar {height:5px; background:#f1f5f9; border-radius:4px; overflow:hidden;}
.proj-mini .pm-bar-fill {height:100%; border-radius:4px;}
.proj-mini .pm-stats {display:flex; justify-content:space-between; font-size:10px; color:#64748B; margin-top:4px;}
.proj-mini .pm-stats b {color:#0F172A;}
</style>
""")


# ============================================================
# Data
# ============================================================
projects = project_service.list_projects(db)
if not projects:
    empty_state(icon="📁", title="Chưa có dự án nào",
                description="Bấm nút **+ Dự án mới** ở header trên để bắt đầu.")
    st.stop()

active_pid = get_current_project_id()
if active_pid is None or proj is None:
    st.warning("Chọn dự án ở header trên để bắt đầu.")
    st.stop()


@st.cache_data(ttl=120, show_spinner=False)
def project_workshops(_db, pid: int) -> dict:
    """
    Aggregate workshop counts trong SQL — KHÔNG fetch 14k rows data_json.
    Tối ưu: dùng JSON operator của Postgres (->>'workshop') hoặc SQLite (json_extract).
    """
    if _db.is_postgres:
        ws_extract = "COALESCE(data_json::jsonb->>'workshop', '(không xưởng)')"
    else:
        ws_extract = "COALESCE(json_extract(data_json, '$.workshop'), '(không xưởng)')"

    rows = _db.conn.execute(
        f"""
        SELECT {ws_extract} AS ws, status, COUNT(*) c
        FROM components WHERE project_id=?
        GROUP BY ws, status
        """,
        (pid,),
    ).fetchall()

    ws_data: dict[str, dict] = {}
    total_proj = 0
    done_proj = 0
    for r in rows:
        w = r["ws"] or "(không xưởng)"
        st_v = r["status"]
        cnt = r["c"]
        if w not in ws_data:
            ws_data[w] = {"workshop": w, "TOTAL": 0,
                          "PENDING": 0, "IN_PROGRESS": 0,
                          "PASSED": 0, "FAILED": 0, "ACCEPTED": 0}
        ws_data[w]["TOTAL"] += cnt
        if st_v in ws_data[w]:
            ws_data[w][st_v] += cnt
        total_proj += cnt
        if st_v in (STATUS_PASSED, STATUS_ACCEPTED):
            done_proj += cnt

    workshops = []
    for w in sorted(ws_data.keys()):
        s = ws_data[w]
        done = s["PASSED"] + s["ACCEPTED"]
        s["percent"] = round(done * 100 / s["TOTAL"], 1) if s["TOTAL"] else 0.0
        workshops.append(s)
    pct_proj = round(done_proj * 100 / total_proj, 1) if total_proj else 0.0
    return {
        "workshops": workshops,
        "total_proj": total_proj,
        "done_proj": done_proj,
        "pct_proj": pct_proj,
    }


@st.cache_data(ttl=120, show_spinner=False)
def all_projects_summary(_db) -> list[dict]:
    """Lấy KPI tóm tắt cho TẤT CẢ dự án — dùng cho multi-project overview."""
    rows = _db.conn.execute(
        """
        SELECT p.id, p.code, p.name, p.location, p.owner,
               c.status, COUNT(c.id) c_count
        FROM projects p
        LEFT JOIN components c ON c.project_id = p.id
        GROUP BY p.id, p.code, p.name, p.location, p.owner, c.status
        ORDER BY p.id
        """
    ).fetchall()
    proj_map: dict[int, dict] = {}
    for r in rows:
        pid = r["id"]
        if pid not in proj_map:
            proj_map[pid] = {
                "pid": pid, "code": r["code"], "name": r["name"],
                "location": r["location"] or "", "owner": r["owner"] or "",
                "total": 0, "accepted": 0, "passed": 0,
                "pending": 0, "in_progress": 0, "failed": 0,
            }
        status = r["status"]
        cnt = r["c_count"] or 0
        if status is None:
            continue
        proj_map[pid]["total"] += cnt
        if status == STATUS_ACCEPTED:
            proj_map[pid]["accepted"] = cnt
        elif status == STATUS_PASSED:
            proj_map[pid]["passed"] = cnt
        elif status == STATUS_PENDING:
            proj_map[pid]["pending"] = cnt
        elif status == STATUS_IN_PROGRESS:
            proj_map[pid]["in_progress"] = cnt
        elif status == STATUS_FAILED:
            proj_map[pid]["failed"] = cnt
    out = []
    for p in proj_map.values():
        done = p["passed"] + p["accepted"]
        p["pct"] = round(done * 100 / p["total"], 1) if p["total"] else 0.0
        p["backlog"] = p["pending"] + p["in_progress"]
        out.append(p)
    return out


@st.cache_data(ttl=60, show_spinner=False)
def workshop_activity(_db, pid: int, workshop: str, limit: int = 10) -> list[dict]:
    """Filter workshop trong SQL — chỉ fetch số dòng cần thiết."""
    if _db.is_postgres:
        ws_extract = "COALESCE(c.data_json::jsonb->>'workshop', '(không xưởng)')"
    else:
        ws_extract = "COALESCE(json_extract(c.data_json, '$.workshop'), '(không xưởng)')"

    rows = _db.conn.execute(
        f"""
        SELECT i.inspection_date, i.imported_at, i.inspection_type, i.result,
               i.inspector, c.code AS comp_code
        FROM inspections i JOIN components c ON i.component_id = c.id
        WHERE i.project_id = ? AND {ws_extract} = ?
        ORDER BY i.id DESC LIMIT ?
        """,
        (pid, workshop, limit),
    ).fetchall()
    return [dict(r) for r in rows]


data = project_workshops(db, active_pid)
workshops = data["workshops"]
total_proj = data["total_proj"]
done_proj = data["done_proj"]
pct_proj = data["pct_proj"]


def pct_color(p: float) -> str:
    if p < 30:  return "#DC2626"
    if p < 50:  return "#EA580C"
    if p < 70:  return "#F59E0B"
    if p < 85:  return "#16A34A"
    return "#0F766E"


# ============================================================
# 0a. GLOBAL SEARCH — tìm cấu kiện xuyên mọi dự án
# ============================================================
from streamlit_qc.services import component_service as _cs

emit('<div class="sec">🔎 Tìm kiếm toàn cục <span class="sub">· gõ mã cấu kiện ≥ 2 ký tự để tìm xuyên dự án</span></div>')

# Trick để clear text_input: dùng counter trong key
# Khi user bấm Xoá → counter +1 → text_input có key mới → reset value
if "search_key_counter" not in st.session_state:
    st.session_state["search_key_counter"] = 0
search_widget_key = f"global_search_input_{st.session_state['search_key_counter']}"

sc1, sc2 = st.columns([5, 1])
with sc1:
    search_query = st.text_input(
        "search_input",
        placeholder="vd: BTG3008, 01USC, VB67, 02BLP1001-001...",
        label_visibility="collapsed",
        key=search_widget_key,
    )
with sc2:
    st.write("")
    if st.button("🧹 Xoá", use_container_width=True):
        # Bump counter → text_input có key mới → tự reset
        st.session_state["search_key_counter"] += 1
        st.rerun()

if search_query and len(search_query.strip()) >= 2:
    with st.spinner("Đang tìm..."):
        results = _cs.global_search(db, search_query.strip(), limit=30)

    if not results:
        st.info(f"Không tìm thấy cấu kiện nào khớp **'{search_query}'**.")
    else:
        emit(f'<div style="margin:4px 0 8px 0;color:#0F1E40;font-weight:600;">Tìm thấy {len(results)} kết quả:</div>')

        # Status badge mapping
        STATUS_BADGE = {
            "ACCEPTED": ("✅ Đã NT", "#0F766E"),
            "PASSED": ("🏆 Đạt", "#16A34A"),
            "IN_PROGRESS": ("🔧 Đã Fit-up", "#D97706"),
            "FAILED": ("⚠️ Không đạt", "#DC2626"),
            "PENDING": ("⏳ Chưa KT", "#94A3B8"),
        }

        # Render kết quả dạng card list
        rows_html = ""
        for r in results:
            label, color = STATUS_BADGE.get(r["status"], (r["status"], "#64748B"))
            rows_html += (
                f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;'
                f'padding:10px 14px;margin-bottom:6px;display:flex;align-items:center;gap:12px;">'
                f'<div style="background:#0F1E40;color:#FCE7A1;padding:3px 8px;border-radius:5px;'
                f'font-size:11px;font-weight:700;min-width:60px;text-align:center;">'
                f'{r["project_code"]}'
                f'</div>'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-weight:700;color:#0F172A;font-size:13px;">{r["code"]}</div>'
                f'<div style="color:#94A3B8;font-size:11px;">'
                f'{r["name"][:50]} · 🏭 {r["workshop"]}'
                f'</div>'
                f'</div>'
                f'<div style="text-align:center;font-size:11px;color:#64748B;">'
                f'<div>Fit-up: <b style="color:#0F172A;">{r["fitup_date"] or "—"}</b></div>'
                f'<div>Final: <b style="color:#0F172A;">{r["final_date"] or "—"}</b></div>'
                f'</div>'
                f'<span style="background:{color}18;color:{color};padding:4px 10px;'
                f'border-radius:6px;font-size:11px;font-weight:700;white-space:nowrap;">'
                f'{label}</span>'
                f'</div>'
            )
        emit(rows_html)

        # Nút action: switch sang project đầu tiên trong kết quả
        unique_pids = list(dict.fromkeys(r["pid"] for r in results))
        if len(unique_pids) >= 1:
            switch_cols = st.columns(min(len(unique_pids), 4))
            for i, target_pid in enumerate(unique_pids[:4]):
                pname = next(r["project_code"] for r in results if r["pid"] == target_pid)
                with switch_cols[i]:
                    if st.button(
                        f"🔀 Sang dự án [{pname}] xem chi tiết",
                        key=f"search_switch_{target_pid}",
                        use_container_width=True,
                    ):
                        from streamlit_qc.core.state import set_current_project_id
                        set_current_project_id(target_pid)
                        st.session_state.pop("selected_workshop", None)
                        # Preset search filter ở page Cấu kiện
                        st.session_state["preset_search_query"] = search_query
                        st.switch_page("pages/4_🔧_Cấu_kiện.py")

    st.divider()

# ============================================================
# 0. TỔNG QUAN ĐA DỰ ÁN — hiện trước hero (nếu > 1 dự án)
# ============================================================
all_projects_data = all_projects_summary(db)
n_total_projects = len(all_projects_data)

if n_total_projects > 1:
    sum_total_all = sum(p["total"] for p in all_projects_data)
    sum_done_all = sum(p["passed"] + p["accepted"] for p in all_projects_data)
    overall_pct = round(sum_done_all * 100 / sum_total_all, 1) if sum_total_all else 0.0

    emit(f"""
<div class="sec">📊 Tổng quan {n_total_projects} dự án
<span class="sub">· tổng {sum_total_all:,} cấu kiện · <b style="color:#0F766E;">{overall_pct}%</b> hoàn thành</span>
</div>
""")

    # Sort theo % giảm dần để dễ thấy dự án nào hot
    projects_sorted = sorted(all_projects_data, key=lambda x: x["pct"], reverse=True)

    # Grid mini-card 5 cột mỗi hàng
    PROJ_PER_ROW = 5
    for row_start in range(0, len(projects_sorted), PROJ_PER_ROW):
        cols = st.columns(PROJ_PER_ROW)
        for i, col in enumerate(cols):
            idx = row_start + i
            if idx >= len(projects_sorted):
                break
            p = projects_sorted[idx]
            with col:
                color = pct_color(p["pct"])
                is_active = (p["pid"] == active_pid)
                active_cls = " active" if is_active else ""
                fail_html = (
                    f'<span style="color:#DC2626;">⚠ {p["failed"]}</span>'
                    if p["failed"] > 0 else ""
                )
                emit(
                    f'<div class="proj-mini{active_cls}">'
                    f'<div class="pm-strip" style="background:{color};"></div>'
                    f'<div class="pm-code">{p["code"]}</div>'
                    f'<div class="pm-name">{p["name"]}</div>'
                    f'<div class="pm-pct" style="color:{color};">{p["pct"]}%</div>'
                    f'<div class="pm-bar"><div class="pm-bar-fill" style="width:{min(p["pct"],100)}%;background:{color};"></div></div>'
                    f'<div class="pm-stats">'
                    f'<span><b>{p["total"]:,}</b> CK</span>'
                    f'<span>✅ <b>{p["accepted"]:,}</b></span>'
                    f'<span>⏳ <b style="color:#D97706;">{p["backlog"]:,}</b></span>'
                    f'{fail_html}'
                    f'</div></div>'
                )
                # Nút switch sang dự án này
                btn_type = "primary" if is_active else "secondary"
                if st.button(
                    "Đang xem" if is_active else "🔀 Chuyển",
                    key=f"switch_proj_{p['pid']}",
                    use_container_width=True,
                    type=btn_type,
                    disabled=is_active,
                ):
                    from streamlit_qc.core.state import set_current_project_id
                    set_current_project_id(p["pid"])
                    # Reset workshop selection vì sang dự án khác
                    st.session_state.pop("selected_workshop", None)
                    st.rerun()

    st.write("")
    st.divider()


# ============================================================
# 1. HERO — 1 dòng compact (dự án ĐANG XEM)
# ============================================================
emit(f"""
<div class="hero">
<div style="flex:1;min-width:0;">
<div class="name">🏗️ {proj['name']}</div>
<div class="meta">Mã: <b>{proj['code']}</b> · {proj.get('location') or '—'} · {proj.get('owner') or '—'} · {len(workshops)} xưởng · {total_proj:,} cấu kiện</div>
</div>
<div style="text-align:right;">
<div class="pct">{pct_proj}%</div>
<div class="ratio">{done_proj:,} / {total_proj:,} đã hoàn thành</div>
</div>
</div>
""")

# ============================================================
# 1.5 CẢNH BÁO OVERDUE — cấu kiện Fit-up > N ngày chưa Final
# ============================================================
from streamlit_qc.services import component_service

# Cấu hình ngưỡng (default 7 ngày, có thể override qua session)
if "overdue_threshold" not in st.session_state:
    st.session_state["overdue_threshold"] = 7
threshold_days = st.session_state["overdue_threshold"]


@st.cache_data(ttl=30, show_spinner=False)
def get_overdue(_db, pid: int, threshold: int) -> list[dict]:
    return component_service.get_overdue_components(_db, pid, threshold)


overdue_list = get_overdue(db, active_pid, threshold_days)
n_overdue = len(overdue_list)

if n_overdue > 0:
    # Box cảnh báo đỏ nếu có overdue
    top3 = overdue_list[:3]
    top3_html = ""
    for o in top3:
        top3_html += (
            f'<div style="display:inline-block;background:#fff;border:1px solid #fecaca;'
            f'border-radius:6px;padding:4px 10px;margin-right:6px;margin-bottom:4px;'
            f'font-size:11px;color:#991b1b;">'
            f'<b>{o["code"]}</b> · {o["workshop"]} · '
            f'<span style="color:#DC2626;font-weight:700;">{o["days_overdue"]} ngày</span>'
            f'</div>'
        )

    emit(f"""
<div style="background:#fef2f2;border:1px solid #fecaca;border-left:5px solid #DC2626;
            border-radius:10px;padding:14px 18px;margin:14px 0;
            display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
<div style="flex:1;min-width:280px;">
<div style="font-size:12px;color:#991b1b;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">
⚠ Cảnh báo: Cấu kiện đã Fit-up quá hạn chưa Final
</div>
<div style="font-size:28px;font-weight:800;color:#DC2626;line-height:1;margin-top:4px;">
{n_overdue:,} <span style="font-size:14px;font-weight:500;color:#7f1d1d;">cấu kiện (Fit-up &gt; {threshold_days} ngày)</span>
</div>
<div style="margin-top:8px;">{top3_html}</div>
</div>
</div>
""")
    btn_col1, btn_col2, _ = st.columns([2, 2, 4])
    with btn_col1:
        if st.button(f"🔧 Xem danh sách {n_overdue} cấu kiện overdue",
                     key="goto_overdue", type="primary", use_container_width=True):
            st.session_state["preset_overdue_filter"] = True
            st.switch_page("pages/4_🔧_Cấu_kiện.py")
    with btn_col2:
        new_threshold = st.number_input(
            "Đổi ngưỡng (ngày)", min_value=1, max_value=90,
            value=threshold_days, key="overdue_threshold_input",
            help="Số ngày sau Fit-up coi là overdue. Mặc định 7.",
        )
        if new_threshold != threshold_days:
            st.session_state["overdue_threshold"] = int(new_threshold)
            get_overdue.clear()
            st.rerun()

# ============================================================
# 2. WORKSHOP GRID — MINIMAL
# ============================================================
if not workshops:
    st.info("Dự án này chưa có dữ liệu xưởng. Hãy import Master trước.")
    st.stop()

emit('<div class="sec">🏭 Xưởng <span class="sub">· click vào card để xem chi tiết</span></div>')

workshops_sorted = sorted(workshops, key=lambda x: x["percent"], reverse=True)

if "selected_workshop" not in st.session_state:
    st.session_state["selected_workshop"] = workshops_sorted[0]["workshop"]
selected_ws = st.session_state["selected_workshop"]

# Grid: 5 cột mỗi hàng
n_per_row = 5
for row_start in range(0, len(workshops_sorted), n_per_row):
    cols = st.columns(n_per_row)
    for i, col in enumerate(cols):
        idx = row_start + i
        if idx >= len(workshops_sorted):
            break
        w = workshops_sorted[idx]
        with col:
            color = pct_color(w["percent"])
            active_cls = " active" if w["workshop"] == selected_ws else ""
            emit(
                f'<div class="ws{active_cls}">'
                f'<div class="row">'
                f'<div class="nm">{w["workshop"]}</div>'
                f'<div class="pc" style="color:{color};">{w["percent"]}%</div>'
                f'</div>'
                f'<div class="bar"><div class="fill" style="width:{min(w["percent"],100)}%;background:{color};"></div></div>'
                f'<div class="tot">{w["TOTAL"]:,} cấu kiện</div>'
                f'</div>'
            )
            # Nút ghost với label rút gọn
            if st.button(
                f"Chọn",
                key=f"ws_{w['workshop']}",
                use_container_width=True,
                type=("primary" if w["workshop"] == selected_ws else "secondary"),
            ):
                st.session_state["selected_workshop"] = w["workshop"]
                st.rerun()

# ============================================================
# 3. WORKSHOP DETAIL PANEL — chỉ donut + activity + action
# ============================================================
selected = next((w for w in workshops_sorted if w["workshop"] == selected_ws), None)
if selected:
    color_sel = pct_color(selected["percent"])
    bk = selected["PENDING"] + selected["IN_PROGRESS"]
    nt = selected["ACCEPTED"]
    fail = selected["FAILED"]

    emit(f"""
<div class="panel">
<div class="panel-head">
<div>
<div class="nm">🏭 {selected['workshop']}</div>
<div class="sub">{selected['TOTAL']:,} cấu kiện trong xưởng này</div>
</div>
<div style="text-align:right;">
<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.8px;">% Hoàn thành</div>
<div class="pct" style="color:{color_sel};">{selected['percent']}%</div>
</div>
</div>
</div>
""")

    # 2 cột: Donut | Activity
    dcol1, dcol2 = st.columns([1, 2], gap="medium")

    with dcol1:
        # Donut compact
        pie_df = pd.DataFrame([
            {"label": "Đã NT",      "value": selected["ACCEPTED"],    "color": "#0F766E"},
            {"label": "Đã Fit-up",  "value": selected["IN_PROGRESS"], "color": "#D97706"},
            {"label": "Chưa KT",    "value": selected["PENDING"],     "color": "#94A3B8"},
            {"label": "Đạt lẻ",     "value": selected["PASSED"],      "color": "#16A34A"},
            {"label": "Không đạt",  "value": selected["FAILED"],      "color": "#DC2626"},
        ])
        pie_df = pie_df[pie_df["value"] > 0]
        if not pie_df.empty:
            fig = go.Figure(go.Pie(
                labels=pie_df["label"], values=pie_df["value"],
                marker=dict(colors=pie_df["color"].tolist(), line=dict(color="#fff", width=2)),
                hole=0.6, textposition="outside", textinfo="percent+label",
                textfont=dict(size=10, color="#0F172A"),
            ))
            fig.update_layout(
                showlegend=False, height=260,
                margin=dict(l=8, r=8, t=8, b=8),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                annotations=[dict(
                    text=f"<b>{selected['percent']}%</b><br>"
                         f"<span style='font-size:10px;color:#64748B;'>hoàn thành</span>",
                    x=0.5, y=0.5, showarrow=False, font=dict(size=20, color="#0F1E40"),
                )],
            )
            st.plotly_chart(fig, use_container_width=True)

    with dcol2:
        emit(f'<div style="font-size:13px;font-weight:600;color:#0F1E40;margin-bottom:8px;">🕒 Hoạt động gần nhất ở {selected["workshop"]}</div>')
        acts = workshop_activity(db, active_pid, selected["workshop"], limit=8)
        if acts:
            rows_html = ""
            for a in acts:
                res = (a.get("result") or "").upper()
                res_cls = "res-pass" if res == "PASS" else ("res-fail" if res == "FAIL" else "res-rec")
                res_label = {"PASS": "✓ Đạt", "FAIL": "✗ Fail", "RECHECK": "↻ Recheck"}.get(res, res or "—")
                t = a.get("inspection_type", "—")
                t_show = "Fit-up" if t == "FUR" else ("Final" if t == "DGRP" else t)
                inspector = a.get("inspector") or "—"
                d = a.get("inspection_date") or a.get("imported_at") or ""
                d10 = d[:10] if d else "—"
                try:
                    d_show = dt.date.fromisoformat(d10).strftime("%d/%m") if d10 != "—" else "—"
                except Exception:
                    d_show = d10
                rows_html += (
                    f'<div class="act-row">'
                    f'<span class="typ">{t_show}</span>'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="font-weight:600;color:#0F172A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{a["comp_code"]}</div>'
                    f'<div style="color:#94A3B8;font-size:10px;">{inspector} · {d_show}</div>'
                    f'</div>'
                    f'<span class="res {res_cls}">{res_label}</span>'
                    f'</div>'
                )
            emit(f'<div class="act-feed">{rows_html}</div>')
        else:
            st.info(f"Xưởng {selected['workshop']} chưa có inspection nào.")

    # Nút action ở đáy detail
    st.write("")
    ba1, ba2, _ = st.columns([2, 2, 4])
    with ba1:
        if st.button(f"🔧 Xem cấu kiện {selected['workshop']}",
                     key="goto_comp", use_container_width=True, type="primary"):
            st.session_state["flt_workshop"] = selected["workshop"]
            st.switch_page("pages/4_🔧_Cấu_kiện.py")
    with ba2:
        if st.button("📊 Chart tổng quan dự án",
                     key="goto_dash", use_container_width=True):
            st.switch_page("pages/1_📊_Tổng_quan.py")

st.write("")

# ============================================================
# 4. NAV TILES — minimal
# ============================================================
emit('<div class="sec">📍 Điều hướng</div>')
actions = [
    ("📊", "Tổng quan", "pages/1_📊_Tổng_quan.py"),
    ("📥", "Import Master", "pages/2_📥_Import_Master.py"),
    ("📤", "Import Daily", "pages/3_📤_Import_Daily.py"),
    ("🔧", "Cấu kiện", "pages/4_🔧_Cấu_kiện.py"),
    ("📈", "Báo cáo", "pages/5_📈_Báo_cáo.py"),
    ("⚙️", "Quản trị", "pages/6_⚙_Quản_trị.py"),
]
cols = st.columns(6)
for i, (icon, title, page) in enumerate(actions):
    with cols[i]:
        emit(
            f'<div class="nav">'
            f'<div class="ic">{icon}</div>'
            f'<div class="lbl">{title}</div>'
            f'</div>'
        )
        if st.button("Mở", key=f"nav_{i}", use_container_width=True):
            st.switch_page(page)

from streamlit_qc.core.constants import APP_VERSION as _AV, COMPANY as _CO
emit(
    f'<div style="text-align:center;color:#94A3B8;font-size:11px;padding-top:18px;margin-top:18px;'
    f'border-top:1px solid #E2E8F0;">QC Component Manager v{_AV} · © 2026 {_CO}</div>'
)
