# -*- coding: utf-8 -*-
"""
Service: Share Token cho Client Portal — link view-only cho CĐT/Tư vấn.

Bảo mật:
- Token random 32 bytes urlsafe (~43 ký tự).
- Password optional, hash SHA256.
- Hết hạn tự động (expires_at).
- Track view_count + last_viewed_at để audit.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

import pandas as pd

from streamlit_qc.core.db import DB


def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def create_token(
    db: DB,
    pid: int,
    label: str = "",
    days_valid: int = 30,
    password: str | None = None,
    created_by: str | None = None,
) -> str:
    """Tạo share token mới. Trả về token string."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(days=int(days_valid))).isoformat()
    pwd_hash = _hash_password(password) if password else None
    db.add_share_token(
        token=token, pid=pid, label=label, expires_at=expires_at,
        password_hash=pwd_hash, created_by=created_by,
    )
    db.conn.commit()
    db.log(created_by or "", "SHARE_CREATE", "share_tokens", 0,
           f"label={label} days={days_valid}")
    return token


def validate_token(
    db: DB,
    token: str,
    password: str | None = None,
) -> tuple[int | None, str]:
    """
    Validate. Trả về (project_id, message). pid=None nếu invalid.

    message: "ok" | "not_found" | "expired" | "need_password" | "wrong_password"
    """
    if not token:
        return None, "not_found"
    row = db.get_share_token(token)
    if not row:
        return None, "not_found"

    # Expiry
    expires = row["expires_at"]
    if expires:
        try:
            exp_dt = datetime.fromisoformat(str(expires)[:19])
            if datetime.now() > exp_dt:
                return None, "expired"
        except ValueError:
            pass

    # Password
    pwd_hash = row["password_hash"]
    if pwd_hash:
        if not password:
            return None, "need_password"
        if _hash_password(password) != pwd_hash:
            return None, "wrong_password"

    # Track view
    db.increment_share_view(token)
    db.conn.commit()
    return row["project_id"], "ok"


def list_tokens_df(db: DB, pid: int) -> pd.DataFrame:
    rows = db.list_share_tokens(pid)
    if not rows:
        return pd.DataFrame()
    out = []
    for r in rows:
        out.append({
            "Token (8 ký tự đầu)": (r["token"] or "")[:8] + "...",
            "Token đầy đủ": r["token"],
            "Mô tả": r["label"] or "",
            "Hết hạn": str(r["expires_at"])[:19].replace("T", " ") if r["expires_at"] else "—",
            "Lượt xem": r["view_count"] or 0,
            "Xem gần nhất": (str(r["last_viewed_at"])[:16].replace("T", " ")
                              if r["last_viewed_at"] else "—"),
            "Tạo bởi": r["created_by"] or "",
            "Ngày tạo": str(r["created_at"])[:16].replace("T", " "),
        })
    return pd.DataFrame(out)


def revoke_token(db: DB, token: str, by_user: str = "") -> None:
    db.delete_share_token(token)
    db.conn.commit()
    db.log(by_user, "SHARE_REVOKE", "share_tokens", 0, f"token={token[:8]}...")


def build_share_url(base_url: str, token: str) -> str:
    """Trả về URL share. base_url ví dụ 'https://qc-daidung.streamlit.app'."""
    base = base_url.rstrip("/")
    return f"{base}/share?token={token}"
