# -*- coding: utf-8 -*-
"""
AUTO IMPORT MASTER — import PKL nhieu du an vao DB chi bang 1 click.

Cach dung:
  1. Sua AUTO_IMPORT_CONFIG.json (tu tao mau o lan chay dau)
  2. Double-click IMPORT_ALL.bat  (hoac: python auto_import_master.py)

Tuy chon:
  python auto_import_master.py --force   # import lai ca file chua doi
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

CONFIG_FILE = ROOT / "AUTO_IMPORT_CONFIG.json"
STATE_FILE = ROOT / ".auto_import_state.json"

SAMPLE_CONFIG = {
    "_huong_dan": [
        "Moi muc trong 'du_an' la 1 du an se duoc import tu dong.",
        "code          : ma du an tren web app (neu chua co se TU TAO).",
        "ten           : ten du an (chi dung khi tu tao moi).",
        "thu_muc       : duong dan thu muc chua file PKL (thu muc mang OK).",
        "mau_ten_file  : pattern ten file, * = bat ky. Lay file MOI NHAT khop pattern.",
        "template      : viola / phuquoc / bison / pvf / auto (auto = tu do cot).",
        "sheet         : de trong = tu chon theo template hoac sheet PKL.",
        "header_row    : de trong = tu do. So dong tieu de (0-based).",
        "bat           : true = import, false = bo qua du an nay.",
    ],
    "du_an": [
        {
            "code": "VIOLA",
            "ten": "VIOLA Structural Steel",
            "thu_muc": "Z:\\DuongDan\\ToiThuMuc\\VIOLA",
            "mau_ten_file": "PKL*VIOLA*.xlsb",
            "template": "viola",
            "sheet": "",
            "header_row": None,
            "bat": False
        }
    ]
}


def resolve_dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if dsn:
        return dsn
    for fname in ("supabase_new.txt", "supabase_url.txt"):
        p = ROOT / fname
        if p.exists():
            s = p.read_text(encoding="utf-8").strip()
            if s.startswith("postgresql://"):
                return s
    raise SystemExit(
        "KHONG tim thay DATABASE_URL.\n"
        "-> Tao file supabase_new.txt chua chuoi ket noi postgresql://... "
        "(Session pooler) ngay canh script nay."
    )


DOWNLOAD_DIR = ROOT / "_drive_cache"


def _drive_url(drive_id: str, kind: str) -> str:
    if kind == "gsheet":
        return f"https://docs.google.com/spreadsheets/d/{drive_id}/export?format=xlsx"
    # Endpoint moi xu ly file lon (>25MB) khong vuong trang canh bao virus.
    return (f"https://drive.usercontent.google.com/download"
            f"?id={drive_id}&export=download&confirm=t")


def head_size(drive_id: str, kind: str):
    """Lay dung luong file (Content-Length) bang HEAD, KHONG tai noi dung.
    Tra int hoac None neu khong lay duoc."""
    import urllib.request
    try:
        req = urllib.request.Request(_drive_url(drive_id, kind),
                                     headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            cl = resp.headers.get("Content-Length")
            return int(cl) if cl and cl.isdigit() else None
    except Exception:
        return None


def download_from_drive(drive_id: str, kind: str, dest: Path) -> Path:
    """Tai 1 file tu Google Drive (link cong khai 'ai co link cung xem')."""
    import urllib.request

    dest.parent.mkdir(exist_ok=True, parents=True)
    url = _drive_url(drive_id, kind)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    # Phong khi van dinh trang HTML xac nhan (file rat lon) -> bat token & tai lai
    if data[:200].lstrip().lower().startswith(b"<!doctype html") or b"<html" in data[:200].lower():
        m = re.search(rb'name="confirm"\s+value="([^"]+)"', data) or re.search(rb'confirm=([0-9A-Za-z_-]+)', data)
        tok = m.group(1).decode() if m else "t"
        url2 = (f"https://drive.usercontent.google.com/download"
                f"?id={drive_id}&export=download&confirm={tok}")
        req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=300) as resp2:
            data = resp2.read()
    dest.write_bytes(data)
    return dest


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def list_drive_folder(folder_id: str) -> list[tuple]:
    """Liet ke (ten, id, kind) trong thu muc Drive cong khai (embeddedfolderview).

    Vi sao can: file cache cua team duoc TAO LAI moi dem -> ID doi lien tuc,
    nen phai do ID moi theo TEN file moi lan chay.
    """
    import urllib.request
    url = f"https://drive.google.com/embeddedfolderview?id={folder_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", "ignore")

    out = []
    pat = re.compile(
        r'href="https://(docs\.google\.com/spreadsheets/d/|drive\.google\.com/file/d/)'
        r'([-\w]{20,})[^"]*"[\s\S]{0,1200}?flip-entry-title">([^<]+)<'
    )
    for host, fid, name in pat.findall(html):
        kind = "gsheet" if "spreadsheets" in host else "file"
        out.append((name.strip(), fid, kind))
    if out:
        return out
    # Fallback: bat cap (id, ten) theo thu tu xuat hien
    ids = re.findall(
        r'https://(docs\.google\.com/spreadsheets/d/|drive\.google\.com/file/d/)([-\w]{20,})',
        html)
    names = re.findall(r'flip-entry-title">([^<]+)<', html)
    seen, uniq = set(), []
    for host, fid in ids:
        if fid not in seen:
            seen.add(fid)
            uniq.append(("gsheet" if "spreadsheets" in host else "file", fid))
    if len(uniq) == len(names):
        return [(n.strip(), fid, k) for (k, fid), n in zip(uniq, names)]
    return []


def resolve_from_folder(folder_id: str, pattern: str):
    """Tim file khop pattern (fnmatch, khong phan biet hoa thuong) trong folder.
    Tra (ten, id, kind) hoac None."""
    import fnmatch
    try:
        entries = list_drive_folder(folder_id)
    except Exception as e:
        print(f"     [!] Khong liet ke duoc thu muc Drive ({repr(e)[:60]})")
        return None
    pat = str(pattern or "*").lower()
    hits = [t for t in entries if fnmatch.fnmatch(t[0].lower(), pat)]
    if not hits:
        return None
    if len(hits) > 1:
        print(f"     [i] {len(hits)} file khop '{pattern}' -> chon: {hits[-1][0][:50]}")
    return hits[-1]


def newest_file(folder: str, pattern: str) -> Path | None:
    files = [Path(p) for p in glob.glob(str(Path(folder) / pattern))]
    files = [f for f in files if f.is_file() and not f.name.startswith("~$")]
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def _resolve_col(headers: list[str], want: str) -> str | None:
    """Tim header thuc khop 'want' (exact, bo \\n, prefix). Tra ten header that."""
    if not want:
        return None
    if want in headers:
        return want
    norm = {str(h).replace("\n", " ").strip().lower(): h for h in headers}
    w = want.replace("\n", " ").strip().lower()
    if w in norm:
        return norm[w]
    pref = [h for n, h in norm.items() if n.startswith(w + " ") or n.startswith(w + "\n")]
    if len(pref) == 1:
        return pref[0]
    return None


def build_mapping(headers: list[str], template_key: str, override: dict | None = None):
    from streamlit_qc.core.constants import STANDARD_FIELDS
    from streamlit_qc.core.excel_engine import smart_match_columns
    from streamlit_qc.services import mapping_service as ms

    fields = [f for f, _ in STANDARD_FIELDS]
    mapping = smart_match_columns(headers, fields)  # nen tang: smart detect
    tpl = {
        "viola": ms.VIOLA_MAPPING,
        "phuquoc": ms.PHUQUOC_MAPPING,
        "bison": ms.BISON_MAPPING,
        "pvf": ms.PVF_MAPPING,
    }.get((template_key or "auto").lower())
    if tpl:
        matched = ms.apply_hardcoded_mapping(tpl, headers)
        mapping.update(matched)  # template thang smart khi trung field
    # 'cot' override (uu tien CAO NHAT) — chi dinh thu cong cot cho field nao do
    if override:
        for fld, want in override.items():
            real = _resolve_col(headers, want)
            if real:
                mapping[fld] = real
            else:
                print(f"     [!] override {fld}={want!r}: khong tim thay cot khop")
    return mapping


def default_sheet_header(template_key: str):
    from streamlit_qc.services import mapping_service as ms
    t = (template_key or "auto").lower()
    return {
        "viola": (ms.VIOLA_DEFAULT_SHEET, ms.VIOLA_DEFAULT_HEADER_ROW),
        "phuquoc": (ms.PHUQUOC_DEFAULT_SHEET, ms.PHUQUOC_DEFAULT_HEADER_ROW),
        "bison": (ms.BISON_DEFAULT_SHEET, ms.BISON_DEFAULT_HEADER_ROW),
        "pvf": (ms.PVF_DEFAULT_SHEET, ms.PVF_DEFAULT_HEADER_ROW),
    }.get(t, (None, None))


def run() -> int:
    force = "--force" in sys.argv

    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(
            json.dumps(SAMPLE_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("=" * 60)
        print("Lan dau chay: DA TAO file cau hinh mau:")
        print(f"  {CONFIG_FILE}")
        print('-> Mo file nay, sua "thu_muc" + "mau_ten_file" cho tung du an,')
        print('   doi "bat": true, luu lai, roi chay lai IMPORT_ALL.bat')
        print("=" * 60)
        return 1

    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    projects = [p for p in cfg.get("du_an", []) if p.get("bat")]
    # Loc theo ma du an tren dong lenh (vd: IMPORT_ALL.bat 10725-009 10626-030)
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    if only:
        projects = [p for p in projects if str(p.get("code", "")) in only]
        print(f"Chi import {len(projects)} du an duoc chon: {only}")
    if not projects:
        print('Khong co du an nao de import (kiem tra "bat": true / ma du an).')
        return 1

    dsn = resolve_dsn()
    print(f"Ket noi DB: {dsn[:35]}...")

    from streamlit_qc.core.db import DB
    from streamlit_qc.core.excel_engine import (
        list_sheet_names, read_excel_any, smart_detect_header_row,
    )
    from streamlit_qc.services import master_import_service

    db = DB(dsn)
    state = load_state()
    n_ok = n_skip = n_err = 0

    for p in projects:
        code = str(p.get("code") or "").strip()
        print()
        print("=" * 60)
        print(f"DU AN: {code}")
        try:
            drive_id = str(p.get("drive_id") or "").strip()
            f = None
            kind = "gsheet" if (p.get("drive_kind") or "gsheet") == "gsheet" else "file"
            # === Do ID MOI NHAT tu thu muc Drive (cache tao lai moi dem -> ID doi) ===
            _folder = str(cfg.get("drive_folder") or "").strip()
            if _folder and kind == "file":
                _hit = resolve_from_folder(_folder, p.get("mau_ten_file") or f"*{code}*")
                if _hit:
                    _name, _fid, _kind = _hit
                    if _fid != drive_id:
                        print(f"  ID Drive moi (file tao lai): {_fid[:14]}... | {_name[:45]}")
                    drive_id, kind = _fid, _kind
                elif drive_id:
                    print("     [i] Khong thay file khop trong thu muc -> dung ID cu")
            if drive_id:
                # === Tai ban moi nhat tu Google Drive ===
                # Kiem tra dung luong truoc (HEAD) -> neu khong doi thi BO QUA, khoi tai
                if not force:
                    hs = head_size(drive_id, kind)
                    if hs and state.get(code) == f"drive:{drive_id}|{hs}":
                        print(f"  -- Drive khong doi ({hs/1e6:.1f} MB) -> BO QUA (khong tai lai)")
                        n_skip += 1
                        continue
                ext = ".xlsx" if kind == "gsheet" else (".xlsb" if str(p.get("drive_name","")).endswith("xlsb") else ".xlsx")
                dest = DOWNLOAD_DIR / f"{code.replace('/','_')}{ext}"
                try:
                    print(f"  Tai tu Google Drive (id={drive_id[:12]}...) ...")
                    t_dl = time.time()
                    f = download_from_drive(drive_id, kind, dest)
                    print(f"     Tai xong {f.stat().st_size/1e6:.1f} MB ({time.time()-t_dl:.0f}s)")
                except Exception as de:
                    print(f"     [!] Tai Drive that bai ({repr(de)[:70]}) -> thu file local")
                    f = None
            if f is None:
                f = newest_file(p.get("thu_muc", ""), p.get("mau_ten_file", "*.xls*"))
            if f is None:
                print(f"  !! Khong co file (Drive loi va khong thay local khop "
                      f"'{p.get('mau_ten_file')}')")
                n_err += 1
                continue
            st_ = f.stat()
            # Khi tai tu Drive: dung kich thuoc lam chu ky (mtime moi tai luon doi)
            sig = (f"drive:{drive_id}|{st_.st_size}" if drive_id
                   else f"{f.name}|{st_.st_size}|{int(st_.st_mtime)}")
            if not force and state.get(code) == sig:
                print(f"  -- Du lieu khong doi tu lan truoc -> BO QUA. "
                      f"(dung --force de ep import lai)")
                n_skip += 1
                continue

            print(f"  File: {f.name}  ({st_.st_size/1e6:.1f} MB)")

            # --- sheet + header row ---
            tpl_sheet, tpl_hr = default_sheet_header(p.get("template"))
            sheet = p.get("sheet") or None
            if sheet is not None and not str(sheet).strip():
                sheet = None
            if sheet is None:
                sheets = list_sheet_names(f)
                if tpl_sheet and tpl_sheet in sheets:
                    sheet = tpl_sheet
                else:
                    # Uu tien sheet du lieu, tranh SPM/SUM/NDT...
                    PRIO = ("pkl", "check_list", "checklist", "check list")
                    SKIP = ("spm", "sum", "ndt", "input", "ktra", "kiểm tra",
                            "kiem tra", "wps", "bbgn", "pivot", "link", "load",
                            "update", "dwg", "aws", "nfi", "master schedule")
                    low = [(s, s.strip().lower()) for s in sheets]
                    sheet = next((s for s, l in low for k in PRIO if l == k or l.startswith(k)), None)
                    if sheet is None:
                        sheet = next((s for s, l in low if not any(k in l for k in SKIP)), sheets[0])
            # Doi chieu ten sheet voi danh sach that (chiu sai dau cach/hoa thuong)
            try:
                _avail = list_sheet_names(f)
                if sheet not in _avail:
                    _norm = {str(x).strip().lower(): x for x in _avail}
                    _hit = _norm.get(str(sheet).strip().lower())
                    if _hit:
                        sheet = _hit
            except Exception:
                pass

            hr = p.get("header_row")
            if hr is None or hr == "":
                hr = tpl_hr if tpl_hr is not None else smart_detect_header_row(f, sheet)
            hr = int(hr)
            print(f"  Sheet: {sheet} | dong tieu de: {hr}")

            df = read_excel_any(f, sheet_name=sheet, header=hr)
            headers = [str(c) for c in df.columns]
            mapping = build_mapping(headers, p.get("template"), p.get("cot"))
            if "code" not in mapping:
                print("  !! Khong tim duoc cot ma cau kien (code) -> BO QUA. "
                      "Kiem tra template/header_row.")
                n_err += 1
                continue
            print(f"  Mapping: {len(mapping)} truong | code -> "
                  f"{mapping['code'].splitlines()[0][:40]!r}")
            for fld in ("rfi_fitup_done", "rfi_final_done"):
                if mapping.get(fld):
                    print(f"           {fld} -> {mapping[fld].splitlines()[0][:40]!r}")

            # --- project id (tu tao neu chua co) ---
            row = db.conn.execute(
                "SELECT id FROM projects WHERE code=?", (code,)
            ).fetchone()
            if row:
                pid = row["id"]
            else:
                pid = db.create_project(code, p.get("ten") or code, owner="auto-import")
                print(f"  ++ Du an chua co tren web -> DA TAO MOI (id={pid})")

            # --- import ---
            t0 = time.time()
            r = master_import_service.import_master(
                db, pid=pid, df=df, mapping=mapping,
                sheet_name=sheet, header_row=hr, user_name="auto-import",
            )
            print(f"  OK ({time.time()-t0:.0f}s): {r.written:,} cau kien "
                  f"({r.new:,} moi, {r.updated:,} cap nhat, bo qua {r.skipped:,})")
            print(f"     Fit-up tao/cap nhat: {r.fitup_seeded:,} | "
                  f"Final tao/cap nhat: {r.final_seeded:,}")
            if r.duplicate_rows:
                print(f"     Luu y: file co {r.duplicate_rows:,} dong trung ma (da tu merge)")
            state[code] = sig
            save_state(state)
            n_ok += 1
        except Exception as e:
            n_err += 1
            print(f"  !! LOI: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"XONG: {n_ok} du an OK, {n_skip} bo qua (du lieu khong doi), {n_err} loi.")
    print("Mo web app -> Tong quan de xem so lieu moi.")
    return 0 if n_err == 0 else 2


if __name__ == "__main__":
    _rc = run()
    sys.exit(_rc)
# ============================================================
# ============================================================
# ============================================================
# ============================================================
