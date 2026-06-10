# -*- coding: utf-8 -*-
"""
Migration tool: copy data từ SQLite local sang Supabase Postgres.

Chạy 1 lần duy nhất từ laptop anh, sau khi:
  - Đã cài: pip install psycopg2-binary
  - Đã có connection string Supabase

Cách dùng:
  cd "D:\\Workshop AH6-AH9\\...\\web app"
  set DATABASE_URL=postgresql://postgres.xxx:PASSWORD@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres
  python migrate_sqlite_to_postgres.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values, RealDictCursor
except ImportError:
    print("LOI: chua cai psycopg2-binary")
    print("Chay: pip install psycopg2-binary")
    sys.exit(1)


SQLITE_PATH = Path(__file__).parent / "streamlit_qc" / "data" / "qc_components.db"
PG_DSN = os.getenv("DATABASE_URL")

# Fallback: doc tu file supabase_url.txt canh script (tranh loi escape ky tu trong .bat)
if not PG_DSN:
    _url_file = Path(__file__).parent / "supabase_url.txt"
    if _url_file.exists():
        _txt = _url_file.read_text(encoding="utf-8").strip()
        if _txt and not _txt.startswith("postgresql://postgres.xxx"):
            PG_DSN = _txt

if not PG_DSN:
    print("LOI: chua set DATABASE_URL")
    print("Cach 1 - set env var truoc khi chay:")
    print('  set DATABASE_URL=postgresql://postgres.xxx:PASS@aws-...:5432/postgres')
    print("Cach 2 - go truc tiep trong script:")
    print('  PG_DSN = "postgresql://..."  o dau file')
    sys.exit(1)

if not SQLITE_PATH.exists():
    print(f"LOI: khong thay file SQLite: {SQLITE_PATH}")
    sys.exit(1)


print("=" * 60)
print("MIGRATION: SQLite -> Supabase Postgres")
print("=" * 60)
print(f"Source: {SQLITE_PATH}")
print(f"Target: {PG_DSN.split('@')[1] if '@' in PG_DSN else PG_DSN}")
print()

# --- Mo SQLite ---
print("[1/5] Doc du lieu tu SQLite local...")
sq = sqlite3.connect(str(SQLITE_PATH))
sq.row_factory = sqlite3.Row

def fetch_all(sql):
    return [dict(r) for r in sq.execute(sql).fetchall()]

projects = fetch_all("SELECT * FROM projects ORDER BY id")
components = fetch_all("SELECT * FROM components ORDER BY id")
inspections = fetch_all("SELECT * FROM inspections ORDER BY id")
column_mappings = fetch_all("SELECT * FROM column_mappings ORDER BY id")
audit_log = fetch_all("SELECT * FROM audit_log ORDER BY id LIMIT 5000")

print(f"  Projects:        {len(projects):>6}")
print(f"  Components:      {len(components):>6}")
print(f"  Inspections:     {len(inspections):>6}")
print(f"  Column mappings: {len(column_mappings):>6}")
print(f"  Audit log:       {len(audit_log):>6} (gioi han 5000 dong moi nhat)")
print()

# --- Connect Postgres ---
print("[2/5] Connect Supabase Postgres...")
pg = psycopg2.connect(PG_DSN, sslmode="require", connect_timeout=15)
pg.autocommit = False
pgc = pg.cursor()
print("  OK!")
print()

# --- Tao schema (an toan: CREATE IF NOT EXISTS) ---
print("[3/5] Tao schema tren Postgres (an toan, idempotent)...")
schema_sql = """
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    location TEXT, owner TEXT, start_date TEXT, end_date TEXT, note TEXT,
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
    inspection_date TEXT, inspector TEXT, result TEXT,
    report_no TEXT, rfi_no TEXT, note TEXT, source_file TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_name TEXT, action TEXT, entity TEXT,
    entity_id INTEGER, detail TEXT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_components_code ON components(project_id, code);
CREATE INDEX IF NOT EXISTS idx_inspections_comp ON inspections(component_id, inspection_type);
CREATE INDEX IF NOT EXISTS idx_inspections_pid ON inspections(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);
"""
for stmt in [s.strip() for s in schema_sql.split(";") if s.strip()]:
    pgc.execute(stmt)
pg.commit()
print("  OK!")
print()

# --- Check du lieu hien co tren Postgres ---
print("[4/5] Check du lieu hien co tren Postgres...")
pgc.execute("SELECT COUNT(*) FROM projects")
n_existing = pgc.fetchone()[0]
if n_existing > 0:
    print(f"  CANH BAO: Postgres da co {n_existing} projects.")
    ans = input("  Tiep tuc se BO QUA project ma code trung. Tiep tuc? [y/N]: ")
    if ans.strip().lower() != "y":
        print("  Da huy migration.")
        sys.exit(0)
print()

# --- Migrate du lieu ---
print("[5/5] Bat dau migrate du lieu...")

# 5a. Projects (giu nguyen id)
print("  5a. Migrate projects...")
id_map_proj: dict[int, int] = {}  # sqlite_id -> postgres_id
for p in projects:
    pgc.execute("""
        INSERT INTO projects (code, name, location, owner, start_date, end_date, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
    """, (p["code"], p["name"], p.get("location"), p.get("owner"),
          p.get("start_date"), p.get("end_date"), p.get("note")))
    new_id = pgc.fetchone()[0]
    id_map_proj[p["id"]] = new_id
pg.commit()
print(f"    Da migrate {len(projects)} projects")

# 5b. Components
print("  5b. Migrate components (co the lau neu nhieu)...")
id_map_comp: dict[int, int] = {}
batch = []
for c in components:
    new_pid = id_map_proj.get(c["project_id"])
    if not new_pid:
        continue
    batch.append((new_pid, c["code"], c["data_json"], c.get("status") or "PENDING"))

# Precompute (pg_project_id, code) -> sqlite component id  [O(n) thay cho O(n^2)]
_comp_key_to_sid = {}
for _c in components:
    _np = id_map_proj.get(_c["project_id"])
    if _np:
        _comp_key_to_sid[(_np, _c["code"])] = _c["id"]

# Batch insert
inserted = 0
for i in range(0, len(batch), 500):
    chunk = batch[i:i+500]
    args_str = ",".join(pgc.mogrify("(%s,%s,%s,%s)", x).decode("utf-8") for x in chunk)
    pgc.execute(f"""
        INSERT INTO components (project_id, code, data_json, status)
        VALUES {args_str}
        ON CONFLICT (project_id, code) DO UPDATE
            SET data_json = EXCLUDED.data_json, status = EXCLUDED.status
        RETURNING id, project_id, code
    """)
    for row in pgc.fetchall():
        _sid = _comp_key_to_sid.get((row[1], row[2]))
        if _sid is not None:
            id_map_comp[_sid] = row[0]
    inserted += len(chunk)
    print(f"    {inserted}/{len(batch)}")
pg.commit()
print(f"    Da migrate {len(id_map_comp)} components")

# 5c. Inspections
print("  5c. Migrate inspections...")
ins_batch = []
for ins in inspections:
    new_pid = id_map_proj.get(ins["project_id"])
    new_cid = id_map_comp.get(ins["component_id"])
    if not new_pid or not new_cid:
        continue
    ins_batch.append((
        new_pid, new_cid, ins["inspection_type"],
        ins.get("inspection_date"), ins.get("inspector"),
        ins.get("result"), ins.get("report_no"), ins.get("rfi_no"),
        ins.get("note"), ins.get("source_file"),
    ))

inserted = 0
for i in range(0, len(ins_batch), 500):
    chunk = ins_batch[i:i+500]
    args_str = ",".join(pgc.mogrify("(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", x).decode("utf-8") for x in chunk)
    pgc.execute(f"""
        INSERT INTO inspections
        (project_id, component_id, inspection_type, inspection_date,
         inspector, result, report_no, rfi_no, note, source_file)
        VALUES {args_str}
    """)
    inserted += len(chunk)
    print(f"    {inserted}/{len(ins_batch)}")
pg.commit()
print(f"    Da migrate {len(ins_batch)} inspections")

# 5d. Column mappings
print("  5d. Migrate column_mappings...")
for m in column_mappings:
    new_pid = id_map_proj.get(m["project_id"])
    if not new_pid:
        continue
    pgc.execute("""
        INSERT INTO column_mappings (project_id, mapping_type, mapping_json, header_row, sheet_name)
        VALUES (%s, %s, %s, %s, %s)
    """, (new_pid, m["mapping_type"], m["mapping_json"],
          m.get("header_row", 0), m.get("sheet_name")))
pg.commit()
print(f"    Da migrate {len(column_mappings)} mappings")

# 5e. Audit log
print("  5e. Migrate audit_log (5000 dong moi nhat)...")
for a in audit_log:
    pgc.execute("""
        INSERT INTO audit_log (user_name, action, entity, entity_id, detail)
        VALUES (%s, %s, %s, %s, %s)
    """, (a.get("user_name"), a.get("action"), a.get("entity"),
          a.get("entity_id"), a.get("detail")))
pg.commit()
print(f"    Da migrate {len(audit_log)} audit entries")

# --- Done ---
print()
print("=" * 60)
print("HOAN TAT MIGRATION!")
print("=" * 60)

# Final stats
pgc.execute("SELECT COUNT(*) FROM projects"); n_p = pgc.fetchone()[0]
pgc.execute("SELECT COUNT(*) FROM components"); n_c = pgc.fetchone()[0]
pgc.execute("SELECT COUNT(*) FROM inspections"); n_i = pgc.fetchone()[0]
print(f"Postgres hien co:")
print(f"  Projects:    {n_p}")
print(f"  Components:  {n_c}")
print(f"  Inspections: {n_i}")
print()
print("Buoc tiep theo:")
print("  1. Test app local voi Postgres: set DATABASE_URL roi chay streamlit")
print("  2. Push code len GitHub")
print("  3. Deploy Streamlit Cloud + set DATABASE_URL trong Secrets")

pg.close()
sq.close()
