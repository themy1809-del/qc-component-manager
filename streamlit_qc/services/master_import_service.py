# -*- coding: utf-8 -*-
"""
Service: import Master List (PKL) vào DB.

Logic giữ NGUYÊN từ Tkinter v1.0.2 dòng 716-739 (`_do_import_master`),
mở rộng v2.0:
  - Phát hiện Rev thay đổi → cảnh báo QC.
  - Phát hiện inspection ĐÃ NGHIỆM THU sẵn từ Master (cột RFI_Fit-up /
    RFI_Final Dim) → tự tạo synthetic inspection PASS, không đè bản ghi cũ.
  - Detect dòng trùng mã trong file Excel + cảnh báo cho user.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from streamlit_qc.core.date_utils import excel_date_to_iso
from streamlit_qc.core.db import DB


# 4 field "đã NT" — dùng nội bộ, KHÔNG ghi vào data_json của component
INSPECTION_DONE_FIELDS = {
    "rfi_fitup_done", "date_fitup_done",
    "rfi_final_done", "date_final_done",
}


@dataclass
class MasterImportResult:
    """Kết quả import master."""
    total_rows: int = 0
    written: int = 0
    new: int = 0
    updated: int = 0
    skipped: int = 0
    rev_changed: list = field(default_factory=list)
    # === Inspection đã có sẵn từ master ===
    fitup_seeded: int = 0
    final_seeded: int = 0
    fitup_skipped_exist: int = 0
    final_skipped_exist: int = 0
    # === Cảnh báo dòng trùng mã trong file gốc ===
    duplicate_rows: int = 0
    duplicate_codes: list = field(default_factory=list)


def _existing_inspection_types(db: DB, cid: int) -> set[str]:
    """Trả về set các inspection_type đã có cho 1 cấu kiện."""
    rows = db.conn.execute(
        "SELECT DISTINCT inspection_type FROM inspections WHERE component_id=?",
        (cid,),
    ).fetchall()
    return {r["inspection_type"] for r in rows}


def _get_master_inspection(db: DB, cid: int, itype: str) -> dict | None:
    """Lấy inspection MASTER-source gần nhất cho component + type."""
    row = db.conn.execute(
        """SELECT id, inspection_date, rfi_no FROM inspections
           WHERE component_id=? AND inspection_type=? AND source_file='MASTER'
           ORDER BY id DESC LIMIT 1""",
        (cid, itype),
    ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "date": row["inspection_date"] or "", "rfi": row["rfi_no"] or ""}


def _update_inspection(db: DB, ins_id: int, new_date: str, new_rfi: str) -> None:
    """Update date + rfi của 1 inspection record."""
    db.conn.execute(
        "UPDATE inspections SET inspection_date=?, rfi_no=? WHERE id=?",
        (new_date, new_rfi, ins_id),
    )


def import_master(
    db: DB,
    pid: int,
    df: pd.DataFrame,
    mapping: dict[str, str],
    sheet_name: str | None,
    header_row: int,
    user_name: str,
) -> MasterImportResult:
    """Import master list vào DB."""
    if "code" not in mapping or not mapping["code"]:
        raise ValueError("Mapping bắt buộc phải có trường 'code'.")

    db.save_mapping(pid, "MASTER", mapping, header_row=header_row, sheet_name=sheet_name)
    result = MasterImportResult(total_rows=len(df))

    # === Detect dòng trùng mã trong file Excel ===
    code_col = mapping["code"]
    if code_col in df.columns:
        dup_series = df[df[code_col].duplicated(keep=False)][code_col].value_counts()
        if len(dup_series) > 0:
            result.duplicate_rows = int((dup_series - 1).sum())
            result.duplicate_codes = [
                {"code": str(c), "count": int(v)}
                for c, v in dup_series.head(10).items()
            ]

    has_fitup_col = bool(mapping.get("rfi_fitup_done"))
    has_final_col = bool(mapping.get("rfi_final_done"))

    # Tập cột Excel đã được map (để loại ra khi gom _extra)
    mapped_excel_cols = {c for c in mapping.values() if c}

    import re as _re_code
    _INV_PATTERN = (
        "[\x00-\x1F\x7F"
        "\u00A0"
        "\u200B-\u200F"
        "\u202A-\u202E"
        "\u2060-\u206F"
        "\uFEFF"
        "]"
    )

    # ⚡ Pre-fetch toàn bộ component hiện có (1 query) thay cho find_component từng dòng
    existing_map = {
        r["code"]: r["data_json"]
        for r in db.conn.execute(
            "SELECT code, data_json FROM components WHERE project_id=?", (pid,)
        ).fetchall()
    }

    seen_codes = set()
    to_upsert = []   # [(code, data_dict đã merge)]
    insp_tasks = []  # [(code, is_new, rfi_fitup, date_fitup, rfi_final, date_final)]

    for _, row in df.iterrows():
        data = {}
        rfi_fitup_val = None
        date_fitup_val = None
        rfi_final_val = None
        date_final_val = None

        for fld, col in mapping.items():
            if not col:
                continue
            v = row.get(col, None)
            if pd.isna(v):
                v = None

            if fld == "rfi_fitup_done":
                rfi_fitup_val = v
                continue
            if fld == "date_fitup_done":
                date_fitup_val = excel_date_to_iso(v)
                continue
            if fld == "rfi_final_done":
                rfi_final_val = v
                continue
            if fld == "date_final_done":
                date_final_val = excel_date_to_iso(v)
                continue

            if fld == "plan_date":
                v = excel_date_to_iso(v)
            data[fld] = v

        # ★ GIỮ TẤT CẢ CỘT CHƯA ĐƯỢC MAP vào data["_extra"]
        extra = {}
        for col in row.index:
            if col in mapped_excel_cols:
                continue
            v = row.get(col)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                continue
            key = str(col).strip()
            if not key or key.lower().startswith("unnamed"):
                continue
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            elif not isinstance(v, (str, int, float, bool)):
                v = str(v)
            extra[key] = v
        if extra:
            data["_extra"] = extra

        raw_code = str(data.get("code") or "")
        code = _re_code.sub(_INV_PATTERN, "", raw_code).strip()
        if not code or code.lower() == "nan":
            result.skipped += 1
            continue
        data["code"] = code

        old_json = existing_map.get(code)
        seen_before = code in seen_codes
        seen_codes.add(code)
        is_new = (old_json is None) and not seen_before

        new_rev = str(data.get("rev_no") or "").strip()
        if old_json is not None and new_rev:
            try:
                old_data = json.loads(old_json)
                old_rev = str(old_data.get("rev_no") or "").strip()
                if old_rev and new_rev and old_rev != new_rev:
                    result.rev_changed.append({
                        "code": code,
                        "name": str(
                            old_data.get("manual_drawing")
                            or old_data.get("drawing")
                            or old_data.get("member_no")
                            or ""
                        ),
                        "old_rev": old_rev,
                        "new_rev": new_rev,
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        # Merge: giữ field cũ nếu field mới rỗng (giống upsert_component)
        if old_json is not None:
            try:
                final_data = json.loads(old_json)
            except (json.JSONDecodeError, TypeError):
                final_data = {}
            final_data.update(
                {k: v for k, v in data.items() if v is not None and v != ""}
            )
            result.updated += 1
        elif seen_before:
            final_data = data
            result.updated += 1
        else:
            final_data = data
            result.new += 1
        result.written += 1
        to_upsert.append((code, final_data))

        if has_fitup_col or has_final_col:
            insp_tasks.append(
                (code, is_new, rfi_fitup_val, date_fitup_val,
                 rfi_final_val, date_final_val)
            )

    # ⚡ BULK upsert toàn bộ component (vài round-trip thay vì hàng nghìn)
    db.bulk_upsert_components(pid, to_upsert)

    # Inspection seeding — chỉ khi file master có cột RFI Fit-up/Final
    if (has_fitup_col or has_final_col) and insp_tasks:
        id_map = {
            r["code"]: r["id"]
            for r in db.conn.execute(
                "SELECT id, code FROM components WHERE project_id=?", (pid,)
            ).fetchall()
        }
        for (code, is_new, rfi_fitup_val, date_fitup_val,
             rfi_final_val, date_final_val) in insp_tasks:
            cid = id_map.get(code)
            if not cid:
                continue

            if has_fitup_col:
                rfi_str = str(rfi_fitup_val or "").strip()
                if rfi_str and rfi_str.lower() != "nan":
                    new_date = date_fitup_val or ""
                    existing_master = (
                        _get_master_inspection(db, cid, "FUR")
                        if not is_new else None
                    )
                    if existing_master:
                        if (existing_master["date"] != new_date
                                or existing_master["rfi"] != rfi_str):
                            _update_inspection(
                                db, existing_master["id"], new_date, rfi_str
                            )
                            result.fitup_seeded += 1
                        else:
                            result.fitup_skipped_exist += 1
                    else:
                        existing_types = _existing_inspection_types(db, cid)
                        if "FUR" in existing_types:
                            result.fitup_skipped_exist += 1
                        else:
                            db.add_inspection(
                                pid=pid, cid=cid, itype="FUR",
                                idate=new_date, inspector=user_name, result="PASS",
                                rep="", rfi=rfi_str,
                                note="Import tu Master (RFI Fit-up co san)",
                                src="MASTER",
                            )
                            result.fitup_seeded += 1

            if has_final_col:
                rfi_str = str(rfi_final_val or "").strip()
                if rfi_str and rfi_str.lower() != "nan":
                    new_date = date_final_val or ""
                    existing_master = (
                        _get_master_inspection(db, cid, "DGRP")
                        if not is_new else None
                    )
                    if existing_master:
                        if (existing_master["date"] != new_date
                                or existing_master["rfi"] != rfi_str):
                            _update_inspection(
                                db, existing_master["id"], new_date, rfi_str
                            )
                            result.final_seeded += 1
                        else:
                            result.final_skipped_exist += 1
                    else:
                        existing_types = _existing_inspection_types(db, cid)
                        if "DGRP" in existing_types:
                            result.final_skipped_exist += 1
                        else:
                            db.add_inspection(
                                pid=pid, cid=cid, itype="DGRP",
                                idate=new_date, inspector=user_name, result="PASS",
                                rep="", rfi=rfi_str,
                                note="Import tu Master (RFI Final co san)",
                                src="MASTER",
                            )
                            result.final_seeded += 1

    db.conn.commit()
    db.log(
        user_name,
        "IMPORT_MASTER",
        "project",
        f"rows={result.total_rows}, written={result.written}, "
        f"new={result.new}, upd={result.updated}, skipped={result.skipped}, "
        f"fitup_seeded={result.fitup_seeded}, final_seeded={result.final_seeded}, "
        f"dup_rows={result.duplicate_rows}",
    )
    return result


def clear_components(db: DB, pid: int, user_name: str) -> int:
    """Xoá toàn bộ cấu kiện của 1 dự án (cascade xoá inspections luôn)."""
    count = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?",
        (pid,),
    ).fetchone()["c"]
    db.conn.execute("DELETE FROM components WHERE project_id=?", (pid,))
    db.conn.commit()
    db.log(user_name, "CLEAR_COMPONENTS", "project", pid, f"deleted={count}")
    return count
