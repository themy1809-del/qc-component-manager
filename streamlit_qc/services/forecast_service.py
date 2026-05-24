# -*- coding: utf-8 -*-
"""
Service: dự báo tiến độ (velocity + ETA) và S-curve.

Công thức:
  - velocity (CK/tuần) = số inspection DGRP PASS trong 4 tuần gần / 4
  - eta_days = (total - done) / (velocity / 7)
  - S-curve = cumulative % ACCEPTED theo ngày

Dùng cho Dashboard P2.8.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from streamlit_qc.core.db import DB


@dataclass
class ForecastData:
    total_components: int = 0
    done_components: int = 0
    progress_pct: float = 0.0
    velocity_per_week: float = 0.0       # CK/tuần (trung bình 4 tuần qua)
    velocity_per_day: float = 0.0
    eta_days: int | None = None          # số ngày dự kiến hoàn thành (None nếu velocity=0)
    eta_date: str = ""                   # YYYY-MM-DD
    avg_lead_time_days: float | None = None  # trung bình từ FUR → DGRP


def get_forecast(db: DB, pid: int) -> ForecastData:
    """Tính velocity + ETA dựa trên dữ liệu thực tế 4 tuần qua."""
    result = ForecastData()

    # Total components
    row = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,),
    ).fetchone()
    result.total_components = row["c"] if row else 0

    # Done = ACCEPTED
    row = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=? AND status='ACCEPTED'",
        (pid,),
    ).fetchone()
    result.done_components = row["c"] if row else 0

    if result.total_components > 0:
        result.progress_pct = result.done_components * 100 / result.total_components

    # Velocity: DGRP PASS inspection trong 28 ngày qua
    if db.is_postgres:
        cutoff_sql = (
            "AND inspection_date IS NOT NULL AND inspection_date != '' "
            "AND inspection_date::date >= CURRENT_DATE - INTERVAL '28 days'"
        )
    else:
        cutoff_sql = (
            "AND inspection_date IS NOT NULL AND inspection_date != '' "
            "AND date(inspection_date) >= date('now', '-28 days')"
        )
    row = db.conn.execute(
        f"SELECT COUNT(*) c FROM inspections "
        f"WHERE project_id=? AND inspection_type='DGRP' AND result='PASS' {cutoff_sql}",
        (pid,),
    ).fetchone()
    done_4w = row["c"] if row else 0
    result.velocity_per_week = done_4w / 4
    result.velocity_per_day = done_4w / 28

    # ETA
    remaining = result.total_components - result.done_components
    if result.velocity_per_day > 0 and remaining > 0:
        eta_days = int(remaining / result.velocity_per_day)
        result.eta_days = eta_days
        result.eta_date = (dt.date.today() + dt.timedelta(days=eta_days)).isoformat()
    elif remaining == 0:
        result.eta_days = 0
        result.eta_date = dt.date.today().isoformat()

    # Lead time: trung bình ngày FUR PASS → DGRP PASS cho cấu kiện đã ACCEPTED
    rows = db.conn.execute(
        """
        SELECT c.id,
               MIN(CASE WHEN i.inspection_type='FUR' AND i.result='PASS'
                        THEN i.inspection_date END) AS fur_d,
               MIN(CASE WHEN i.inspection_type='DGRP' AND i.result='PASS'
                        THEN i.inspection_date END) AS dgrp_d
        FROM components c
        JOIN inspections i ON i.component_id = c.id
        WHERE c.project_id=? AND c.status='ACCEPTED'
        GROUP BY c.id
        """,
        (pid,),
    ).fetchall()
    deltas = []
    for r in rows:
        f = r["fur_d"] or ""
        d = r["dgrp_d"] or ""
        if len(f) >= 10 and len(d) >= 10:
            try:
                df = dt.date.fromisoformat(f[:10])
                dd = dt.date.fromisoformat(d[:10])
                delta = (dd - df).days
                if 0 <= delta < 365:
                    deltas.append(delta)
            except ValueError:
                continue
    if deltas:
        result.avg_lead_time_days = sum(deltas) / len(deltas)

    return result


def get_scurve(db: DB, pid: int, days: int = 90) -> list[dict]:
    """
    Tính S-curve: cumulative % ACCEPTED theo ngày trong N ngày qua.

    Trả về list of {date, cumulative, cum_pct} sorted ASC by date.
    """
    total_row = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,),
    ).fetchone()
    total = total_row["c"] if total_row else 0
    if total == 0:
        return []

    if db.is_postgres:
        date_expr = "i.inspection_date::date"
        cutoff = f"i.inspection_date::date >= CURRENT_DATE - INTERVAL '{days} days'"
    else:
        date_expr = "date(i.inspection_date)"
        cutoff = f"date(i.inspection_date) >= date('now', '-{days} days')"

    rows = db.conn.execute(
        f"""
        SELECT {date_expr} AS d, COUNT(DISTINCT c.id) AS n
        FROM inspections i
        JOIN components c ON c.id = i.component_id
        WHERE c.project_id=? AND i.inspection_type='DGRP' AND i.result='PASS'
          AND i.inspection_date IS NOT NULL AND i.inspection_date != ''
          AND {cutoff}
        GROUP BY d ORDER BY d ASC
        """,
        (pid,),
    ).fetchall()

    # Already-done (before window)
    rows_before = db.conn.execute(
        f"""
        SELECT COUNT(DISTINCT c.id) n
        FROM inspections i
        JOIN components c ON c.id = i.component_id
        WHERE c.project_id=? AND i.inspection_type='DGRP' AND i.result='PASS'
          AND i.inspection_date IS NOT NULL AND i.inspection_date != ''
          AND NOT ({cutoff})
        """,
        (pid,),
    ).fetchone()
    base = rows_before["n"] if rows_before else 0

    cumulative = base
    out = []
    for r in rows:
        cumulative += r["n"]
        out.append({
            "date": str(r["d"]),
            "cumulative": cumulative,
            "cum_pct": round(cumulative * 100 / total, 2),
        })
    return out
