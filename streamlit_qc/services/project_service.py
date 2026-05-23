# -*- coding: utf-8 -*-
"""Service: quản lý dự án (CRUD basic)."""
from __future__ import annotations

import sqlite3

from streamlit_qc.core.db import DB


def list_projects(db: DB) -> list[sqlite3.Row]:
    """Danh sách dự án, mới nhất lên đầu."""
    return db.list_projects()


def get_project(db: DB, pid: int) -> sqlite3.Row | None:
    return db.get_project(pid)


def create_project(
    db: DB,
    code: str,
    name: str,
    location: str = "",
    owner: str = "",
    note: str = "",
    user_name: str = "system",
) -> int:
    """
    Tạo dự án mới.

    Raises:
        ValueError: nếu code hoặc name rỗng.
        sqlite3.IntegrityError: nếu code đã tồn tại.
    """
    code = (code or "").strip()
    name = (name or "").strip()
    if not code:
        raise ValueError("Mã dự án không được để trống.")
    if not name:
        raise ValueError("Tên dự án không được để trống.")
    pid = db.create_project(code, name, location.strip(), owner.strip(), note.strip())
    db.log(user_name, "CREATE_PROJECT", "project", pid, f"code={code}, name={name}")
    return pid
