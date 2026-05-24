# -*- coding: utf-8 -*-
"""
Service quản lý báo cáo QC: Dimension / Welding / Paint.

Mô hình:
- 1 bảng `qc_reports` chung, phân biệt qua `report_type`.
- Trường `data_json` chứa các field đặc thù theo loại.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

from streamlit_qc.core.db import DB


REPORT_TYPES = ("DIMENSION", "WELDING", "PAINT")
RESULT_OPTIONS = ("PASS", "FAIL", "NA")


# Các field đặc thù theo từng loại report — UI dùng để render form
DIMENSION_FIELDS = [
    ("length_mm", "Chiều dài (mm)"),
    ("width_mm", "Chiều rộng (mm)"),
    ("height_mm", "Chiều cao (mm)"),
    ("thickness_mm", "Độ dày (mm)"),
    ("tolerance_mm", "Dung sai cho phép (mm)"),
    ("deviation_mm", "Độ lệch đo được (mm)"),
    ("squareness_mm", "Độ vuông góc (mm)"),
    ("note", "Ghi chú"),
]

WELDING_FIELDS = [
    ("joint_no", "Số mối hàn"),
    ("weld_type", "Loại mối (FW/BW/PJP/CJP)"),
    ("wps_no", "WPS số"),
    ("welder_id", "Mã thợ hàn"),
    ("ndt_method", "Phương pháp NDT (Visual/MT/PT/UT/RT)"),
    ("defect_type", "Loại khuyết tật (nếu có)"),
    ("acceptance_std", "Tiêu chuẩn nghiệm thu (AWS D1.1...)"),
    ("note", "Ghi chú"),
]

PAINT_FIELDS = [
    ("layer", "Lớp sơn (Primer/Intermediate/Top)"),
    ("color", "Màu / RAL"),
    ("surface_prep", "Chuẩn bị bề mặt (Sa2.5/Sa3)"),
    ("dft_required_um", "DFT yêu cầu (µm)"),
    ("dft_measured_um", "DFT đo được (µm)"),
    ("adhesion_mpa", "Độ bám dính (MPa)"),
    ("ambient_temp_c", "Nhiệt độ môi trường (°C)"),
    ("humidity_pct", "Độ ẩm (%)"),
    ("note", "Ghi chú"),
]


FIELDS_BY_TYPE = {
    "DIMENSION": DIMENSION_FIELDS,
    "WELDING": WELDING_FIELDS,
    "PAINT": PAINT_FIELDS,
}


@dataclass
class ImportReportResult:
    """Kết quả khi import báo cáo từ file Excel."""
    total: int = 0
    success: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)


# ====================================================================
# CRUD
# ====================================================================
def add_report(
    db: DB,
    pid: int,
    report_type: str,
    component_code: str | None,
    report_date: str | None,
    inspector: str | None,
    result: str | None,
    data: dict,
    rfi_no: str | None = None,
    source_file: str | None = None,
    created_by: str | None = None,
) -> int:
    """Tạo 1 báo cáo. Nếu component_code có → resolve component_id."""
    cid = None
    if component_code:
        row = db.find_component(pid, str(component_code).strip())
        if row:
            cid = row["id"]
    return db.add_qc_report(
        pid=pid,
        component_id=cid,
        report_type=report_type,
        report_date=report_date,
        inspector=inspector,
        result=result,
        data=data,
        rfi_no=rfi_no,
        source_file=source_file,
        created_by=created_by,
    )


def list_reports(
    db: DB,
    pid: int,
    report_type: str | None = None,
    component_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    """Lấy DataFrame các báo cáo theo filter."""
    rows = db.list_qc_reports(
        pid=pid,
        report_type=report_type,
        component_id=component_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    if not rows:
        return pd.DataFrame()
    out = []
    for r in rows:
        try:
            data = json.loads(r["data_json"]) if r["data_json"] else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        rec = {
            "ID": r["id"],
            "Loại": r["report_type"],
            "Ngày": r["report_date"] or "",
            "Mã cấu kiện": r["component_code"] or "",
            "Người KT": r["inspector"] or "",
            "Kết quả": r["result"] or "",
            "RFI": r["rfi_no"] or "",
            "Nguồn": r["source_file"] or "",
            "Người tạo": r["created_by"] or "",
        }
        # merge data fields cho UI hiển thị
        for k, v in data.items():
            if k not in rec:
                rec[k] = v
        out.append(rec)
    return pd.DataFrame(out)


def delete_report(db: DB, rid: int) -> None:
    db.delete_qc_report(rid)
    db.conn.commit()


def update_report(db: DB, rid: int, **fields) -> None:
    db.update_qc_report(rid, **fields)
    db.conn.commit()


def count_by_type(db: DB, pid: int) -> dict[str, int]:
    return db.count_qc_reports(pid)


# ====================================================================
# IMPORT EXCEL
# ====================================================================
def import_reports_from_excel(
    db: DB,
    pid: int,
    report_type: str,
    df: pd.DataFrame,
    created_by: str = "import",
    source_file: str | None = None,
) -> ImportReportResult:
    """
    Import báo cáo từ DataFrame Excel.

    Quy ước cột (case-insensitive):
      - Bắt buộc: 'code' hoặc 'Mã cấu kiện'
      - Tuỳ chọn: 'date' hoặc 'Ngày', 'inspector' hoặc 'Người KT',
                  'result' hoặc 'Kết quả', 'rfi'
      - Còn lại: lưu hết vào data_json
    """
    result = ImportReportResult(total=len(df))

    # Normalize column names (lower + strip)
    col_map = {c: str(c).strip().lower() for c in df.columns}
    rev = {v: k for k, v in col_map.items()}  # lower → original

    def pick(*aliases):
        for a in aliases:
            if a in rev:
                return rev[a]
        return None

    code_col = pick("code", "mã cấu kiện", "mã", "ma cau kien")
    date_col = pick("date", "ngày", "ngay", "report_date")
    inspector_col = pick("inspector", "người kt", "nguoi kt", "qc")
    result_col = pick("result", "kết quả", "ket qua", "pass/fail")
    rfi_col = pick("rfi", "rfi_no", "rfi no")

    if not code_col:
        result.errors.append("Không tìm thấy cột mã cấu kiện (code / Mã cấu kiện).")
        return result

    fixed_cols = {code_col, date_col, inspector_col, result_col, rfi_col}
    fixed_cols.discard(None)

    for idx, row in df.iterrows():
        code = row.get(code_col)
        if code is None or pd.isna(code) or str(code).strip() == "":
            result.skipped += 1
            continue
        code = str(code).strip()

        # extract data từ các cột còn lại
        data = {}
        for col in df.columns:
            if col in fixed_cols:
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
            data[key] = v

        date_val = None
        if date_col:
            d = row.get(date_col)
            if d is not None and not (isinstance(d, float) and pd.isna(d)):
                if hasattr(d, "strftime"):
                    date_val = d.strftime("%Y-%m-%d")
                else:
                    date_val = str(d).strip()

        ins_val = None
        if inspector_col:
            v = row.get(inspector_col)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                ins_val = str(v).strip()

        res_val = None
        if result_col:
            v = row.get(result_col)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                rv = str(v).strip().upper()
                if rv in RESULT_OPTIONS:
                    res_val = rv
                elif rv in ("OK", "ĐẠT", "DAT"):
                    res_val = "PASS"
                elif rv in ("NG", "KHÔNG ĐẠT", "KHONG DAT", "FAIL"):
                    res_val = "FAIL"

        rfi_val = None
        if rfi_col:
            v = row.get(rfi_col)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                rfi_val = str(v).strip()

        try:
            add_report(
                db=db,
                pid=pid,
                report_type=report_type,
                component_code=code,
                report_date=date_val,
                inspector=ins_val,
                result=res_val,
                data=data,
                rfi_no=rfi_val,
                source_file=source_file,
                created_by=created_by,
            )
            result.success += 1
        except Exception as e:
            result.errors.append(f"Dòng {idx + 2}: {e}")
            result.skipped += 1

    db.conn.commit()
    return result


def get_template_df(report_type: str) -> pd.DataFrame:
    """Trả về DataFrame mẫu cho từng loại report để QC tải về điền."""
    headers = ["code", "date", "inspector", "result", "rfi"]
    fields = FIELDS_BY_TYPE.get(report_type.upper(), [])
    for fld, _label in fields:
        headers.append(fld)
    return pd.DataFrame(columns=headers)
