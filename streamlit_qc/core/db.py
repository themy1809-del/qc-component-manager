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


class _PgPandasCursor:
    """Cursor cho pandas.read_sql_query: dich '?' -> '%s'. Cursor thuong (tuple rows)."""

    def __init__(self, cur):
        self._cur = cur

    def execute(self, query, params=None):
        q = query.replace("?", "%s")
        if params is None:
            self._cur.execute(q)
        else:
            self._cur.execute(q, params)
        return self

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
        # autocommit=True: moi statement tu commit -> tranh InFailedSqlTransaction
        # (cac best-effort query loi se khong dau doc transaction cua query sau)
        self._conn.set_session(autocommit=True)
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
        try:
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
        except Exception:
            # Roll back aborted transaction so the NEXT query is not poisoned
            # (best-effort queries upstream swallow errors without rollback).
            try:
                self._conn.rollback()
            except Exception:
                pass
            raise

    def executescript(self, script: str) -> None:
        """Split bằng dấu chấm phẩy + execute từng câu (Postgres không có executescript)."""
        # Loại bỏ comment + chia câu
        statements = [s.strip() for s in script.split(";") if s.strip()]
        cur = self._conn.cursor()
        for stmt in statements:
            cur.execute(stmt)
        cur.close()

    def cursor(self):
        """Tra ve cursor cho pandas.read_sql_query (dich '?' -> '%s')."""
        return _PgPandasCursor(self._conn.cursor())

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

            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'qc_worker',
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS access_log (
                id SERIAL PRIMARY KEY,
                session_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                page_name TEXT,
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
            CREATE INDEX IF NOT EXISTS idx_access_session
                ON access_log(session_id);
            CREATE INDEX IF NOT EXISTS idx_access_ts
                ON access_log(ts DESC);

            CREATE TABLE IF NOT EXISTS ncrs (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
                ncr_no TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                severity TEXT DEFAULT 'MEDIUM',
                status TEXT DEFAULT 'OPEN',
                deadline TEXT,
                raised_by TEXT,
                resolved_by TEXT,
                resolved_at TEXT,
                root_cause TEXT,
                corrective_action TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_ncr_proj_status
                ON ncrs(project_id, status);
            CREATE INDEX IF NOT EXISTS idx_ncr_no
                ON ncrs(ncr_no);

            CREATE TABLE IF NOT EXISTS rfis (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                component_id INTEGER REFERENCES components(id) ON DELETE CASCADE,
                rfi_no TEXT UNIQUE NOT NULL,
                inspection_type TEXT NOT NULL,
                proposed_date TEXT NOT NULL,
                confirmed_date TEXT,
                status TEXT DEFAULT 'SUBMITTED',
                submitted_by TEXT,
                response_note TEXT,
                is_hold_point INTEGER DEFAULT 0,
                witness_required TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_rfis_proj_status
                ON rfis(project_id, status);
            CREATE INDEX IF NOT EXISTS idx_rfis_no ON rfis(rfi_no);

            CREATE TABLE IF NOT EXISTS itp_templates (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                component_type TEXT,
                checkpoints TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS itp_records (
                id SERIAL PRIMARY KEY,
                component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
                template_id INTEGER REFERENCES itp_templates(id) ON DELETE SET NULL,
                checkpoint_seq INTEGER NOT NULL,
                checkpoint_name TEXT NOT NULL,
                hold_type TEXT,
                result TEXT,
                inspector TEXT,
                inspected_at TIMESTAMP,
                witness_by TEXT,
                witness_at TIMESTAMP,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(component_id, checkpoint_seq)
            );
            CREATE INDEX IF NOT EXISTS idx_itp_records_comp
                ON itp_records(component_id);

            CREATE TABLE IF NOT EXISTS batches (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                batch_no TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'DRAFT',
                total_weight_kg NUMERIC(12,2),
                handover_date TEXT,
                receiver_name TEXT,
                receiver_company TEXT,
                notes TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS batch_items (
                batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (batch_id, component_id)
            );

            CREATE TABLE IF NOT EXISTS materials (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                heat_no TEXT NOT NULL,
                grade TEXT,
                supplier TEXT,
                origin TEXT,
                cert_no TEXT,
                test_date TEXT,
                chemical TEXT,
                mechanical TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, heat_no)
            );

            CREATE TABLE IF NOT EXISTS material_assignments (
                material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_by TEXT,
                PRIMARY KEY (material_id, component_id)
            );

            CREATE TABLE IF NOT EXISTS share_tokens (
                token TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                label TEXT,
                expires_at TIMESTAMP,
                password_hash TEXT,
                view_count INTEGER DEFAULT 0,
                last_viewed_at TIMESTAMP,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS qc_reports (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                component_id INTEGER REFERENCES components(id) ON DELETE CASCADE,
                report_type TEXT NOT NULL,
                report_date TEXT,
                inspector TEXT,
                result TEXT,
                rfi_no TEXT,
                data_json TEXT NOT NULL,
                source_file TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_qcrep_proj
                ON qc_reports(project_id, report_type);
            CREATE INDEX IF NOT EXISTS idx_qcrep_comp
                ON qc_reports(component_id);
            CREATE INDEX IF NOT EXISTS idx_qcrep_date
                ON qc_reports(report_date DESC);
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

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'qc_worker',
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                page_name TEXT,
                ts TEXT DEFAULT CURRENT_TIMESTAMP
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

            CREATE TABLE IF NOT EXISTS ncrs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                component_id INTEGER,
                ncr_no TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                severity TEXT DEFAULT 'MEDIUM',
                status TEXT DEFAULT 'OPEN',
                deadline TEXT,
                raised_by TEXT,
                resolved_by TEXT,
                resolved_at TEXT,
                root_cause TEXT,
                corrective_action TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ncr_proj_status
                ON ncrs(project_id, status);
            CREATE INDEX IF NOT EXISTS idx_ncr_no
                ON ncrs(ncr_no);

            CREATE TABLE IF NOT EXISTS rfis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                component_id INTEGER,
                rfi_no TEXT UNIQUE NOT NULL,
                inspection_type TEXT NOT NULL,
                proposed_date TEXT NOT NULL,
                confirmed_date TEXT,
                status TEXT DEFAULT 'SUBMITTED',
                submitted_by TEXT,
                response_note TEXT,
                is_hold_point INTEGER DEFAULT 0,
                witness_required TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_rfis_proj_status
                ON rfis(project_id, status);
            CREATE INDEX IF NOT EXISTS idx_rfis_no ON rfis(rfi_no);

            CREATE TABLE IF NOT EXISTS itp_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                name TEXT NOT NULL,
                component_type TEXT,
                checkpoints TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS itp_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id INTEGER NOT NULL,
                template_id INTEGER,
                checkpoint_seq INTEGER NOT NULL,
                checkpoint_name TEXT NOT NULL,
                hold_type TEXT,
                result TEXT,
                inspector TEXT,
                inspected_at TEXT,
                witness_by TEXT,
                witness_at TEXT,
                remarks TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(component_id, checkpoint_seq),
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE,
                FOREIGN KEY (template_id) REFERENCES itp_templates(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_itp_records_comp
                ON itp_records(component_id);

            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                batch_no TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'DRAFT',
                total_weight_kg REAL,
                handover_date TEXT,
                receiver_name TEXT,
                receiver_company TEXT,
                notes TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS batch_items (
                batch_id INTEGER NOT NULL,
                component_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (batch_id, component_id),
                FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                heat_no TEXT NOT NULL,
                grade TEXT,
                supplier TEXT,
                origin TEXT,
                cert_no TEXT,
                test_date TEXT,
                chemical TEXT,
                mechanical TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, heat_no),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS material_assignments (
                material_id INTEGER NOT NULL,
                component_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                assigned_by TEXT,
                PRIMARY KEY (material_id, component_id),
                FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS share_tokens (
                token TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL,
                label TEXT,
                expires_at TEXT,
                password_hash TEXT,
                view_count INTEGER DEFAULT 0,
                last_viewed_at TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS qc_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                component_id INTEGER,
                report_type TEXT NOT NULL,
                report_date TEXT,
                inspector TEXT,
                result TEXT,
                rfi_no TEXT,
                data_json TEXT NOT NULL,
                source_file TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_qcrep_proj
                ON qc_reports(project_id, report_type);
            CREATE INDEX IF NOT EXISTS idx_qcrep_comp
                ON qc_reports(component_id);
            CREATE INDEX IF NOT EXISTS idx_qcrep_date
                ON qc_reports(report_date DESC);
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
        """Upsert atomic. Merge data_json (giữ field cũ nếu field mới rỗng).

        Pattern: try INSERT trước → nếu UNIQUE conflict thì UPDATE.
        Race-safe khi file có dòng trùng mã hoặc khi SQLite normalize ký tự vô hình.
        """
        payload = json.dumps(data, ensure_ascii=False, default=str)
        # Thử INSERT trước
        try:
            cur = self.conn.execute(
                "INSERT INTO components(project_id, code, data_json) VALUES (?, ?, ?)",
                (pid, code, payload),
            )
            return cur.lastrowid, True
        except sqlite3.IntegrityError:
            pass  # UNIQUE conflict → fall through tới UPDATE
        # Đã tồn tại → UPDATE với merge logic
        ex = self.conn.execute(
            "SELECT id, data_json FROM components WHERE project_id=? AND code=?",
            (pid, code),
        ).fetchone()
        if ex is None:
            # Edge case: IntegrityError nhưng SELECT không tìm thấy.
            # Mã chứa ký tự vô hình → bỏ qua, log để debug.
            print(
                f"[upsert_component] IntegrityError nhưng SELECT không match: "
                f"pid={pid}, code={code!r}. Bỏ qua row."
            )
            return -1, False
        merged = json.loads(ex["data_json"])
        merged.update({k: v for k, v in data.items() if v is not None and v != ""})
        self.conn.execute(
            "UPDATE components SET data_json=? WHERE id=?",
            (json.dumps(merged, ensure_ascii=False, default=str), ex["id"]),
        )
        return ex["id"], False

    def bulk_upsert_components(self, pid: int, records) -> int:
        """Bulk upsert components. records = list[(code, data_dict)].
        data_json da merge san o caller. Nhanh tren Postgres (execute_values)
        — tranh round-trip tung dong. Tra ve so dong xu ly.
        """
        if not records:
            return 0
        rows = [
            (pid, code, json.dumps(data, ensure_ascii=False, default=str))
            for code, data in records
        ]
        if self.is_postgres:
            from psycopg2.extras import execute_values
            raw = self.conn._conn
            cur = raw.cursor()
            try:
                for i in range(0, len(rows), 1000):
                    execute_values(
                        cur,
                        "INSERT INTO components (project_id, code, data_json) "
                        "VALUES %s "
                        "ON CONFLICT (project_id, code) "
                        "DO UPDATE SET data_json = EXCLUDED.data_json",
                        rows[i:i + 1000],
                    )
                raw.commit()
            finally:
                cur.close()
            return len(rows)
        for _pid, code, payload in rows:
            try:
                self.conn.execute(
                    "INSERT INTO components(project_id, code, data_json) "
                    "VALUES (?, ?, ?)",
                    (_pid, code, payload),
                )
            except sqlite3.IntegrityError:
                self.conn.execute(
                    "UPDATE components SET data_json=? "
                    "WHERE project_id=? AND code=?",
                    (payload, _pid, code),
                )
        self.conn.commit()
        return len(rows)

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

    # ------------------------------------------------------------------
    # QC REPORTS (Dimension / Welding / Paint)
    # ------------------------------------------------------------------
    def add_qc_report(self, pid, component_id, report_type, report_date,
                      inspector, result, data, rfi_no=None, source_file=None,
                      created_by=None) -> int:
        cur = self.conn.execute(
            "INSERT INTO qc_reports("
            "project_id, component_id, report_type, report_date, inspector, "
            "result, rfi_no, data_json, source_file, created_by"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, component_id, report_type.upper(), report_date, inspector,
             result, rfi_no,
             json.dumps(data or {}, ensure_ascii=False, default=str),
             source_file, created_by),
        )
        return cur.lastrowid

    def list_qc_reports(self, pid, report_type=None, component_id=None,
                        date_from=None, date_to=None, limit=500):
        sql = (
            "SELECT r.id, r.report_type, r.report_date, r.inspector, r.result, "
            "r.rfi_no, r.data_json, r.source_file, r.created_by, r.created_at, "
            "r.component_id, c.code AS component_code "
            "FROM qc_reports r "
            "LEFT JOIN components c ON c.id = r.component_id "
            "WHERE r.project_id=? "
        )
        params = [pid]
        if report_type:
            sql += "AND r.report_type=? "
            params.append(report_type.upper())
        if component_id is not None:
            sql += "AND r.component_id=? "
            params.append(component_id)
        if date_from:
            sql += "AND r.report_date >= ? "
            params.append(date_from)
        if date_to:
            sql += "AND r.report_date <= ? "
            params.append(date_to)
        sql += "ORDER BY r.report_date DESC, r.id DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, tuple(params)).fetchall()

    def get_qc_report(self, rid):
        return self.conn.execute("SELECT * FROM qc_reports WHERE id=?", (rid,)).fetchone()

    def update_qc_report(self, rid, **fields):
        allowed = {"report_date","inspector","result","rfi_no","data_json","source_file"}
        if "data" in fields:
            fields["data_json"] = json.dumps(fields.pop("data") or {}, ensure_ascii=False, default=str)
        sets, params = [], []
        for k, v in fields.items():
            if k not in allowed: continue
            sets.append(f"{k}=?"); params.append(v)
        if not sets: return
        params.append(rid)
        self.conn.execute(f"UPDATE qc_reports SET {', '.join(sets)} WHERE id=?", tuple(params))

    def delete_qc_report(self, rid):
        self.conn.execute("DELETE FROM qc_reports WHERE id=?", (rid,))

    def count_qc_reports(self, pid) -> dict:
        rows = self.conn.execute(
            "SELECT report_type, COUNT(*) AS n FROM qc_reports "
            "WHERE project_id=? GROUP BY report_type", (pid,),
        ).fetchall()
        out = {"DIMENSION": 0, "WELDING": 0, "PAINT": 0}
        for r in rows: out[r["report_type"]] = r["n"]
        return out

    # ------------------------------------------------------------------
    # NCR
    # ------------------------------------------------------------------
    def add_ncr(self, pid, ncr_no, title, description="", component_id=None,
                severity="MEDIUM", deadline=None, raised_by=None) -> int:
        cur = self.conn.execute(
            "INSERT INTO ncrs(project_id, component_id, ncr_no, title, description, "
            "severity, deadline, raised_by, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')",
            (pid, component_id, ncr_no, title, description,
             severity.upper(), deadline, raised_by),
        )
        return cur.lastrowid

    def list_ncrs(self, pid, status=None, severity=None, limit=500):
        sql = ("SELECT n.id, n.ncr_no, n.title, n.description, n.severity, "
               "n.status, n.deadline, n.raised_by, n.resolved_by, n.resolved_at, "
               "n.root_cause, n.corrective_action, n.created_at, "
               "n.component_id, c.code AS component_code "
               "FROM ncrs n LEFT JOIN components c ON c.id = n.component_id "
               "WHERE n.project_id=? ")
        params = [pid]
        if status: sql += "AND n.status=? "; params.append(status.upper())
        if severity: sql += "AND n.severity=? "; params.append(severity.upper())
        sql += "ORDER BY n.created_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, tuple(params)).fetchall()

    def update_ncr_status(self, ncr_id, new_status, resolved_by=None,
                          root_cause=None, corrective_action=None):
        new_status = new_status.upper()
        params = [new_status]
        sets = ["status=?"]
        if root_cause is not None: sets.append("root_cause=?"); params.append(root_cause)
        if corrective_action is not None:
            sets.append("corrective_action=?"); params.append(corrective_action)
        if new_status in ("RESOLVED", "CLOSED"):
            sets.append("resolved_by=?"); params.append(resolved_by or "")
            if self.is_postgres: sets.append("resolved_at=CURRENT_TIMESTAMP")
            else: sets.append("resolved_at=datetime('now')")
        params.append(ncr_id)
        self.conn.execute(f"UPDATE ncrs SET {', '.join(sets)} WHERE id=?", tuple(params))

    def delete_ncr(self, ncr_id):
        self.conn.execute("DELETE FROM ncrs WHERE id=?", (ncr_id,))

    def count_ncrs_by_status(self, pid) -> dict:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM ncrs WHERE project_id=? GROUP BY status", (pid,),
        ).fetchall()
        out = {"OPEN": 0, "IN_REVIEW": 0, "RESOLVED": 0, "CLOSED": 0}
        for r in rows: out[r["status"]] = r["n"]
        return out

    def get_next_ncr_no(self, pid) -> str:
        from datetime import datetime
        year = datetime.now().year
        prefix = f"NCR-{year}-"
        row = self.conn.execute(
            "SELECT COUNT(*) c FROM ncrs WHERE project_id=? AND ncr_no LIKE ?",
            (pid, f"{prefix}%"),
        ).fetchone()
        return f"{prefix}{(row['c'] if row else 0) + 1:03d}"

    # ------------------------------------------------------------------
    # RFI (Request for Inspection)
    # ------------------------------------------------------------------
    def get_next_rfi_no(self, pid: int, project_code: str) -> str:
        from datetime import datetime
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"RFI-{project_code}-{today}-"
        row = self.conn.execute(
            "SELECT COUNT(*) c FROM rfis WHERE project_id=? AND rfi_no LIKE ?",
            (pid, f"{prefix}%"),
        ).fetchone()
        return f"{prefix}{(row['c'] if row else 0) + 1:03d}"

    def add_rfi(self, pid, component_id, rfi_no, inspection_type, proposed_date,
                submitted_by=None, is_hold_point=0, witness_required=None) -> int:
        cur = self.conn.execute(
            "INSERT INTO rfis(project_id, component_id, rfi_no, inspection_type, "
            "proposed_date, submitted_by, is_hold_point, witness_required, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SUBMITTED')",
            (pid, component_id, rfi_no, inspection_type, proposed_date,
             submitted_by, int(is_hold_point), witness_required),
        )
        return cur.lastrowid

    def list_rfis(self, pid, status=None, limit=500):
        sql = ("SELECT r.id, r.rfi_no, r.inspection_type, r.proposed_date, "
               "r.confirmed_date, r.status, r.submitted_by, r.response_note, "
               "r.is_hold_point, r.witness_required, r.created_at, "
               "r.component_id, c.code AS component_code "
               "FROM rfis r LEFT JOIN components c ON c.id = r.component_id "
               "WHERE r.project_id=? ")
        params = [pid]
        if status: sql += "AND r.status=? "; params.append(status.upper())
        sql += "ORDER BY r.created_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, tuple(params)).fetchall()

    def update_rfi_status(self, rfi_id, new_status, confirmed_date=None,
                          response_note=None):
        new_status = new_status.upper()
        params = [new_status]
        sets = ["status=?"]
        if confirmed_date is not None:
            sets.append("confirmed_date=?"); params.append(confirmed_date)
        if response_note is not None:
            sets.append("response_note=?"); params.append(response_note)
        if self.is_postgres: sets.append("updated_at=CURRENT_TIMESTAMP")
        else: sets.append("updated_at=datetime('now')")
        params.append(rfi_id)
        self.conn.execute(f"UPDATE rfis SET {', '.join(sets)} WHERE id=?", tuple(params))

    def count_rfis_by_status(self, pid) -> dict:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM rfis WHERE project_id=? GROUP BY status", (pid,),
        ).fetchall()
        out = {"SUBMITTED": 0, "CONFIRMED": 0, "REJECTED": 0,
               "IN_PROGRESS": 0, "COMPLETED": 0, "CLOSED": 0}
        for r in rows: out[r["status"]] = r["n"]
        return out

    # ------------------------------------------------------------------
    # ITP (Inspection Test Plan)
    # ------------------------------------------------------------------
    def add_itp_template(self, pid, name, component_type, checkpoints) -> int:
        cur = self.conn.execute(
            "INSERT INTO itp_templates(project_id, name, component_type, checkpoints) "
            "VALUES (?, ?, ?, ?)",
            (pid, name, component_type,
             json.dumps(checkpoints, ensure_ascii=False)),
        )
        return cur.lastrowid

    def list_itp_templates(self, pid, only_active=True):
        sql = "SELECT * FROM itp_templates WHERE project_id=?"
        params = [pid]
        if only_active:
            sql += " AND is_active=1"
        sql += " ORDER BY name"
        return self.conn.execute(sql, tuple(params)).fetchall()

    def get_itp_template(self, tid):
        return self.conn.execute(
            "SELECT * FROM itp_templates WHERE id=?", (tid,),
        ).fetchone()

    def upsert_itp_record(self, component_id, template_id, checkpoint_seq,
                          checkpoint_name, hold_type, result, inspector,
                          remarks="", witness_by=None, witness_at=None) -> int:
        """Upsert. SQLite syntax (Postgres handle qua adapter ?→%s + ON CONFLICT)."""
        # Try update
        ex = self.conn.execute(
            "SELECT id FROM itp_records WHERE component_id=? AND checkpoint_seq=?",
            (component_id, checkpoint_seq),
        ).fetchone()
        now_expr = "CURRENT_TIMESTAMP" if self.is_postgres else "datetime('now')"
        if ex:
            self.conn.execute(
                f"UPDATE itp_records SET template_id=?, checkpoint_name=?, "
                f"hold_type=?, result=?, inspector=?, inspected_at={now_expr}, "
                f"remarks=?, witness_by=?, witness_at=? WHERE id=?",
                (template_id, checkpoint_name, hold_type, result, inspector,
                 remarks, witness_by, witness_at, ex["id"]),
            )
            return ex["id"]
        cur = self.conn.execute(
            f"INSERT INTO itp_records(component_id, template_id, checkpoint_seq, "
            f"checkpoint_name, hold_type, result, inspector, inspected_at, remarks, "
            f"witness_by, witness_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, {now_expr}, ?, ?, ?)",
            (component_id, template_id, checkpoint_seq, checkpoint_name,
             hold_type, result, inspector, remarks, witness_by, witness_at),
        )
        return cur.lastrowid

    def list_itp_records(self, component_id):
        return self.conn.execute(
            "SELECT * FROM itp_records WHERE component_id=? "
            "ORDER BY checkpoint_seq ASC", (component_id,),
        ).fetchall()

    def witness_itp_record(self, component_id, checkpoint_seq, witness_by) -> bool:
        now_expr = "CURRENT_TIMESTAMP" if self.is_postgres else "datetime('now')"
        cur = self.conn.execute(
            f"UPDATE itp_records SET result='PASS', witness_by=?, "
            f"witness_at={now_expr} "
            f"WHERE component_id=? AND checkpoint_seq=? AND result='HOLD_WAITING'",
            (witness_by, component_id, checkpoint_seq),
        )
        return cur.rowcount > 0 if hasattr(cur, "rowcount") else True

    # ------------------------------------------------------------------
    # BATCHES (handover)
    # ------------------------------------------------------------------
    def get_next_batch_no(self, pid, project_code) -> str:
        from datetime import datetime
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"BG-{project_code}-{today}-"
        row = self.conn.execute(
            "SELECT COUNT(*) c FROM batches WHERE project_id=? AND batch_no LIKE ?",
            (pid, f"{prefix}%"),
        ).fetchone()
        return f"{prefix}{(row['c'] if row else 0) + 1:03d}"

    def add_batch(self, pid, batch_no, total_weight_kg=None, notes=None,
                  created_by=None) -> int:
        cur = self.conn.execute(
            "INSERT INTO batches(project_id, batch_no, status, total_weight_kg, "
            "notes, created_by) VALUES (?, ?, 'DRAFT', ?, ?, ?)",
            (pid, batch_no, total_weight_kg, notes, created_by),
        )
        return cur.lastrowid

    def add_batch_items(self, batch_id, component_ids, quantities=None) -> int:
        n = 0
        for i, cid in enumerate(component_ids):
            qty = (quantities[i] if quantities and i < len(quantities) else 1)
            try:
                self.conn.execute(
                    "INSERT INTO batch_items(batch_id, component_id, quantity) "
                    "VALUES (?, ?, ?)", (batch_id, cid, qty),
                )
                n += 1
            except Exception:
                pass
        return n

    def list_batches(self, pid, status=None, limit=200):
        sql = "SELECT * FROM batches WHERE project_id=? "
        params = [pid]
        if status: sql += "AND status=? "; params.append(status.upper())
        sql += "ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, tuple(params)).fetchall()

    def list_batch_items(self, batch_id):
        return self.conn.execute(
            "SELECT bi.batch_id, bi.component_id, bi.quantity, "
            "c.code AS component_code, c.status, c.data_json "
            "FROM batch_items bi JOIN components c ON c.id = bi.component_id "
            "WHERE bi.batch_id=? ORDER BY c.code", (batch_id,),
        ).fetchall()

    def update_batch_status(self, batch_id, new_status, handover_date=None,
                            receiver_name=None, receiver_company=None):
        sets = ["status=?"]
        params = [new_status.upper()]
        if handover_date is not None:
            sets.append("handover_date=?"); params.append(handover_date)
        if receiver_name is not None:
            sets.append("receiver_name=?"); params.append(receiver_name)
        if receiver_company is not None:
            sets.append("receiver_company=?"); params.append(receiver_company)
        params.append(batch_id)
        self.conn.execute(f"UPDATE batches SET {', '.join(sets)} WHERE id=?", tuple(params))

    # ------------------------------------------------------------------
    # MATERIALS
    # ------------------------------------------------------------------
    def add_material(self, pid, heat_no, grade=None, supplier=None,
                     origin=None, cert_no=None, test_date=None,
                     chemical=None, mechanical=None) -> int:
        cur = self.conn.execute(
            "INSERT INTO materials(project_id, heat_no, grade, supplier, origin, "
            "cert_no, test_date, chemical, mechanical) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, heat_no, grade, supplier, origin, cert_no, test_date,
             json.dumps(chemical or {}, ensure_ascii=False) if chemical else None,
             json.dumps(mechanical or {}, ensure_ascii=False) if mechanical else None),
        )
        return cur.lastrowid

    def list_materials(self, pid, limit=500):
        return self.conn.execute(
            "SELECT * FROM materials WHERE project_id=? ORDER BY heat_no LIMIT ?",
            (pid, limit),
        ).fetchall()

    def find_material(self, pid, heat_no):
        return self.conn.execute(
            "SELECT * FROM materials WHERE project_id=? AND heat_no=?",
            (pid, heat_no),
        ).fetchone()

    def assign_material(self, material_id, component_id, assigned_by=None) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO material_assignments(material_id, component_id, assigned_by) "
                "VALUES (?, ?, ?)", (material_id, component_id, assigned_by),
            )
            return True
        except Exception:
            return False

    def list_material_for_component(self, component_id):
        return self.conn.execute(
            "SELECT m.* FROM materials m "
            "JOIN material_assignments ma ON ma.material_id = m.id "
            "WHERE ma.component_id=?", (component_id,),
        ).fetchall()

    def list_components_for_material(self, material_id):
        return self.conn.execute(
            "SELECT c.id, c.code, c.status FROM components c "
            "JOIN material_assignments ma ON ma.component_id = c.id "
            "WHERE ma.material_id=? ORDER BY c.code", (material_id,),
        ).fetchall()

    # ------------------------------------------------------------------
    # SHARE TOKENS (Client Portal)
    # ------------------------------------------------------------------
    def add_share_token(self, token, pid, label=None, expires_at=None,
                        password_hash=None, created_by=None):
        self.conn.execute(
            "INSERT INTO share_tokens(token, project_id, label, expires_at, "
            "password_hash, created_by) VALUES (?, ?, ?, ?, ?, ?)",
            (token, pid, label, expires_at, password_hash, created_by),
        )

    def get_share_token(self, token):
        return self.conn.execute(
            "SELECT * FROM share_tokens WHERE token=?",
            (token,),
        ).fetchone()
