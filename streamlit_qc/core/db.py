# -*- coding: utf-8 -*-
"""
Database layer — Dual backend: SQLite (local) + PostgreSQL (Supabase cloud).

Tự detect backend từ connection string:
- "postgresql://..." hoặc "postgres://..." → Postgres (Supabase)
- Else → SQLite file path (local)

API public không đổi — toàn bộ service code dùng `db.conn.execute(...)` như cũ.
Lớp `_PgConnAdapter` ở dưới làm cầu nối: dịch `?` → `%s`, chia executescript thành nhiều execute.

QUY TẮC NGHIỆP VỤ ACCEPTED GIỮ NGUYÊN:
- DGRP (Final) PASS → ACCEPTED
- DGRP (Final) FAIL → FAILED
- FUR (Fit-up) PASS → IN_PROGRESS
- FUR (Fit-up) FAIL → FAILED
- PASS đủ DIR+VIR+NDT → ACCEPTED (backward compat)
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from streamlit_qc.core.constants import ACCEPTANCE_TYPES


# =====================================================================
# Postgres connection adapter — mimic sqlite3.Connection API
# =====================================================================
class _PgCursorWrapper:
    """Wrap psycopg2 cursor để hỗ trợ ['key'] access trên row + lastrowid sau RETURNING."""

    def __init__(self, cursor):
        self._cur = cursor
        self._returning_row = None
        self.lastrowid = None
        self.rowcount = cursor.rowcount if hasattr(cursor, "rowcount") else 0

    def fetchone(self):
        try:
            return self._cur.fetchone()
        except Exception:
            return None

    def fetchall(self):
        try:
            return self._cur.fetchall()
        except Exception:
            return []

    def __iter__(self):
        return iter(self._cur)

    def __getattr__(self, name):
        return getattr(self._cur, name)


class _PgConnAdapter:
    """
    Wrap psycopg2.Connection để có API giống sqlite3.Connection.

    Cung cấp:
    - execute(query, params) — dịch '?' → '%s', tự handle INSERT lastrowid
    - executescript(sql) — split semicolon, execute từng câu
    - commit(), close()
    """

    def __init__(self, dsn: str):
        import psycopg2
        from psycopg2.extras import RealDictCursor

        self._conn = psycopg2.connect(dsn, sslmode="require", connect_timeout=15)
        self._conn.set_session(autocommit=False)
        self._RealDictCursor = RealDictCursor

    def execute(self, query: str, params=()) -> _PgCursorWrapper:
        """Translate '?' → '%s'. Nếu là INSERT thiếu RETURNING → tự thêm."""
        if params is None:
            params = ()
        q = query.replace("?", "%s")

        # Auto-append RETURNING id cho INSERT để emulate sqlite lastrowid
        q_upper_stripped = q.strip().upper()
        is_insert = q_upper_stripped.startswith("INSERT")
        has_returning = "RETURNING" in q_upper_stripped

        cur = self._conn.cursor(cursor_factory=self._RealDictCursor)
        if is_insert and not has_returning:
            cur.execute(q + " RETURNING id", params)
            wrapper = _PgCursorWrapper(cur)
            try:
                row = cur.fetchone()
                if row and "id" in row:
                    wrapper.lastrowid = row["id"]
            except Exception:
                pass
            return wrapper
        cur.execute(q, params)
        return _PgCursorWrapper(cur)

    def executescript(self, script: str) -> None:
        """Split bằng dấu chấm phẩy + execute từng câu (Postgres không có executescript)."""
        # Loại bỏ comment + chia câu
        statements = [s.strip() for s in script.split(";") if s.strip()]
        cur = self._conn.cursor()
        for stmt in statements:
            cur.execute(stmt)
        cur.close()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# =====================================================================
# Detect backend
# =====================================================================
def _is_postgres_url(s: str) -> bool:
    return isinstance(s, str) and (s.startswith("postgresql://") or s.startswith("postgres://"))


# =====================================================================
# Main DB class — public API giữ nguyên với code hiện tại
# =====================================================================
class DB:
    """
    Wrapper hỗ trợ cả SQLite (local file) và PostgreSQL (Supabase).

    Usage:
        db = DB("path/to/qc.db")                          # SQLite local
        db = DB("postgresql://user:pass@host:5432/db")    # Postgres cloud
    """

    def __init__(self, path_or_dsn: str | Path) -> None:
        path_str = str(path_or_dsn)
        self.is_postgres = _is_postgres_url(path_str)
        self.path = path_str

        if self.is_postgres:
            self.conn = _PgConnAdapter(path_str)
        else:
            self.conn = sqlite3.connect(
                path_str,
                check_same_thread=False,
                timeout=30.0,
            )
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode = WAL")

        self._init_schema()

    # ------------------------------------------------------------------
    # SCHEMA — tự detect backend để dùng kiểu data phù hợp
    # ------------------------------------------------------------------
    def _init_schema(self) -> None:
        """Tạo bảng + index. Idempotent (chạy lại không lỗi)."""
        if self.is_postgres:
            schema = """
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                location TEXT,
                owner TEXT,
                start_date TEXT,
                end_date TEXT,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS column_mappings (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                mapping_type TEXT NOT NULL,
                mapping_json TEXT NOT NULL,
                header_row INTEGER DEFAULT 0,
                sheet_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS components (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                code TEXT NOT NULL,
                data_json TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                UNIQUE (project_id, code)
            );

            CREATE TABLE IF NOT EXISTS inspections (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
                inspection_type TEXT NOT NULL,
                inspection_date TEXT,
                inspector TEXT,
                result TEXT,
                report_no TEXT,
                rfi_no TEXT,
                note TEXT,
                source_file TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_name TEXT,
                action TEXT,
                entity TEXT,
                entity_id INTEGER,
                detail TEXT,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
                user_name TEXT,
                text TEXT NOT NULL,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_components_code
                ON components(project_id, code);
            CREATE INDEX IF NOT EXISTS idx_inspections_comp
                ON inspections(component_id, inspection_type);
            CREATE INDEX IF NOT EXISTS idx_inspections_pid
                ON inspections(project_id);
            CREATE INDEX IF NOT EXISTS idx_audit_ts
                ON audit_log(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_comments_comp
                ON comments(component_id, ts DESC);
            """
        else:
            schema = """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                location TEXT,
                owner TEXT,
                start_date TEXT,
                end_date TEXT,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS column_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                mapping_type TEXT NOT NULL,
                mapping_json TEXT NOT NULL,
                header_row INTEGER DEFAULT 0,
                sheet_name TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                data_json TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                UNIQUE (project_id, code),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                component_id INTEGER NOT NULL,
                inspection_type TEXT NOT NULL,
                inspection_date TEXT,
                inspector TEXT,
                result TEXT,
                report_no TEXT,
                rfi_no TEXT,
                note TEXT,
                source_file TEXT,
                imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                action TEXT,
                entity TEXT,
                entity_id INTEGER,
                detail TEXT,
                ts TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id INTEGER NOT NULL,
                user_name TEXT,
                text TEXT NOT NULL,
                ts TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_components_code
                ON components(project_id, code);
            CREATE INDEX IF NOT EXISTS idx_inspections_comp
                ON inspections(component_id, inspection_type);
            CREATE INDEX IF NOT EXISTS idx_inspections_pid
                ON inspections(project_id);
            CREATE INDEX IF NOT EXISTS idx_audit_ts
                ON audit_log(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_comments_comp
                ON comments(component_id, ts DESC);
            """
        self.conn.executescript(schema)
        self.conn.commit()

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------
    def log(
        self,
        user: str,
        action: str,
        entity: str,
        eid: int | None = None,
        detail: str = "",
    ) -> None:
        """Ghi audit_log. Không bao giờ raise."""
        try:
            self.conn.execute(
                "INSERT INTO audit_log(user_name, action, entity, entity_id, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                (user, action, entity, eid, detail),
            )
            self.conn.commit()
        except Exception:
            try:
                if self.is_postgres:
                    self.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # PROJECTS
    # ------------------------------------------------------------------
    def list_projects(self):
        return self.conn.execute(
            "SELECT * FROM projects ORDER BY id DESC"
        ).fetchall()

    def get_project(self, pid: int):
        return self.conn.execute(
            "SELECT * FROM projects WHERE id=?", (pid,)
        ).fetchone()

    def create_project(
        self,
        code: str,
        name: str,
        location: str = "",
        owner: str = "",
        note: str = "",
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO projects(code, name, location, owner, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (code, name, location, owner, note),
        )
        self.conn.commit()
        return cur.lastrowid

    # ------------------------------------------------------------------
    # MAPPINGS
    # ------------------------------------------------------------------
    def save_mapping(
        self,
        pid: int,
        mtype: str,
        mapping: dict[str, str],
        header_row: int = 0,
        sheet_name: str | None = None,
    ) -> None:
        self.conn.execute(
            "DELETE FROM column_mappings WHERE project_id=? AND mapping_type=?",
            (pid, mtype),
        )
        self.conn.execute(
            "INSERT INTO column_mappings(project_id, mapping_type, mapping_json, "
            "header_row, sheet_name) VALUES (?, ?, ?, ?, ?)",
            (pid, mtype, json.dumps(mapping, ensure_ascii=False), header_row, sheet_name),
        )
        self.conn.commit()

    def load_mapping(self, pid: int, mtype: str) -> dict | None:
        row = self.conn.execute(
            "SELECT mapping_json, header_row, sheet_name FROM column_mappings "
            "WHERE project_id=? AND mapping_type=?",
            (pid, mtype),
        ).fetchone()
        if not row:
            return None
        return {
            "mapping": json.loads(row["mapping_json"]),
            "header_row": row["header_row"],
            "sheet_name": row["sheet_name"],
        }

    # ------------------------------------------------------------------
    # COMPONENTS
    # ------------------------------------------------------------------
    def upsert_component(
        self,
        pid: int,
        code: str,
        data: dict,
    ) -> tuple[int, bool]:
        """Upsert. Merge data_json (giữ field cũ nếu field mới rỗng)."""
        ex = self.conn.execute(
            "SELECT id, data_json FROM components WHERE project_id=? AND code=?",
            (pid, code),
        ).fetchone()
        if ex:
            merged = json.loads(ex["data_json"])
            merged.update({k: v for k, v in data.items() if v is not None and v != ""})
            self.conn.execute(
                "UPDATE components SET data_json=? WHERE id=?",
                (json.dumps(merged, ensure_ascii=False, default=str), ex["id"]),
            )
            return ex["id"], False
        cur = self.conn.execute(
            "INSERT INTO components(project_id, code, data_json) VALUES (?, ?, ?)",
            (pid, code, json.dumps(data, ensure_ascii=False, default=str)),
        )
        return cur.lastrowid, True

    def find_component(self, pid: int, code: str):
        return self.conn.execute(
            "SELECT * FROM components WHERE project_id=? AND code=?",
            (pid, code),
        ).fetchone()

    def list_components(
        self,
        pid: int,
        status: str | None = None,
        search: str = "",
        limit: int = 50000,
    ):
        """Liệt kê cấu kiện theo bộ lọc trạng thái + tìm theo mã."""
        q = "SELECT * FROM components WHERE project_id=?"
        args: list = [pid]
        if status and status != "ALL":
            q += " AND status=?"
            args.append(status)
        if search:
            q += " AND code LIKE ?"
            args.append(f"%{search}%")
        q += f" ORDER BY code LIMIT {int(limit)}"
        return self.conn.execute(q, args).fetchall()

    def count_status(self, pid: int) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) c FROM components "
            "WHERE project_id=? GROUP BY status",
            (pid,),
        ).fetchall()
        d = {r["status"]: r["c"] for r in rows}
        d["TOTAL"] = sum(d.values())
        return d

    # ------------------------------------------------------------------
    # INSPECTIONS
    # ------------------------------------------------------------------
    def add_inspection(
        self,
        pid: int,
        cid: int,
        itype: str,
        idate: str,
        inspector: str,
        result: str,
        rep: str,
        rfi: str,
        note: str,
        src: str,
    ) -> None:
        """Thêm 1 inspection + tự update status component theo quy tắc nghiệp vụ."""
        self.conn.execute(
            "INSERT INTO inspections(project_id, component_id, inspection_type, "
            "inspection_date, inspector, result, report_no, rfi_no, note, source_file) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, cid, itype, idate, inspector, result, rep, rfi, note, src),
        )

        if result == "FAIL":
            new_status = "FAILED"
        elif result == "PASS":
            if itype == "DGRP":
                new_status = "ACCEPTED"
            elif itype == "FUR":
                new_status = "IN_PROGRESS"
            elif itype in ACCEPTANCE_TYPES:
                new_status = "PASSED"
            else:
                new_status = "IN_PROGRESS"
        else:
            new_status = "IN_PROGRESS"

        # Backward compat: PASS đủ DIR+VIR+NDT → ACCEPTED
        passed_rows = self.conn.execute(
            "SELECT inspection_type FROM inspections "
            "WHERE component_id=? AND result='PASS'",
            (cid,),
        ).fetchall()
        passed_types = {r["inspection_type"] for r in passed_rows}
        if itype in ACCEPTANCE_TYPES and ACCEPTANCE_TYPES.issubset(passed_types):
            new_status = "ACCEPTED"

        cur_row = self.conn.execute(
            "SELECT status FROM components WHERE id=?", (cid,)
        ).fetchone()
        if cur_row and cur_row["status"] == "ACCEPTED" and new_status != "FAILED":
            new_status = "ACCEPTED"

        self.conn.execute(
            "UPDATE components SET status=? WHERE id=?",
            (new_status, cid),
        )

    def list_inspections(self, cid: int):
        return self.conn.execute(
            "SELECT * FROM inspections WHERE component_id=? "
            "ORDER BY inspection_date DESC, id DESC",
            (cid,),
        ).fetchall()

    def recent_inspections(
        self,
        pid: int,
        component_ids: set[int] | None = None,
        limit: int = 200,
    ):
        if component_ids is not None:
            if not component_ids:
                return []
            placeholders = ",".join("?" * len(component_ids))
            q = (
                "SELECT i.inspection_date d, c.code code, i.inspection_type t, "
                "i.result r, i.inspector ins, i.report_no rep "
                "FROM inspections i "
                "JOIN components c ON c.id = i.component_id "
                f"WHERE i.project_id=? AND i.component_id IN ({placeholders}) "
                "ORDER BY i.id DESC LIMIT ?"
            )
            params = [pid, *component_ids, limit]
        else:
            q = (
                "SELECT i.inspection_date d, c.code code, i.inspection_type t, "
                "i.result r, i.inspector ins, i.report_no rep "
                "FROM inspections i "
                "JOIN components c ON c.id = i.component_id "
                "WHERE i.project_id=? ORDER BY i.id DESC LIMIT ?"
            )
            params = [pid, limit]
        return self.conn.execute(q, params).fetchall()
