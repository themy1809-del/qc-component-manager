# -*- coding: utf-8 -*-
"""Service: Quản lý comment trên cấu kiện."""
from __future__ import annotations

from streamlit_qc.core.db import DB


def add_comment(db: DB, cid: int, user_name: str, text: str) -> int:
    """Thêm comment cho cấu kiện. Trả về comment id."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Comment không được rỗng.")
    if len(text) > 2000:
        raise ValueError("Comment quá dài (max 2000 ký tự).")

    cur = db.conn.execute(
        "INSERT INTO comments (component_id, user_name, text) VALUES (?, ?, ?)",
        (cid, user_name or "anonymous", text),
    )
    db.conn.commit()
    db.log(user_name, "ADD_COMMENT", "component", cid, text[:100])
    return cur.lastrowid


def list_comments(db: DB, cid: int, limit: int = 100) -> list[dict]:
    """List comment cho 1 cấu kiện, mới nhất lên đầu."""
    rows = db.conn.execute(
        """SELECT id, user_name, text, ts
           FROM comments WHERE component_id = ?
           ORDER BY id DESC LIMIT ?""",
        (cid, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_comment(db: DB, comment_id: int, user_name: str) -> bool:
    """Xóa comment. Chỉ author hoặc admin xóa được."""
    row = db.conn.execute(
        "SELECT user_name, component_id FROM comments WHERE id = ?",
        (comment_id,),
    ).fetchone()
    if not row:
        return False
    if row["user_name"] != user_name and user_name != "admin":
        return False
    db.conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    db.conn.commit()
    db.log(user_name, "DEL_COMMENT", "comment", comment_id,
           f"by={user_name}, on_comp={row['component_id']}")
    return True


def count_comments(db: DB, cids: list[int]) -> dict[int, int]:
    """Đếm số comment cho list cấu kiện. Trả về dict {cid: count}."""
    if not cids:
        return {}
    placeholders = ",".join("?" * len(cids))
    rows = db.conn.execute(
        f"""SELECT component_id, COUNT(*) c FROM comments
            WHERE component_id IN ({placeholders})
            GROUP BY component_id""",
        cids,
    ).fetchall()
    return {r["component_id"]: r["c"] for r in rows}
