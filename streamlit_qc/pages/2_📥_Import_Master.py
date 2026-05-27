# -*- coding: utf-8 -*-
"""Page: Import Master List (PKL) — Single-page UX."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from streamlit_qc.core.constants import APP_NAME, STANDARD_FIELDS
from streamlit_qc.core.excel_engine import (
    list_sheet_names,
    read_excel_any,
    smart_detect_header_row,
    smart_match_columns,
)
from streamlit_qc.core.state import (
    S_CURRENT_USER,
    get_current_project_id,
    get_db,
    init_session_state,
)
from streamlit_qc.core.theme import apply_theme
from streamlit_qc.core.ui import (
    empty_state,
    project_info_strip,
    render_page_header,
    render_top_nav,
)
from streamlit_qc.services import (
    mapping_service,
    master_import_service,
    project_service,
)

st.set_page_config(
    page_title=f"Import Master · {APP_NAME}",
    page_icon="📥",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("master")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav(active_page="master")

proj = render_page_header(
    "Import Master List",
    subtitle="Nạp danh sách cấu kiện từ file PKL (.xlsb/.xlsx)",
    page_icon="📥",
)
pid = get_current_project_id()
if pid is None or proj is None:
    empty_state(
        icon="📁",
        title="Chưa có dự án",
        description="Bấm **+ Dự án mới** ở header trên để tạo dự án trước khi import.",
    )
    st.stop()

project_info_strip(proj)

# ============================================================
# 🎯 BANNER XÁC NHẬN DỰ ÁN — chống import nhầm
# ============================================================
st.markdown(
    f'<div style="background:linear-gradient(135deg,#0F1E40,#1E3A8A);'
    f'padding:18px 22px;border-radius:12px;color:#fff;margin:8px 0 12px 0;'
    f'border-left:6px solid #D4A744;box-shadow:0 4px 14px rgba(15,30,64,0.18);">'
    f'<div style="font-size:11px;color:#FCE7A1;font-weight:700;'
    f'letter-spacing:1.5px;text-transform:uppercase;">⚠️ Bạn đang IMPORT vào dự án:</div>'
    f'<div style="font-size:24px;font-weight:800;margin-top:4px;letter-spacing:-0.5px;">'
    f'[{proj["code"]}] {proj["name"]}'
    f'</div>'
    f'<div style="font-size:12px;color:rgba(255,255,255,0.78);margin-top:4px;">'
    f'Đảm bảo file Excel anh upload thuộc đúng dự án này. '
    f'Nếu sai → đổi dự án ở header trên trước khi import.'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

K_UPLOAD = "master_upload_filepath"
K_UPLOAD_NAME = "master_upload_name"
K_SHEETS = "master_sheets"
K_DF = "master_df"
K_HEADERS = "master_headers"
K_MAPPING = "master_mapping"
K_HEADER_ROW = "master_header_row"
K_SHEET = "master_sheet"

if st.session_state.get("master_last_pid") != pid:
    for k in [K_UPLOAD, K_UPLOAD_NAME, K_SHEETS, K_DF, K_HEADERS, K_MAPPING,
              K_HEADER_ROW, K_SHEET]:
        st.session_state.pop(k, None)
    st.session_state["master_last_pid"] = pid


# ============================================================
# Auto-map TẤT CẢ cột Excel chưa được map sang field `extra_<slug>`
# → đảm bảo không mất dữ liệu nào khi import
# ============================================================
import re as _re_slug


def _slugify_col(name: str) -> str:
    """Convert tên cột Excel sang field key an toàn.

    Vd: "Length [mm]"   → "length_mm"
        "Weight (kg)"   → "weight_kg"
        "Số NFI"        → "so_nfi"
        "Q.ty"          → "q_ty"
    """
    s = str(name or "").strip().lower()
    # Bỏ dấu tiếng Việt thô
    s = (s.replace("á","a").replace("à","a").replace("ả","a").replace("ã","a").replace("ạ","a")
           .replace("â","a").replace("ấ","a").replace("ầ","a").replace("ẩ","a").replace("ẫ","a").replace("ậ","a")
           .replace("ă","a").replace("ắ","a").replace("ằ","a").replace("ẳ","a").replace("ẵ","a").replace("ặ","a")
           .replace("é","e").replace("è","e").replace("ẻ","e").replace("ẽ","e").replace("ẹ","e")
           .replace("ê","e").replace("ế","e").replace("ề","e").replace("ể","e").replace("ễ","e").replace("ệ","e")
           .replace("í","i").replace("ì","i").replace("ỉ","i").replace("ĩ","i").replace("ị","i")
           .replace("ó","o").replace("ò","o").replace("ỏ","o").replace("õ","o").replace("ọ","o")
           .replace("ô","o").replace("ố","o").replace("ồ","o").replace("ổ","o").replace("ỗ","o").replace("ộ","o")
           .replace("ơ","o").replace("ớ","o").replace("ờ","o").replace("ở","o").replace("ỡ","o").replace("ợ","o")
           .replace("ú","u").replace("ù","u").replace("ủ","u").replace("ũ","u").replace("ụ","u")
           .replace("ư","u").replace("ứ","u").replace("ừ","u").replace("ử","u").replace("ữ","u").replace("ự","u")
           .replace("ý","y").replace("ỳ","y").replace("ỷ","y").replace("ỹ","y").replace("ỵ","y")
           .replace("đ","d"))
    s = _re_slug.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "col"


def _auto_map_all_columns(current_mapping: dict, all_headers: list) -> dict:
    """Tạo mapping mới: GIỮ NGUYÊN các trường chuẩn đã map, thêm `extra_<slug>` cho cột chưa map."""
    new_mapping = dict(current_mapping)
    mapped_cols = {v for v in new_mapping.values() if v}
    used_keys = set(new_mapping.keys())
    for col in all_headers:
        if not col or str(col).strip().lower().startswith("unnamed"):
            continue
        if col in mapped_cols:
            continue
        slug = _slugify_col(col)
        key = f"extra_{slug}"
        # Tránh collision: nếu key trùng, thêm hậu tố số
        suffix = 1
        while key in used_keys:
            suffix += 1
            key = f"extra_{slug}_{suffix}"
        new_mapping[key] = col
        used_keys.add(key)
    return new_mapping


def _run_smart_detect(filepath, sheet=None):
    try:
        sheets = list_sheet_names(filepath)
        st.session_state[K_SHEETS] = sheets
        if sheet is None:
            sheet = "PKL" if "PKL" in sheets else sheets[0]
        st.session_state[K_SHEET] = sheet
        best_row = smart_detect_header_row(filepath, sheet)
        st.session_state[K_HEADER_ROW] = best_row
        df = read_excel_any(filepath, sheet_name=sheet, header=best_row)
        headers = [str(c) for c in df.columns]
        st.session_state[K_DF] = df
        st.session_state[K_HEADERS] = headers
        fields = [f for f, _ in STANDARD_FIELDS]
        st.session_state[K_MAPPING] = smart_match_columns(headers, fields)
    except Exception as e:
        st.error(f"Lỗi auto-detect: {e}")


uploaded = st.file_uploader(
    "Kéo thả file PKL vào đây",
    type=["xlsb", "xlsx", "xlsm", "xls", "csv"],
    accept_multiple_files=False,
    label_visibility="collapsed",
)

if uploaded is not None:
    if st.session_state.get(K_UPLOAD_NAME) != uploaded.name:
        suffix = Path(uploaded.name).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(uploaded.getbuffer())
        tmp.close()
        st.session_state[K_UPLOAD] = tmp.name
        st.session_state[K_UPLOAD_NAME] = uploaded.name
        for k in [K_DF, K_HEADERS, K_MAPPING]:
            st.session_state.pop(k, None)
        with st.spinner("🤖 Đang đọc file và tự động dò mapping..."):
            _run_smart_detect(tmp.name)
        st.rerun()

if K_UPLOAD not in st.session_state:
    empty_state(
        icon="📤",
        title="Chưa upload file nào",
        description="Kéo thả file PKL (.xlsb / .xlsx) vào ô trên để bắt đầu.",
    )
    st.stop()

df = st.session_state.get(K_DF)
headers = st.session_state.get(K_HEADERS, [])
mapping = st.session_state.get(K_MAPPING, {})
header_row = st.session_state.get(K_HEADER_ROW, 0)
sheet = st.session_state.get(K_SHEET)

c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
with c1:
    st.markdown(
        f"<div style='color:#64748B;font-size:13px;'>📄 File</div>"
        f"<div style='font-weight:600;color:#0F1E40;'>{st.session_state[K_UPLOAD_NAME]}</div>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"<div style='color:#64748B;font-size:13px;'>📋 Sheet</div>"
        f"<div style='font-weight:600;color:#0F1E40;'>{sheet}</div>",
        unsafe_allow_html=True,
    )
with c3:
    if df is not None:
        st.markdown(
            f"<div style='color:#64748B;font-size:13px;'>📑 Số dòng</div>"
            f"<div style='font-weight:600;color:#0F1E40;'>{len(df):,}</div>",
            unsafe_allow_html=True,
        )
with c4:
    n_mapped = len(mapping)
    color = "#16A34A" if "code" in mapping else "#D97706"
    st.markdown(
        f"<div style='color:#64748B;font-size:13px;'>🔗 Mapping</div>"
        f"<div style='font-weight:600;color:{color};'>{n_mapped}/{len(STANDARD_FIELDS)} trường</div>",
        unsafe_allow_html=True,
    )

st.write("")
st.divider()

if "code" in mapping:
    st.success(
        f"✅ **Đã tự động phát hiện**: header dòng {header_row}, "
        f"map {len(mapping)}/{len(STANDARD_FIELDS)} trường. Bấm **Import** ngay."
    )
else:
    st.warning("⚠ Chưa tìm được cột `code`. Vào **Tinh chỉnh mapping** để chọn thủ công.")

# Gộp Thử VIOLA/PVF + Auto-detect + Templates user-saved vào 1 dropdown
# → scale tốt khi có nhiều template (vd 50 dự án)
templates_user = mapping_service.load_templates()

TPL_OPTIONS = [
    ("auto", "🤖 Smart Auto-detect (mọi form PKL)"),
    ("viola", "🏭 Form VIOLA — Structural Steel"),
    ("pvf", "🏢 Form PVF Hưng Yên"),
    ("phuquoc", "✈️ Form Phú Quốc (có RFI Fit-up + Final sẵn)"),
    ("bison", "🏗️ Form Bison Generation Station (chỉ Final)"),
]
for tname in sorted(templates_user.keys()):
    TPL_OPTIONS.append((f"user::{tname}", f"📂 {tname} (lưu sẵn)"))

c_tpl, c_apply, c_import = st.columns([4, 2, 4])
with c_tpl:
    tpl_label = st.selectbox(
        "Áp dụng template mapping",
        [lbl for _, lbl in TPL_OPTIONS],
        label_visibility="collapsed",
        key="tpl_select",
    )
    tpl_key = next(k for k, lbl in TPL_OPTIONS if lbl == tpl_label)

with c_apply:
    if st.button("✓ Áp dụng", use_container_width=True):
        try:
            if tpl_key == "auto":
                _run_smart_detect(st.session_state[K_UPLOAD])
            elif tpl_key == "viola":
                sheets_local = st.session_state.get(K_SHEETS, [])
                sheet_use = mapping_service.VIOLA_DEFAULT_SHEET if mapping_service.VIOLA_DEFAULT_SHEET in sheets_local else sheet
                df_new = read_excel_any(st.session_state[K_UPLOAD], sheet_name=sheet_use,
                                       header=mapping_service.VIOLA_DEFAULT_HEADER_ROW)
                headers_new = [str(c) for c in df_new.columns]
                st.session_state[K_DF] = df_new
                st.session_state[K_HEADERS] = headers_new
                st.session_state[K_SHEET] = sheet_use
                st.session_state[K_HEADER_ROW] = mapping_service.VIOLA_DEFAULT_HEADER_ROW
                st.session_state[K_MAPPING] = mapping_service.apply_hardcoded_mapping(
                    mapping_service.VIOLA_MAPPING, headers_new)
            elif tpl_key == "pvf":
                sheets_local = st.session_state.get(K_SHEETS, [])
                sheet_use = mapping_service.PVF_DEFAULT_SHEET if mapping_service.PVF_DEFAULT_SHEET in sheets_local else sheet
                df_new = read_excel_any(st.session_state[K_UPLOAD], sheet_name=sheet_use,
                                       header=mapping_service.PVF_DEFAULT_HEADER_ROW)
                headers_new = [str(c) for c in df_new.columns]
                st.session_state[K_DF] = df_new
                st.session_state[K_HEADERS] = headers_new
                st.session_state[K_SHEET] = sheet_use
                st.session_state[K_HEADER_ROW] = mapping_service.PVF_DEFAULT_HEADER_ROW
                st.session_state[K_MAPPING] = mapping_service.apply_hardcoded_mapping(
                    mapping_service.PVF_MAPPING, headers_new)
            elif tpl_key == "phuquoc":
                sheets_local = st.session_state.get(K_SHEETS, [])
                sheet_use = mapping_service.PHUQUOC_DEFAULT_SHEET if mapping_service.PHUQUOC_DEFAULT_SHEET in sheets_local else sheet
                df_new = read_excel_any(st.session_state[K_UPLOAD], sheet_name=sheet_use,
                                       header=mapping_service.PHUQUOC_DEFAULT_HEADER_ROW)
                headers_new = [str(c) for c in df_new.columns]
                st.session_state[K_DF] = df_new
                st.session_state[K_HEADERS] = headers_new
                st.session_state[K_SHEET] = sheet_use
                st.session_state[K_HEADER_ROW] = mapping_service.PHUQUOC_DEFAULT_HEADER_ROW
                st.session_state[K_MAPPING] = mapping_service.apply_hardcoded_mapping(
                    mapping_service.PHUQUOC_MAPPING, headers_new)
            elif tpl_key == "bison":
                sheets_local = st.session_state.get(K_SHEETS, [])
                sheet_use = mapping_service.BISON_DEFAULT_SHEET if mapping_service.BISON_DEFAULT_SHEET in sheets_local else sheet
                df_new = read_excel_any(st.session_state[K_UPLOAD], sheet_name=sheet_use,
                                       header=mapping_service.BISON_DEFAULT_HEADER_ROW)
                headers_new = [str(c) for c in df_new.columns]
                st.session_state[K_DF] = df_new
                st.session_state[K_HEADERS] = headers_new
                st.session_state[K_SHEET] = sheet_use
                st.session_state[K_HEADER_ROW] = mapping_service.BISON_DEFAULT_HEADER_ROW
                st.session_state[K_MAPPING] = mapping_service.apply_hardcoded_mapping(
                    mapping_service.BISON_MAPPING, headers_new)
            elif tpl_key.startswith("user::"):
                tname = tpl_key.split("::", 1)[1]
                matched, hr, sn = mapping_service.apply_template(tname, headers)
                st.session_state[K_MAPPING] = matched
                if hr:
                    st.session_state[K_HEADER_ROW] = hr
                if sn:
                    st.session_state[K_SHEET] = sn
            st.rerun()
        except Exception as e:
            st.error(f"Lỗi: {e}")

with c_import:
    # === Check filename mismatch với project code ===
    filename = st.session_state.get(K_UPLOAD_NAME, "") or ""
    filename_upper = filename.upper()
    proj_code_upper = (proj["code"] or "").upper()
    proj_name_upper = (proj["name"] or "").upper()

    # Detect các project code khác trong filename
    KNOWN_PROJECTS = ["VIOLA", "PQA", "PHU QUOC", "PPVF", "PVF", "BISON"]
    detected_in_filename = []
    for kp in KNOWN_PROJECTS:
        if kp in filename_upper:
            detected_in_filename.append(kp)

    # Heuristic: project code KHỚP nếu xuất hiện trong filename hoặc tên project
    name_match = bool(
        proj_code_upper in filename_upper
        or any(token in filename_upper for token in proj_name_upper.split() if len(token) >= 3)
    )

    has_other_project = any(
        kp not in proj_code_upper and kp not in proj_name_upper
        for kp in detected_in_filename
    )

    do_import = st.button(
        f"▶ Import {len(df):,} cấu kiện vào DB" if df is not None else "▶ Import",
        type="primary", use_container_width=True,
        disabled=("code" not in mapping or df is None),
    )

# === Cảnh báo filename mismatch ===
if filename and df is not None and "code" in mapping:
    if has_other_project and not name_match:
        st.error(
            f"🚨 **CẢNH BÁO MISMATCH!** Tên file **`{filename}`** "
            f"chứa từ khoá dự án khác ({', '.join(detected_in_filename)}), "
            f"nhưng anh đang import vào **[{proj['code']}] {proj['name']}**. "
            f"**Kiểm tra lại — có thể anh chọn nhầm dự án!**"
        )
    elif name_match:
        st.success(
            f"✅ Filename khớp với dự án [{proj['code']}] — yên tâm import."
        )

# Toggle workflow option
opt_col1, opt_col2 = st.columns([3, 5])
with opt_col1:
    force_reseed = st.checkbox(
        "🔄 Tạo lại Fit-up/Final từ Master (xóa inspection MASTER cũ trước)",
        value=False,
        help="Bật nếu cần force update toàn bộ inspection từ Master columns. "
             "Inspection từ Daily import sẽ KHÔNG bị đụng vào."
    )
    auto_map_all = st.checkbox(
        "🔒 Lấy HẾT mọi cột Excel khi import (auto-map cột chưa map)",
        value=True,
        help="Mặc định BẬT — đảm bảo không bỏ sót dữ liệu nào. "
             "Các cột chưa map sẽ tự động được lưu thành trường `extra_<tên>` "
             "trong data_json của cấu kiện.",
        key="opt_auto_map_all",
    )

st.write("")

# ============================================================
# PREVIEW MODE — hiển thị summary mapping trước khi import
# ============================================================
if df is not None and "code" in mapping:
    code_col = mapping["code"]
    n_unique_code = df[code_col].nunique() if code_col in df.columns else 0
    n_rfi_fitup = (df[mapping["rfi_fitup_done"]].notna().sum()
                   if mapping.get("rfi_fitup_done") in df.columns else 0)
    n_rfi_final = (df[mapping["rfi_final_done"]].notna().sum()
                   if mapping.get("rfi_final_done") in df.columns else 0)
    has_date_fitup = mapping.get("date_fitup_done") in df.columns
    has_date_final = mapping.get("date_final_done") in df.columns

    code_check_emoji = "✅" if n_unique_code > len(df) * 0.5 else "⚠️"
    fitup_emoji = "✅" if has_date_fitup else "⚠️"
    final_emoji = "✅" if has_date_final else "⚠️"

    # Tìm dòng trùng mã code trong file Excel
    n_duplicates_total = 0
    dup_codes_info = []
    if code_col in df.columns:
        dup_series = df[df[code_col].duplicated(keep=False)][code_col].value_counts()
        if len(dup_series) > 0:
            n_duplicates_total = int((dup_series - 1).sum())  # số dòng dư (mỗi mã unique tính 1 dòng "gốc")
            dup_codes_info = [
                {"code": str(c), "count": int(v)}
                for c, v in dup_series.head(10).items()
            ]

    with st.expander("📋 Preview — Kiểm tra mapping trước khi import", expanded=True):
        # === Banner "Đã lấy HẾT N cột" ===
        _hdrs_clean = [h for h in (headers or []) if h and not str(h).strip().lower().startswith("unnamed")]
        _total_cols_pv = len(_hdrs_clean)
        _std_mapped_pv = sum(1 for f, _ in STANDARD_FIELDS if mapping.get(f))
        _extra_mapped_pv = sum(1 for k in mapping if k.startswith("extra_"))
        _will_auto_pv = bool(st.session_state.get("opt_auto_map_all", True))
        _unmapped_pv = max(0, _total_cols_pv - _std_mapped_pv - _extra_mapped_pv)
        if _will_auto_pv and _unmapped_pv > 0:
            st.success(
                f"✅ **Sẽ lấy HẾT {_total_cols_pv} cột** khi import: "
                f"**{_std_mapped_pv}** cột chuẩn + **{_extra_mapped_pv}** cột extra đã map + "
                f"**{_unmapped_pv}** cột phụ (tự động lưu thành `extra_*` khi bấm Import). "
                f"_Không cột nào bị bỏ qua._"
            )
        elif _unmapped_pv == 0 and _total_cols_pv > 0:
            st.success(
                f"✅ **Đã map HẾT {_total_cols_pv} cột** ({_std_mapped_pv} chuẩn + {_extra_mapped_pv} extra) — "
                f"không cột nào bị bỏ qua khi import."
            )
        else:
            st.info(
                f"📦 Tổng **{_total_cols_pv}** cột trong file — đang map "
                f"**{_std_mapped_pv}** trường chuẩn + **{_extra_mapped_pv}** trường extra. "
                f"Có **{_unmapped_pv}** cột chưa map. "
                f"_(Tick '🔒 Lấy HẾT mọi cột' ở trên hoặc bấm '✨ Map HẾT' để lấy hết.)_"
            )

        pcol1, pcol2 = st.columns(2)
        with pcol1:
            dup_line = (
                f"\n- ⚠️ Dòng trùng mã trong file: **{n_duplicates_total:,}** "
                f"(sẽ merge thành 1 record)"
            ) if n_duplicates_total > 0 else ""
            st.markdown(f"""
**📊 Thống kê file:**
- Tổng dòng Excel: **{len(df):,}**
- Mã unique theo cột `code`: **{n_unique_code:,}** {code_check_emoji}
- Cấu kiện sẽ có Fit-up: **{n_rfi_fitup:,}** {fitup_emoji} ngày
- Cấu kiện sẽ có Final: **{n_rfi_final:,}** {final_emoji} ngày{dup_line}
""")
        with pcol2:
            st.markdown(f"""
**🔗 Mapping cột chính:**
- `code` → `{mapping.get('code', '—')[:50]}`
- `name` → `{mapping.get('name', '(không map)')[:50]}`
- `workshop` → `{mapping.get('workshop', '(không map)')[:30]}`
- `rfi_fitup_done` → `{mapping.get('rfi_fitup_done', '(không có)')[:50]}`
- `date_fitup_done` → `{mapping.get('date_fitup_done', '(không có)')[:50]}`
- `rfi_final_done` → `{mapping.get('rfi_final_done', '(không có)')[:50]}`
- `date_final_done` → `{mapping.get('date_final_done', '(không có)')[:50]}`
""")
        if n_unique_code < len(df) * 0.5:
            st.warning(
                f"⚠️ **Số mã unique ({n_unique_code:,}) nhỏ hơn nửa số dòng ({len(df):,})!** "
                f"Có thể cột `code` đang map nhầm. Kiểm tra ở **Tinh chỉnh mapping** bên dưới — "
                f"nên dùng cột có 'Tên hồ sơ' / 'Tên cấu kiện' / 'Punch No' (full piece-level)."
            )
        if not has_date_fitup and mapping.get("rfi_fitup_done"):
            st.warning("⚠️ Có RFI Fit-up nhưng KHÔNG có Date Fit-up → ngày sẽ rỗng. Check mapping `date_fitup_done`.")
        if not has_date_final and mapping.get("rfi_final_done"):
            st.warning("⚠️ Có RFI Final nhưng KHÔNG có Date Final → ngày sẽ rỗng. Check mapping `date_final_done`.")

        # Cảnh báo dòng trùng mã trong file gốc
        if n_duplicates_total > 0:
            st.warning(
                f"⚠️ **File có {n_duplicates_total:,} dòng trùng mã** "
                f"({len(dup_codes_info)} mã bị lặp). "
                f"App sẽ tự **merge các dòng trùng** thành 1 record (giữ field cuối cùng). "
                f"Nên báo team làm file kiểm tra lại."
            )
            # Bảng danh sách mã trùng
            import pandas as pd_local
            dup_df = pd_local.DataFrame(dup_codes_info)
            dup_df.columns = ["Mã cấu kiện", "Số lần xuất hiện"]
            st.dataframe(
                dup_df, hide_index=True, use_container_width=False,
                column_config={
                    "Số lần xuất hiện": st.column_config.NumberColumn(format="%d"),
                },
            )

st.write("")

with st.expander("Xem trước 5 dòng đầu", expanded=False):
    if df is not None and mapping:
        preview_cols = list(dict.fromkeys(c for c in mapping.values() if c in df.columns))
        if preview_cols:
            st.dataframe(df[preview_cols].head(5), use_container_width=True, height=220)

_n_std_mapped = sum(1 for f, _ in STANDARD_FIELDS if mapping.get(f))
_n_extra_mapped = sum(1 for k in mapping if k.startswith("extra_"))
_n_total_cols = len([h for h in (headers or []) if h and not str(h).strip().lower().startswith("unnamed")])
_n_unmapped = _n_total_cols - _n_std_mapped - _n_extra_mapped

with st.expander(
    f"Tinh chỉnh mapping ({_n_std_mapped}/{len(STANDARD_FIELDS)} trường chuẩn"
    + (f" + {_n_extra_mapped} cột extra" if _n_extra_mapped else "")
    + ")",
    expanded=False,
):
    cc1, cc2, cc3, cc4 = st.columns([2.5, 1.5, 2, 2])
    with cc1:
        sheets_local = st.session_state.get(K_SHEETS, [])
        new_sheet = st.selectbox("Sheet", sheets_local,
                                 index=sheets_local.index(sheet) if sheet in sheets_local else 0)
    with cc2:
        new_hr = st.number_input("Dòng tiêu đề (0-based)", min_value=0, max_value=30, value=header_row)
    with cc3:
        st.write("")
        st.write("")
        if st.button("✨ Map HẾT các cột", use_container_width=True,
                     help="Tự động map TẤT CẢ các cột Excel chưa được map "
                          "thành trường extra_<tên> để lấy hết dữ liệu."):
            st.session_state[K_MAPPING] = _auto_map_all_columns(
                mapping or {}, headers or []
            )
            st.success(
                f"✅ Đã map HẾT {_n_total_cols} cột — "
                f"không cột nào bị bỏ qua khi import."
            )
            st.rerun()
    with cc4:
        st.write("")
        st.write("")
        if st.button("📖 Đọc lại", use_container_width=True):
            try:
                df_new = read_excel_any(st.session_state[K_UPLOAD], sheet_name=new_sheet, header=new_hr)
                headers_new = [str(c) for c in df_new.columns]
                st.session_state[K_DF] = df_new
                st.session_state[K_HEADERS] = headers_new
                st.session_state[K_SHEET] = new_sheet
                st.session_state[K_HEADER_ROW] = new_hr
                fields = [f for f, _ in STANDARD_FIELDS]
                st.session_state[K_MAPPING] = smart_match_columns(headers_new, fields)
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")

    st.write("")
    st.caption(f"📋 File có **{len(headers)} cột**:")
    options = ["(bỏ qua)"] + headers
    new_mapping = {}
    edit_cols = st.columns(2)
    half = (len(STANDARD_FIELDS) + 1) // 2
    for i, (field, desc) in enumerate(STANDARD_FIELDS):
        target_col = edit_cols[0] if i < half else edit_cols[1]
        with target_col:
            current = mapping.get(field, "")
            idx = options.index(current) if current in options else 0
            label = f"**{field}** — _{desc}_"
            if field == "code":
                label = f"🔑 **{field}** *(bắt buộc)* — _{desc}_"
            chosen = st.selectbox(label, options, index=idx, key=f"map_{field}")
            if chosen and chosen != "(bỏ qua)":
                new_mapping[field] = chosen
    # GIỮ lại các trường extra_* (do "Map HẾT" hoặc auto khi import sinh ra)
    for k, v in (mapping or {}).items():
        if k.startswith("extra_") and v and k not in new_mapping:
            new_mapping[k] = v
    st.session_state[K_MAPPING] = new_mapping
    if any(k.startswith("extra_") for k in new_mapping):
        n_extra = sum(1 for k in new_mapping if k.startswith("extra_"))
        st.caption(
            f"➕ _Đã giữ {n_extra} cột extra (auto-map). "
            f"Nếu muốn bỏ, bấm nút **🔄 Reset** dưới đây._"
        )
        if st.button("🔄 Reset (chỉ giữ trường chuẩn)", key="reset_extras"):
            st.session_state[K_MAPPING] = {k: v for k, v in new_mapping.items()
                                           if not k.startswith("extra_")}
            st.rerun()

with st.expander("Lưu / Tải template mapping", expanded=False):
    templates = mapping_service.load_templates()
    tcol1, tcol2 = st.columns([3, 2])
    with tcol1:
        if templates:
            picked = st.selectbox("Template có sẵn", sorted(templates.keys()))
        else:
            picked = None
            st.caption("_Chưa có template nào._")
    with tcol2:
        st.write("")
        if picked and st.button("📂 Tải template này", use_container_width=True):
            try:
                if not headers:
                    st.warning("Cần đọc file trước.")
                else:
                    matched, hr, sn = mapping_service.apply_template(picked, headers)
                    st.session_state[K_MAPPING] = matched
                    st.success(f"Đã tải '{picked}' — {len(matched)} trường.")
                    st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")

if do_import and df is not None and "code" in mapping:
    try:
        # AUTO-MAP HẾT: nếu user bật toggle "Lấy HẾT mọi cột"
        if st.session_state.get("opt_auto_map_all", True):
            _before = len(mapping)
            mapping = _auto_map_all_columns(mapping, headers or [])
            st.session_state[K_MAPPING] = mapping
            _added = len(mapping) - _before
            if _added > 0:
                st.info(f"🔒 Auto-map đã thêm **{_added}** cột extra trước khi import — lấy hết dữ liệu.")

        # FORCE RE-SEED: xóa MASTER-source inspections trước khi import (giữ DAILY)
        if force_reseed:
            n_deleted = db.conn.execute(
                """DELETE FROM inspections
                   WHERE project_id = ? AND source_file = 'MASTER'""",
                (pid,)
            ).rowcount
            db.conn.commit()
            st.warning(f"🔄 Đã xóa {n_deleted:,} inspection MASTER cũ — sẽ tạo lại từ file mới.")

        with st.spinner(f"Đang import {len(df):,} dòng..."):
            result = master_import_service.import_master(
                db, pid=pid, df=df, mapping=mapping,
                sheet_name=sheet, header_row=header_row,
                user_name=st.session_state[S_CURRENT_USER],
            )
        st.balloons()
        total_in_db = db.conn.execute(
            "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,)
        ).fetchone()["c"]
        st.success(
            f"**Import thành công** · {result.written:,} cấu kiện đã ghi DB "
            f"({result.new:,} mới + {result.updated:,} cập nhật) · "
            f"bỏ qua {result.skipped:,} dòng · "
            f"Tổng DB: **{total_in_db:,}**"
        )

        # ⚠ Cảnh báo dòng trùng mã trong file Excel gốc
        if result.duplicate_rows > 0:
            import pandas as _pd
            st.warning(
                f"⚠️ **File Excel gốc có {result.duplicate_rows:,} dòng trùng mã** "
                f"({len(result.duplicate_codes)} mã bị lặp). "
                f"App đã tự **merge các dòng trùng** thành 1 record (giữ field cuối cùng). "
                f"Nên báo team làm file Excel kiểm tra lại."
            )
            with st.expander(f"Xem {len(result.duplicate_codes)} mã trùng", expanded=False):
                dup_df = _pd.DataFrame(result.duplicate_codes)
                dup_df.columns = ["Mã cấu kiện", "Số lần xuất hiện trong file"]
                st.dataframe(
                    dup_df, hide_index=True, use_container_width=True,
                    column_config={
                        "Số lần xuất hiện trong file": st.column_config.NumberColumn(format="%d"),
                    },
                )
                csv_dup = dup_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 Tải danh sách mã trùng (CSV)",
                    csv_dup,
                    file_name=f"duplicate_codes_{proj['code']}.csv",
                    mime="text/csv",
                )

        # 🎯 Stats inspection có sẵn từ Master (RFI Fit-up + RFI Final)
        if (result.fitup_seeded or result.final_seeded or
                result.fitup_skipped_exist or result.final_skipped_exist):
            st.info(
                f"📋 **Phát hiện inspection có sẵn trong file Master**:\n\n"
                f"• 🟢 Fit-up tự tạo: **{result.fitup_seeded:,}** cấu kiện "
                f"(bỏ qua {result.fitup_skipped_exist:,} đã có)\n\n"
                f"• 🎯 Final tự tạo: **{result.final_seeded:,}** cấu kiện "
                f"→ chuyển thành **ACCEPTED** "
                f"(bỏ qua {result.final_skipped_exist:,} đã có)\n\n"
                f"_Anh không cần import file Daily cho các cấu kiện này._"
            )

        # ⚠ Cảnh báo Rev thay đổi
        if result.rev_changed:
            import pandas as _pd
            n_rev = len(result.rev_changed)
            st.warning(
                f"🔄 **Phát hiện {n_rev} cấu kiện có REVISION THAY ĐỔI** so với master cũ."
            )
            with st.expander(f"Xem chi tiết {n_rev} cấu kiện đổi Rev", expanded=False):
                df_rev = _pd.DataFrame(result.rev_changed).rename(columns={
                    "code": "Mã cấu kiện",
                    "name": "Bản vẽ",
                    "old_rev": "Rev cũ",
                    "new_rev": "Rev mới",
                })
                st.dataframe(df_rev, hide_index=True, use_container_width=True, height=300)
                csv_data = df_rev.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 Tải danh sách CSV",
                    csv_data,
                    file_name=f"rev_changed_{proj['code']}.csv",
                    mime="text/csv",
                )

        st.caption("Vào **Tổng quan** xem KPI hoặc **Import Daily** để nạp file kiểm tra.")
    except Exception as e:
        st.error(f"Lỗi import: {e}")
        import traceback
        with st.expander("Chi tiết lỗi"):
            st.code(traceback.format_exc())

st.divider()
