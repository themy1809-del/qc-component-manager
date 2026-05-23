# -*- coding: utf-8 -*-
"""
QC Component Manager v1.0.2
============================================================
- Quản lý nhiều dự án, import PKL master + daily DGRP/NDT
- Cột Xưởng cạnh Material, sort khi click header
- Filter dropdown kiểu Excel cho Zone / Phase / Material / Xưởng / Type
- Threading-safe SQLite
============================================================
pip install pandas openpyxl pyxlsb
"""
import os, re, sys, json, sqlite3, datetime as dt, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Vui lòng cài: pip install pandas openpyxl pyxlsb")
    sys.exit(1)

APP_NAME = "QC Component Manager"
APP_VERSION = "1.0.2"
DB_FILE = "qc_components.db"

INSPECTION_TYPES = [
    ("FUR",  "Fit-Up Report"),
    ("DIR",  "Dimension Inspection Report"),
    ("VIR",  "Visual Inspection Report"),
    ("NDT",  "Non-Destructive Testing (MT/UT)"),
    ("TAIR", "Trial Assembly Inspection Report"),
    ("PRE",  "Pre-Assembly Inspection"),
    ("MB",   "Milling/Straightness"),
    ("MTR",  "Material Traceability Report"),
    ("DGRP", "DGRP - Biên bản bàn giao (đa loại từ Remark)"),
]

REMARK_TO_TYPES = {
    "DIM":"DIR","DIMEN":"DIR","VISUAL":"VIR","NDT":"NDT","MT":"NDT","UT":"NDT",
    "FUR":"FUR","FIT":"FUR","TAIR":"TAIR","PRE":"PRE","MB":"MB","MILL":"MB","MTR":"MTR",
}

# Bộ từ khóa để Auto-detect cột thông minh (không phụ thuộc template cụ thể)
# Thứ tự ưu tiên: keyword sớm hơn match trước
SMART_KEYWORDS = {
    "code":      ["member punch no","tên cấu kiện","ten cau kien","punch no","item code","mã chi tiết","ma chi tiet","piece mark","piece id","unique","tên hồ sơ"],
    "member_no": ["member no","mã cấu kiện","ma cau kien","item no","part no","mark no"],
    "name":      ["tên hạng mục","ten hang muc","drawing","drawing no","ten bv","item name","tên cấu kiện","drawing name"],
    "zone":      ["zone","khu vực","khu vuc","area"],
    "phase":     ["phase","mã hạng mục","ma hang muc","giai đoạn","milestone","module"],
    "street":    ["street","trục","truc","grid line","axis"],
    "guid":      ["guid","uuid","unique id"],
    "note2":     ["note2","bundle","module","sub-module","bộ phận"],
    "type":      ["type","kiểu cấu kiện","kieu cau kien","category"],
    "symbol":    ["ký hiệu","ky hieu","symbol","original mark","short code"],
    "material":  ["material","vật liệu","vat lieu","grade","mác","mac"],
    "profile":   ["profile","profile type","tiết diện"],
    "section":   ["section","tiết diện","tiet dien","cross section"],
    "length_mm": ["length [mm]","length mm","chiều dài","chieu dai","length"],
    "weight_kg": ["weight [kg]","weight kg","khối lượng","khoi luong","weight","mass"],
    "paint_area":["paint area","diện tích sơn","dien tich son","painting area"],
    "workshop":  ["xưởng","xuong","workshop","nhà máy","nha may","factory","shop","plant","line"],
    "plan_date": ["plan date","ngày kế hoạch","ngay ke hoach","cutting plan","planned"],
    "priority":  ["priority","ưu tiên","uu tien"],
    "note":      ["note","ghi chú","ghi chu","remark","comment"],
    "drawing":   ["drawing no","drawing number","số bản vẽ","so ban ve","drawing"],
    "rev_no":    ["rev no","revision","phiên bản","rev"],
    "grid_position":["grid position","grid","vị trí","vi tri"],
    "elevation": ["elevation","cao độ","cao do"],
}

TEMPLATE_FILE = "mapping_templates.json"


def smart_detect_header_row(file_path, sheet_name):
    """Tự dò dòng tiêu đề: dòng có nhiều ô là chuỗi text ngắn (không null, không phải số/ngày)."""
    try:
        # Đọc thử 15 dòng đầu, không header
        df_preview = read_excel_any(file_path, sheet_name=sheet_name, header=None)
        df_preview = df_preview.head(15)
    except Exception:
        return 0
    best_row, best_score = 0, -1
    keywords_all = []
    for kws in SMART_KEYWORDS.values():
        keywords_all.extend(kws)
    for i, row in df_preview.iterrows():
        cells = [str(v).strip().lower() for v in row if v is not None and str(v).strip() and not pd.isna(v)]
        if len(cells) < 3: continue
        score = 0
        # +1 cho mỗi ô là chuỗi text ngắn (5-50 ký tự)
        for c in cells:
            if 2 <= len(c) <= 60 and not c.replace(".","").replace(",","").isdigit():
                score += 1
        # +3 cho mỗi ô khớp với keyword
        for c in cells:
            for kw in keywords_all:
                if kw in c:
                    score += 3; break
        if score > best_score:
            best_score, best_row = score, i
    return best_row


def smart_match_columns(headers, fields_widgets):
    """Match từng header với trường hệ thống dựa trên SMART_KEYWORDS. Trả về số trường đã map."""
    used_headers = set()
    n = 0
    norm_headers = []
    for h in headers:
        norm = str(h).replace("\n"," ").replace("_"," ").strip().lower()
        norm_headers.append((h, norm))
    # Lượt 1: match chính xác từ khóa đầu tiên (ưu tiên cao)
    for field, keywords in SMART_KEYWORDS.items():
        if field not in fields_widgets: continue
        best_h, best_score = None, 0
        for h, norm in norm_headers:
            if h in used_headers: continue
            # Score: match đầy đủ keyword = 10, contains = 5
            for rank, kw in enumerate(keywords):
                kw_norm = kw.lower()
                if norm == kw_norm:
                    score = 100 - rank
                elif kw_norm in norm:
                    score = 50 - rank
                elif norm in kw_norm and len(norm) >= 3:
                    score = 30 - rank
                else:
                    continue
                if score > best_score:
                    best_score, best_h = score, h
        if best_h:
            fields_widgets[field].set(best_h)
            used_headers.add(best_h)
            n += 1
    return n


def load_templates():
    """Load saved mapping templates from JSON."""
    if not os.path.exists(TEMPLATE_FILE):
        return {}
    try:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_templates(templates):
    with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)

STANDARD_FIELDS = [
    ("code","Mã cấu kiện (Member Punch No)"),
    ("member_no","Member No"),("name","Tên cấu kiện / Drawing"),
    ("zone","Zone"),("phase","Phase"),("street","Street"),("guid","GUID"),
    ("note2","Note2 (Module/Bundle)"),("type","Type"),("symbol","Ký hiệu"),
    ("material","Material"),("profile","Profile Type"),("section","Section"),
    ("length_mm","Length [mm]"),("weight_kg","Weight [kg]"),("paint_area","Paint Area [m2]"),
    ("workshop","Xưởng / Workshop"),("plan_date","Ngày kế hoạch"),
    ("priority","Priority"),("note","Ghi chú"),
    ("drawing","Drawing No"),("rev_no","Rev No"),
    ("grid_position","Grid Position"),("elevation","Elevation"),
]


def extract_date_from_filename(filename):
    name = os.path.basename(filename)
    m = re.search(r"(\d{1,2})[\.\-](\d{1,2})[\.\-](\d{4})", name)
    if m:
        d, mo, y = map(int, m.groups())
        try: return dt.date(y, mo, d).strftime("%Y-%m-%d")
        except ValueError: pass
    m = re.search(r"(\d{4})[\.\-](\d{1,2})[\.\-](\d{1,2})", name)
    if m:
        y, mo, d = map(int, m.groups())
        try: return dt.date(y, mo, d).strftime("%Y-%m-%d")
        except ValueError: pass
    return None


def parse_remark_types(remark):
    if not remark or not isinstance(remark, str): return []
    text = remark.upper(); found = []
    for kw, t in REMARK_TO_TYPES.items():
        if kw in text and t not in found: found.append(t)
    return found


def read_excel_any(path, sheet_name=None, header=0):
    ext = Path(path).suffix.lower()
    if ext == ".xlsb":
        return pd.read_excel(path, sheet_name=sheet_name, header=header, engine="pyxlsb")
    if ext in (".xlsx",".xlsm"):
        return pd.read_excel(path, sheet_name=sheet_name, header=header, engine="openpyxl")
    if ext == ".xls":
        return pd.read_excel(path, sheet_name=sheet_name, header=header)
    if ext == ".csv":
        return pd.read_csv(path, header=header)
    raise ValueError(f"Định dạng không hỗ trợ: {ext}")


def list_sheet_names(path):
    ext = Path(path).suffix.lower()
    if ext == ".xlsb":
        from pyxlsb import open_workbook
        with open_workbook(path) as wb:
            return list(wb.sheets)
    if ext in (".xlsx",".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        return wb.sheetnames
    return ["Sheet1"]


def excel_date_to_iso(v):
    if v is None or v == "" or pd.isna(v): return None
    if isinstance(v, (int, float)):
        try: return (dt.datetime(1899,12,30) + dt.timedelta(days=float(v))).strftime("%Y-%m-%d")
        except Exception: return str(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    return str(v)


def format_date_vn(iso_or_text):
    """Chuyển YYYY-MM-DD → DD/MM/YYYY để hiển thị kiểu Việt Nam."""
    if not iso_or_text: return ""
    s = str(iso_or_text).strip()
    if not s: return ""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{int(d):02d}/{int(mo):02d}/{y}"
    return s  # nếu đã ở định dạng khác, để nguyên


def parse_date_input(text):
    """Chấp nhận DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD → trả về ISO YYYY-MM-DD."""
    if not text: return ""
    s = str(text).strip()
    # DD/MM/YYYY hoặc DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", s)
    if m:
        d, mo, y = m.groups()
        try: return dt.date(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError: return s
    # YYYY-MM-DD
    m = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", s)
    if m:
        y, mo, d = m.groups()
        try: return dt.date(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError: return s
    return s


# ============================================================
class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            location TEXT, owner TEXT, start_date TEXT, end_date TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP );
        CREATE TABLE IF NOT EXISTS column_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL, mapping_type TEXT NOT NULL,
            mapping_json TEXT NOT NULL, header_row INTEGER DEFAULT 0, sheet_name TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL, code TEXT NOT NULL,
            data_json TEXT NOT NULL, status TEXT DEFAULT 'PENDING',
            UNIQUE (project_id, code),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL, component_id INTEGER NOT NULL,
            inspection_type TEXT NOT NULL, inspection_date TEXT,
            inspector TEXT, result TEXT, report_no TEXT, rfi_no TEXT, note TEXT,
            source_file TEXT, imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT, action TEXT, entity TEXT, entity_id INTEGER,
            detail TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP );
        CREATE INDEX IF NOT EXISTS idx_components_code ON components(project_id, code);
        CREATE INDEX IF NOT EXISTS idx_inspections_comp ON inspections(component_id, inspection_type);
        """)
        self.conn.commit()

    def log(self, user, action, entity, eid=None, detail=""):
        with self._lock:
            self.conn.execute("INSERT INTO audit_log(user_name,action,entity,entity_id,detail) VALUES (?,?,?,?,?)",
                              (user, action, entity, eid, detail))
            self.conn.commit()

    def list_projects(self):
        return self.conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()

    def create_project(self, code, name, location="", owner="", note=""):
        with self._lock:
            cur = self.conn.execute("INSERT INTO projects(code,name,location,owner,note) VALUES (?,?,?,?,?)",
                                    (code, name, location, owner, note))
            self.conn.commit()
            return cur.lastrowid

    def save_mapping(self, pid, mtype, mapping, header_row=0, sheet_name=None):
        with self._lock:
            self.conn.execute("DELETE FROM column_mappings WHERE project_id=? AND mapping_type=?", (pid, mtype))
            self.conn.execute("INSERT INTO column_mappings(project_id,mapping_type,mapping_json,header_row,sheet_name) VALUES (?,?,?,?,?)",
                              (pid, mtype, json.dumps(mapping, ensure_ascii=False), header_row, sheet_name))
            self.conn.commit()

    def upsert_component(self, pid, code, data):
        ex = self.conn.execute("SELECT id, data_json FROM components WHERE project_id=? AND code=?",
                               (pid, code)).fetchone()
        if ex:
            merged = json.loads(ex["data_json"])
            merged.update({k: v for k, v in data.items() if v is not None and v != ""})
            self.conn.execute("UPDATE components SET data_json=? WHERE id=?",
                              (json.dumps(merged, ensure_ascii=False, default=str), ex["id"]))
            return ex["id"], False
        cur = self.conn.execute("INSERT INTO components(project_id,code,data_json) VALUES (?,?,?)",
                                (pid, code, json.dumps(data, ensure_ascii=False, default=str)))
        return cur.lastrowid, True

    def find_component(self, pid, code):
        return self.conn.execute("SELECT * FROM components WHERE project_id=? AND code=?",
                                 (pid, code)).fetchone()

    def list_components(self, pid, status=None, search=""):
        q = "SELECT * FROM components WHERE project_id=?"; args = [pid]
        if status and status != "ALL":
            q += " AND status=?"; args.append(status)
        if search:
            q += " AND code LIKE ?"; args.append(f"%{search}%")
        q += " ORDER BY code LIMIT 10000"
        return self.conn.execute(q, args).fetchall()

    def count_status(self, pid):
        rows = self.conn.execute("SELECT status, COUNT(*) c FROM components WHERE project_id=? GROUP BY status",
                                 (pid,)).fetchall()
        d = {r["status"]: r["c"] for r in rows}
        d["TOTAL"] = sum(d.values())
        return d

    def add_inspection(self, pid, cid, itype, idate, inspector, result, rep, rfi, note, src):
        self.conn.execute("""INSERT INTO inspections(project_id,component_id,inspection_type,inspection_date,
            inspector,result,report_no,rfi_no,note,source_file) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (pid, cid, itype, idate, inspector, result, rep, rfi, note, src))
        if result == "PASS":
            new_status = "PASSED" if itype in ("DIR","VIR","NDT") else "IN_PROGRESS"
        elif result == "FAIL":
            new_status = "FAILED"
        else:
            new_status = "IN_PROGRESS"
        ex = self.conn.execute("SELECT inspection_type, result FROM inspections WHERE component_id=?",
                               (cid,)).fetchall()
        passed = {r["inspection_type"] for r in ex if r["result"] == "PASS"}
        if itype in ("DIR","VIR","NDT") and {"DIR","VIR","NDT"}.issubset(passed):
            new_status = "ACCEPTED"
        self.conn.execute("UPDATE components SET status=? WHERE id=?", (new_status, cid))

    def list_inspections(self, cid):
        return self.conn.execute("SELECT * FROM inspections WHERE component_id=? ORDER BY inspection_date DESC, id DESC",
                                 (cid,)).fetchall()


# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1340x800")
        self.minsize(1100, 680)
        self.user_name = os.getenv("USERNAME", "qc_user")
        self.db = DB(DB_FILE)
        self.current_project = None
        self._build_style()
        self._build_ui()
        self._refresh_projects()

    def _build_style(self):
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=6)
        style.configure("Status.TLabel", font=("Segoe UI", 9))
        style.configure("H1.TLabel", font=("Segoe UI", 14, "bold"), foreground="#1e3a8a")
        style.configure("H2.TLabel", font=("Segoe UI", 11, "bold"), foreground="#1e40af")

    def _build_ui(self):
        top = ttk.Frame(self, padding=8); top.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(top, text=APP_NAME, style="H1.TLabel").pack(side=tk.LEFT)
        ttk.Label(top, text=f"  User: {self.user_name}", style="Status.TLabel").pack(side=tk.LEFT, padx=12)
        ttk.Button(top, text="+ Dự án mới", command=self.new_project).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="⟳", width=3, command=self._refresh_projects).pack(side=tk.RIGHT, padx=2)
        ttk.Label(top, text="Dự án:").pack(side=tk.RIGHT)
        self.cbo_project = ttk.Combobox(top, width=42, state="readonly")
        self.cbo_project.pack(side=tk.RIGHT, padx=4)
        self.cbo_project.bind("<<ComboboxSelected>>", self._on_project_change)

        self.nb = ttk.Notebook(self); self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self._build_dashboard_tab()
        self._build_master_tab()
        self._build_daily_tab()
        self._build_components_tab()
        self._build_settings_tab()

        self.status_var = tk.StringVar(value="Sẵn sàng")
        sb = ttk.Frame(self, padding=4); sb.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(sb, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)

    # ============ DASHBOARD ============
    def _build_dashboard_tab(self):
        f = ttk.Frame(self.nb, padding=12); self.nb.add(f, text="📊 Tổng quan")

        # Hàng filter xưởng
        bar = ttk.Frame(f); bar.pack(fill=tk.X, pady=4)
        ttk.Label(bar, text="Tiến độ Nghiệm thu", style="H2.TLabel").pack(side=tk.LEFT)
        ttk.Label(bar, text="     Lọc xưởng:", foreground="#1e40af",
                  font=("Segoe UI",10,"bold")).pack(side=tk.LEFT, padx=(20,4))
        self.dash_workshop = ttk.Combobox(bar, width=18, state="readonly", values=["(Tất cả)"])
        self.dash_workshop.current(0)
        self.dash_workshop.pack(side=tk.LEFT, padx=4)
        self.dash_workshop.bind("<<ComboboxSelected>>", lambda e: self._refresh_dashboard())

        self.stats_frame = ttk.Frame(f, padding=8); self.stats_frame.pack(fill=tk.X, pady=8)
        self.stat_cards = {}
        for i, (k, lbl, col) in enumerate([
            ("TOTAL","Tổng","#1e3a8a"),("PENDING","Chưa KT","#64748b"),
            ("IN_PROGRESS","Đang KT","#d97706"),("PASSED","Đạt","#16a34a"),
            ("FAILED","Không đạt","#dc2626"),("ACCEPTED","Đã nghiệm thu","#0f766e"),
        ]):
            card = tk.Frame(self.stats_frame, bg="white", bd=1, relief=tk.SOLID, padx=14, pady=10)
            card.grid(row=0, column=i, padx=6, sticky="ew")
            self.stats_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=lbl, bg="white", fg="#475569", font=("Segoe UI",10)).pack(anchor="w")
            v = tk.Label(card, text="0", bg="white", fg=col, font=("Segoe UI",22,"bold")); v.pack(anchor="w")
            self.stat_cards[k] = v

        # Bảng thống kê theo từng xưởng
        ttk.Label(f, text="Thống kê theo Xưởng", style="H2.TLabel").pack(anchor="w", pady=(12,4))
        cols_ws = ("workshop","total","pending","in_progress","passed","failed","accepted","percent")
        self.tv_workshop = ttk.Treeview(f, columns=cols_ws, show="headings", height=7)
        names_ws = {"workshop":"Xưởng","total":"Tổng","pending":"Chưa KT","in_progress":"Đang KT",
                    "passed":"Đạt","failed":"K.đạt","accepted":"Đã NT","percent":"% Hoàn thành"}
        widths_ws = (120, 80, 80, 80, 80, 80, 100, 130)
        for c, w in zip(cols_ws, widths_ws):
            self.tv_workshop.heading(c, text=names_ws[c])
            self.tv_workshop.column(c, width=w, anchor="center")
        self.tv_workshop.pack(fill=tk.X, pady=4)

        ttk.Label(f, text="Lịch sử kiểm tra gần nhất", style="H2.TLabel").pack(anchor="w", pady=(12,4))
        cols = ("date","code","type","result","inspector","report")
        self.tv_recent = ttk.Treeview(f, columns=cols, show="headings", height=10)
        names = {"date":"Ngày KT","code":"Mã cấu kiện","type":"Loại","result":"KQ","inspector":"Người KT","report":"Số báo cáo"}
        for c, w in zip(cols, (110,180,80,80,140,260)):
            self.tv_recent.heading(c, text=names[c])
            self.tv_recent.column(c, width=w, anchor="center")
        self.tv_recent.pack(fill=tk.BOTH, expand=True, pady=4)

    # ============ MASTER ============
    def _build_master_tab(self):
        f = ttk.Frame(self.nb, padding=12); self.nb.add(f, text="📥 Import Danh sách Tổng")
        ttk.Label(f, text="Bước 1 – Chọn file PKL / Master List", style="H2.TLabel").pack(anchor="w")
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        self.master_file_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.master_file_var, width=80).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="Chọn file…", command=self._pick_master_file).pack(side=tk.LEFT, padx=4)

        ttk.Label(f, text="Bước 2 – Sheet & dòng tiêu đề", style="H2.TLabel").pack(anchor="w", pady=(8,0))
        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=6)
        ttk.Label(row2, text="Sheet:").pack(side=tk.LEFT)
        self.cbo_master_sheet = ttk.Combobox(row2, width=30, state="readonly"); self.cbo_master_sheet.pack(side=tk.LEFT, padx=6)
        ttk.Label(row2, text="Dòng tiêu đề:").pack(side=tk.LEFT, padx=(16,4))
        self.master_header_var = tk.IntVar(value=4)
        ttk.Spinbox(row2, from_=0, to=30, textvariable=self.master_header_var, width=5).pack(side=tk.LEFT)
        ttk.Button(row2, text="Đọc tiêu đề", command=self._read_master_headers).pack(side=tk.LEFT, padx=10)

        ttk.Label(f, text="Bước 3 – Mapping cột Excel → Trường", style="H2.TLabel").pack(anchor="w", pady=(8,0))
        fmap = ttk.Frame(f); fmap.pack(fill=tk.BOTH, expand=True, pady=6)
        self.master_map_widgets = {}
        canvas = tk.Canvas(fmap, height=300)
        scroll = ttk.Scrollbar(fmap, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for col, txt in enumerate(["Trường","Mô tả","Cột Excel"]):
            ttk.Label(inner, text=txt, font=("Segoe UI",10,"bold")).grid(row=0, column=col, padx=6, pady=4, sticky="w")
        for i, (field, desc) in enumerate(STANDARD_FIELDS, 1):
            ttk.Label(inner, text=field).grid(row=i, column=0, padx=6, pady=2, sticky="w")
            ttk.Label(inner, text=desc, foreground="#475569").grid(row=i, column=1, padx=6, pady=2, sticky="w")
            cbo = ttk.Combobox(inner, width=40, state="readonly")
            cbo.grid(row=i, column=2, padx=6, pady=2, sticky="w")
            self.master_map_widgets[field] = cbo

        row3 = ttk.Frame(f); row3.pack(fill=tk.X, pady=6)
        ttk.Button(row3, text="🤖 Auto-detect THÔNG MINH (mọi form PKL)",
                   command=self._smart_auto_detect).pack(side=tk.LEFT, padx=4)
        ttk.Button(row3, text="🔁 VIOLA", command=self._auto_map_viola).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text="🔁 PVF Hưng Yên", command=self._auto_map_pvf).pack(side=tk.LEFT, padx=2)

        row3b = ttk.Frame(f); row3b.pack(fill=tk.X, pady=4)
        ttk.Label(row3b, text="Template:", foreground="#1e40af",
                  font=("Segoe UI",9,"bold")).pack(side=tk.LEFT)
        self.cbo_template = ttk.Combobox(row3b, width=30, state="readonly")
        self.cbo_template.pack(side=tk.LEFT, padx=4)
        ttk.Button(row3b, text="📂 Tải", command=self._load_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3b, text="💾 Lưu mapping hiện tại thành template…",
                   command=self._save_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3b, text="🗑 Xóa template", command=self._delete_template).pack(side=tk.LEFT, padx=2)
        self._refresh_templates_combo()

        row4 = ttk.Frame(f); row4.pack(fill=tk.X, pady=10)
        ttk.Button(row4, text="💾 Lưu Mapping & Import", command=self._import_master).pack(side=tk.LEFT, padx=4)
        ttk.Button(row4, text="🧹 Xóa toàn bộ cấu kiện", command=self._clear_components).pack(side=tk.LEFT, padx=20)

    def _pick_master_file(self):
        p = filedialog.askopenfilename(filetypes=[("Excel","*.xlsb;*.xlsx;*.xlsm;*.xls;*.csv"),("All","*.*")])
        if not p: return
        self.master_file_var.set(p)
        try:
            sheets = list_sheet_names(p)
            self.cbo_master_sheet["values"] = sheets
            self.cbo_master_sheet.set("PKL" if "PKL" in sheets else sheets[0])
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _read_master_headers(self):
        p = self.master_file_var.get()
        if not p: messagebox.showwarning("Thiếu file",""); return
        try:
            df = read_excel_any(p, sheet_name=self.cbo_master_sheet.get() or 0,
                                header=self.master_header_var.get())
            headers = [str(c) for c in df.columns]
            for cbo in self.master_map_widgets.values(): cbo["values"] = [""] + headers
            self._cached_master_df = df
            self._cached_master_headers = headers
            self._set_status(f"Đã đọc {len(headers)} cột, {len(df)} dòng.")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _smart_auto_detect(self):
        """Tự dò header row + map cột thông minh cho mọi form PKL."""
        p = self.master_file_var.get()
        if not p:
            messagebox.showwarning("Thiếu file","Hãy chọn file Excel trước."); return
        # Bước 1: tự dò header row
        try:
            best_row = smart_detect_header_row(p, self.cbo_master_sheet.get() or 0)
            self.master_header_var.set(best_row)
        except Exception as e:
            messagebox.showerror("Lỗi dò header", str(e)); return
        # Bước 2: đọc tiêu đề
        self._read_master_headers()
        headers = getattr(self, "_cached_master_headers", [])
        if not headers: return
        # Bước 3: smart match
        # Reset các mapping cũ trước
        for cbo in self.master_map_widgets.values(): cbo.set("")
        n = smart_match_columns(headers, self.master_map_widgets)
        messagebox.showinfo("Auto-detect",
            f"Đã tự dò:\n  • Dòng tiêu đề: {best_row}\n  • Số cột map được: {n}/{len(self.master_map_widgets)}\n\n"
            f"Hãy kiểm tra mapping và bổ sung thủ công nếu cần, rồi nhấn '💾 Lưu mapping hiện tại thành template…' để dùng lại lần sau.")

    def _refresh_templates_combo(self):
        templates = load_templates()
        names = sorted(templates.keys())
        self.cbo_template["values"] = names
        if names: self.cbo_template.set(names[0])

    def _save_template(self):
        from tkinter import simpledialog
        mapping = {f: w.get() for f, w in self.master_map_widgets.items() if w.get()}
        if not mapping:
            messagebox.showwarning("Trống","Chưa có mapping nào để lưu."); return
        name = simpledialog.askstring("Lưu template",
            "Đặt tên cho template này (vd: 'PVF Hưng Yên', 'Form Đại Dũng 2026'):",
            parent=self)
        if not name: return
        templates = load_templates()
        templates[name] = {
            "mapping": mapping,
            "header_row": self.master_header_var.get(),
            "sheet_name": self.cbo_master_sheet.get(),
        }
        save_templates(templates)
        self._refresh_templates_combo()
        self.cbo_template.set(name)
        messagebox.showinfo("Đã lưu", f"Template '{name}' đã được lưu.\nLần sau chỉ cần chọn tên này và nhấn 'Tải'.")

    def _load_template(self):
        name = self.cbo_template.get()
        if not name:
            messagebox.showwarning("Chưa chọn","Chưa chọn template."); return
        templates = load_templates()
        if name not in templates:
            messagebox.showerror("Không tìm thấy", f"Template '{name}' không tồn tại."); return
        t = templates[name]
        if t.get("header_row") is not None:
            self.master_header_var.set(t["header_row"])
        if t.get("sheet_name"):
            try: self.cbo_master_sheet.set(t["sheet_name"])
            except Exception: pass
        self._read_master_headers()
        headers = getattr(self, "_cached_master_headers", [])
        if not headers: return
        for cbo in self.master_map_widgets.values(): cbo.set("")
        n = 0
        for f, h in t["mapping"].items():
            if h in headers and f in self.master_map_widgets:
                self.master_map_widgets[f].set(h); n += 1
            else:
                # soft match
                target = str(h).replace("\n"," ").strip().lower()
                for hh in headers:
                    if str(hh).replace("\n"," ").strip().lower() == target and f in self.master_map_widgets:
                        self.master_map_widgets[f].set(hh); n += 1; break
        self._set_status(f"Đã tải template '{name}': {n} trường khớp.")

    def _delete_template(self):
        name = self.cbo_template.get()
        if not name: return
        if not messagebox.askyesno("Xác nhận", f"Xóa template '{name}'?"): return
        templates = load_templates()
        templates.pop(name, None)
        save_templates(templates)
        self._refresh_templates_combo()

    def _auto_map_viola(self):
        viola = {
            "code":"Member Punch No\nTên hồ sơ","member_no":"Member No","name":"Drawing",
            "zone":"Zone","phase":"Phase","street":"Street","guid":"GUID","note2":"Note2",
            "type":"Type","symbol":"Ký hiệu","material":"Material","profile":"Profile Type",
            "section":"Section","length_mm":"Length [mm]","weight_kg":"Weight [kg]",
            "paint_area":"Paint Area [m2]","workshop":"xưởng","plan_date":"After Cutting Plan Date",
            "priority":"Priority","note":"Note","drawing":"Drawing","rev_no":"Rev No ",
            "grid_position":"Grid Position","elevation":"Elevation",
        }
        headers = getattr(self, "_cached_master_headers", [])
        if not headers: messagebox.showwarning("Chưa đọc tiêu đề",""); return
        n = 0
        for f, h in viola.items():
            if h in headers and f in self.master_map_widgets:
                self.master_map_widgets[f].set(h); n += 1
        self._set_status(f"Đã auto-map {n} trường VIOLA.")

    def _auto_map_pvf(self):
        """Auto-map cho PKL PVF Hưng Yên / Sân vận động - header ở dòng 3."""
        # Tự đặt dòng tiêu đề về 3 và đọc lại
        self.master_header_var.set(3)
        self._read_master_headers()
        headers = getattr(self, "_cached_master_headers", [])
        if not headers: return
        pvf = {
            "code": "Tên cấu kiện",
            "member_no": "Mã cấu kiện",
            "name": "Tên Hạng mục",
            "zone": "Khu vực\n(Zone)",
            "phase": "Mã hạng mục",
            "street": "Trục",
            "guid": "GUID",
            "type": "Type",
            "symbol": "Original Mark",
            "material": "Material",
            "section": "Section",
            "length_mm": "Length [mm]",
            "weight_kg": "Weight [kg]",
            "workshop": "Nhà máy",
            "rev_no": "Rev No",
        }
        n = 0
        for f, h in pvf.items():
            # Match chính xác trước
            if h in headers and f in self.master_map_widgets:
                self.master_map_widgets[f].set(h); n += 1; continue
            # Match mềm: bỏ \n và so sánh
            target = h.replace("\n"," ").strip().lower()
            for hh in headers:
                if str(hh).replace("\n"," ").strip().lower() == target and f in self.master_map_widgets:
                    self.master_map_widgets[f].set(hh); n += 1; break
        self._set_status(f"Đã auto-map {n} trường PVF Hưng Yên (header row=3).")

    def _import_master(self):
        if not self.current_project: messagebox.showwarning("Chưa chọn dự án",""); return
        df = getattr(self, "_cached_master_df", None)
        if df is None: messagebox.showwarning("Chưa đọc file",""); return
        mapping = {f: w.get() for f, w in self.master_map_widgets.items() if w.get()}
        if "code" not in mapping:
            messagebox.showerror("Thiếu mapping","Phải map 'code'."); return
        self.db.save_mapping(self.current_project["id"], "MASTER", mapping,
                             header_row=self.master_header_var.get(),
                             sheet_name=self.cbo_master_sheet.get())
        threading.Thread(target=self._do_import_master, args=(df, mapping), daemon=True).start()

    def _do_import_master(self, df, mapping):
        try:
            pid = self.current_project["id"]
            ok = new = upd = 0
            with self.db._lock:
                for _, row in df.iterrows():
                    data = {}
                    for f, col in mapping.items():
                        v = row.get(col, None)
                        if pd.isna(v): v = None
                        if f == "plan_date": v = excel_date_to_iso(v)
                        data[f] = v
                    code = str(data.get("code") or "").strip()
                    if not code or code.lower() == "nan": continue
                    _, is_new = self.db.upsert_component(pid, code, data)
                    ok += 1; new += 1 if is_new else 0; upd += 0 if is_new else 1
                self.db.conn.commit()
            self.db.log(self.user_name, "IMPORT_MASTER", "project", pid, f"rows={len(df)}, ok={ok}, new={new}, upd={upd}")
            self.after(0, lambda: messagebox.showinfo("Hoàn tất",
                f"Tổng: {len(df)}\nĐã ghi: {ok}\nMới: {new}\nCập nhật: {upd}"))
            self.after(0, lambda: setattr(self, "_col_filter_populated_pid", None))
            self.after(0, self._refresh_components); self.after(0, self._refresh_dashboard)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Lỗi import", str(e)))

    def _clear_components(self):
        if not self.current_project: return
        if not messagebox.askyesno("Xác nhận","Xóa TOÀN BỘ cấu kiện?"): return
        with self.db._lock:
            self.db.conn.execute("DELETE FROM components WHERE project_id=?", (self.current_project["id"],))
            self.db.conn.commit()
        self._col_filter_populated_pid = None
        self._refresh_components(); self._refresh_dashboard()

    # ============ DAILY ============
    def _build_daily_tab(self):
        f = ttk.Frame(self.nb, padding=12); self.nb.add(f, text="📤 Import File Kiểm tra Hàng ngày")
        ttk.Label(f, text="Chọn loại kiểm tra và file Excel", style="H2.TLabel").pack(anchor="w")
        row = ttk.Frame(f); row.pack(fill=tk.X, pady=6)
        ttk.Label(row, text="Loại kiểm tra:").pack(side=tk.LEFT)
        self.cbo_inspect_type = ttk.Combobox(row, width=50, state="readonly",
            values=[f"{k} - {v}" for k, v in INSPECTION_TYPES])
        self.cbo_inspect_type.current(0); self.cbo_inspect_type.pack(side=tk.LEFT, padx=8)

        row2 = ttk.Frame(f); row2.pack(fill=tk.X, pady=6)
        self.daily_file_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.daily_file_var, width=80).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="Chọn file…", command=self._pick_daily_file).pack(side=tk.LEFT, padx=4)

        row3 = ttk.Frame(f); row3.pack(fill=tk.X, pady=6)
        ttk.Label(row3, text="Sheet:").pack(side=tk.LEFT)
        self.cbo_daily_sheet = ttk.Combobox(row3, width=30, state="readonly"); self.cbo_daily_sheet.pack(side=tk.LEFT, padx=6)
        ttk.Label(row3, text="Dòng tiêu đề:").pack(side=tk.LEFT, padx=(16,4))
        self.daily_header_var = tk.IntVar(value=2)
        ttk.Spinbox(row3, from_=0, to=30, textvariable=self.daily_header_var, width=5).pack(side=tk.LEFT)
        ttk.Button(row3, text="Đọc tiêu đề", command=self._read_daily_headers).pack(side=tk.LEFT, padx=10)

        ttk.Label(f, text="Mapping cột", style="H2.TLabel").pack(anchor="w", pady=(8,0))
        fmap = ttk.Frame(f); fmap.pack(fill=tk.X, pady=6)
        self.daily_map_widgets = {}
        for i, (field, desc) in enumerate([
            ("code","Mã cấu kiện"),("inspection_date","Ngày kiểm tra"),
            ("inspector","Người kiểm tra"),("result","Kết quả - trống = PASS"),
            ("report_no","Số báo cáo"),("rfi_no","RFI No."),("note","Ghi chú / Remark"),
        ]):
            ttk.Label(fmap, text=desc).grid(row=i, column=0, padx=6, pady=2, sticky="w")
            cbo = ttk.Combobox(fmap, width=50, state="readonly")
            cbo.grid(row=i, column=1, padx=6, pady=2, sticky="w")
            self.daily_map_widgets[field] = cbo

        # Ô nhập NFI và Ngày kiểm tra áp cho cả file
        row_nfi = ttk.Frame(f); row_nfi.pack(fill=tk.X, pady=4)
        ttk.Label(row_nfi, text="Số NFI:", foreground="#1e40af",
                  font=("Segoe UI",10,"bold")).pack(side=tk.LEFT, padx=4)
        self.daily_nfi_var = tk.StringVar()
        ttk.Entry(row_nfi, textvariable=self.daily_nfi_var, width=28).pack(side=tk.LEFT, padx=4)
        ttk.Label(row_nfi, text="Ngày kiểm tra:", foreground="#1e40af",
                  font=("Segoe UI",10,"bold")).pack(side=tk.LEFT, padx=(20,4))
        self.daily_date_var = tk.StringVar()
        ttk.Entry(row_nfi, textvariable=self.daily_date_var, width=16).pack(side=tk.LEFT, padx=4)
        ttk.Label(row_nfi, text="(YYYY-MM-DD, tự lấy từ tên file)",
                  foreground="#64748b").pack(side=tk.LEFT, padx=4)

        row4 = ttk.Frame(f); row4.pack(fill=tk.X, pady=12)
        ttk.Button(row4, text="🔁 Auto-mapping NDT VIOLA", command=self._auto_map_daily_ndt).pack(side=tk.LEFT, padx=4)
        ttk.Button(row4, text="🔁 Auto-mapping DGRP VIOLA (Bàn giao)", command=self._auto_map_daily_dgrp).pack(side=tk.LEFT, padx=4)
        ttk.Button(row4, text="▶ Import và cập nhật trạng thái", command=self._import_daily).pack(side=tk.LEFT, padx=10)
        ttk.Button(row4, text="🔍 Debug Match", command=self._debug_match).pack(side=tk.LEFT, padx=4)

        ttk.Label(f, text="DGRP: app tự phân tích Remark ('Dim,Visual,NDT') tạo nhiều inspection. Ngày lấy từ tên file.",
                  foreground="#0f5132", wraplength=1100).pack(anchor="w", padx=4)
        self.daily_log = tk.Text(f, height=10, wrap="word"); self.daily_log.pack(fill=tk.BOTH, expand=True, pady=8)

    def _pick_daily_file(self):
        p = filedialog.askopenfilename(filetypes=[("Excel","*.xlsb;*.xlsx;*.xlsm;*.xls;*.csv"),("All","*.*")])
        if not p: return
        self.daily_file_var.set(p)
        # Tự điền ngày kiểm tra từ tên file (vd: 13.5.2026 → 2026-05-13)
        d = extract_date_from_filename(p)
        if d: self.daily_date_var.set(d)
        try:
            sheets = list_sheet_names(p)
            self.cbo_daily_sheet["values"] = sheets
            t = (self.cbo_inspect_type.get() or "").split(" ")[0]
            self.cbo_daily_sheet.set(t if t in sheets else sheets[0])
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _read_daily_headers(self):
        p = self.daily_file_var.get()
        if not p: return
        try:
            df = read_excel_any(p, sheet_name=self.cbo_daily_sheet.get() or 0,
                                header=self.daily_header_var.get())
            headers = [str(c) for c in df.columns]
            for cbo in self.daily_map_widgets.values(): cbo["values"] = [""] + headers
            self._cached_daily_df = df
            self._cached_daily_headers = headers
            self._set_status(f"Đã đọc {len(headers)} cột, {len(df)} dòng.")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _auto_map_daily_ndt(self):
        if self.daily_file_var.get():
            try:
                sheets = list_sheet_names(self.daily_file_var.get())
                if "NDT" in sheets: self.cbo_daily_sheet.set("NDT")
            except Exception: pass
        self.daily_header_var.set(2)
        for i, (k, _) in enumerate(INSPECTION_TYPES):
            if k == "NDT": self.cbo_inspect_type.current(i); break
        self._read_daily_headers()
        guess = {"code":"Tên cấu kiện\nItem Name","inspection_date":"Ngày kiểm tra\nDate of Inspection",
                 "inspector":"QC Check","report_no":"Welding Procedure no.",
                 "rfi_no":"Số bản vẽ\nDrawing no.","note":"Chi chú\nRemark"}
        headers = getattr(self, "_cached_daily_headers", [])
        if not headers: return
        n = 0
        for f, h in guess.items():
            if h in headers and f in self.daily_map_widgets:
                self.daily_map_widgets[f].set(h); n += 1
            else:
                for hh in headers:
                    if hh and hh.split("\n")[0].strip().lower() == h.split("\n")[0].strip().lower():
                        self.daily_map_widgets[f].set(hh); n += 1; break
        self._set_status(f"Auto-map {n} cột (NDT).")

    def _auto_map_daily_dgrp(self):
        if not self.daily_file_var.get():
            messagebox.showwarning("Thiếu file",""); return
        try:
            sheets = list_sheet_names(self.daily_file_var.get())
            target = None
            for s in sheets:
                if any(k in s.upper() for k in ("BÀN GIAO","BIEN BAN","BIÊN BẢN")):
                    target = s; break
            if target: self.cbo_daily_sheet.set(target)
            elif sheets: self.cbo_daily_sheet.set(sheets[0])
        except Exception: pass
        # Tự dò header row: file DGRP có thể có header ở dòng 11 hoặc 12
        try:
            best_hr = 11
            for try_hr in (11, 12, 10, 9, 13):
                try:
                    df_t = read_excel_any(self.daily_file_var.get(),
                                          sheet_name=self.cbo_daily_sheet.get() or 0,
                                          header=try_hr)
                    hdrs = [str(c) for c in df_t.columns]
                    # Tìm cột "Tên - Mã số"
                    if any("Tên - Mã số" in h or "Name - Code" in h or "Mã số" in h for h in hdrs):
                        best_hr = try_hr; break
                except Exception: continue
            self.daily_header_var.set(best_hr)
        except Exception:
            self.daily_header_var.set(11)
        for i, (k, _) in enumerate(INSPECTION_TYPES):
            if k == "DGRP": self.cbo_inspect_type.current(i); break
        self._read_daily_headers()
        headers = getattr(self, "_cached_daily_headers", [])
        if not headers: return
        # Tìm cột mã linh hoạt: ưu tiên "Tên - Mã số", fallback Unnamed: 3, Unnamed: 2
        code_col = None
        for h in headers:
            if "Tên - Mã số" in h or "Name - Code" in h:
                code_col = h; break
        if not code_col:
            for h in ("Unnamed: 3","Unnamed: 2"):
                if h in headers: code_col = h; break
        # Tìm cột remark
        note_col = None
        for h in headers:
            if "Ghi Chú" in h or "Remark" in h:
                note_col = h; break
        if not note_col and "Unnamed: 17" in headers: note_col = "Unnamed: 17"
        guess = {"code": code_col, "note": note_col,
                 "report_no": "Barcode" if "Barcode" in headers else None,
                 # KHÔNG auto-map rfi_no nữa - user nhập số NFI tay ở ô riêng
                 }
        n = 0
        for f, h in guess.items():
            if h and h in headers and f in self.daily_map_widgets:
                self.daily_map_widgets[f].set(h); n += 1
        d = extract_date_from_filename(self.daily_file_var.get())
        self._set_status(f"Auto-map DGRP: header row={self.daily_header_var.get()}, {n} cột, ngày: {d or 'hôm nay'}")

    def _import_daily(self):
        if not self.current_project: messagebox.showwarning("Chưa chọn dự án",""); return
        df = getattr(self, "_cached_daily_df", None)
        if df is None: messagebox.showwarning("Chưa đọc file",""); return
        mapping = {f: w.get() for f, w in self.daily_map_widgets.items() if w.get()}
        if "code" not in mapping:
            messagebox.showerror("Thiếu mapping","Phải map 'code'."); return
        itype = self.cbo_inspect_type.get().split(" - ")[0]
        threading.Thread(target=self._do_import_daily,
                         args=(df, mapping, itype, self.daily_file_var.get()),
                         daemon=True).start()

    def _do_import_daily(self, df, mapping, itype, src_file):
        try:
            pid = self.current_project["id"]
            ok = not_found = ins_count = 0; logs = []
            # Ưu tiên ngày nhập tay > ngày từ tên file
            manual_date = (self.daily_date_var.get() or "").strip()
            date_from_file = manual_date or extract_date_from_filename(src_file) or dt.date.today().strftime("%Y-%m-%d")
            manual_nfi = (self.daily_nfi_var.get() or "").strip()
            with self.db._lock:
                for _, row in df.iterrows():
                    cr = row.get(mapping["code"])
                    if pd.isna(cr): continue
                    code = str(cr).strip()
                    if not code or code.lower() == "nan": continue
                    if len(code) <= 2 or code.upper() in ("TOTAL","PRINT"): continue
                    # Tạo các phiên bản mã có thể có để match
                    candidates = [code]
                    # Tách prefix "1-", "2-", "3-" ở đầu (file DGRP có dạng "1-01ERC3001-001")
                    m = re.match(r"^\d+-(.+)$", code)
                    if m: candidates.append(m.group(1))
                    # Tách suffix "-J1", "-J3-R1" (file NDT mối hàn)
                    if "-J" in code: candidates.append(code.split("-J")[0])
                    # Match theo thứ tự ưu tiên
                    comp = None
                    for cand in candidates:
                        comp = self.db.find_component(pid, cand)
                        if comp: break
                    if not comp:
                        not_found += 1
                        if len(logs) < 50: logs.append(f"  ⚠ Không tìm thấy: {code}")
                        continue
                    d = excel_date_to_iso(row.get(mapping.get("inspection_date"))) if mapping.get("inspection_date") else None
                    if not d: d = date_from_file
                    ins = row.get(mapping.get("inspector")) if mapping.get("inspector") else None
                    ins_s = str(ins) if ins and not pd.isna(ins) else ""
                    nv = row.get(mapping.get("note"),"") if mapping.get("note") else ""
                    note_s = str(nv) if nv and not pd.isna(nv) else ""
                    rep_s = str(row.get(mapping.get("report_no"),"") or "")
                    rfi_s = manual_nfi or str(row.get(mapping.get("rfi_no"),"") or "")
                    rr = row.get(mapping.get("result")) if mapping.get("result") else None
                    rv = "PASS"
                    chk = (str(rr) if rr else "") + " " + note_s
                    if any(k in chk.upper() for k in ("FAIL","REJ","NG")): rv = "FAIL"
                    elif "RECHECK" in chk.upper() or "-R1" in code or "-R2" in code: rv = "RECHECK"

                    if itype == "DGRP":
                        types = parse_remark_types(note_s) or ["DIR"]
                        for t in types:
                            self.db.add_inspection(pid, comp["id"], t, d, ins_s, rv, rep_s, rfi_s, note_s, os.path.basename(src_file))
                            ins_count += 1
                    else:
                        self.db.add_inspection(pid, comp["id"], itype, d, ins_s, rv, rep_s, rfi_s, note_s, os.path.basename(src_file))
                        ins_count += 1
                    ok += 1
                self.db.conn.commit()
            self.db.log(self.user_name, "IMPORT_DAILY", "project", pid,
                        f"type={itype}, ok={ok}, ins={ins_count}, nf={not_found}")
            self.after(0, lambda: self._daily_log_msg(
                f"\n=== {dt.datetime.now():%H:%M:%S} | {itype} | {date_from_file} ===\n"
                f"Cấu kiện: {ok}  |  Inspection: {ins_count}  |  Không khớp: {not_found}\n"
                + "\n".join(logs[:30])))
            self.after(0, self._refresh_components); self.after(0, self._refresh_dashboard)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Lỗi", str(e)))

    def _daily_log_msg(self, msg):
        self.daily_log.insert(tk.END, msg + "\n"); self.daily_log.see(tk.END)

    def _debug_match(self):
        """So sánh mã master DB vs mã daily file. Giúp chẩn đoán không khớp."""
        if not self.current_project:
            messagebox.showwarning("Chưa chọn dự án",""); return
        pid = self.current_project["id"]
        # 10 mã master
        master_rows = self.db.conn.execute(
            "SELECT code FROM components WHERE project_id=? ORDER BY code LIMIT 10", (pid,)).fetchall()
        master_total = self.db.conn.execute(
            "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,)).fetchone()["c"]
        # 10 mã daily file (nếu đã đọc)
        df = getattr(self, "_cached_daily_df", None)
        mapping = {f: w.get() for f, w in self.daily_map_widgets.items() if w.get()}
        msg = f"\n=========== DEBUG MATCH | Dự án: {self.current_project['code']} ===========\n"
        msg += f"📋 MASTER DB: {master_total} cấu kiện\n"
        msg += "10 mã đầu trong DB:\n"
        for r in master_rows:
            msg += f"    • {r['code']}\n"
        if df is None or "code" not in mapping:
            msg += "\n⚠ Chưa đọc file daily hoặc chưa map cột 'code' - hãy 'Đọc tiêu đề' và Auto-map trước.\n"
        else:
            msg += f"\n📥 DAILY FILE: {len(df)} dòng (cột code = '{mapping['code']}')\n"
            msg += "10 mã đầu (đã tách prefix):\n"
            shown = 0
            for _, row in df.iterrows():
                if shown >= 10: break
                v = row.get(mapping["code"])
                if pd.isna(v): continue
                code = str(v).strip()
                if not code or len(code) <= 2 or code.upper() in ("TOTAL","PRINT"): continue
                # Áp prefix stripping
                stripped = code
                m = re.match(r"^\d+-(.+)$", code)
                if m: stripped = m.group(1)
                # Check trong master
                found = bool(self.db.find_component(pid, code) or
                             (m and self.db.find_component(pid, stripped)))
                mark = "✅" if found else "❌"
                msg += f"    {mark} '{code}' → tách thành '{stripped}'\n"
                shown += 1
        msg += "\nNếu mã master KHÁC định dạng mã daily (sau khi tách prefix), bạn cần re-import master với mapping 'code' đúng (Member Punch No / Tên cấu kiện).\n"
        msg += "===================================================\n"
        self._daily_log_msg(msg)

    # ============ COMPONENTS TAB ============
    def _build_components_tab(self):
        f = ttk.Frame(self.nb, padding=8); self.nb.add(f, text="🔧 Danh sách Cấu kiện")

        # Hàng 1: Trạng thái + Tìm + Nút
        bar = ttk.Frame(f); bar.pack(fill=tk.X, pady=4)
        ttk.Label(bar, text="Trạng thái:").pack(side=tk.LEFT)
        self.cbo_filter = ttk.Combobox(bar, width=15, state="readonly",
            values=["ALL","PENDING","IN_PROGRESS","PASSED","FAILED","ACCEPTED"])
        self.cbo_filter.current(0); self.cbo_filter.pack(side=tk.LEFT, padx=4)
        self.cbo_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_components())

        ttk.Label(bar, text="Tìm mã:").pack(side=tk.LEFT, padx=(12,0))
        self.search_var = tk.StringVar()
        es = ttk.Entry(bar, textvariable=self.search_var, width=24); es.pack(side=tk.LEFT, padx=4)
        es.bind("<Return>", lambda e: self._refresh_components())
        ttk.Button(bar, text="🔎 Lọc", command=self._refresh_components).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="🧹 Xóa tất cả lọc", command=self._clear_filters).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="📊 Xuất Excel báo cáo", command=self._export_report).pack(side=tk.RIGHT)

        # Hàng 2: Filter dropdown kiểu Excel
        bar2 = ttk.Frame(f); bar2.pack(fill=tk.X, pady=2)
        ttk.Label(bar2, text="Lọc cột:", foreground="#1e40af",
                  font=("Segoe UI",9,"bold")).pack(side=tk.LEFT)
        self.col_filters = {}
        for field, label, w in [
            ("zone","Zone",14),("phase","Phase",22),("material","Material",12),
            ("workshop","Xưởng",10),("type","Type",16),
        ]:
            ttk.Label(bar2, text=label+":").pack(side=tk.LEFT, padx=(10,2))
            cbo = ttk.Combobox(bar2, width=w, state="readonly", values=["(Tất cả)"])
            cbo.current(0); cbo.pack(side=tk.LEFT, padx=2)
            cbo.bind("<<ComboboxSelected>>", lambda e: self._refresh_components())
            self.col_filters[field] = cbo

        # Treeview - cột mới theo yêu cầu QC
        cols = ("code","name","rev_no","workshop","status","nfi_no","insp_date")
        self.tv_comp = ttk.Treeview(f, columns=cols, show="headings", height=22)
        self._tv_comp_headers = {
            "code":"Tên cấu kiện","name":"Bản vẽ","rev_no":"Revision",
            "workshop":"Xưởng","status":"Tình trạng",
            "nfi_no":"Số NFI","insp_date":"Ngày kiểm tra"
        }
        widths = (160, 200, 90, 100, 120, 200, 130)
        # Căn giữa TẤT CẢ cột cho đồng đều
        self._sort_state = {"col": None, "reverse": False}
        for c, w in zip(cols, widths):
            self.tv_comp.heading(c, text=self._tv_comp_headers[c] + "  ⇅",
                                 anchor="center",
                                 command=lambda col=c: self._sort_components_by(col))
            self.tv_comp.column(c, width=w, anchor="center")
        self.tv_comp.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        # Double-click: NFI/Ngày KT → inline edit; cột khác → mở chi tiết
        self.tv_comp.bind("<Double-1>", self._on_comp_double_click)

        for st, color in [("PENDING","#f1f5f9"),("IN_PROGRESS","#fef3c7"),
                          ("PASSED","#dcfce7"),("FAILED","#fee2e2"),("ACCEPTED","#bbf7d0")]:
            self.tv_comp.tag_configure(st, background=color)

    def _sort_components_by(self, col):
        items = [(self.tv_comp.set(k, col), k) for k in self.tv_comp.get_children("")]
        reverse = self._sort_state["col"] == col and not self._sort_state["reverse"]
        def keyf(x):
            v = x[0]
            try: return (0, float(v))
            except (ValueError, TypeError): return (1, str(v).lower())
        items.sort(key=keyf, reverse=reverse)
        for idx, (_, k) in enumerate(items):
            self.tv_comp.move(k, "", idx)
        self._sort_state = {"col": col, "reverse": reverse}
        for c in self._tv_comp_headers:
            arrow = "  ▼" if (c == col and reverse) else ("  ▲" if c == col else "  ⇅")
            self.tv_comp.heading(c, text=self._tv_comp_headers[c] + arrow)

    def _on_comp_double_click(self, evt):
        """Xử lý double-click: cột NFI/Ngày KT → inline edit, cột khác → chi tiết."""
        region = self.tv_comp.identify("region", evt.x, evt.y)
        if region != "cell": return
        col_id = self.tv_comp.identify_column(evt.x)
        try: col_idx = int(col_id.replace("#","")) - 1
        except ValueError: return
        cols = ("code","name","rev_no","workshop","status","nfi_no","insp_date")
        if col_idx < 0 or col_idx >= len(cols): return
        col_name = cols[col_idx]
        item = self.tv_comp.identify_row(evt.y)
        if not item: return
        # Cho phép sửa: Bản vẽ, Revision, Xưởng, Số NFI, Ngày kiểm tra
        if col_name in ("name","rev_no","workshop","nfi_no","insp_date"):
            self._inline_edit_cell(item, col_idx, col_name)
        else:
            self._show_component_detail(None, item_override=item)

    def _inline_edit_cell(self, item, col_idx, col_name):
        """Hiển thị Entry ngay tại ô để nhập giá trị, Enter để lưu, Esc để huỷ."""
        x, y, w, h = self.tv_comp.bbox(item, column=f"#{col_idx+1}")
        current = self.tv_comp.set(item, col_name)
        entry = tk.Entry(self.tv_comp)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current); entry.focus_set(); entry.select_range(0, tk.END)

        def save(_evt=None):
            new_val = entry.get().strip()
            entry.destroy()
            # Lưu vào DB
            try:
                cid = int(item)
                row = self.db.conn.execute("SELECT data_json FROM components WHERE id=?", (cid,)).fetchone()
                if not row: return
                data = json.loads(row["data_json"])
                # Map col_name → field trong data_json
                field_map = {
                    "nfi_no": "manual_nfi",
                    "insp_date": "manual_insp_date",
                    "name": "manual_drawing",
                    "rev_no": "rev_no",
                    "workshop": "workshop",
                }
                field = field_map.get(col_name, "manual_" + col_name)
                # Với ngày: chuẩn hoá DD/MM/YYYY → YYYY-MM-DD trước khi lưu
                if col_name == "insp_date" and new_val:
                    new_val = parse_date_input(new_val)
                if new_val:
                    data[field] = new_val
                else:
                    data.pop(field, None)
                with self.db._lock:
                    self.db.conn.execute("UPDATE components SET data_json=? WHERE id=?",
                        (json.dumps(data, ensure_ascii=False, default=str), cid))
                    self.db.conn.commit()
                # Cập nhật tại chỗ
                self.tv_comp.set(item, col_name, new_val)
                self._set_status(f"Đã lưu {self._tv_comp_headers[col_name]} cho cấu kiện #{cid}: '{new_val}'")
            except Exception as e:
                messagebox.showerror("Lỗi lưu", str(e))

        def cancel(_evt=None):
            entry.destroy()

        entry.bind("<Return>", save)
        entry.bind("<FocusOut>", save)
        entry.bind("<Escape>", cancel)

    def _show_component_detail(self, _evt, item_override=None):
        item = item_override or (self.tv_comp.selection()[0] if self.tv_comp.selection() else None)
        if not item: return
        code = self.tv_comp.item(item)["values"][0]
        comp = self.db.find_component(self.current_project["id"], code)
        if not comp: return
        w = tk.Toplevel(self); w.title(f"Cấu kiện: {code}"); w.geometry("780x560")
        nb = ttk.Notebook(w); nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        f1 = ttk.Frame(nb, padding=10); nb.add(f1, text="Thông tin")
        data = json.loads(comp["data_json"])
        ttk.Label(f1, text=str(code), style="H1.TLabel").pack(anchor="w")
        ttk.Label(f1, text=f"Trạng thái: {comp['status']}", style="H2.TLabel").pack(anchor="w", pady=(0,8))
        for k, label in STANDARD_FIELDS:
            v = data.get(k, "")
            if v in (None, ""): continue
            r = ttk.Frame(f1); r.pack(fill=tk.X)
            ttk.Label(r, text=label+":", width=30, foreground="#475569").pack(side=tk.LEFT)
            ttk.Label(r, text=str(v)).pack(side=tk.LEFT)
        f2 = ttk.Frame(nb, padding=10); nb.add(f2, text="Lịch sử kiểm tra")
        cols = ("date","type","result","inspector","report","rfi","note")
        tv = ttk.Treeview(f2, columns=cols, show="headings", height=18)
        for c, w_ in zip(cols, (100,80,80,140,180,140,260)):
            tv.heading(c, text=c.upper()); tv.column(c, width=w_, anchor="w")
        for r in self.db.list_inspections(comp["id"]):
            tv.insert("", "end", values=(r["inspection_date"], r["inspection_type"],
                r["result"], r["inspector"], r["report_no"], r["rfi_no"], r["note"]))
        tv.pack(fill=tk.BOTH, expand=True)

    def _build_settings_tab(self):
        f = ttk.Frame(self.nb, padding=12); self.nb.add(f, text="⚙ Cấu hình")
        ttk.Label(f, text="Thông tin dự án", style="H2.TLabel").pack(anchor="w")
        self.lbl_project_info = tk.Text(f, height=8, width=100); self.lbl_project_info.pack(anchor="w", pady=4)
        ttk.Label(f, text="Đường dẫn DB:", style="H2.TLabel").pack(anchor="w", pady=(8,0))
        ttk.Label(f, text=os.path.abspath(DB_FILE)).pack(anchor="w")
        ttk.Label(f, text=f"App: {APP_NAME} v{APP_VERSION}").pack(anchor="w", pady=(20,0))
        ttk.Label(f, text="© 2026 - QC Department - Đại Dũng", foreground="#475569").pack(anchor="w")

    def _refresh_projects(self):
        projects = self.db.list_projects()
        self._projects = projects
        self.cbo_project["values"] = [f"[{p['code']}] {p['name']}" for p in projects]
        if projects and not self.current_project:
            self.cbo_project.current(0); self.current_project = projects[0]
            self._on_project_change()
        elif not projects:
            self.current_project = None
            self._refresh_dashboard(); self._refresh_components()

    def _on_project_change(self, _evt=None):
        idx = self.cbo_project.current()
        if idx < 0: return
        self.current_project = self._projects[idx]
        self._col_filter_populated_pid = None
        if hasattr(self, "col_filters"):
            for cbo in self.col_filters.values(): cbo.set("(Tất cả)")
        self._refresh_dashboard(); self._refresh_components()
        p = self.current_project
        self.lbl_project_info.delete("1.0", tk.END)
        self.lbl_project_info.insert(tk.END,
            f"Mã: {p['code']}\nTên: {p['name']}\nĐịa điểm: {p['location'] or ''}\n"
            f"Owner: {p['owner'] or ''}\nNgày tạo: {p['created_at']}\nGhi chú: {p['note'] or ''}\n")
        self._set_status(f"Dự án: [{p['code']}] {p['name']}")

    def new_project(self):
        d = NewProjectDialog(self); self.wait_window(d.top)
        if d.result:
            try:
                self.db.create_project(**d.result)
                self.db.log(self.user_name, "CREATE_PROJECT", "project", None, str(d.result))
                self._refresh_projects()
                messagebox.showinfo("OK", f"Đã tạo dự án [{d.result['code']}]")
            except Exception as e:
                messagebox.showerror("Lỗi", str(e))

    def _refresh_dashboard(self):
        if not self.current_project:
            for k in self.stat_cards: self.stat_cards[k].config(text="0")
            return
        pid = self.current_project["id"]
        # Cập nhật danh sách xưởng trong dropdown filter (1 lần khi đổi dự án)
        if getattr(self, "_dash_ws_loaded_pid", None) != pid:
            ws_set = set()
            for r in self.db.conn.execute("SELECT data_json FROM components WHERE project_id=?", (pid,)):
                d = json.loads(r["data_json"])
                w = d.get("workshop")
                if w: ws_set.add(str(w))
            vals = ["(Tất cả)"] + sorted(ws_set)
            self.dash_workshop["values"] = vals
            if self.dash_workshop.get() not in vals:
                self.dash_workshop.set("(Tất cả)")
            self._dash_ws_loaded_pid = pid
        sel_ws = self.dash_workshop.get()
        ws_filter = sel_ws if sel_ws and sel_ws != "(Tất cả)" else None
        # Đếm trạng thái (có lọc xưởng)
        counts = {"PENDING":0,"IN_PROGRESS":0,"PASSED":0,"FAILED":0,"ACCEPTED":0,"TOTAL":0}
        ids_in_filter = set()
        for r in self.db.conn.execute("SELECT id, status, data_json FROM components WHERE project_id=?", (pid,)):
            if ws_filter:
                d = json.loads(r["data_json"])
                if str(d.get("workshop","")) != ws_filter: continue
            ids_in_filter.add(r["id"])
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            counts["TOTAL"] += 1
        for k, lbl in self.stat_cards.items():
            lbl.config(text=str(counts.get(k, 0)))
        # Bảng thống kê theo xưởng
        for i in self.tv_workshop.get_children(): self.tv_workshop.delete(i)
        ws_stats = {}
        for r in self.db.conn.execute("SELECT status, data_json FROM components WHERE project_id=?", (pid,)):
            d = json.loads(r["data_json"])
            w = str(d.get("workshop") or "(không xưởng)")
            if w not in ws_stats:
                ws_stats[w] = {"TOTAL":0,"PENDING":0,"IN_PROGRESS":0,"PASSED":0,"FAILED":0,"ACCEPTED":0}
            ws_stats[w]["TOTAL"] += 1
            ws_stats[w][r["status"]] = ws_stats[w].get(r["status"], 0) + 1
        for w in sorted(ws_stats.keys()):
            s = ws_stats[w]
            done = s["PASSED"] + s["ACCEPTED"]
            pct = f"{done*100/s['TOTAL']:.1f}%" if s["TOTAL"] else "0%"
            self.tv_workshop.insert("", "end", values=(w, s["TOTAL"], s["PENDING"],
                s["IN_PROGRESS"], s["PASSED"], s["FAILED"], s["ACCEPTED"], pct))
        # Lịch sử KT gần nhất (lọc theo xưởng)
        for i in self.tv_recent.get_children(): self.tv_recent.delete(i)
        if ws_filter and ids_in_filter:
            placeholders = ",".join("?"*len(ids_in_filter))
            q = f"""SELECT i.inspection_date d, c.code code, i.inspection_type t,
                       i.result r, i.inspector ins, i.report_no rep
                FROM inspections i JOIN components c ON c.id=i.component_id
                WHERE i.project_id=? AND i.component_id IN ({placeholders})
                ORDER BY i.id DESC LIMIT 200"""
            params = [pid] + list(ids_in_filter)
        elif ws_filter:
            rows = []; params = None
        else:
            q = """SELECT i.inspection_date d, c.code code, i.inspection_type t,
                       i.result r, i.inspector ins, i.report_no rep
                FROM inspections i JOIN components c ON c.id=i.component_id
                WHERE i.project_id=? ORDER BY i.id DESC LIMIT 200"""
            params = [pid]
        if params is not None:
            rows = self.db.conn.execute(q, params).fetchall()
        else:
            rows = []
        for r in rows:
            self.tv_recent.insert("", "end", values=(format_date_vn(r["d"]), r["code"], r["t"], r["r"], r["ins"], r["rep"]))

    def _refresh_components(self):
        for i in self.tv_comp.get_children(): self.tv_comp.delete(i)
        if not self.current_project: return
        pid = self.current_project["id"]
        rows = self.db.list_components(pid, self.cbo_filter.get(), self.search_var.get().strip())
        if getattr(self, "_col_filter_populated_pid", None) != pid:
            self._populate_col_filters(rows); self._col_filter_populated_pid = pid
        # Lấy inspection mới nhất của TẤT CẢ cấu kiện trong 1 query
        latest_ins = {}
        for r in self.db.conn.execute("""
            SELECT i.component_id cid, i.inspection_date d, i.rfi_no rfi
            FROM inspections i
            INNER JOIN (
                SELECT component_id, MAX(id) maxid
                FROM inspections WHERE project_id=? GROUP BY component_id
            ) m ON m.maxid=i.id
            WHERE i.project_id=?
        """, (pid, pid)):
            latest_ins[r["cid"]] = (r["d"] or "", r["rfi"] or "")
        active = {}
        for f, cbo in self.col_filters.items():
            v = cbo.get()
            if v and v != "(Tất cả)": active[f] = v
        shown = 0
        for r in rows:
            data = json.loads(r["data_json"])
            skip = False
            for f, v in active.items():
                if str(data.get(f, "")) != v: skip = True; break
            if skip: continue
            d_auto, rfi_auto = latest_ins.get(r["id"], ("", ""))
            rfi_show = data.get("manual_nfi") or rfi_auto
            d_raw = data.get("manual_insp_date") or d_auto
            d_show = format_date_vn(d_raw)
            # "Bản vẽ" hiển thị: ưu tiên manual_drawing → drawing → member_no → section
            drawing_show = (data.get("manual_drawing")
                            or data.get("drawing")
                            or data.get("member_no")
                            or data.get("section")
                            or "")
            self.tv_comp.insert("", "end", iid=str(r["id"]),
                values=(r["code"],
                        drawing_show,
                        data.get("rev_no",""),
                        data.get("workshop",""),
                        r["status"],
                        rfi_show, d_show),
                tags=(r["status"],))
            shown += 1
        self._sort_state = {"col": None, "reverse": False}
        for c in self._tv_comp_headers:
            self.tv_comp.heading(c, text=self._tv_comp_headers[c] + "  ⇅")
        if active:
            self._set_status(f"Hiển thị {shown}/{len(rows)} cấu kiện. Lọc: " + ", ".join(f"{k}={v}" for k,v in active.items()))
        else:
            self._set_status(f"Đang hiển thị {shown} cấu kiện.")

    def _populate_col_filters(self, rows):
        uniq = {f: set() for f in self.col_filters.keys()}
        for r in rows:
            data = json.loads(r["data_json"])
            for f in uniq:
                v = data.get(f)
                if v not in (None, ""): uniq[f].add(str(v))
        for f, cbo in self.col_filters.items():
            cur = cbo.get()
            vals = ["(Tất cả)"] + sorted(uniq[f])
            cbo["values"] = vals
            cbo.set(cur if cur in vals else "(Tất cả)")

    def _clear_filters(self):
        self.cbo_filter.current(0)
        self.search_var.set("")
        for cbo in self.col_filters.values(): cbo.set("(Tất cả)")
        self._refresh_components()

    def _export_report(self):
        if not self.current_project: messagebox.showwarning("Chưa có dự án",""); return
        p = filedialog.asksaveasfilename(defaultextension=".xlsx",
            filetypes=[("Excel","*.xlsx")],
            initialfile=f"BaoCaoNghiemThu_{self.current_project['code']}_{dt.date.today():%Y%m%d}.xlsx")
        if not p: return
        pid = self.current_project["id"]
        rows = self.db.list_components(pid)
        recs = []
        for r in rows:
            d = json.loads(r["data_json"]); d["__code"] = r["code"]; d["__status"] = r["status"]
            recs.append(d)
        df = pd.DataFrame(recs)
        ins = pd.read_sql_query("SELECT * FROM inspections WHERE project_id=?", self.db.conn, params=[pid])
        with pd.ExcelWriter(p, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Components", index=False)
            ins.to_excel(w, sheet_name="Inspections", index=False)
            s = self.db.count_status(pid)
            pd.DataFrame([s]).to_excel(w, sheet_name="Summary", index=False)
        self.db.log(self.user_name, "EXPORT_REPORT", "project", pid, p)
        messagebox.showinfo("Đã xuất", f"Báo cáo: {p}")

    def _set_status(self, msg): self.status_var.set(msg)


class NewProjectDialog:
    def __init__(self, parent):
        self.top = tk.Toplevel(parent); self.top.title("Tạo dự án mới"); self.top.geometry("460x320")
        self.result = None; self.vars = {}
        for i, (key, label) in enumerate([
            ("code","Mã dự án (UNIQUE) *"),("name","Tên dự án *"),
            ("location","Địa điểm"),("owner","Chủ đầu tư"),("note","Ghi chú"),
        ]):
            ttk.Label(self.top, text=label).grid(row=i, column=0, padx=10, pady=8, sticky="w")
            v = tk.StringVar(); self.vars[key] = v
            ttk.Entry(self.top, textvariable=v, width=42).grid(row=i, column=1, padx=10, pady=8)
        ttk.Button(self.top, text="Tạo", command=self._ok).grid(row=10, column=0, pady=12)
        ttk.Button(self.top, text="Hủy", command=self.top.destroy).grid(row=10, column=1, pady=12)

    def _ok(self):
        if not self.vars["code"].get().strip() or not self.vars["name"].get().strip():
            messagebox.showwarning("Thiếu","Mã và Tên dự án bắt buộc."); return
        self.result = {k: v.get().strip() for k, v in self.vars.items()}
        self.top.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
