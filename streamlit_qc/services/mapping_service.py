# -*- coding: utf-8 -*-
"""
Service: mapping cột Excel ↔ trường hệ thống.

3 nguồn mapping:
1. **Smart auto-detect** — dùng SMART_KEYWORDS + smart_match_columns (xem core/excel_engine).
2. **Template** — user save/load file mapping_templates.json để dùng lại.
3. **Auto-map hardcoded** cho 2 form đã biết: VIOLA, PVF Hưng Yên (copy từ Tkinter dòng 650-702).

KHÔNG sửa dict VIOLA / PVF — đã verify với dữ liệu thực.
"""
from __future__ import annotations

import json
from pathlib import Path

from streamlit_qc.core.constants import TEMPLATE_FILENAME


# ====================================================================
# HARDCODED AUTO-MAPPING (giữ NGUYÊN từ Tkinter)
# ====================================================================
# Tkinter dòng 651-659
VIOLA_MAPPING: dict[str, str] = {
    "code": "Member Punch No\nTên hồ sơ",
    "member_no": "Member No",
    "name": "Drawing",
    "zone": "Zone",
    "phase": "Phase",
    "street": "Street",
    "guid": "GUID",
    "note2": "Note2",
    "type": "Type",
    "symbol": "Ký hiệu",
    "material": "Material",
    "profile": "Profile Type",
    "section": "Section",
    "length_mm": "Length [mm]",
    "weight_kg": "Weight [kg]",
    "paint_area": "Paint Area [m2]",
    "workshop": "xưởng",
    "plan_date": "After Cutting Plan Date",
    "priority": "Priority",
    "note": "Note",
    "drawing": "Drawing",
    "rev_no": "Rev No ",
    "grid_position": "Grid Position",
    "elevation": "Elevation",
}
VIOLA_DEFAULT_HEADER_ROW = 4
VIOLA_DEFAULT_SHEET = "PKL"

# Tkinter dòng 675-691
PVF_MAPPING: dict[str, str] = {
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
PVF_DEFAULT_HEADER_ROW = 3
PVF_DEFAULT_SHEET = "PKL"

# === FORM PHÚ QUỐC (TCTN.D0.25.066 - Đầu tư mở rộng CHK Phú Quốc) ===
# File master có sẵn cột RFI Fit-up & Final đã ký → app tự tạo inspection PASS.
PHUQUOC_MAPPING: dict[str, str] = {
    "code": "Member No.\nTên cấu kiện",
    "member_no": "Member No.",
    "name": "Drawing No.\nTên bản vẽ",
    "rev_no": "Rev.\nSHOP",
    "zone": "ZONE",
    "type": "Type",
    "grid_position": "Grid Position",
    "guid": "GUID",
    "drawing": "Drawing No.\nTên bản vẽ",
    "workshop": "After Cutting Plan Workshop",
    "weight_kg": "Weight [kg]",
    "section": "Section",
    "length_mm": "Length [mm]",
    "material": "Material",
    "paint_area": "Paint Area [m2]",
    "elevation": "Elevation",
    # === 4 cột đặc biệt — đã nghiệm thu ===
    "rfi_fitup_done": "RFI_Fit-up",
    "date_fitup_done": "Ngày kiểm tra.4",
    "rfi_final_done": "RFI_Final Dim",
    "date_final_done": "Ngày kiểm tra.5",
}
PHUQUOC_DEFAULT_HEADER_ROW = 7  # dòng 8 trong Excel (0-indexed = 7)
PHUQUOC_DEFAULT_SHEET = "CHECKLIST"


def apply_hardcoded_mapping(
    template: dict[str, str],
    available_headers: list[str],
) -> dict[str, str]:
    """
    Match dict template với headers thực tế. Soft-match: bỏ \\n để so sánh.

    Tkinter logic dòng 693-701.

    Args:
        template: VIOLA_MAPPING hoặc PVF_MAPPING.
        available_headers: Danh sách header thật từ file Excel.

    Returns:
        Dict {field: header_thực} chỉ với những trường match được.
    """
    matched: dict[str, str] = {}
    norm_lookup = {
        str(h).replace("\n", " ").strip().lower(): h
        for h in available_headers
    }
    for field, expected in template.items():
        # Match chính xác trước
        if expected in available_headers:
            matched[field] = expected
            continue
        # Soft-match: bỏ \n và so sánh lowercase
        target = expected.replace("\n", " ").strip().lower()
        if target in norm_lookup:
            matched[field] = norm_lookup[target]
    return matched


# ====================================================================
# TEMPLATE FILE (mapping_templates.json)
# ====================================================================
def _template_path() -> Path:
    """Đường dẫn file template, đặt cùng folder data/."""
    base = Path(__file__).resolve().parent.parent  # streamlit_qc/
    return base / "data" / TEMPLATE_FILENAME


def load_templates() -> dict[str, dict]:
    """
    Load mapping templates từ file JSON.

    Returns:
        Dict {template_name: {mapping, header_row, sheet_name}}.
        Trả {} nếu file chưa tồn tại hoặc lỗi parse.
    """
    p = _template_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_templates(templates: dict[str, dict]) -> None:
    """Lưu toàn bộ templates ra file JSON."""
    p = _template_path()
    p.parent.mkdir(exist_ok=True)
    p.write_text(
        json.dumps(templates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_template(
    name: str,
    mapping: dict[str, str],
    header_row: int,
    sheet_name: str | None,
) -> None:
    """Lưu 1 template (ghi đè nếu tên đã tồn tại)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Tên template không được để trống.")
    if not mapping:
        raise ValueError("Mapping rỗng — chưa có trường nào được map.")
    templates = load_templates()
    templates[name] = {
        "mapping": mapping,
        "header_row": header_row,
        "sheet_name": sheet_name,
    }
    save_templates(templates)


def delete_template(name: str) -> bool:
    """Xoá template theo tên. Trả True nếu xoá được, False nếu không tồn tại."""
    templates = load_templates()
    if name not in templates:
        return False
    templates.pop(name)
    save_templates(templates)
    return True


def apply_template(
    template_name: str,
    available_headers: list[str],
) -> tuple[dict[str, str], int, str | None]:
    """
    Load 1 template và match với headers thực tế.

    Args:
        template_name: Tên template đã lưu.
        available_headers: Headers thật từ file Excel hiện tại.

    Returns:
        (mapping_đã_match, header_row, sheet_name)

    Raises:
        KeyError: Nếu template không tồn tại.
    """
    templates = load_templates()
    if template_name not in templates:
        raise KeyError(f"Template '{template_name}' không tồn tại.")
    t = templates[template_name]
    matched = apply_hardcoded_mapping(t["mapping"], available_headers)
    return matched, t.get("header_row", 0), t.get("sheet_name")
