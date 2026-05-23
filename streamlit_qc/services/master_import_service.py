# -*- coding: utf-8 -*-
"""
Service: import Master List (PKL) vào DB.

Logic giữ NGUYÊN từ Tkinter v1.0.2 dòng 716-739 (`_do_import_master`),
mở rộng v2.0:
  - Phát hiện Rev thay đổi → cảnh báo QC.
  - Phát hiện inspection ĐÃ NGHIỆM THU sẵn từ Master (cột RFI_Fit-up /
    RFI_Final Dim) → tự tạo synthetic inspection PASS, không đè bản ghi cũ.
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
    fitup_seeded: int = 0   # số FUR PASS tự tạo từ cột RFI_Fit-up
    final_seeded: int = 0   # số DGRP PASS tự tạo từ cột RFI_Final
    fitup_skipped_exist: int = 0  # đã có FUR rồi → không tạo trùng
    final_skipped_exist: int = 0  # đã có DGRP rồi → không tạo trùng


def _existing_inspection_types(db: DB, cid: int) -> set[str]:
    """Trả về set các inspection_type đã có cho 1 cấu kiện."""
    rows = db.conn.execute(
        "SELECT DISTINCT inspection_type FROM inspections WHERE component_id=?",
        (cid,),
    ).fetchall()
    return {r["inspection_type"] for r in rows}


def _get_master_inspection(db: DB, cid: int, itype: str) -> dict | None:
    """
    Lấy inspection MASTER-source (từ Master import) gần nhất cho component + type.
    Trả về dict {id, date, rfi} hoặc None nếu chưa có.
    """
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
    """
    Import master list vào DB.

    Nếu mapping có chứa `rfi_fitup_done` / `rfi_final_done` → các cấu kiện
    đã có số phiếu RFI trong master sẽ được tự động tạo 1 inspection PASS
    tương ứng (FUR cho Fit-up, DGRP cho Final). Logic chống trùng:
    component nào đã có inspection cùng loại trong DB → bỏ qua, không tạo
    thêm.

    Args:
        db: DB instance.
        pid: ID dự án.
        df: DataFrame đã đọc sẵn (đã có header đúng).
        mapping: {field: column_name_excel}, bắt buộc có key 'code'.
        sheet_name: Tên sheet (để lưu lại cho mapping).
        header_row: Index dòng tiêu đề (để lưu lại).
        user_name: Tên QC để ghi audit_log.

    Returns:
        MasterImportResult với số liệu chi tiết.

    Raises:
        ValueError: Nếu mapping không có 'code'.
    """
    if "code" not in mapping or not mapping["code"]:
        raise ValueError("Mapping bắt buộc phải có trường 'code'.")

    # Lưu mapping vào DB để dùng lại lần sau
    db.save_mapping(pid, "MASTER", mapping, header_row=header_row, sheet_name=sheet_name)

    result = MasterImportResult(total_rows=len(df))

    # Có map cột RFI đã NT không?
    has_fitup_col = bool(mapping.get("rfi_fitup_done"))
    has_final_col = bool(mapping.get("rfi_final_done"))

    for _, row in df.iterrows():
        # Build data dict theo mapping (LOẠI BỎ 4 trường inspection-done)
        data = {}
        # Tách riêng 4 giá trị inspection-done để xử lý sau
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

            # Inspection-done → tách riêng, KHÔNG ghi vào data_json
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

            # plan_date: Excel serial → ISO date string
            if fld == "plan_date":
                v = excel_date_to_iso(v)
            data[fld] = v

        # Validate code
        code = str(data.get("code") or "").strip()
        if not code or code.lower() == "nan":
            result.skipped += 1
            continue

        # CHECK REV CHANGE — trước khi upsert
        existing = db.find_component(pid, code)
        new_rev = str(data.get("rev_no") or "").strip()
        if existing and new_rev:
            try:
                old_data = json.loads(existing["data_json"])
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

        # Upsert component
        cid, is_new = db.upsert_component(pid, code, data)
        result.written += 1
        if is_new:
            result.new += 1
        else:
            result.updated += 1

        # === Tạo/cập nhật inspection PASS từ cột RFI có sẵn ===
        # NEW LOGIC: nếu đã có MASTER-source inspection → UPDATE date/rfi nếu khác,
        # KHÔNG skip như trước. Inspection từ DAILY source sẽ KHÔNG bị đụng vào.
        if has_fitup_col or has_final_col:

            # FUR (Fit-up) — có RFI = đã nghiệm thu
            if has_fitup_col:
                rfi_str = str(rfi_fitup_val or "").strip()
                if rfi_str and rfi_str.lower() != "nan":
                    new_date = date_fitup_val or ""
                    existing_master = _get_master_inspection(db, cid, "FUR") if not is_new else None
                    if existing_master:
                        # Đã có MASTER inspection — update nếu date/rfi đổi
                        if existing_master["date"] != new_date or existing_master["rfi"] != rfi_str:
                            _update_inspection(db, existing_master["id"], new_date, rfi_str)
                            result.fitup_seeded += 1  # tính như seeded vì có cập nhật
                        else:
                            result.fitup_skipped_exist += 1
                    else:
                        # Chưa có MASTER inspection — check xem có DAILY không
                        existing_types = _existing_inspection_types(db, cid)
                        if "FUR" in existing_types:
                            # Đã có FUR từ DAILY → tôn trọng, không tạo trùng từ Master
                            result.fitup_skipped_exist += 1
                        else:
                            db.add_inspection(
                                pid=pid, cid=cid, itype="FUR",
                                idate=new_date, inspector=user_name, result="PASS",
                                rep="", rfi=rfi_str,
                                note="Import từ Master (RFI_Fit-up có sẵn)",
                                src="MASTER",
                            )
                            result.fitup_seeded += 1

            # DGRP (Final) — có RFI = đã nghiệm thu → ACCEPTED
            if has_final_col:
                rfi_str = str(rfi_final_val or "").strip()
                if rfi_str and rfi_str.lower() != "nan":
                    new_date = date_final_val or ""
                    existing_master = _get_master_inspection(db, cid, "DGRP") if not is_new else None
                    if existing_master:
                        if existing_master["date"] != new_date or existing_master["rfi"] != rfi_str:
                            _update_inspection(db, existing_master["id"], new_date, rfi_str)
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
                                note="Import từ Master (RFI_Final có sẵn)",
                                src="MASTER",
                            )
                            result.final_seeded += 1

    # Commit + audit log
    db.conn.commit()
    db.log(
        user_name,
        "IMPORT_MASTER",
        "project",
        pid,
        f"rows={result.total_rows}, written={result.written}, "
        f"new={result.new}, upd={result.updated}, skipped={result.skipped}, "
        f"fitup_seeded={result.fitup_seeded}, final_seeded={result.final_seeded}",
    )

    return result


def clear_components(db: DB, pid: int, user_name: str) -> int:
    """
    Xoá toàn bộ cấu kiện của 1 dự án (cascade xoá inspections luôn).

    Returns:
        Số cấu kiện đã xoá.
    """
    count = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?",
        (pid,),
    ).fetchone()["c"]
    db.conn.execute("DELETE FROM components WHERE project_id=?", (pid,))
    db.conn.commit()
    db.log(user_name, "CLEAR_COMPONENTS", "project", pid, f"deleted={count}")
    return count
