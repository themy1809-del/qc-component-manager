# -*- coding: utf-8 -*-
"""
Service: RFI (Request for Inspection) Management.

State machine:
  SUBMITTED → CONFIRMED → IN_PROGRESS → COMPLETED → CLOSED
  SUBMITTED → REJECTED (với reason)
"""
from __future__ import annotations

import pandas as pd

from streamlit_qc.core.db import DB


RFI_STATUSES = ("SUBMITTED", "CONFIRMED", "REJECTED",
                "IN_PROGRESS", "COMPLETED", "CLOSED")
INSPECTION_TYPES = ("FUR", "DIR", "VIR", "NDT", "DGRP", "PAINT")

STATUS_LABEL = {
    "SUBMITTED":   "📨 Đã gửi",
    "CONFIRMED":   "✅ Đã xác nhận",
    "REJECTED":    "❌ Từ chối",
    "IN_PROGRESS": "🔧 Đang KT",
    "COMPLETED":   "🏁 Hoàn tất",
    "CLOSED":      "⚫ Đóng",
}

TYPE_LABEL = {
    "FUR":   "FUR — Fit-up",
    "DIR":   "DIR — Dimension",
    "VIR":   "VIR — Visual",
    "NDT":   "NDT — Không phá huỷ",
    "DGRP":  "DGRP — Final",
    "PAINT": "PAINT — Sơn",
}


def submit_rfi(
    db: DB,
    pid: int,
    project_code: str,
    component_code: str,
    inspection_type: str,
    proposed_date: str,
    submitted_by: str,
    is_hold_point: bool = False,
    witness_required: str | None = None,
) -> tuple[int, str]:
    """Submit RFI mới. Trả về (id, rfi_no)."""
    comp = db.find_component(pid, component_code)
    if not comp:
        raise ValueError(f"Không tìm thấy cấu kiện: {component_code}")

    rfi_no = db.get_next_rfi_no(pid, project_code)
    rid = db.add_rfi(
        pid=pid,
        component_id=comp["id"],
        rfi_no=rfi_no,
        inspection_type=inspection_type,
        proposed_date=proposed_date,
        submitted_by=submitted_by,
        is_hold_point=1 if is_hold_point else 0,
        witness_required=witness_required,
    )
    db.conn.commit()
    db.log(submitted_by or "", "RFI_SUBMIT", "rfis", rid,
           f"rfi_no={rfi_no} type={inspection_type}")
    return rid, rfi_no


def confirm_rfi(db: DB, rfi_id: int, confirmed_date: str,
                inspector: str, note: str = "") -> None:
    db.update_rfi_status(rfi_id, "CONFIRMED",
                         confirmed_date=confirmed_date, response_note=note)
    db.conn.commit()
    db.log(inspector, "RFI_CONFIRM", "rfis", rfi_id, f"date={confirmed_date}")


def reject_rfi(db: DB, rfi_id: int, inspector: str, reason: str) -> None:
    db.update_rfi_status(rfi_id, "REJECTED", response_note=reason)
    db.conn.commit()
    db.log(inspector, "RFI_REJECT", "rfis", rfi_id, f"reason={reason[:80]}")


def complete_rfi(db: DB, rfi_id: int, by_user: str) -> None:
    db.update_rfi_status(rfi_id, "COMPLETED")
    db.conn.commit()
    db.log(by_user, "RFI_COMPLETE", "rfis", rfi_id, "")


def close_rfi(db: DB, rfi_id: int, by_user: str) -> None:
    db.update_rfi_status(rfi_id, "CLOSED")
    db.conn.commit()
    db.log(by_user, "RFI_CLOSE", "rfis", rfi_id, "")


def list_rfis_df(db: DB, pid: int, status: str | None = None) -> pd.DataFrame:
    rows = db.list_rfis(pid, status=status)
    if not rows:
        return pd.DataFrame()
    out = []
    for r in rows:
        out.append({
            "ID": r["id"],
            "Số RFI": r["rfi_no"],
            "Cấu kiện": r["component_code"] or "—",
            "Loại KT": TYPE_LABEL.get(r["inspection_type"], r["inspection_type"]),
            "Ngày đề xuất": r["proposed_date"] or "",
            "Ngày xác nhận": r["confirmed_date"] or "",
            "Trạng thái": STATUS_LABEL.get(r["status"], r["status"]),
            "Hold Point": "🛑 YES" if r["is_hold_point"] else "—",
            "Witness": r["witness_required"] or "",
            "Người gửi": r["submitted_by"] or "",
            "Ghi chú": r["response_note"] or "",
            "Ngày tạo": str(r["created_at"])[:16].replace("T", " "),
        })
    return pd.DataFrame(out)


def counts(db: DB, pid: int) -> dict[str, int]:
    return db.count_rfis_by_status(pid)
