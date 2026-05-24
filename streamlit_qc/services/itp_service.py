# -*- coding: utf-8 -*-
"""
Service: ITP (Inspection Test Plan) Template + Engine.

Mô hình:
- Template chứa danh sách checkpoints (JSON array):
  [{"seq":1, "name":"Dim Check", "hold_type":"WITNESS", "required":true}, ...]
- Mỗi cấu kiện đi qua từng checkpoint theo seq.
- hold_type:
    HOLD    — phải có witness_by + witness_at trước khi PASS
    WITNESS — thông báo, CĐT có thể bỏ qua (auto PASS)
    REVIEW  — internal only, không cần witness
"""
from __future__ import annotations

import json

from streamlit_qc.core.db import DB


HOLD_TYPES = ("HOLD", "WITNESS", "REVIEW")
HOLD_TYPE_LABEL = {
    "HOLD":    "🛑 HOLD — bắt buộc witness",
    "WITNESS": "👁️ WITNESS — CĐT chứng kiến",
    "REVIEW":  "📝 REVIEW — nội bộ",
}

CP_RESULT = ("PASS", "FAIL", "PENDING", "HOLD_WAITING")
CP_RESULT_LABEL = {
    "PASS":         "✅ PASS",
    "FAIL":         "❌ FAIL",
    "PENDING":      "⏳ PENDING",
    "HOLD_WAITING": "🛑 CHỜ WITNESS",
}


# ====================================================================
# TEMPLATE CRUD
# ====================================================================
def create_template(
    db: DB,
    pid: int,
    name: str,
    component_type: str | None,
    checkpoints: list[dict],
) -> int:
    """Tạo ITP template. checkpoints = list of dict với keys seq/name/hold_type/required."""
    # Validate
    for cp in checkpoints:
        if "seq" not in cp or "name" not in cp:
            raise ValueError("Mỗi checkpoint cần có 'seq' và 'name'.")
        cp.setdefault("hold_type", "REVIEW")
        cp.setdefault("required", True)
    return db.add_itp_template(pid, name, component_type, checkpoints)


def list_templates_df(db: DB, pid: int):
    import pandas as pd
    rows = db.list_itp_templates(pid)
    if not rows:
        return pd.DataFrame()
    out = []
    for r in rows:
        try:
            cps = json.loads(r["checkpoints"])
        except (json.JSONDecodeError, TypeError):
            cps = []
        out.append({
            "ID": r["id"],
            "Tên template": r["name"],
            "Loại CK": r["component_type"] or "(mọi loại)",
            "Số checkpoint": len(cps),
            "Hold Points": sum(1 for c in cps if c.get("hold_type") == "HOLD"),
            "Ngày tạo": str(r["created_at"])[:16].replace("T", " "),
        })
    return pd.DataFrame(out)


def get_template_checkpoints(db: DB, tid: int) -> list[dict]:
    r = db.get_itp_template(tid)
    if not r:
        return []
    try:
        return json.loads(r["checkpoints"])
    except (json.JSONDecodeError, TypeError):
        return []


# ====================================================================
# ENGINE: chạy ITP cho 1 cấu kiện
# ====================================================================
def submit_checkpoint(
    db: DB,
    component_id: int,
    template_id: int,
    checkpoint_seq: int,
    result: str,           # PASS | FAIL | HOLD_WAITING
    inspector: str,
    remarks: str = "",
) -> dict:
    """
    Ghi kết quả 1 checkpoint.

    Trả về dict:
      {"ok": True, "next_action": "continue"}              — checkpoint OK, tiếp tục
      {"ok": True, "next_action": "hold_waiting", ...}      — cần witness
      {"ok": True, "next_action": "all_passed"}             — tất cả CP PASS → ACCEPTED
      {"ok": False, "error": "..."}
    """
    tpl = db.get_itp_template(template_id)
    if not tpl:
        return {"ok": False, "error": "Template không tồn tại"}
    try:
        cps = json.loads(tpl["checkpoints"])
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "error": "Checkpoints JSON lỗi"}

    cp = next((c for c in cps if int(c.get("seq", 0)) == checkpoint_seq), None)
    if not cp:
        return {"ok": False, "error": f"Checkpoint seq={checkpoint_seq} không tồn tại"}

    hold_type = cp.get("hold_type", "REVIEW")
    db_result = result.upper()

    # Nếu là HOLD POINT và PASS → cần witness trước khi ghi PASS
    if hold_type == "HOLD" and db_result == "PASS":
        db_result = "HOLD_WAITING"

    db.upsert_itp_record(
        component_id=component_id,
        template_id=template_id,
        checkpoint_seq=checkpoint_seq,
        checkpoint_name=cp.get("name", "?"),
        hold_type=hold_type,
        result=db_result,
        inspector=inspector,
        remarks=remarks,
    )
    db.conn.commit()
    db.log(inspector, "ITP_CHECKPOINT", "itp_records", component_id,
           f"seq={checkpoint_seq} result={db_result}")

    if db_result == "HOLD_WAITING":
        return {
            "ok": True, "next_action": "hold_waiting",
            "checkpoint": cp.get("name"),
            "witness_required": cp.get("witness_required", "CĐT/Tư vấn"),
        }

    # Check tất cả CP required đã PASS chưa
    records = db.list_itp_records(component_id)
    passed_seq = {r["checkpoint_seq"] for r in records if r["result"] == "PASS"}
    required_seq = {int(c["seq"]) for c in cps if c.get("required", True)}

    if required_seq.issubset(passed_seq) and result.upper() == "PASS":
        # Tất cả CP required PASS → ACCEPTED
        db.conn.execute(
            "UPDATE components SET status='ACCEPTED' WHERE id=?",
            (component_id,),
        )
        db.conn.commit()
        db.log(inspector, "ITP_ALL_PASSED", "components", component_id,
               f"template={template_id}")
        return {"ok": True, "next_action": "all_passed"}

    return {"ok": True, "next_action": "continue"}


def witness_checkpoint(db: DB, component_id: int, checkpoint_seq: int,
                       witness_by: str) -> bool:
    """CĐT/Tư vấn ký witness → unlock checkpoint từ HOLD_WAITING → PASS."""
    ok = db.witness_itp_record(component_id, checkpoint_seq, witness_by)
    if ok:
        db.conn.commit()
        db.log(witness_by, "ITP_WITNESS", "itp_records", component_id,
               f"seq={checkpoint_seq}")
    return ok


def get_progress(db: DB, component_id: int) -> dict:
    """Lấy tiến độ ITP cho 1 cấu kiện."""
    records = db.list_itp_records(component_id)
    total = len(records)
    passed = sum(1 for r in records if r["result"] == "PASS")
    failed = sum(1 for r in records if r["result"] == "FAIL")
    waiting = sum(1 for r in records if r["result"] == "HOLD_WAITING")
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "hold_waiting": waiting,
        "records": records,
    }


# ====================================================================
# PRESET — Template mẫu cho ngành thép
# ====================================================================
DEFAULT_TEMPLATES = {
    "Dầm thép H (Beam)": [
        {"seq": 1, "name": "Dimension Check (kích thước)", "hold_type": "WITNESS", "required": True},
        {"seq": 2, "name": "Fit-up Inspection (gá lắp)",     "hold_type": "HOLD",    "required": True},
        {"seq": 3, "name": "NDT — VT (Visual welding)",       "hold_type": "REVIEW",  "required": True},
        {"seq": 4, "name": "NDT — MT/PT/UT (nếu có)",         "hold_type": "WITNESS", "required": False},
        {"seq": 5, "name": "Surface preparation",             "hold_type": "REVIEW",  "required": True},
        {"seq": 6, "name": "Paint DFT check",                 "hold_type": "REVIEW",  "required": True},
        {"seq": 7, "name": "Final Inspection (nghiệm thu)",   "hold_type": "HOLD",    "required": True},
    ],
    "Cột ống tròn (Tubular column)": [
        {"seq": 1, "name": "Dimension Check",         "hold_type": "WITNESS", "required": True},
        {"seq": 2, "name": "Fit-up Inspection",        "hold_type": "HOLD",    "required": True},
        {"seq": 3, "name": "NDT — UT (siêu âm mối hàn)", "hold_type": "WITNESS", "required": True},
        {"seq": 4, "name": "Paint DFT check",          "hold_type": "REVIEW",  "required": True},
        {"seq": 5, "name": "Final Inspection",         "hold_type": "HOLD",    "required": True},
    ],
    "Tấm thép phẳng (Plate)": [
        {"seq": 1, "name": "Dimension + Flatness",   "hold_type": "WITNESS", "required": True},
        {"seq": 2, "name": "Surface preparation",     "hold_type": "REVIEW",  "required": True},
        {"seq": 3, "name": "Paint DFT check",         "hold_type": "REVIEW",  "required": True},
        {"seq": 4, "name": "Final Inspection",        "hold_type": "HOLD",    "required": True},
    ],
}
