# -*- coding: utf-8 -*-
"""
Service: Material Traceability — Heat number + Mill Certificate.

Workflow:
1. QC nhập thông tin lô vật liệu (heat_no, grade, chemical, mechanical)
2. Assign heat_no → nhiều components (many-to-many)
3. Truy xuất ngược: từ 1 cấu kiện ra heat_no, hoặc từ heat_no ra danh sách cấu kiện
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass

import pandas as pd

from streamlit_qc.core.db import DB


# Phần tử hoá học thường gặp trên mill cert
COMMON_ELEMENTS = ["C", "Si", "Mn", "P", "S", "Cu", "Cr", "Ni", "Mo", "V", "N"]

# Cơ tính: yield, tensile, elongation, impact
COMMON_MECHANICAL_FIELDS = [
    ("yield_mpa", "Giới hạn chảy (MPa)"),
    ("tensile_mpa", "Giới hạn bền (MPa)"),
    ("elongation_pct", "Độ giãn dài (%)"),
    ("impact_J", "Năng lượng va đập (J)"),
]


def create_material(
    db: DB,
    pid: int,
    heat_no: str,
    grade: str | None = None,
    supplier: str | None = None,
    origin: str | None = None,
    cert_no: str | None = None,
    test_date: str | None = None,
    chemical: dict | None = None,
    mechanical: dict | None = None,
) -> int:
    """Tạo mới hoặc raise nếu trùng heat_no."""
    existing = db.find_material(pid, heat_no)
    if existing:
        raise ValueError(f"Heat No '{heat_no}' đã tồn tại trong dự án.")
    mid = db.add_material(
        pid=pid, heat_no=heat_no, grade=grade, supplier=supplier,
        origin=origin, cert_no=cert_no, test_date=test_date,
        chemical=chemical, mechanical=mechanical,
    )
    db.conn.commit()
    return mid


def list_materials_df(db: DB, pid: int) -> pd.DataFrame:
    rows = db.list_materials(pid)
    if not rows:
        return pd.DataFrame()
    out = []
    for r in rows:
        try:
            chem = json.loads(r["chemical"]) if r["chemical"] else {}
        except (json.JSONDecodeError, TypeError):
            chem = {}
        try:
            mech = json.loads(r["mechanical"]) if r["mechanical"] else {}
        except (json.JSONDecodeError, TypeError):
            mech = {}
        out.append({
            "ID": r["id"],
            "Heat No": r["heat_no"],
            "Grade": r["grade"] or "",
            "NCC": r["supplier"] or "",
            "Xuất xứ": r["origin"] or "",
            "Cert No": r["cert_no"] or "",
            "Ngày test": r["test_date"] or "",
            "C (%)": chem.get("C", ""),
            "Mn (%)": chem.get("Mn", ""),
            "S (%)": chem.get("S", ""),
            "Yield (MPa)": mech.get("yield_mpa", ""),
            "Tensile (MPa)": mech.get("tensile_mpa", ""),
            "Ngày tạo": str(r["created_at"])[:16].replace("T", " "),
        })
    return pd.DataFrame(out)


def assign_to_components(
    db: DB,
    material_id: int,
    component_codes: list[str],
    pid: int,
    assigned_by: str,
) -> tuple[int, list[str]]:
    """Link heat_no với nhiều cấu kiện theo code. Trả về (n_ok, not_found_codes)."""
    not_found = []
    n_ok = 0
    for code in component_codes:
        code = code.strip()
        if not code:
            continue
        comp = db.find_component(pid, code)
        if not comp:
            not_found.append(code)
            continue
        ok = db.assign_material(material_id, comp["id"], assigned_by=assigned_by)
        if ok:
            n_ok += 1
    db.conn.commit()
    db.log(assigned_by, "MATERIAL_ASSIGN", "materials", material_id,
           f"n_ok={n_ok}")
    return n_ok, not_found


def get_traceability_for_component(db: DB, component_id: int) -> list[dict]:
    """Truy xuất vật liệu của 1 cấu kiện."""
    rows = db.list_material_for_component(component_id)
    out = []
    for r in rows:
        try:
            chem = json.loads(r["chemical"]) if r["chemical"] else {}
            mech = json.loads(r["mechanical"]) if r["mechanical"] else {}
        except (json.JSONDecodeError, TypeError):
            chem, mech = {}, {}
        out.append({
            "heat_no": r["heat_no"],
            "grade": r["grade"],
            "supplier": r["supplier"],
            "origin": r["origin"],
            "cert_no": r["cert_no"],
            "test_date": r["test_date"],
            "chemical": chem,
            "mechanical": mech,
        })
    return out


def get_components_for_material(db: DB, material_id: int) -> pd.DataFrame:
    rows = db.list_components_for_material(material_id)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "ID": r["id"],
        "Mã cấu kiện": r["code"],
        "Trạng thái": r["status"],
    } for r in rows])


# ====================================================================
# MILL CERT PDF PARSER (best-effort)
# ====================================================================
def parse_mill_cert_pdf(pdf_bytes: bytes) -> dict:
    """
    Best-effort parse mill certificate PDF.
    Extract: heat_no, grade, chemical composition.

    Cần pdfplumber. Nếu không có → trả {} với note.
    """
    try:
        import pdfplumber
    except ImportError:
        return {"_error": "Cần cài pdfplumber để parse PDF"}

    result: dict = {"heat_no": None, "grade": None, "chemical": {}, "mechanical": {}}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        return {"_error": f"Đọc PDF lỗi: {e}"}

    # Heat number
    heat_patterns = [
        r'[Hh]eat\s*[Nn]o\.?\s*:?\s*([A-Z0-9\-/]+)',
        r'[Ss]ố\s*mẻ\s*:?\s*([A-Z0-9\-/]+)',
        r'[Cc]harge\s*[Nn]o\.?\s*:?\s*([A-Z0-9\-/]+)',
    ]
    for pat in heat_patterns:
        m = re.search(pat, text)
        if m:
            result["heat_no"] = m.group(1).strip()
            break

    # Grade
    grade_pat = r'\b(SS\s?\d{3}|A\s?\d{2,3}|S\s?\d{3}[A-Z]{0,3}|SM\s?\d{3}[A-Z]?|Q\s?\d{3}[A-Z]?)\b'
    m = re.search(grade_pat, text)
    if m:
        result["grade"] = m.group(1).replace(" ", "")

    # Chemical
    for elem in COMMON_ELEMENTS:
        pat = rf'(?:^|\s){elem}\s*[:=]?\s*([0-9]+\.[0-9]+)'
        m = re.search(pat, text, re.MULTILINE)
        if m:
            try:
                result["chemical"][elem] = float(m.group(1))
            except ValueError:
                pass

    # Mechanical
    mech_patterns = {
        "yield_mpa":      r'[Yy]ield\s*(?:strength)?\s*[:=]?\s*([0-9]+)',
        "tensile_mpa":    r'[Tt]ensile\s*(?:strength)?\s*[:=]?\s*([0-9]+)',
        "elongation_pct": r'[Ee]longation\s*[:=]?\s*([0-9]+\.?[0-9]*)',
        "impact_J":       r'[Ii]mpact\s*[:=]?\s*([0-9]+)',
    }
    for k, pat in mech_patterns.items():
        m = re.search(pat, text)
        if m:
            try:
                result["mechanical"][k] = float(m.group(1))
            except ValueError:
                pass

    return result
