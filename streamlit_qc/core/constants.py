# -*- coding: utf-8 -*-
"""
Hằng số dùng chung cho QC Component Manager Web v2.0.

Tất cả các constant ở đây được copy nguyên xi từ phiên bản Tkinter v1.0.2
(file Tai_lieu_tham_khao/QCComponentManager_Tkinter_v1.py dòng 23-71)
để đảm bảo logic nghiệp vụ KHÔNG BỊ ĐỔI giữa 2 phiên bản.

Nguyên tắc:
- KHÔNG sửa SMART_KEYWORDS, STANDARD_FIELDS, INSPECTION_TYPES, REMARK_TO_TYPES
  nếu chưa được oke (QC Đại Dũng) duyệt — đã verify với dữ liệu thực VIOLA + PVF.
"""
from __future__ import annotations

# ====================================================================
# APP METADATA
# ====================================================================
APP_NAME = "QC Component Manager"
APP_VERSION = "2.0.0"
APP_CHANNEL = "Web (Streamlit)"
COMPANY = "Đại Dũng - Phòng QC"

# ====================================================================
# DATABASE
# ====================================================================
DB_FILENAME = "qc_components.db"  # đặt trong data/
TEMPLATE_FILENAME = "mapping_templates.json"

# ====================================================================
# INSPECTION TYPES (8 loại + DGRP đặc biệt)
# ====================================================================
INSPECTION_TYPES: list[tuple[str, str]] = [
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

# Map keyword trong Remark → loại inspection (dùng cho DGRP)
REMARK_TO_TYPES: dict[str, str] = {
    "DIM": "DIR", "DIMEN": "DIR",
    "VISUAL": "VIR",
    "NDT": "NDT", "MT": "NDT", "UT": "NDT",
    "FUR": "FUR", "FIT": "FUR",
    "TAIR": "TAIR", "PRE": "PRE",
    "MB": "MB", "MILL": "MB",
    "MTR": "MTR",
}

# 3 loại quyết định trạng thái ACCEPTED khi PASS đủ 3
ACCEPTANCE_TYPES: frozenset[str] = frozenset({"DIR", "VIR", "NDT"})

# ====================================================================
# COMPONENT STATUSES
# ====================================================================
STATUS_PENDING = "PENDING"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_PASSED = "PASSED"
STATUS_FAILED = "FAILED"
STATUS_ACCEPTED = "ACCEPTED"

ALL_STATUSES = [
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_PASSED,
    STATUS_FAILED,
    STATUS_ACCEPTED,
]

# Tên hiển thị tiếng Việt + màu KPI card (lấy từ Tkinter dòng 445-449)
STATUS_LABELS: dict[str, str] = {
    "TOTAL": "Tổng",
    STATUS_PENDING: "Chưa KT",
    STATUS_IN_PROGRESS: "Đã Fit-up",    # Đã PASS Fit-up, chờ Final
    STATUS_PASSED: "Đạt",                # (luồng cũ — DIR+VIR+NDT PASS đủ)
    STATUS_FAILED: "Không đạt",
    STATUS_ACCEPTED: "Đã nghiệm thu",   # Đã PASS Final (DGRP)
}

STATUS_COLORS: dict[str, str] = {
    "TOTAL": "#1e3a8a",
    STATUS_PENDING: "#64748b",
    STATUS_IN_PROGRESS: "#d97706",
    STATUS_PASSED: "#16a34a",
    STATUS_FAILED: "#dc2626",
    STATUS_ACCEPTED: "#0f766e",
}

STATUS_BG: dict[str, str] = {
    STATUS_PENDING: "#f1f5f9",
    STATUS_IN_PROGRESS: "#fef3c7",
    STATUS_PASSED: "#dcfce7",
    STATUS_FAILED: "#fee2e2",
    STATUS_ACCEPTED: "#bbf7d0",
}

# ====================================================================
# SMART KEYWORDS — auto-detect cột Excel (từ Tkinter dòng 46-71)
# Thứ tự ưu tiên: keyword sớm hơn match trước
# ====================================================================
SMART_KEYWORDS: dict[str, list[str]] = {
    # "tên hồ sơ" + "tên cấu kiện" đặt LÊN ĐẦU để ưu tiên cột Đại Dũng "Member Punch No\nTên hồ sơ"
    # so với plain "Member Punch No" (cột gom group, không unique sub-piece).
    "code":      ["tên hồ sơ", "ten ho so", "tên cấu kiện", "ten cau kien", "member punch no", "punch no", "item code", "mã chi tiết", "ma chi tiet", "piece mark", "piece id", "unique"],
    "member_no": ["member no", "mã cấu kiện", "ma cau kien", "item no", "part no", "mark no"],
    "name":      ["tên hạng mục", "ten hang muc", "drawing", "drawing no", "ten bv", "item name", "tên cấu kiện", "drawing name"],
    "zone":      ["zone", "khu vực", "khu vuc", "area"],
    "phase":     ["phase", "mã hạng mục", "ma hang muc", "giai đoạn", "milestone", "module"],
    "street":    ["street", "trục", "truc", "grid line", "axis"],
    "guid":      ["guid", "uuid", "unique id"],
    "note2":     ["note2", "bundle", "module", "sub-module", "bộ phận"],
    "type":      ["type", "kiểu cấu kiện", "kieu cau kien", "category"],
    "symbol":    ["ký hiệu", "ky hieu", "symbol", "original mark", "short code"],
    "material":  ["material", "vật liệu", "vat lieu", "grade", "mác", "mac"],
    "profile":   ["profile", "profile type", "tiết diện"],
    "section":   ["section", "tiết diện", "tiet dien", "cross section"],
    "length_mm": ["length [mm]", "length mm", "chiều dài", "chieu dai", "length"],
    "weight_kg": ["weight [kg]", "weight kg", "khối lượng", "khoi luong", "weight", "mass"],
    "paint_area": ["paint area", "diện tích sơn", "dien tich son", "painting area"],
    "workshop":  ["xưởng", "xuong", "workshop", "nhà máy", "nha may", "factory", "shop", "plant", "line"],
    "plan_date": ["plan date", "ngày kế hoạch", "ngay ke hoach", "cutting plan", "planned"],
    "priority":  ["priority", "ưu tiên", "uu tien"],
    "note":      ["note", "ghi chú", "ghi chu", "remark", "comment"],
    "drawing":   ["drawing no", "drawing number", "số bản vẽ", "so ban ve", "drawing"],
    "rev_no":    ["rev no", "revision", "phiên bản", "rev"],
    "grid_position": ["grid position", "grid", "vị trí", "vi tri"],
    "elevation": ["elevation", "cao độ", "cao do"],
    # === 4 field cho inspection ĐÃ NGHIỆM THU sẵn từ Master ===
    # File master một số dự án (vd: Phú Quốc) đã có cột RFI Fit-up / Final
    # đã ký → app sẽ tự tạo inspection PASS tương ứng khi import.
    # Hỗ trợ cả 2 quy ước: Phú Quốc (Fit-up) + VIOLA (FUR / DIR+VIR)
    "rfi_fitup_done":   [
        "rfi no-fur", "rfi-fur", "rfi fur", "rfi_fur",  # VIOLA
        "rfi_fit-up", "rfi fit-up", "rfi fitup", "rfi_fitup",  # Phú Quốc
        "phiếu rfi fit-up",
    ],
    "date_fitup_done":  [
        "date-fur", "date fur", "date_fur",  # VIOLA
        "ngày kiểm tra fit-up", "ngày fit-up", "date fitup", "date fit-up",  # Phú Quốc
    ],
    "rfi_final_done":   [
        "rfi no-dir+vir", "rfi-dir+vir", "rfi dir+vir", "rfi_dir+vir",  # VIOLA (Final = DIR+VIR)
        "rfi-dir", "rfi dir", "rfi-vir", "rfi vir",
        "rfi_final dim", "rfi_final", "rfi final", "rfi final dim",  # Phú Quốc
        "phiếu rfi final",
    ],
    "date_final_done":  [
        "date-dir+vir", "date dir+vir", "date_dir+vir",  # VIOLA
        "date-dir", "date dir", "date-vir", "date vir",
        "ngày kiểm tra final", "ngày final", "date final", "date final dim",  # Phú Quốc
    ],
}

# 24 trường chuẩn (mô tả tiếng Việt) - từ Tkinter dòng 155-166
STANDARD_FIELDS: list[tuple[str, str]] = [
    ("code", "Mã cấu kiện (Member Punch No)"),
    ("member_no", "Member No"),
    ("name", "Tên cấu kiện / Drawing"),
    ("zone", "Zone"),
    ("phase", "Phase"),
    ("street", "Street"),
    ("guid", "GUID"),
    ("note2", "Note2 (Module/Bundle)"),
    ("type", "Type"),
    ("symbol", "Ký hiệu"),
    ("material", "Material"),
    ("profile", "Profile Type"),
    ("section", "Section"),
    ("length_mm", "Length [mm]"),
    ("weight_kg", "Weight [kg]"),
    ("paint_area", "Paint Area [m2]"),
    ("workshop", "Xưởng / Workshop"),
    ("plan_date", "Ngày kế hoạch"),
    ("priority", "Priority"),
    ("note", "Ghi chú"),
    ("drawing", "Drawing No"),
    ("rev_no", "Rev No"),
    ("grid_position", "Grid Position"),
    ("elevation", "Elevation"),
    # === 4 trường đặc biệt — inspection đã có sẵn trong Master ===
    ("rfi_fitup_done", "RFI Fit-up đã NT (số phiếu)"),
    ("date_fitup_done", "Ngày Fit-up đã NT"),
    ("rfi_final_done", "RFI Final đã NT (số phiếu)"),
    ("date_final_done", "Ngày Final đã NT"),
]

# ====================================================================
# UI - PAGE COMPONENTS (7 cột chốt với QC - từ Tkinter dòng 1081)
# ====================================================================
COMPONENT_DISPLAY_COLUMNS: list[tuple[str, str]] = [
    ("code", "Tên cấu kiện"),
    ("name", "Bản vẽ"),
    ("rev_no", "Revision"),
    ("workshop", "Xưởng"),
    ("status", "Tình trạng"),
    ("nfi_no", "Số NFI"),
    ("insp_date", "Ngày kiểm tra"),
]

# Filter dropdown kiểu Excel cho 5 cột (từ Tkinter dòng 1070-1073)
COMPONENT_FILTER_FIELDS: list[tuple[str, str]] = [
    ("zone", "Zone"),
    ("phase", "Phase"),
    ("material", "Material"),
    ("workshop", "Xưởng"),
    ("type", "Type"),
]
