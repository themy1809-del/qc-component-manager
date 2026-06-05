# -*- coding: utf-8 -*-
"""
Service: Visitor tracking — ghi log mỗi lần truy cập + thống kê.

Ghi nhận: timestamp, session_id, IP (nếu có header), user_agent, page name.
Dùng cho thống kê có bao nhiêu máy/người vào app, page nào hot, lúc nào peak.

Fail-safe: nếu DB lỗi, không raise — không ảnh hưởng nghiệp vụ.
"""
from __future__ import annotations

import secrets
import streamlit as st

from streamlit_qc.core.db import DB


SESSION_KEY = "_access_session_id"
LAST_PAGE_KEY = "_access_last_page"


def _get_session_id() -> str:
    """Sinh session_id ngẫu nhiên 1 lần / session Streamlit."""
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = secrets.token_hex(8)
    return st.session_state[SESSION_KEY]


def _get_request_info() -> tuple[str, str]:
    """
    Trả về (ip, user_agent) từ Streamlit context headers (nếu có).
    Trên Streamlit Cloud có header X-Forwarded-For.
    """
    ip = ""
    ua = ""
    try:
        headers = dict(st.context.headers)
        # Try X-Forwarded-For (cloud) → first IP
        xff = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for")
        if xff:
            ip = xff.split(",")[0].strip()
        # Fallback: Real-IP
        if not ip:
            ip = headers.get("X-Real-Ip") or headers.get("x-real-ip") or ""
        ua = headers.get("User-Agent") or headers.get("user-agent") or ""
    except Exception:
        pass
    return ip[:100], ua[:500]


def _get_current_page() -> str:
    """Tên page hiện tại từ URL hoặc script name."""
    try:
        # Streamlit > 1.30 has st.runtime tools, but simpler:
        import inspect
        # Use frame inspection — fallback
        page = "home"
        # try filename from session
    except Exception:
        page = "unknown"
    # Better: just return from session_state if pages set it
    return st.session_state.get("_current_page_name", "home")


def track_visit(db: DB, page_name: str | None = None) -> None:
    """
    Ghi 1 visit. Dedup theo (session, page, giờ) để giảm spam.

    BUG FIX 2026-05: dedup cũ chỉ check (session, page) → mỗi page chỉ log
    1 lần trong cả session → user truy cập lại sau vài giờ KHÔNG được ghi.
    Giờ dedup theo (page, hour) → mỗi giờ 1 lần / page.
    Errors được lưu vào session_state["_access_last_error"] để debug.
    """
    import time
    try:
        session_id = _get_session_id()
        page = page_name or _get_current_page()

        hour_bucket = int(time.time() // 3600)
        dedup_key = f"{page}_{hour_bucket}"
        last_key = st.session_state.get(LAST_PAGE_KEY)
        if last_key == dedup_key:
            return
        st.session_state[LAST_PAGE_KEY] = dedup_key

        ip, ua = _get_request_info()
        db.conn.execute(
            "INSERT INTO access_log (session_id, ip_address, user_agent, page_name) "
            "VALUES (?, ?, ?, ?)",
            (session_id, ip, ua, page),
        )
        db.conn.commit()
    except Exception as e:
        try:
            st.session_state["_access_last_error"] = f"{type(e).__name__}: {e}"
        except Exception:
            pass


def force_test_log(db: DB) -> tuple[bool, str]:
    """
    Ghi 1 record test (bypass dedup) để verify hệ thống logging có hoạt động.
    Trả về (success, message).
    """
    try:
        session_id = _get_session_id()
        ip, ua = _get_request_info()
        db.conn.execute(
            "INSERT INTO access_log (session_id, ip_address, user_agent, page_name) "
            "VALUES (?, ?, ?, ?)",
            (session_id, ip or "test", ua or "test-agent", "__TEST__"),
        )
        db.conn.commit()
        cnt = db.conn.execute("SELECT COUNT(*) c FROM access_log").fetchone()
        total = cnt["c"] if cnt else 0
        return True, f"OK — đã ghi 1 record. Tổng pageviews: {total}"
    except Exception as e:
        return False, f"LỖI: {type(e).__name__}: {e}"


def get_last_error() -> str | None:
    """Lấy error gần nhất khi track_visit gặp lỗi."""
    return st.session_state.get("_access_last_error")


def get_stats_summary(db: DB) -> dict:
    """
    Trả về dict với:
    - total_sessions (toàn thời gian)
    - sessions_today
    - sessions_7d
    - total_page_views
    """
    if db.is_postgres:
        today_expr = "ts::date = CURRENT_DATE"
        week_expr = "ts::date >= CURRENT_DATE - INTERVAL '7 days'"
    else:
        today_expr = "date(ts) = date('now')"
        week_expr = "date(ts) >= date('now', '-7 days')"

    try:
        row1 = db.conn.execute(
            "SELECT COUNT(DISTINCT session_id) c FROM access_log"
        ).fetchone()
        row2 = db.conn.execute(
            f"SELECT COUNT(DISTINCT session_id) c FROM access_log WHERE {today_expr}"
        ).fetchone()
        row3 = db.conn.execute(
            f"SELECT COUNT(DISTINCT session_id) c FROM access_log WHERE {week_expr}"
        ).fetchone()
        row4 = db.conn.execute(
            "SELECT COUNT(*) c FROM access_log"
        ).fetchone()
        return {
            "total_sessions": row1["c"] if row1 else 0,
            "sessions_today": row2["c"] if row2 else 0,
            "sessions_7d": row3["c"] if row3 else 0,
            "total_page_views": row4["c"] if row4 else 0,
        }
    except Exception:
        return {"total_sessions": 0, "sessions_today": 0,
                "sessions_7d": 0, "total_page_views": 0}


def get_daily_visits(db: DB, days: int = 14) -> list[dict]:
    """Trả về visits per day cho N ngày gần nhất."""
    if db.is_postgres:
        date_expr = "ts::date"
        cutoff = f"ts::date >= CURRENT_DATE - INTERVAL '{days} days'"
    else:
        date_expr = "date(ts)"
        cutoff = f"date(ts) >= date('now', '-{days} days')"

    try:
        rows = db.conn.execute(
            f"""SELECT {date_expr} AS d,
                       COUNT(DISTINCT session_id) AS sessions,
                       COUNT(*) AS page_views
                FROM access_log
                WHERE {cutoff}
                GROUP BY d
                ORDER BY d ASC"""
        ).fetchall()
        return [{"date": str(r["d"]), "sessions": r["sessions"],
                 "page_views": r["page_views"]} for r in rows]
    except Exception:
        return []


def get_top_pages(db: DB, days: int = 7, limit: int = 10) -> list[dict]:
    """Top pages được xem nhiều nhất trong N ngày."""
    if db.is_postgres:
        cutoff = f"ts::date >= CURRENT_DATE - INTERVAL '{days} days'"
    else:
        cutoff = f"date(ts) >= date('now', '-{days} days')"

    try:
        rows = db.conn.execute(
            f"""SELECT page_name, COUNT(*) c
                FROM access_log
                WHERE {cutoff} AND page_name IS NOT NULL AND page_name != ''
                GROUP BY page_name
                ORDER BY c DESC
                LIMIT {limit}"""
        ).fetchall()
        return [{"page": r["page_name"], "views": r["c"]} for r in rows]
    except Exception:
        return []


def get_recent_visitors(db: DB, limit: int = 50) -> list[dict]:
    """Recent visitors — distinct sessions với last_seen, page_views, ip, ua."""
    try:
        rows = db.conn.execute(
            f"""SELECT session_id,
                       MAX(ts) AS last_seen,
                       MIN(ts) AS first_seen,
                       COUNT(*) AS page_views,
                       MAX(ip_address) AS ip,
                       MAX(user_agent) AS ua
                FROM access_log
                GROUP BY session_id
                ORDER BY last_seen DESC
                LIMIT {limit}"""
        ).fetchall()
        return [{
            "session_id": r["session_id"][:12] if r["session_id"] else "",
            "last_seen": str(r["last_seen"])[:19],
            "first_seen": str(r["first_seen"])[:19],
            "page_views": r["page_views"],
            "ip": r["ip"] or "—",
            "ua": (r["ua"] or "")[:80],
        } for r in rows]
    except Exception:
        return []


def set_current_page(page: str) -> None:
    """Helper: pages call this đầu file để set page name."""
    st.session_state["_current_page_name"] = page
