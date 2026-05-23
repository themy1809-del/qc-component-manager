# -*- coding: utf-8 -*-
"""
Service: báo cáo + xuất Excel + chart tiến độ.

Tương đương `_export_report` trong Tkinter (dòng 1409-1429) + bổ sung chart.
"""
from __future__ import annotations

import datetime as dt
import io
import json
from dataclasses import dataclass, field

import pandas as pd

from streamlit_qc.core.db import DB


@dataclass
class WeeklyProgress:
    """Tiến độ theo tuần."""
    week_start: str            # ISO date (Monday)
    week_label: str            # vd "T20 (12-18/05)"
    inspections: int           # số inspection trong tuần
    components_inspected: int  # số cấu kiện unique được inspect
    cumulative: int = 0        # số inspection cộng dồn


@dataclass
class ReportData:
    """Tất cả số liệu cho page Báo cáo."""
    # Số liệu tổng quan trong range
    total_components: int = 0
    total_inspections: int = 0
    accepted: int = 0
    passed: int = 0
    failed: int = 0

    # Theo tuần
    weekly: list[WeeklyProgress] = field(default_factory=list)

    # Theo NT type
    by_type: dict[str, int] = field(default_factory=dict)

    # Top xưởng theo % hoàn thành
    workshop_progress: list[dict] = field(default_factory=list)

    # Theo người kiểm tra
    by_inspector: list[dict] = field(default_factory=list)


def get_inspection_date_range(db: DB, pid: int) -> tuple[dt.date | None, dt.date | None]:
    """Trả về (min_date, max_date) của tất cả inspection trong dự án."""
    row = db.conn.execute(
        "SELECT MIN(inspection_date) mn, MAX(inspection_date) mx "
        "FROM inspections WHERE project_id=? AND inspection_date IS NOT NULL",
        (pid,),
    ).fetchone()
    if not row or not row["mn"]:
        return None, None
    try:
        mn = dt.date.fromisoformat(row["mn"][:10])
        mx = dt.date.fromisoformat(row["mx"][:10])
        return mn, mx
    except ValueError:
        return None, None


def compute_report(
    db: DB,
    pid: int,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> ReportData:
    """
    Tính số liệu báo cáo trong khoảng date.

    Args:
        date_from, date_to: nếu None = không lọc.
    """
    data = ReportData()

    # ---- Components total (luôn lấy hết, không lọc theo ngày) ----
    data.total_components = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,)
    ).fetchone()["c"]

    # ---- Inspection query với date filter ----
    sql = (
        "SELECT i.*, c.code comp_code, c.data_json comp_data "
        "FROM inspections i JOIN components c ON c.id=i.component_id "
        "WHERE i.project_id=?"
    )
    params: list = [pid]
    if date_from:
        sql += " AND i.inspection_date >= ?"
        params.append(date_from.isoformat())
    if date_to:
        sql += " AND i.inspection_date <= ?"
        params.append(date_to.isoformat())
    sql += " ORDER BY i.inspection_date ASC, i.id ASC"

    rows = db.conn.execute(sql, params).fetchall()
    data.total_inspections = len(rows)

    # ---- Components: status counts (không theo range) ----
    for r in db.conn.execute(
        "SELECT status, COUNT(*) c FROM components WHERE project_id=? GROUP BY status",
        (pid,),
    ).fetchall():
        if r["status"] == "ACCEPTED":
            data.accepted = r["c"]
        elif r["status"] == "PASSED":
            data.passed = r["c"]
        elif r["status"] == "FAILED":
            data.failed = r["c"]

    # ---- Aggregate theo tuần + theo NT type + theo inspector ----
    weekly_map: dict[dt.date, dict] = {}
    type_map: dict[str, int] = {}
    inspector_map: dict[str, dict] = {}
    workshop_inspected: dict[str, set[int]] = {}

    for r in rows:
        # Parse date
        try:
            d = dt.date.fromisoformat(r["inspection_date"][:10])
        except (ValueError, TypeError):
            continue

        # Weekly
        # ISO week: Monday-based
        monday = d - dt.timedelta(days=d.weekday())
        if monday not in weekly_map:
            weekly_map[monday] = {"inspections": 0, "components": set()}
        weekly_map[monday]["inspections"] += 1
        weekly_map[monday]["components"].add(r["component_id"])

        # By type
        t = r["inspection_type"]
        type_map[t] = type_map.get(t, 0) + 1

        # By inspector
        ins = (r["inspector"] or "(không rõ)").strip()
        if ins not in inspector_map:
            inspector_map[ins] = {"inspections": 0, "components": set()}
        inspector_map[ins]["inspections"] += 1
        inspector_map[ins]["components"].add(r["component_id"])

        # Workshop inspected
        try:
            comp_data = json.loads(r["comp_data"])
            ws = str(comp_data.get("workshop") or "(không xưởng)")
        except (json.JSONDecodeError, TypeError):
            ws = "(không xưởng)"
        if ws not in workshop_inspected:
            workshop_inspected[ws] = set()
        workshop_inspected[ws].add(r["component_id"])

    # Sort weekly và tính cumulative
    cumulative = 0
    for monday in sorted(weekly_map.keys()):
        w = weekly_map[monday]
        cumulative += w["inspections"]
        sunday = monday + dt.timedelta(days=6)
        # Tuần ISO
        iso_week = monday.isocalendar().week
        data.weekly.append(WeeklyProgress(
            week_start=monday.isoformat(),
            week_label=f"T{iso_week} ({monday.day:02d}-{sunday.day:02d}/{monday.month:02d})",
            inspections=w["inspections"],
            components_inspected=len(w["components"]),
            cumulative=cumulative,
        ))

    data.by_type = dict(sorted(type_map.items(), key=lambda x: -x[1]))

    data.by_inspector = sorted(
        [
            {
                "inspector": ins,
                "inspections": v["inspections"],
                "components": len(v["components"]),
            }
            for ins, v in inspector_map.items()
        ],
        key=lambda x: -x["inspections"],
    )

    # Workshop progress: cần tổng cấu kiện mỗi xưởng + số đã inspect
    ws_total: dict[str, int] = {}
    for r in db.conn.execute(
        "SELECT data_json FROM components WHERE project_id=?", (pid,)
    ):
        try:
            d = json.loads(r["data_json"])
            ws = str(d.get("workshop") or "(không xưởng)")
            ws_total[ws] = ws_total.get(ws, 0) + 1
        except json.JSONDecodeError:
            pass

    rows_ws = []
    for ws, total in sorted(ws_total.items()):
        inspected = len(workshop_inspected.get(ws, set()))
        pct = round(inspected * 100 / total, 1) if total else 0.0
        rows_ws.append({
            "workshop": ws,
            "total": total,
            "inspected_in_range": inspected,
            "percent_in_range": pct,
        })
    data.workshop_progress = sorted(rows_ws, key=lambda x: -x["percent_in_range"])

    return data


def export_to_excel(db: DB, pid: int, project_code: str) -> bytes:
    """
    Xuất báo cáo ra file Excel 3 sheet: Components / Inspections / Summary.

    Returns:
        Bytes của file Excel (để dùng với st.download_button).
    """
    # Sheet 1: Components (tất cả 24 trường + status + audit fields)
    comp_rows = db.conn.execute(
        "SELECT id, code, status, data_json FROM components WHERE project_id=?",
        (pid,),
    ).fetchall()
    comp_records = []
    for r in comp_rows:
        try:
            d = json.loads(r["data_json"])
        except json.JSONDecodeError:
            d = {}
        d["__id"] = r["id"]
        d["__code"] = r["code"]
        d["__status"] = r["status"]
        comp_records.append(d)
    df_comp = pd.DataFrame(comp_records)
    # Đưa __code, __status lên đầu
    if "__code" in df_comp.columns:
        cols = ["__code", "__status"] + [c for c in df_comp.columns if c not in ("__code", "__status", "__id")]
        df_comp = df_comp[cols]

    # Sheet 2: Inspections (raw)
    df_ins = pd.read_sql_query(
        "SELECT i.*, c.code component_code "
        "FROM inspections i JOIN components c ON c.id=i.component_id "
        "WHERE i.project_id=? "
        "ORDER BY i.inspection_date DESC, i.id DESC",
        db.conn,
        params=[pid],
    )

    # Sheet 3: Summary (status counts)
    status_counts = db.count_status(pid)
    df_sum = pd.DataFrame([{
        "Mã dự án": project_code,
        "Tổng cấu kiện": status_counts.get("TOTAL", 0),
        "Chưa KT (PENDING)": status_counts.get("PENDING", 0),
        "Đang KT (IN_PROGRESS)": status_counts.get("IN_PROGRESS", 0),
        "Đạt (PASSED)": status_counts.get("PASSED", 0),
        "Không đạt (FAILED)": status_counts.get("FAILED", 0),
        "Đã nghiệm thu (ACCEPTED)": status_counts.get("ACCEPTED", 0),
        "Tổng inspection records": len(df_ins),
        "Ngày xuất": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }])

    # Sheet 4: Inspection by type (thêm để báo cáo nghiệp vụ)
    by_type = pd.read_sql_query(
        "SELECT inspection_type 'Loại NT', COUNT(*) 'Số inspection' "
        "FROM inspections WHERE project_id=? "
        "GROUP BY inspection_type ORDER BY COUNT(*) DESC",
        db.conn,
        params=[pid],
    )

    # Write to bytes
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df_sum.to_excel(w, sheet_name="Tổng quan", index=False)
        df_comp.to_excel(w, sheet_name="Cấu kiện", index=False)
        df_ins.to_excel(w, sheet_name="Inspections", index=False)
        by_type.to_excel(w, sheet_name="Theo loại NT", index=False)

    db.log("system", "EXPORT_REPORT", "project", pid,
           f"components={len(df_comp)}, inspections={len(df_ins)}")
    return buf.getvalue()
