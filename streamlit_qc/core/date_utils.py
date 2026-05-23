# -*- coding: utf-8 -*-
"""
Tiện ích ngày tháng — copy nguyên từ Tkinter v1.0.2 dòng 169-256.

QUY TẮC NGHIỆP VỤ (KHÔNG ĐỔI):
- Hiển thị UI: DD/MM/YYYY (kiểu Việt Nam)
- Lưu DB: YYYY-MM-DD (ISO chuẩn)
- Input accept cả 2 định dạng
- Tên file daily có pattern DD.MM.YYYY → auto-extract
"""
from __future__ import annotations

import datetime as dt
import os
import re

import pandas as pd


def extract_date_from_filename(filename: str) -> str | None:
    """
    Tách ngày từ tên file daily. Hỗ trợ 2 pattern:
      - DD.MM.YYYY hoặc DD-MM-YYYY (vd: 15.5.2026 hoặc 16.05.2026)
      - YYYY.MM.DD hoặc YYYY-MM-DD

    Returns:
        Ngày dạng ISO 'YYYY-MM-DD' hoặc None nếu không tìm thấy.
    """
    name = os.path.basename(filename)
    # Pattern 1: DD.MM.YYYY hoặc DD-MM-YYYY
    m = re.search(r"(\d{1,2})[\.\-](\d{1,2})[\.\-](\d{4})", name)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return dt.date(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Pattern 2: YYYY.MM.DD hoặc YYYY-MM-DD
    m = re.search(r"(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})", name)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return dt.date(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def excel_date_to_iso(v) -> str | None:
    """
    Chuyển 1 giá trị Excel (số serial date, datetime, hoặc text) → ISO 'YYYY-MM-DD'.

    Args:
        v: Giá trị thô từ pandas (int/float = Excel serial, datetime, hoặc text).

    Returns:
        Chuỗi ISO hoặc None nếu rỗng/NaN.
    """
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        try:
            return (dt.datetime(1899, 12, 30) + dt.timedelta(days=float(v))).strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            return str(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    return str(v)


def format_date_vn(iso_or_text: str | None) -> str:
    """
    Chuyển YYYY-MM-DD → DD/MM/YYYY để hiển thị kiểu Việt Nam.

    Nếu chuỗi đã ở định dạng khác (vd DD/MM/YYYY hoặc text), giữ nguyên.

    Args:
        iso_or_text: Chuỗi ISO 'YYYY-MM-DD' hoặc bất kỳ text nào.

    Returns:
        Chuỗi hiển thị (DD/MM/YYYY) hoặc rỗng nếu input rỗng.
    """
    if not iso_or_text:
        return ""
    s = str(iso_or_text).strip()
    if not s:
        return ""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{int(d):02d}/{int(mo):02d}/{y}"
    return s


def parse_date_input(text: str | None) -> str:
    """
    Parse input từ user. Accept:
      - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
      - YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD

    Returns:
        Chuỗi ISO 'YYYY-MM-DD' nếu parse được, ngược lại trả nguyên text.
    """
    if not text:
        return ""
    s = str(text).strip()
    # DD/MM/YYYY hoặc DD-MM-YYYY hoặc DD.MM.YYYY
    m = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", s)
    if m:
        d, mo, y = m.groups()
        try:
            return dt.date(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            return s
    # YYYY-MM-DD
    m = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", s)
    if m:
        y, mo, d = m.groups()
        try:
            return dt.date(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            return s
    return s


def parse_remark_types(remark: str | None) -> list[str]:
    """
    Parse cột Remark dạng "Dim,Visual,NDT" → danh sách loại inspection.

    Dùng cho logic DGRP: 1 dòng Excel có thể sinh nhiều inspection records.

    Args:
        remark: Text từ cột Remark, vd "Dim, Visual, NDT" hoặc "FUR, MT".

    Returns:
        Danh sách loại unique, vd ["DIR", "VIR", "NDT"].
        Trả [] nếu remark rỗng/không nhận được keyword nào (caller fallback ["DIR"]).
    """
    # Lazy import để tránh circular
    from streamlit_qc.core.constants import REMARK_TO_TYPES

    if not remark or not isinstance(remark, str):
        return []
    text = remark.upper()
    found: list[str] = []
    for kw, t in REMARK_TO_TYPES.items():
        if kw in text and t not in found:
            found.append(t)
    return found
