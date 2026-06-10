# -*- coding: utf-8 -*-
"""
Migrate Postgres -> Postgres (vd Sydney -> US) GIỮ NGUYÊN id.

Cách dùng (chạy trên máy có internet, tới được cả 2 Supabase):
  1. Tạo file 'supabase_old.txt' = connection string Supabase CŨ (Sydney).
  2. Tạo file 'supabase_new.txt' = connection string Supabase MỚI (US).
  3. Chạy: python migrate_pg_to_pg.py   (hoặc double-click MIGRATE_TO_US.bat)

An toàn: chạy lại được (ON CONFLICT DO NOTHING). KHÔNG đụng dữ liệu Supabase cũ.
"""
from __future__ import annotations
import os, sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values, RealDictCursor
except ImportError:
    print("LOI: chua cai psycopg2-binary  ->  pip install psycopg2-binary")
    sys.exit(1)


def _dsn(envvar, fname):
    v = os.getenv(envvar)
    if v:
        return v.strip()
    f = Path(__file__).parent / fname
    if f.exists():
        t = f.read_text(encoding="utf-8").strip()
        if t and not t.startswith("postgresql://postgres.xxx"):
            return t
    return None


OLD = _dsn("OLD_DATABASE_URL", "supabase_old.txt")
NEW = _dsn("NEW_DATABASE_URL", "supabase_new.txt")
if not OLD or not NEW:
    print("LOI: thieu connection string.")
    print("  - supabase_old.txt = chuoi Supabase CU (Sydney)")
    print("  - supabase_new.txt = chuoi Supabase MOI (US)")
    sys.exit(1)

print("=" * 56)
print("MIGRATE Postgres -> Postgres (giu id)")
print("  CU :", OLD.split("@")[-1][:45] if "@" in OLD else OLD)
print("  MOI:", NEW.split("@")[-1][:45] if "@" in NEW else NEW)
print("=" * 56)

print("[1/3] Ket noi 2 DB...")
src = psycopg2.connect(OLD, sslmode="require", connect_timeout=20)
src.set_session(readonly=True, autocommit=True)
dst = psycopg2.connect(NEW, sslmode="require", connect_timeout=20)
dst.autocommit = False
print("  OK")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    location TEXT, owner TEXT, start_date TEXT, end_date TEXT, note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS components (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code TEXT NOT NULL, data_json TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING', UNIQUE (project_id, code)
);
CREATE TABLE IF NOT EXISTS inspections (
    id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL,
    component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
    inspection_type TEXT NOT NULL, inspection_date TEXT, inspector TEXT,
    result TEXT, report_no TEXT, rfi_no TEXT, note TEXT, source_file TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS column_mappings (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    mapping_type TEXT NOT NULL, mapping_json TEXT NOT NULL,
    header_row INTEGER DEFAULT 0, sheet_name TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY, user_name TEXT, action TEXT, entity TEXT,
    entity_id INTEGER, detail TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
print("[2/3] Tao schema tren DB MOI...")
dc = dst.cursor()
for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
    dc.execute(stmt)
dst.commit()
print("  OK")

print("[3/3] Copy du lieu (giu id)...")
TABLES = ["projects", "components", "inspections", "column_mappings", "audit_log"]
for t in TABLES:
    sc = src.cursor(cursor_factory=RealDictCursor)
    sc.execute("SELECT * FROM " + t + " ORDER BY id")
    rows = sc.fetchall()
    sc.close()
    if not rows:
        print("   %-16s 0 dong" % t)
        continue
    cols = list(rows[0].keys())
    collist = ", ".join('"' + c + '"' for c in cols)
    data = [tuple(r[c] for c in cols) for r in rows]
    n = 0
    for i in range(0, len(data), 1000):
        execute_values(
            dc,
            "INSERT INTO " + t + " (" + collist + ") VALUES %s ON CONFLICT DO NOTHING",
            data[i:i + 1000],
        )
        n += len(data[i:i + 1000])
    dst.commit()
    # reset sequence id
    try:
        dc.execute(
            "SELECT setval(pg_get_serial_sequence(%s,'id'), "
            "COALESCE((SELECT MAX(id) FROM " + t + "), 1))", (t,)
        )
        dst.commit()
    except Exception:
        dst.rollback()
    print("   %-16s %d dong" % (t, n))

# Thong ke
for t in ["projects", "components", "inspections"]:
    dc.execute("SELECT COUNT(*) FROM " + t)
    print("   DB MOI %-12s = %d" % (t, dc.fetchone()[0]))

src.close(); dst.close()
print("\nHOAN TAT! Buoc cuoi: doi DATABASE_URL trong Streamlit Secrets = chuoi US, roi Reboot.")
