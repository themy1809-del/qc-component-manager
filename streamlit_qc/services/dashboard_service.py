# -*- coding: utf-8 -*-
"""
Service: tính toán số liệu cho Dashboard (Tổng quan).

Tách logic query/aggregate khỏi UI (page) để dễ test và tái sử dụng.

Tương ứng với hàm `_refresh_dashboard` trong Tkinter v1.0.2 dòng 1261-1331.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from streamlit_qc.core.constants import ALL_STATUSES
from streamlit_qc.core.db import DB


@dataclass
class DashboardData:
    """Tất cả số liệu cần thiết cho page Tổng quan."""

    counts: dict[str, int] = field(default_factory=dict)
    """{status: count, 'TOTAL': N}, đã áp filter xưởng nếu có."""

    workshop_stats: list[dict] = field(default_factory=list)
    """Bảng thống kê theo xưởng. Mỗi item: {workshop, TOTAL, PENDING, ..., percent}."""

    workshop_list: list[str] = field(default_factory=list)
    """Danh sách unique xưởng để hiện dropdown filter."""

    recent_inspections: list[dict] = field(default_factory=list)
    """Top 200 inspection mới nhất (đã áp filter)."""


def get_workshop_list(db: DB, pid: int) -> list[str]:
    """Trả về danh sách xưởng unique có trong dự án, sorted."""
    ws_set: set[str] = set()
    for r in db.conn.execute(
        "SELECT data_json FROM components WHERE project_id=?",
        (pid,),
    ):
        d = json.loads(r["data_json"])
        w = d.get("workshop")
        if w:
            ws_set.add(str(w))
    return sorted(ws_set)


def compute_dashboard(
    db: DB,
    pid: int,
    workshop_filter: str | None = None,
) -> DashboardData:
    """
    Tính toàn bộ số liệu dashboard.

    Args:
        db: DB instance.
        pid: ID dự án hiện tại.
        workshop_filter: Tên xưởng cụ thể, None = tất cả xưởng.

    Returns:
        DashboardData với 4 phần dữ liệu.
    """
    data = DashboardData()
    data.workshop_list = get_workshop_list(db, pid)

    # ----- 1. Đếm theo status (có filter xưởng) -----
    counts: dict[str, int] = {s: 0 for s in ALL_STATUSES}
    counts["TOTAL"] = 0
    ids_in_filter: set[int] = set()

    for r in db.conn.execute(
        "SELECT id, status, data_json FROM components WHERE project_id=?",
        (pid,),
    ):
        if workshop_filter:
            d = json.loads(r["data_json"])
            if str(d.get("workshop", "")) != workshop_filter:
                continue
        ids_in_filter.add(r["id"])
        status = r["status"]
        counts[status] = counts.get(status, 0) + 1
        counts["TOTAL"] += 1
    data.counts = counts

    # ----- 2. Bảng thống kê theo xưởng (KHÔNG áp filter để xem toàn cảnh) -----
    ws_stats: dict[str, dict[str, int]] = {}
    for r in db.conn.execute(
        "SELECT status, data_json FROM components WHERE project_id=?",
        (pid,),
    ):
        d = json.loads(r["data_json"])
        w = str(d.get("workshop") or "(không xưởng)")
        if w not in ws_stats:
            ws_stats[w] = {s: 0 for s in ALL_STATUSES}
            ws_stats[w]["TOTAL"] = 0
        ws_stats[w]["TOTAL"] += 1
        ws_stats[w][r["status"]] = ws_stats[w].get(r["status"], 0) + 1

    rows = []
    for w in sorted(ws_stats.keys()):
        s = ws_stats[w]
        done = s.get("PASSED", 0) + s.get("ACCEPTED", 0)
        total = s.get("TOTAL", 0)
        pct = round(done * 100 / total, 1) if total else 0.0
        rows.append({
            "workshop": w,
            "TOTAL": total,
            "PENDING": s.get("PENDING", 0),
            "IN_PROGRESS": s.get("IN_PROGRESS", 0),
            "PASSED": s.get("PASSED", 0),
            "FAILED": s.get("FAILED", 0),
            "ACCEPTED": s.get("ACCEPTED", 0),
            "percent": pct,
        })
    data.workshop_stats = rows

    # ----- 3. Lịch sử kiểm tra gần nhất (200 dòng) -----
    if workshop_filter:
        ins_rows = db.recent_inspections(pid, component_ids=ids_in_filter, limit=200)
    else:
        ins_rows = db.recent_inspections(pid, limit=200)
    data.recent_inspections = [
        {
            "date": r["d"],
            "code": r["code"],
            "type": r["t"],
            "result": r["r"],
            "inspector": r["ins"],
            "report": r["rep"],
        }
        for r in ins_rows
    ]

    return data
