# -*- coding: utf-8 -*-
"""
Service: User authentication.

Dùng hashlib (built-in) thay bcrypt để giảm dependency.
Password hash: sha256(salt + password).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from streamlit_qc.core.db import DB


ROLES = ["admin", "qc_lead", "qc_worker", "viewer"]
ROLE_LABELS = {
    "admin": "Quản trị",
    "qc_lead": "Trưởng nhóm QC",
    "qc_worker": "QC viên",
    "viewer": "Xem only",
}


def _hash_password(password: str, salt: str | None = None) -> str:
    """Trả về dạng salt$hash (cho dễ verify)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def _verify_password(password: str, stored: str) -> bool:
    """So sánh password với hash dạng salt$hash."""
    if "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return _hash_password(password, salt) == stored


def ensure_default_admin(db: DB) -> None:
    """Tạo user admin mặc định nếu chưa có user nào.
    Username: admin
    Password: admin123 (NÊN ĐỔI ngay sau login lần đầu)
    """
    row = db.conn.execute("SELECT COUNT(*) c FROM users").fetchone()
    if row and row["c"] > 0:
        return
    db.conn.execute(
        "INSERT INTO users (username, password_hash, full_name, role) "
        "VALUES (?, ?, ?, ?)",
        ("admin", _hash_password("admin123"), "Administrator", "admin"),
    )
    db.conn.commit()


def login(db: DB, username: str, password: str) -> dict | None:
    """Trả về user dict nếu OK, None nếu sai."""
    username = (username or "").strip().lower()
    if not username or not password:
        return None
    row = db.conn.execute(
        "SELECT * FROM users WHERE LOWER(username) = ? AND active = 1",
        (username,),
    ).fetchone()
    if not row:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    # Update last_login
    try:
        db.conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), row["id"]),
        )
        db.conn.commit()
    except Exception:
        pass
    return {
        "id": row["id"], "username": row["username"],
        "full_name": row["full_name"] or row["username"],
        "role": row["role"], "active": row["active"],
    }


def create_user(
    db: DB, username: str, password: str, full_name: str = "",
    role: str = "qc_worker", actor: str = "admin",
) -> int:
    """Tạo user mới. Raises ValueError nếu username đã tồn tại."""
    username = (username or "").strip().lower()
    if not username or len(username) < 3:
        raise ValueError("Username phải ≥ 3 ký tự.")
    if not password or len(password) < 6:
        raise ValueError("Password phải ≥ 6 ký tự.")
    if role not in ROLES:
        raise ValueError(f"Role không hợp lệ. Phải là: {ROLES}")
    existing = db.conn.execute(
        "SELECT id FROM users WHERE LOWER(username) = ?",
        (username,),
    ).fetchone()
    if existing:
        raise ValueError(f"Username '{username}' đã tồn tại.")
    cur = db.conn.execute(
        "INSERT INTO users (username, password_hash, full_name, role) "
        "VALUES (?, ?, ?, ?)",
        (username, _hash_password(password), full_name or username, role),
    )
    db.conn.commit()
    db.log(actor, "CREATE_USER", "user", cur.lastrowid,
           f"username={username}, role={role}")
    return cur.lastrowid


def change_password(db: DB, user_id: int, old_password: str, new_password: str) -> bool:
    """Đổi password. False nếu old sai."""
    row = db.conn.execute(
        "SELECT password_hash, username FROM users WHERE id = ?", (user_id,),
    ).fetchone()
    if not row:
        return False
    if not _verify_password(old_password, row["password_hash"]):
        return False
    if not new_password or len(new_password) < 6:
        raise ValueError("Password mới phải ≥ 6 ký tự.")
    db.conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (_hash_password(new_password), user_id),
    )
    db.conn.commit()
    db.log(row["username"], "CHANGE_PASSWORD", "user", user_id, "")
    return True


def list_users(db: DB) -> list[dict]:
    """List all users."""
    rows = db.conn.execute(
        "SELECT id, username, full_name, role, active, last_login, created_at "
        "FROM users ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def set_user_active(db: DB, user_id: int, active: bool, actor: str = "admin") -> None:
    db.conn.execute(
        "UPDATE users SET active = ? WHERE id = ?",
        (1 if active else 0, user_id),
    )
    db.conn.commit()
    db.log(actor, "SET_USER_ACTIVE", "user", user_id, f"active={active}")


def update_role(db: DB, user_id: int, role: str, actor: str = "admin") -> None:
    if role not in ROLES:
        raise ValueError(f"Role không hợp lệ.")
    db.conn.execute(
        "UPDATE users SET role = ? WHERE id = ?", (role, user_id),
    )
    db.conn.commit()
    db.log(actor, "UPDATE_ROLE", "user", user_id, f"role={role}")


def reset_password(db: DB, user_id: int, new_password: str, actor: str = "admin") -> None:
    """Admin reset password cho user khác (bypass old password check)."""
    if not new_password or len(new_password) < 6:
        raise ValueError("Password phải ≥ 6 ký tự.")
    db.conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (_hash_password(new_password), user_id),
    )
    db.conn.commit()
    db.log(actor, "RESET_PASSWORD", "user", user_id, "")
