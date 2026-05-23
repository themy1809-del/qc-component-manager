# -*- coding: utf-8 -*-
"""
Service: import file kiểm tra hàng ngày (Daily).

Logic giữ NGUYÊN từ Tkinter v1.0.2 dòng 933-996 (`_do_import_daily`).

QUY TẮC NGHIỆP VỤ (KHÔNG ĐỔI):
1. Match mã cấu kiện theo 3 candidates ưu tiên:
   a. Mã gốc
   b. Mã sau khi strip prefix `^\\d+-` (vd "1-01BTG3008-001" → "01BTG3008-001")
   c. Mã sau khi strip suffix `-J...` (vd "01USC3020-001-J1" → "01USC3020-001")

2. DGRP đặc biệt: parse cột Remark "Dim,Visual,NDT" → tạo nhiều inspection records.
   Nếu remark rỗng/không parse được → fallback DIR.

3. Result auto-detect:
   - "FAIL" / "REJ" / "NG" trong result/note → FAIL
   - "RECHECK" hoặc code có "-R1"/"-R2" → RECHECK
   - Còn lại → PASS

4. Date priority: manual_date > date từ file > extract_date_from_filename > today.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass, field

import pandas as pd

from streamlit_qc.core.date_utils import (
    excel_date_to_iso,
    extract_date_from_filename,
    parse_remark_types,
)
from streamlit_qc.core.db import DB


# ====================================================================
# CONSTANTS — không nên đổi
# ====================================================================
# Mã giả thường gặp ở footer Excel cần bỏ qua
SKIP_CODES = {"TOTAL", "PRINT", "SUM", "GRAND TOTAL", "GRANDTOTAL"}

# Regex match prefix kiểu "1-", "12-", "999-" (file DGRP có module number)
PREFIX_PATTERN = re.compile(r"^(\d+)-(.+)$")

# Suffix kiểu "-J1", "-J3-R1" (file NDT có mối hàn)
SUFFIX_J_PATTERN = re.compile(r"^(.+?)-J\d", re.IGNORECASE)


@dataclass
class DailyImportResult:
    """Kết quả import daily."""
    total_rows: int = 0
    matched_components: int = 0  # số cấu kiện match được
    inspections_added: int = 0    # số inspection record được tạo (DGRP có thể >1 per row)
    not_found: int = 0           # số dòng không match được mã
    skipped: int = 0             # số dòng bỏ qua (mã rỗng/giả)
    unmatched_codes: list[str] = field(default_factory=list)  # max 50 mẫu


# ====================================================================
# HELPERS
# ====================================================================
def _generate_match_candidates(code: str) -> list[str]:
    """
    Sinh các phiên bản có thể của mã cấu kiện để thử match với master.

    Args:
        code: Mã thô từ file daily, vd "1-01BTG3008-001" hoặc "01USC3020-001-J1".

    Returns:
        Danh sách các candidates theo thứ tự ưu tiên.
    """
    candidates = [code]
    # Strip prefix "1-", "2-", "N-"
    m = PREFIX_PATTERN.match(code)
    if m:
        candidates.append(m.group(2))
    # Strip suffix "-J1", "-J3-R1"...
    m_j = SUFFIX_J_PATTERN.match(code)
    if m_j:
        candidates.append(m_j.group(1))
    return candidates


def _detect_result(raw_result: str, note: str, code: str) -> str:
    """
    Tự suy đoán kết quả PASS/FAIL/RECHECK từ cột result + note + mã.

    Tkinter dòng 973-976.
    """
    chk = (str(raw_result) if raw_result else "") + " " + (note or "")
    chk_upper = chk.upper()
    if any(k in chk_upper for k in ("FAIL", "REJ", "NG")):
        return "FAIL"
    if "RECHECK" in chk_upper or "-R1" in code or "-R2" in code:
        return "RECHECK"
    return "PASS"


def _resolve_date(
    row_date_raw,
    manual_date: str,
    source_file: str,
) -> str:
    """
    Quyết định ngày kiểm tra theo thứ tự ưu tiên:
    1. Manual date user nhập (ô bên cạnh file)
    2. Cột inspection_date trong file
    3. Date extract từ tên file
    4. Today

    Returns: ISO date string 'YYYY-MM-DD'.
    """
    if manual_date:
        return manual_date
    d = excel_date_to_iso(row_date_raw) if row_date_raw is not None else None
    if d:
        return d
    d = extract_date_from_filename(source_file)
    if d:
        return d
    return dt.date.today().strftime("%Y-%m-%d")


# ====================================================================
# MAIN
# ====================================================================
def import_daily(
    db: DB,
    pid: int,
    df: pd.DataFrame,
    mapping: dict[str, str],
    inspection_type: str,
    source_file: str,
    manual_date: str = "",
    manual_nfi: str = "",
    user_name: str = "qc_user",
) -> DailyImportResult:
    """
    Import file daily vào DB.

    Args:
        db: DB instance.
        pid: ID dự án.
        df: DataFrame đã đọc sẵn.
        mapping: {field: column_name}. Bắt buộc có 'code'.
        inspection_type: 1 trong 9 loại NT (FUR/DIR/VIR/NDT/TAIR/PRE/MB/MTR/DGRP).
        source_file: Tên file gốc (để lưu source_file + extract date).
        manual_date: Ngày user nhập (ưu tiên cao nhất). Format YYYY-MM-DD.
        manual_nfi: Số NFI user nhập (áp cho mọi dòng).
        user_name: Tên QC để ghi audit.

    Returns:
        DailyImportResult.

    Raises:
        ValueError: Nếu mapping thiếu 'code'.
    """
    if "code" not in mapping or not mapping["code"]:
        raise ValueError("Mapping bắt buộc phải có trường 'code'.")

    result = DailyImportResult(total_rows=len(df))
    date_fallback = _resolve_date(None, manual_date, source_file)
    src_basename = os.path.basename(source_file)

    code_col = mapping["code"]

    for _, row in df.iterrows():
        # --- 1. Validate code ---
        cr = row.get(code_col)
        if pd.isna(cr):
            result.skipped += 1
            continue
        code = str(cr).strip()
        if not code or code.lower() == "nan":
            result.skipped += 1
            continue
        if len(code) <= 2 or code.upper() in SKIP_CODES:
            result.skipped += 1
            continue

        # --- 2. Tìm component bằng 3 candidates ---
        comp = None
        for cand in _generate_match_candidates(code):
            comp = db.find_component(pid, cand)
            if comp:
                break
        if not comp:
            result.not_found += 1
            if len(result.unmatched_codes) < 50:
                result.unmatched_codes.append(code)
            continue

        # --- 3. Build inspection fields ---
        idate = _resolve_date(
            row.get(mapping["inspection_date"]) if mapping.get("inspection_date") else None,
            manual_date,
            source_file,
        ) or date_fallback

        inspector = ""
        if mapping.get("inspector"):
            v = row.get(mapping["inspector"])
            if v is not None and not pd.isna(v):
                inspector = str(v).strip()

        note = ""
        if mapping.get("note"):
            v = row.get(mapping["note"])
            if v is not None and not pd.isna(v):
                note = str(v).strip()

        report_no = ""
        if mapping.get("report_no"):
            v = row.get(mapping["report_no"])
            if v is not None and not pd.isna(v):
                report_no = str(v).strip()

        # NFI: ưu tiên manual_nfi
        if manual_nfi:
            rfi_no = manual_nfi
        elif mapping.get("rfi_no"):
            v = row.get(mapping["rfi_no"])
            rfi_no = str(v).strip() if v is not None and not pd.isna(v) else ""
        else:
            rfi_no = ""

        # Result
        raw_result = row.get(mapping["result"]) if mapping.get("result") else None
        rv = _detect_result(str(raw_result) if raw_result else "", note, code)

        # --- 4. DGRP đặc biệt: 1 dòng → nhiều inspection ---
        if inspection_type == "DGRP":
            types = parse_remark_types(note) or ["DIR"]
            for t in types:
                db.add_inspection(
                    pid, comp["id"], t, idate, inspector, rv,
                    report_no, rfi_no, note, src_basename,
                )
                result.inspections_added += 1
        else:
            db.add_inspection(
                pid, comp["id"], inspection_type, idate, inspector, rv,
                report_no, rfi_no, note, src_basename,
            )
            result.inspections_added += 1

        result.matched_components += 1

    # Commit + audit
    db.conn.commit()
    db.log(
        user_name,
        "IMPORT_DAILY",
        "project",
        pid,
        f"type={inspection_type}, matched={result.matched_components}, "
        f"ins={result.inspections_added}, not_found={result.not_found}, "
        f"skipped={result.skipped}, file={src_basename}",
    )

    return result
