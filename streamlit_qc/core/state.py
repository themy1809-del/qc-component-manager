# -*- coding: utf-8 -*-
"""
Helpers cho st.session_state + cached DB singleton.

DB connection:
- Nếu st.secrets["DATABASE_URL"] có (Streamlit Cloud) → Postgres (Supabase)
- Hoặc env var DATABASE_URL → Postgres
- Fallback → SQLite local file `streamlit_qc/data/qc_components.db`
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from streamlit_qc.core.constants import DB_FILENAME
from streamlit_qc.core.db import DB


# ====================================================================
# Resolve DB connection string
# ====================================================================
def _resolve_db_dsn() -> str:
    """Tìm DATABASE_URL theo thứ tự: st.secrets → env var → SQLite local."""
    # 1. Streamlit secrets (cloud deploy)
    try:
        if "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"]).strip()
    except Exception:
        pass

    # 2. Env var (local dev với .env hoặc CLI export)
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url.strip()

    # 3. Fallback SQLite local
    base = Path(__file__).resolve().parent.parent  # streamlit_qc/
    data_dir = base / "data"
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / DB_FILENAME)


# ====================================================================
# DB SINGLETON
# ====================================================================
@st.cache_resource
def get_db() -> DB:
    """
    Trả về DB instance dùng chung. Tự detect SQLite local vs Postgres cloud.
    """
    dsn = _resolve_db_dsn()
    return DB(dsn)


# ====================================================================
# SESSION STATE KEYS
# ====================================================================
S_CURRENT_USER = "current_user"
S_CURRENT_PROJECT_ID = "current_project_id"


def init_session_state() -> None:
    if S_CURRENT_USER not in st.session_state:
        st.session_state[S_CURRENT_USER] = (
            os.getenv("USERNAME") or os.getenv("USER") or "qc_user"
        )
    if S_CURRENT_PROJECT_ID not in st.session_state:
        st.session_state[S_CURRENT_PROJECT_ID] = None


def get_current_user() -> str:
    return st.session_state.get(S_CURRENT_USER, "qc_user")


def get_current_project_id() -> int | None:
    return st.session_state.get(S_CURRENT_PROJECT_ID)


def set_current_project_id(pid: int | None) -> None:
    st.session_state[S_CURRENT_PROJECT_ID] = pid
