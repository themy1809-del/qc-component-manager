# -*- coding: utf-8 -*-
"""
Service: chức năng quản trị (audit log, project CRUD, backup/restore DB).
"""
from __future__ import annotations

import datetime as dt
import io
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pandas as pd

from streamlit_qc.core.db import DB


# ====================================================================
# AUDIT LOG
# ====================================================================
def query_audit_log(
    db: DB,
    user: str = "",
    action: str = "",
    entity: str = "",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """Query audit log với filter."""
    sql = "SELECT * FROM audit_log WHERE 1=1"
    params: list = []
    if user:
        sql += " AND user_name LIKE ?"
        params.append(f"%{user}%")
    if action:
        sql += " AND action LIKE ?"
        params.append(f"%{action}%")
    if entity:
        sql += " AND entity LIKE ?"
        params.append(f"%{entity}%")
    if date_from:
        sql += " AND ts >= ?"
        params.append(date_from.isoformat())
    if date_to:
        sql += " AND ts <= ?"
        params.append(date_to.isoformat() + " 23:59:59")
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return pd.read_sql_query(sql, db.conn, params=params)


def get_audit_stats(db: DB) -> dict:
    """Tổng quan audit log."""
    total = db.conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    by_action = db.conn.execute(
        "SELECT action, COUNT(*) c FROM audit_log GROUP BY action ORDER BY c DESC LIMIT 10"
    ).fetchall()
    by_user = db.conn.execute(
        "SELECT user_name, COUNT(*) c FROM audit_log GROUP BY user_name ORDER BY c DESC LIMIT 10"
    ).fetchall()
    return {
        "total": total,
        "by_action": [{"action": r["action"], "count": r["c"]} for r in by_action],
        "by_user": [{"user": r["user_name"] or "(rỗng)", "count": r["c"]} for r in by_user],
    }


# ====================================================================
# PROJECT CRUD
# ====================================================================
def update_project(
    db: DB,
    pid: int,
    name: str | None = None,
    location: str | None = None,
    owner: str | None = None,
    note: str | None = None,
    user_name: str = "admin",
) -> bool:
    """Update info của 1 dự án."""
    updates: list[tuple[str, str]] = []
    if name is not None:
        updates.append(("name", name.strip()))
    if location is not None:
        updates.append(("location", location.strip()))
    if owner is not None:
        updates.append(("owner", owner.strip()))
    if note is not None:
        updates.append(("note", note.strip()))

    if not updates:
        return False

    set_clause = ", ".join(f"{k}=?" for k, _ in updates)
    params = [v for _, v in updates] + [pid]
    db.conn.execute(f"UPDATE projects SET {set_clause} WHERE id=?", params)
    db.conn.commit()
    db.log(
        user_name, "UPDATE_PROJECT", "project", pid,
        ", ".join(f"{k}={v}" for k, v in updates),
    )
    return True


def delete_project(db: DB, pid: int, user_name: str = "admin") -> dict:
    """
    Xoá toàn bộ 1 dự án (cascade: components + inspections + mappings).

    Returns:
        {components, inspections, mappings} - số rows đã xoá.
    """
    proj = db.get_project(pid)
    if not proj:
        return {"error": "Project not found"}

    n_comp = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,)
    ).fetchone()["c"]
    n_ins = db.conn.execute(
        "SELECT COUNT(*) c FROM inspections WHERE project_id=?", (pid,)
    ).fetchone()["c"]
    n_map = db.conn.execute(
        "SELECT COUNT(*) c FROM column_mappings WHERE project_id=?", (pid,)
    ).fetchone()["c"]

    # ON DELETE CASCADE đã setup trong schema → DELETE projects sẽ xoá hết
    db.conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    db.conn.commit()

    db.log(
        user_name, "DELETE_PROJECT", "project", pid,
        f"code={proj['code']}, components={n_comp}, inspections={n_ins}",
    )
    return {
        "components": n_comp,
        "inspections": n_ins,
        "mappings": n_map,
    }


def reset_inspections(db: DB, pid: int, user_name: str = "admin") -> int:
    """
    Xoá toàn bộ inspections của 1 dự án, reset status component về PENDING.
    Giữ nguyên components.
    """
    n = db.conn.execute(
        "SELECT COUNT(*) c FROM inspections WHERE project_id=?", (pid,)
    ).fetchone()["c"]
    db.conn.execute("DELETE FROM inspections WHERE project_id=?", (pid,))
    db.conn.execute(
        "UPDATE components SET status='PENDING' WHERE project_id=?", (pid,)
    )
    db.conn.commit()
    db.log(user_name, "RESET_INSPECTIONS", "project", pid, f"deleted={n}")
    return n


# ====================================================================
# BACKUP / RESTORE
# ====================================================================
def _to_sqlite_val(v):
    """Chuyen gia tri Postgres -> dang SQLite luu duoc (datetime/Decimal... -> str)."""
    if v is None or isinstance(v, (int, float, str, bytes)):
        return v
    return str(v)


def _backup_postgres(db: DB) -> bytes:
    """Backup Postgres (Supabase) -> file SQLite snapshot -> zip bytes (tai ve duoc)."""
    import tempfile
    tmp_path = Path(tempfile.gettempdir()) / f"qc_snapshot_{dt.datetime.now():%Y%m%d_%H%M%S}.db"
    sq = sqlite3.connect(str(tmp_path))
    counts = {}
    try:
        trows = db.conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ).fetchall()
        tables = [dict(r)["table_name"] for r in trows]
    except Exception:
        tables = []
    if not tables:
        tables = [
            "projects", "components", "inspections", "column_mappings", "audit_log",
            "users", "comments", "ncrs", "rfis", "itp_templates", "itp_records",
            "batches", "batch_items", "materials", "material_assignments",
            "share_tokens", "qc_reports", "access_log",
        ]
    for t in tables:
        try:
            cur = db.conn.execute('SELECT * FROM "' + t + '"')
            rows = cur.fetchall()
        except Exception:
            continue
        if rows:
            cols = list(dict(rows[0]).keys())
        else:
            desc = getattr(cur, "description", None)
            cols = [d[0] for d in desc] if desc else []
        if not cols:
            continue
        col_def = ", ".join('"' + c + '"' for c in cols)
        sq.execute('CREATE TABLE IF NOT EXISTS "' + t + '" (' + col_def + ')')
        if rows:
            ph = ", ".join("?" * len(cols))
            data = [tuple(_to_sqlite_val(dict(r).get(c)) for c in cols) for r in rows]
            sq.executemany('INSERT INTO "' + t + '" VALUES (' + ph + ')', data)
        counts[t] = len(rows)
    sq.commit()
    sq.close()
    db_bytes = tmp_path.read_bytes()
    try:
        tmp_path.unlink()
    except Exception:
        pass
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("qc_components.db", db_bytes)
        meta = (
            "QC Component Manager - Supabase Postgres snapshot\n"
            f"Created: {dt.datetime.now().isoformat()}\n"
            f"Tables: {len(counts)}\n"
            + "\n".join(f"  {t}: {n}" for t, n in counts.items())
        )
        zf.writestr("README.txt", meta)
    return buf.getvalue()


def backup_db(db: DB) -> bytes:
    """
    Tạo backup .zip chứa file DB (an toàn với WAL).

    Returns:
        Bytes của file .zip để dùng với st.download_button.
    """
    if getattr(db, "is_postgres", False):
        return _backup_postgres(db)

    db_path = Path(db.path)

    # Force checkpoint WAL để đảm bảo dữ liệu nằm hết trong file .db chính
    db.conn.execute("PRAGMA wal_checkpoint(FULL)")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Backup file .db chính
        if db_path.exists():
            zf.write(db_path, arcname=db_path.name)
        # Metadata
        meta = (
            f"QC Component Manager Backup\n"
            f"Created: {dt.datetime.now().isoformat()}\n"
            f"DB file: {db_path.name}\n"
            f"DB size: {db_path.stat().st_size if db_path.exists() else 0} bytes\n"
        )
        zf.writestr("README.txt", meta)

    return buf.getvalue()


def restore_db(db: DB, uploaded_bytes: bytes, user_name: str = "admin") -> dict:
    """
    Restore DB từ file .db hoặc .zip upload.

    CHIẾN LƯỢC AN TOÀN:
    1. Validate file là SQLite valid trước
    2. Backup file hiện tại sang .bak
    3. Đóng connection cũ
    4. Replace file
    5. Mở connection mới (KHÔNG làm vì caller cần re-init)

    LƯU Ý: Sau khi restore, caller PHẢI restart Streamlit (clear @st.cache_resource).

    Returns:
        Dict {success, backup_path, restored_size, error?}
    """
    if getattr(db, "is_postgres", False):
        return {
            "success": False,
            "error": "Restore từ file .db chỉ áp dụng cho SQLite local. "
                     "Với Postgres/Supabase, dữ liệu đã nằm trên cloud — khôi phục qua Supabase.",
        }

    db_path = Path(db.path)
    backup_path = db_path.parent / f"{db_path.stem}.bak"

    # ---- 1. Xác định file là .db hay .zip ----
    is_zip = uploaded_bytes[:4] == b"PK\x03\x04"
    db_bytes: bytes | None = None

    if is_zip:
        try:
            with zipfile.ZipFile(io.BytesIO(uploaded_bytes)) as zf:
                for name in zf.namelist():
                    if name.endswith(".db"):
                        db_bytes = zf.read(name)
                        break
            if db_bytes is None:
                return {"success": False, "error": "Zip không chứa file .db nào."}
        except zipfile.BadZipFile:
            return {"success": False, "error": "File zip không hợp lệ."}
    else:
        db_bytes = uploaded_bytes

    # ---- 2. Validate là SQLite ----
    if not db_bytes.startswith(b"SQLite format 3\x00"):
        return {"success": False, "error": "File không phải SQLite database hợp lệ."}

    # ---- 3. Test mở thử trong memory ----
    try:
        tmp_path = db_path.parent / f".restore_test_{dt.datetime.now():%Y%m%d_%H%M%S}.db"
        tmp_path.write_bytes(db_bytes)
        test_conn = sqlite3.connect(str(tmp_path))
        # Kiểm tra có bảng projects không
        has_projects = test_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        ).fetchone()
        test_conn.close()
        if not has_projects:
            tmp_path.unlink(missing_ok=True)
            return {"success": False, "error": "DB không có bảng 'projects' — không đúng schema QC."}
        tmp_path.unlink(missing_ok=True)
    except sqlite3.DatabaseError as e:
        return {"success": False, "error": f"Lỗi mở DB: {e}"}

    # ---- 4. Backup file hiện tại ----
    if db_path.exists():
        shutil.copy2(db_path, backup_path)

    # ---- 5. Đóng connection cũ + ghi đè ----
    try:
        db.conn.close()
    except Exception:
        pass

    try:
        db_path.write_bytes(db_bytes)
    except Exception as e:
        # Rollback từ backup
        if backup_path.exists():
            shutil.copy2(backup_path, db_path)
        return {"success": False, "error": f"Lỗi ghi file: {e}"}

    return {
        "success": True,
        "backup_path": str(backup_path),
        "restored_size": len(db_bytes),
    }
