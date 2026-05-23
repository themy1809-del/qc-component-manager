# -*- coding: utf-8 -*-
"""
Service: query + cập nhật bảng cấu kiện cho page "🔧 Cấu kiện".

Tương đương hàm `_refresh_components` + `_inline_edit_cell` + `_populate_col_filters`
trong Tkinter v1.0.2 (dòng 1137-1407).

Chiến lược performance:
- 1 query duy nhất để lấy components + status + data_json
- 1 query duy nhất để lấy latest inspection per component (subquery MAX(id))
- Filter ngoài Python với data_json (vì các trường nằm trong JSON)
- Đã verify với 8212 cấu kiện VIOLA: < 1s
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from streamlit_qc.core.constants import COMPONENT_FILTER_FIELDS
from streamlit_qc.core.date_utils import format_date_vn, parse_date_input
from streamlit_qc.core.db import DB


# ====================================================================
# DATACLASS
# ====================================================================
@dataclass
class ComponentRow:
    """1 dòng dữ liệu cho bảng UI."""
    id: int
    code: str
    name: str        # = manual_drawing > drawing > member_no > section
    rev_no: str
    workshop: str
    status: str
    nfi_no: str      # = manual_nfi > latest inspection rfi_no (giữ cho backward compat)
    insp_date: str   # = manual_insp_date > latest inspection date (đã format DD/MM/YYYY)
    fitup_status: str = ""   # status Fit-up (FUR) — Chưa / PASS / FAIL
    final_status: str = ""   # status Final (DGRP) — Chưa / PASS / FAIL
    fitup_date: str = ""     # ngày Fit-up gần nhất (DD/MM/YYYY)
    final_date: str = ""     # ngày Final gần nhất (DD/MM/YYYY)


@dataclass
class ComponentListResult:
    """Kết quả query."""
    rows: list[ComponentRow] = field(default_factory=list)
    total_in_db: int = 0                # tổng cấu kiện trong dự án (chưa filter)
    after_status_search: int = 0        # sau filter status + search
    after_dropdown_filter: int = 0      # sau khi áp 5 dropdown
    unique_values: dict[str, list[str]] = field(default_factory=dict)
    # {field: [val1, val2, ...]} để fill dropdown


# ====================================================================
# QUERY
# ====================================================================
def _get_latest_inspections(db: DB, pid: int) -> dict[int, tuple[str, str]]:
    """
    Trả về {component_id: (date_iso, rfi_no)} của inspection mới nhất (mọi loại).

    1 query với subquery MAX(id) — nhanh hơn N+1 query rất nhiều.
    """
    rows = db.conn.execute(
        """
        SELECT i.component_id cid, i.inspection_date d, i.rfi_no rfi
        FROM inspections i
        INNER JOIN (
            SELECT component_id, MAX(id) maxid
            FROM inspections WHERE project_id=?
            GROUP BY component_id
        ) m ON m.maxid = i.id
        WHERE i.project_id=?
        """,
        (pid, pid),
    ).fetchall()
    return {r["cid"]: (r["d"] or "", r["rfi"] or "") for r in rows}


def _get_status_by_type(db: DB, pid: int) -> dict[tuple[int, str], tuple[str, str]]:
    """
    Trả về {(component_id, inspection_type): (result, date_iso)}.

    Result = "PASS" / "FAIL" / "RECHECK" / ...
    Date = inspection_date của bản ghi mới nhất.

    Dùng cho cột Fit-up (FUR) và Final (DGRP) + ngày tương ứng.
    """
    rows = db.conn.execute(
        """
        SELECT i.component_id cid, i.inspection_type itype,
               i.result r, i.inspection_date d
        FROM inspections i
        INNER JOIN (
            SELECT component_id, inspection_type, MAX(id) maxid
            FROM inspections WHERE project_id=?
            GROUP BY component_id, inspection_type
        ) m ON m.maxid = i.id
        WHERE i.project_id=?
        """,
        (pid, pid),
    ).fetchall()
    return {(r["cid"], r["itype"]): ((r["r"] or ""), (r["d"] or "")) for r in rows}


def get_components_missing_fitup(db: DB, pid: int, codes: list[str]) -> list[dict]:
    """
    Tìm các mã cấu kiện CHƯA có inspection Fit-up (FUR) PASS.

    Dùng để cảnh báo khi anh import Final mà chưa Fit-up.

    Args:
        db: DB instance.
        pid: project id.
        codes: list mã cấu kiện cần check (đã được strip prefix/suffix).

    Returns:
        List dict {code, name, workshop, in_master} — đầy đủ thông tin để
        hiển thị cho QC dễ tra cứu.
        - in_master = False: mã không tồn tại trong master (rác hoặc sai mapping).
        - in_master = True:  mã tồn tại nhưng chưa có Fit-up PASS.
    """
    if not codes:
        return []
    placeholders = ",".join("?" * len(codes))
    comp_rows = db.conn.execute(
        f"SELECT id, code, data_json FROM components WHERE project_id=? AND code IN ({placeholders})",
        [pid] + codes,
    ).fetchall()

    def _extract_info(row) -> tuple[str, str]:
        """Lấy (name, workshop) từ data_json."""
        try:
            d = json.loads(row["data_json"])
            name = str(
                d.get("manual_drawing")
                or d.get("drawing")
                or d.get("member_no")
                or d.get("section")
                or ""
            )
            workshop = str(d.get("workshop", "") or "")
            return name, workshop
        except (json.JSONDecodeError, TypeError, KeyError):
            return "", ""

    # Map code → (id, name, workshop)
    code_info: dict[str, dict] = {}
    for r in comp_rows:
        nm, ws = _extract_info(r)
        code_info[r["code"]] = {"id": r["id"], "name": nm, "workshop": ws}

    result: list[dict] = []

    # Trường hợp 1: code không có trong master (in_master=False)
    for c in codes:
        if c not in code_info:
            result.append({"code": c, "name": "(không có trong master)", "workshop": "—", "in_master": False})

    # Trường hợp 2: code có trong master nhưng chưa có Fit-up PASS
    ids = [info["id"] for info in code_info.values()]
    if ids:
        placeholders2 = ",".join("?" * len(ids))
        rows_with_fitup = db.conn.execute(
            f"SELECT DISTINCT component_id FROM inspections "
            f"WHERE project_id=? AND inspection_type='FUR' AND result='PASS' "
            f"AND component_id IN ({placeholders2})",
            [pid] + ids,
        ).fetchall()
        ids_with_fitup = {r["component_id"] for r in rows_with_fitup}

        for code, info in code_info.items():
            if info["id"] not in ids_with_fitup:
                result.append({
                    "code": code,
                    "name": info["name"] or "(không tên)",
                    "workshop": info["workshop"] or "—",
                    "in_master": True,
                })
    return result


def list_components(
    db: DB,
    pid: int,
    status: str = "ALL",
    search: str = "",
    dropdown_filters: dict[str, str] | None = None,
    limit: int = 50000,
) -> ComponentListResult:
    """
    Query danh sách cấu kiện theo các filter.

    Args:
        db: DB.
        pid: project id.
        status: ALL hoặc 1 trong PENDING/IN_PROGRESS/PASSED/FAILED/ACCEPTED.
        search: tìm kiếm theo mã (LIKE).
        dropdown_filters: {field: value}, vd {"workshop": "AH7", "zone": "ZONE-A"}.
        limit: tối đa số rows trả về.

    Returns:
        ComponentListResult.
    """
    result = ComponentListResult()
    dropdown_filters = dropdown_filters or {}

    # Tổng cấu kiện trong dự án
    result.total_in_db = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,)
    ).fetchone()["c"]

    # Lấy raw rows + filter status/search ở SQL (nhanh)
    raw_rows = db.list_components(pid, status=status, search=search, limit=limit)
    result.after_status_search = len(raw_rows)

    # Latest inspection per component
    latest_ins = _get_latest_inspections(db, pid)
    # Latest result per (component, inspection_type) — cho cột Fit-up + Final
    status_by_type = _get_status_by_type(db, pid)

    # Thu thập unique values cho 5 dropdown filter
    uniq: dict[str, set[str]] = {f: set() for f, _ in COMPONENT_FILTER_FIELDS}

    # Build ComponentRow + áp dropdown filter
    rows_after_dropdown: list[ComponentRow] = []
    for r in raw_rows:
        data = json.loads(r["data_json"])

        # Thu thập unique values
        for f, _ in COMPONENT_FILTER_FIELDS:
            v = data.get(f)
            if v not in (None, ""):
                uniq[f].add(str(v))

        # Áp dropdown filter
        skip = False
        for f, val in dropdown_filters.items():
            if val and val != "(Tất cả)" and str(data.get(f, "")) != val:
                skip = True
                break
        if skip:
            continue

        # Build row
        d_auto, rfi_auto = latest_ins.get(r["id"], ("", ""))
        rfi_show = str(data.get("manual_nfi") or rfi_auto or "")
        d_raw = data.get("manual_insp_date") or d_auto
        d_show = format_date_vn(d_raw)

        # "Bản vẽ" hiển thị: ưu tiên manual_drawing → drawing → member_no → section
        name_show = (
            data.get("manual_drawing")
            or data.get("drawing")
            or data.get("member_no")
            or data.get("section")
            or ""
        )

        # Fit-up + Final status + date từ inspection_type
        fitup_tuple = status_by_type.get((r["id"], "FUR"), ("", ""))
        final_tuple = status_by_type.get((r["id"], "DGRP"), ("", ""))
        fitup_raw, fitup_date_iso = fitup_tuple
        final_raw, final_date_iso = final_tuple

        rows_after_dropdown.append(ComponentRow(
            id=r["id"],
            code=r["code"],
            name=str(name_show),
            rev_no=str(data.get("rev_no", "") or ""),
            workshop=str(data.get("workshop", "") or ""),
            status=r["status"],
            nfi_no=rfi_show,
            insp_date=d_show,
            fitup_status=fitup_raw,
            final_status=final_raw,
            fitup_date=format_date_vn(fitup_date_iso),
            final_date=format_date_vn(final_date_iso),
        ))

    result.rows = rows_after_dropdown
    result.after_dropdown_filter = len(rows_after_dropdown)
    result.unique_values = {f: sorted(uniq[f]) for f in uniq}

    return result


# ====================================================================
# INLINE EDIT
# ====================================================================
# Map cột UI → field trong data_json
# (Tkinter dòng 1155-1161)
INLINE_EDIT_FIELD_MAP: dict[str, str] = {
    "name": "manual_drawing",       # cột "Bản vẽ"
    "rev_no": "rev_no",
    "workshop": "workshop",
    "nfi_no": "manual_nfi",         # cột "Số NFI"
    "insp_date": "manual_insp_date",  # cột "Ngày kiểm tra"
}


def update_component_field(
    db: DB,
    component_id: int,
    ui_column: str,
    new_value: str,
    user_name: str = "qc_user",
) -> bool:
    """
    Cập nhật 1 field cụ thể trong data_json của 1 component (inline edit).

    Args:
        db: DB.
        component_id: ID cấu kiện.
        ui_column: tên cột UI ('name'/'rev_no'/'workshop'/'nfi_no'/'insp_date').
        new_value: giá trị mới (string). Rỗng = xoá field.
        user_name: cho audit log.

    Returns:
        True nếu cập nhật thành công.

    Raises:
        ValueError: nếu ui_column không phải cột cho phép edit.
    """
    if ui_column not in INLINE_EDIT_FIELD_MAP:
        raise ValueError(f"Cột '{ui_column}' không hỗ trợ inline edit.")

    field_in_json = INLINE_EDIT_FIELD_MAP[ui_column]

    row = db.conn.execute(
        "SELECT data_json, code FROM components WHERE id=?", (component_id,)
    ).fetchone()
    if not row:
        return False

    data = json.loads(row["data_json"])
    new_value = (new_value or "").strip()

    # Với ngày: chuẩn hoá DD/MM/YYYY → YYYY-MM-DD
    if ui_column == "insp_date" and new_value:
        new_value = parse_date_input(new_value)

    if new_value:
        data[field_in_json] = new_value
    else:
        data.pop(field_in_json, None)

    db.conn.execute(
        "UPDATE components SET data_json=? WHERE id=?",
        (json.dumps(data, ensure_ascii=False, default=str), component_id),
    )
    db.conn.commit()
    db.log(
        user_name,
        "EDIT_COMPONENT",
        "component",
        component_id,
        f"code={row['code']}, field={field_in_json}, value={new_value}",
    )
    return True


def get_component_detail(db: DB, pid: int, code: str) -> dict | None:
    """
    Trả về thông tin chi tiết + lịch sử inspection của 1 cấu kiện.

    Returns:
        {component: Row, data: dict, inspections: [Row, ...]}
        hoặc None nếu không tồn tại.
    """
    comp = db.find_component(pid, code)
    if not comp:
        return None
    return {
        "component": dict(comp),
        "data": json.loads(comp["data_json"]),
        "inspections": [dict(r) for r in db.list_inspections(comp["id"])],
    }
