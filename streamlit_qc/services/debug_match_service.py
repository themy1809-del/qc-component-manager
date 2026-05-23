# -*- coding: utf-8 -*-
"""
Service: Debug Match — chẩn đoán khi import daily không khớp.

Tương đương `_debug_match` trong Tkinter dòng 1001-1043.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from streamlit_qc.core.db import DB
from streamlit_qc.services.daily_import_service import (
    PREFIX_PATTERN,
    SKIP_CODES,
    _generate_match_candidates,
)


@dataclass
class DebugMatchReport:
    """Report cho UI hiển thị."""
    master_total: int = 0
    master_samples: list[str] = field(default_factory=list)  # 10 mã đầu
    daily_total: int = 0
    daily_results: list[dict] = field(default_factory=list)
    # Mỗi item: {raw, stripped, found, candidate_matched}


def debug_match(
    db: DB,
    pid: int,
    df: pd.DataFrame | None,
    code_col: str | None,
    sample_size: int = 10,
) -> DebugMatchReport:
    """
    Sinh report chẩn đoán: so 10 mã master vs 10 mã daily.

    Args:
        db: DB.
        pid: project id.
        df: DataFrame daily đã đọc (có thể None nếu chưa đọc).
        code_col: tên cột chứa mã trong df.
        sample_size: số mã lấy mẫu mỗi bên.

    Returns:
        DebugMatchReport.
    """
    report = DebugMatchReport()

    # --- Master samples ---
    master_total = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?",
        (pid,),
    ).fetchone()["c"]
    report.master_total = master_total

    master_rows = db.conn.execute(
        "SELECT code FROM components WHERE project_id=? ORDER BY code LIMIT ?",
        (pid, sample_size),
    ).fetchall()
    report.master_samples = [r["code"] for r in master_rows]

    # --- Daily samples ---
    if df is None or code_col is None or code_col not in df.columns:
        return report

    report.daily_total = len(df)
    shown = 0
    for _, row in df.iterrows():
        if shown >= sample_size:
            break
        v = row.get(code_col)
        if pd.isna(v):
            continue
        code = str(v).strip()
        if not code or len(code) <= 2 or code.upper() in SKIP_CODES:
            continue

        # Sinh tất cả candidates
        candidates = _generate_match_candidates(code)
        stripped = candidates[1] if len(candidates) > 1 else code

        # Check match với master
        matched_candidate = None
        for cand in candidates:
            if db.find_component(pid, cand):
                matched_candidate = cand
                break

        report.daily_results.append({
            "raw": code,
            "stripped": stripped if stripped != code else "—",
            "found": matched_candidate is not None,
            "matched_with": matched_candidate or "",
        })
        shown += 1

    return report
