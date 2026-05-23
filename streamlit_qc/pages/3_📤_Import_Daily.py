# -*- coding: utf-8 -*-
"""Page: Import Daily — Fit-up hoặc Final."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from streamlit_qc.core.constants import APP_NAME
from streamlit_qc.core.date_utils import (
    extract_date_from_filename,
    format_date_vn,
    parse_date_input,
)
from streamlit_qc.core.excel_engine import list_sheet_names, read_excel_any, smart_detect_header_row
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
from streamlit_qc.services import component_service, daily_import_service, debug_match_service

st.set_page_config(
    page_title=f"Import Daily · {APP_NAME}",
    page_icon="📤",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
init_session_state()
db = get_db()

from streamlit_qc.services.access_tracker import set_current_page as _scp
_scp("daily")
from streamlit_qc.core.state import require_login
require_login()
render_top_nav(active_page="daily")

INSPECTION_OPTIONS = [
    {"code": "AUTO", "label": "🤖 Tự động (cả Fit-up + Final)",
     "desc": "App phát hiện cột NỘI DUNG → tự chia mỗi dòng vào Fit-up hoặc Final",
     "default_header": 0,
     # Keyword sheet linh hoạt cho mọi dạng
     "sheet_keywords": ["LỊCH MỜI", "RFI", "NT", "NGHIỆM THU", "FIT", "FINAL", "DGRP", "DSNT", "BBNT", "HOÀN THIỆN"]},
    {"code": "FUR", "label": "🔨 Fit-up",
     "desc": "Kiểm tra trước khi hàn — trạng thái 'Đã Fit-up'",
     "default_header": 0,
     "sheet_keywords": ["FUR", "FIT-UP", "FIT UP", "FITUP", "FIT", "RFI", "DSNT", "NT", "NGHIỆM THU", "HOÀN THIỆN"]},
    {"code": "DGRP", "label": "✅ Final (Nghiệm thu)",
     "desc": "Bàn giao cuối — PASS → 'Đã NT' (ACCEPTED)",
     "default_header": 11,
     "sheet_keywords": ["DGRP", "FINAL", "BÀN GIAO", "BIÊN BẢN", "BIEN BAN", "BBNT", "DSNT", "RFI", "NT", "NGHIỆM THU"]},
]
OPT_LABELS = [o["label"] for o in INSPECTION_OPTIONS]
OPT_BY_LABEL = {o["label"]: o for o in INSPECTION_OPTIONS}


# === KEYWORDS cho cột NỘI DUNG (auto-classify mỗi dòng) ===
# Khi user chọn "AUTO", app đọc cột nội dung và mỗi dòng vào nhóm tương ứng.
FUR_KEYWORDS = ["FIT UP", "FIT-UP", "FITUP", "FIT_UP"]
DGRP_KEYWORDS = ["FINAL DIM", "FINAL DIMENTION", "FINAL DIMENSION", "FINAL",
                 "BÀN GIAO", "DGRP", "BIÊN BẢN", "BIEN BAN"]

# Tên cột có thể chứa loại NT — KEYWORDS ngắn, exact-match
NOIDUNG_COL_KEYWORDS = ["nội dung", "noi dung", "nôi dung", "loại nt", "loai nt",
                        "loại kiểm tra", "loai kiem tra", "inspection type"]


def _classify_inspection_row(noidung_value) -> str:
    """
    Phân loại 1 dòng dựa vào cột NỘI DUNG.

    Returns:
        "FUR"   nếu là Fit-up
        "DGRP"  nếu là Final / Bàn giao
        ""      nếu không xác định (sẽ bỏ qua khi import AUTO)
    """
    if noidung_value is None:
        return ""
    s = str(noidung_value).strip().upper()
    if not s or s == "NAN":
        return ""
    # Check Fit-up trước
    for kw in FUR_KEYWORDS:
        if kw in s:
            return "FUR"
    # Check Final
    for kw in DGRP_KEYWORDS:
        if kw in s:
            return "DGRP"
    return ""


def _find_noidung_column(headers: list[str]) -> str | None:
    """
    Tìm cột chứa loại NT trong headers.

    Yêu cầu match tên cột NGẮN (≤ 30 ký tự) để tránh match nhầm vào
    ô metadata dài (vd "ĐĂNG KÝ LỊCH MỜI NGHIỆM THU CÔNG TÁC...").
    """
    for h in headers:
        h_str = str(h)
        if len(h_str) > 30:  # quá dài → không phải tên cột bình thường
            continue
        h_low = h_str.lower().strip()
        for kw in NOIDUNG_COL_KEYWORDS:
            if kw in h_low:
                return h
    return None

proj = render_page_header(
    "Import File Kiểm tra Hàng ngày",
    subtitle="Chọn Fit-up (trước hàn) hoặc Final (nghiệm thu) · Tập trung kích thước",
    page_icon="📤",
)
pid = get_current_project_id()
if pid is None or proj is None:
    empty_state(icon="📁", title="Chưa có dự án",
                description="Bấm **+ Dự án mới** ở header trên.")
    st.stop()

n_comp = db.conn.execute(
    "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,)
).fetchone()["c"]
project_info_strip(proj, n_comp=n_comp)

if n_comp == 0:
    empty_state(icon="📦", title="Dự án chưa có cấu kiện",
                description="Vào page Import Master nạp PKL trước.")
    st.stop()

K_UPLOAD = "daily_upload_path"
K_UPLOAD_NAME = "daily_upload_name"
K_SHEETS = "daily_sheets"
K_DF = "daily_df"
K_HEADERS = "daily_headers"
K_MAPPING = "daily_mapping"
K_HEADER_ROW = "daily_header_row"
K_SHEET = "daily_sheet"

if st.session_state.get("daily_last_pid") != pid:
    for k in [K_UPLOAD, K_UPLOAD_NAME, K_SHEETS, K_DF, K_HEADERS, K_MAPPING,
              K_HEADER_ROW, K_SHEET]:
        st.session_state.pop(k, None)
    st.session_state["daily_last_pid"] = pid


def _score_sheet(filepath: str, sheet_name: str, keywords: list[str]) -> int:
    """
    Chấm điểm 1 sheet xem có khả năng là sheet kiểm tra hay không.

    Tiêu chí (cộng dồn):
      +200  nếu tên sheet trùng keyword chính (FUR/DGRP/FINAL...)
      +50   nếu tên có chứa từ chung QC (RFI/NT/DSNT)
      +30 mỗi header keyword match (Member No / Tên cấu kiện / Punch No / ...)
      +1   mỗi dòng có ≥3 ô có nội dung (trong 50 dòng đầu)
      -100 nếu tên có "DATA"/"INPUT"/"REF" (sheet phụ trợ, không phải dữ liệu)
    """
    score = 0
    s_upper = sheet_name.upper()

    # 1. Tên sheet match keyword chính
    main_kw_hit = False
    for kw in keywords[:5]:  # 5 keyword đầu = quan trọng nhất
        if kw.upper() in s_upper:
            score += 200
            main_kw_hit = True
            break
    # Match keyword phụ
    if not main_kw_hit:
        for kw in keywords[5:]:
            if kw.upper() in s_upper:
                score += 50
                break

    # 2. Tên có gợi ý là sheet phụ trợ → trừ điểm
    for bad_kw in ["DATA", "INPUT", "REF", "TEMPLATE", "BLANK", "MẪU", "DEMO"]:
        if bad_kw in s_upper:
            score -= 100
            break

    # 3. Đọc nội dung — header & signal density
    try:
        df = read_excel_any(filepath, sheet_name=sheet_name, header=None)
        df_head = df.head(50)
        # Cộng điểm theo signal density
        for _, row in df_head.iterrows():
            non_empty = sum(
                1 for v in row
                if v is not None and str(v).strip() not in ("", "nan")
            )
            if non_empty >= 3:
                score += 1
        # Cộng điểm cho header QC chuẩn xuất hiện trong 30 dòng đầu
        all_text = " ".join(
            str(v) for v in df_head.head(30).values.flatten()
            if v is not None
        ).lower()
        for hint in [
            "member no", "punch no", "tên cấu kiện", "tên - mã số",
            "mã cấu kiện", "name - code", "piece mark", "drawing no",
        ]:
            if hint in all_text:
                score += 30
    except Exception:
        pass

    return score


def _detect_sheet(sheets, keywords, filepath: str = ""):
    """
    Chọn sheet tốt nhất.

    - Nếu chỉ có 1 sheet → trả về luôn.
    - Nếu có filepath: dùng scoring (đọc nội dung).
    - Nếu không có filepath: fallback về match tên đơn giản.
    """
    if not sheets:
        return ""
    if len(sheets) == 1:
        return sheets[0]

    if filepath:
        best, best_score = sheets[0], -1
        for s in sheets:
            try:
                sc = _score_sheet(filepath, s, keywords)
            except Exception:
                sc = 0
            if sc > best_score:
                best_score, best = sc, s
        return best

    # Fallback — match tên đơn giản
    for s in sheets:
        s_upper = s.upper()
        for kw in keywords:
            if kw.upper() in s_upper:
                return s
    return sheets[0]


def _detect_columns(headers, inspection_code):
    mapping = {}
    # Ưu tiên 1: cột có tên đầy đủ
    for h in headers:
        h_lower = str(h).lower().strip()
        if ("tên - mã số" in h_lower or "name - code" in h_lower
                or "tên cấu kiện" in h_lower or "item name" in h_lower
                or "member punch" in h_lower or "piece mark" in h_lower
                or "mã cấu kiện" in h_lower or "punch no" in h_lower
                or "tên hồ sơ" in h_lower):
            mapping["code"] = h
            break
    # Ưu tiên 2: cột tên ngắn "TÊN" / "Tên" / "Code" / "Mã"
    if "code" not in mapping:
        for h in headers:
            h_lower = str(h).lower().strip()
            if h_lower in ("tên", "ten", "code", "mã", "ma"):
                mapping["code"] = h
                break
    # Ưu tiên 3: fallback các vị trí cũ
    if "code" not in mapping:
        for h in ("Unnamed: 3", "Unnamed: 2", "Unnamed: 4"):
            if h in headers:
                mapping["code"] = h
                break

    for h in headers:
        h_lower = str(h).lower()
        if "ghi chú" in h_lower or "remark" in h_lower or "note" in h_lower:
            mapping["note"] = h
            break
    if "note" not in mapping and "Unnamed: 17" in headers:
        mapping["note"] = "Unnamed: 17"

    for h in headers:
        if "qc check" in str(h).lower() or "người" in str(h).lower():
            mapping["inspector"] = h
            break

    if "Barcode" in headers:
        mapping["report_no"] = "Barcode"
    return mapping


def _auto_setup(filepath, inspection_code, default_header, sheet_keywords):
    """
    Auto-detect sheet + header + mapping cho file daily.
    Thứ tự ưu tiên header detection:
      1. smart_detect_header_row — quét keyword "Tên Cấu Kiện"/"Member No"/"STT"/...
      2. Fallback: dò các header phổ biến cho DGRP (11/12/10/9/13)
      3. Fallback cuối: default_header từ INSPECTION_OPTIONS
    """
    try:
        sheets = list_sheet_names(filepath)
        st.session_state[K_SHEETS] = sheets
        sheet = _detect_sheet(sheets, sheet_keywords, filepath)
        st.session_state[K_SHEET] = sheet

        # 1) Smart auto-detect header row (cải tiến mới — quét 20 dòng đầu)
        best_hr = smart_detect_header_row(filepath, sheet)
        best_df = None
        try:
            best_df = read_excel_any(filepath, sheet_name=sheet, header=best_hr)
            hdrs = [str(c).lower().strip() for c in best_df.columns]
            # Kiểm tra: có cột chứa tên/mã hợp lệ không?
            # Mở rộng từ khoá để chấp nhận cả cột "TÊN" (rút gọn) chứ không
            # chỉ "Tên cấu kiện" / "Member No" / ...
            CODE_HINTS = [
                "tên cấu kiện", "ten cau kien", "member no", "punch no",
                "mã cấu kiện", "ma cau kien", "piece mark", "tên - mã số",
                "name - code", "tên hồ sơ", "tên",  # ngắn — cuối cùng
            ]
            has_code_col = False
            for h in hdrs:
                # Bỏ qua các tên cột Unnamed / quá dài (>40 ký tự = không phải header thật)
                if h.startswith("unnamed") or len(h) > 40:
                    continue
                if any(kw in h for kw in CODE_HINTS):
                    has_code_col = True
                    break
            if not has_code_col:
                best_df = None  # ép sang fallback
        except Exception:
            best_df = None

        # 2) Fallback cho DGRP form cũ (VIOLA, ...) — dò 11/12/10/9/13
        if best_df is None and inspection_code == "DGRP":
            for try_hr in (11, 12, 10, 9, 13, 7, 6, 5):
                try:
                    df_t = read_excel_any(filepath, sheet_name=sheet, header=try_hr)
                    hdrs = [str(c) for c in df_t.columns]
                    if any(
                        "tên - mã số" in str(h).lower() or "name - code" in str(h).lower()
                        or "mã số" in str(h).lower() or "tên cấu kiện" in str(h).lower()
                        or "member no" in str(h).lower()
                        for h in hdrs
                    ):
                        best_hr = try_hr
                        best_df = df_t
                        break
                except Exception:
                    continue

        # 3) Fallback cuối
        if best_df is None:
            best_hr = default_header
            best_df = read_excel_any(filepath, sheet_name=sheet, header=best_hr)

        st.session_state[K_HEADER_ROW] = best_hr
        headers = [str(c) for c in best_df.columns]
        st.session_state[K_DF] = best_df
        st.session_state[K_HEADERS] = headers
        st.session_state[K_MAPPING] = _detect_columns(headers, inspection_code)
    except Exception as e:
        st.error(f"Lỗi auto-detect: {e}")


c_type, c_upload = st.columns([1, 2])
with c_type:
    st.markdown("**Loại kiểm tra**")
    chosen_label = st.radio(
        "Loại", OPT_LABELS,
        label_visibility="collapsed", horizontal=False,
        captions=[o["desc"] for o in INSPECTION_OPTIONS],
    )
    chosen_opt = OPT_BY_LABEL[chosen_label]
    chosen_code = chosen_opt["code"]

with c_upload:
    st.markdown("**File Excel daily**")
    uploaded = st.file_uploader(
        "Upload", type=["xlsx", "xlsm", "xls", "xlsb", "csv"],
        accept_multiple_files=False,
        label_visibility="collapsed",
        key=f"daily_uploader_{chosen_code}",
    )

if uploaded is not None:
    new_key = f"{uploaded.name}__{chosen_code}"
    if st.session_state.get("daily_session_key") != new_key:
        suffix = Path(uploaded.name).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(uploaded.getbuffer())
        tmp.close()
        st.session_state[K_UPLOAD] = tmp.name
        st.session_state[K_UPLOAD_NAME] = uploaded.name
        st.session_state["daily_session_key"] = new_key
        with st.spinner(f"🤖 Đang đọc file..."):
            _auto_setup(tmp.name, chosen_code, chosen_opt["default_header"],
                       chosen_opt["sheet_keywords"])
        st.rerun()

if K_UPLOAD not in st.session_state:
    empty_state(icon="📤", title="Chưa upload file",
                description="Chọn loại bên trái rồi kéo thả file Excel.")
    st.stop()

df = st.session_state.get(K_DF)
headers = st.session_state.get(K_HEADERS, [])
mapping = st.session_state.get(K_MAPPING, {})
header_row = st.session_state.get(K_HEADER_ROW, 0)
sheet = st.session_state.get(K_SHEET)

st.write("")
st.divider()

c1, c2, c3, c4 = st.columns([3, 2, 1.5, 2])
with c1:
    st.markdown(
        f"<div style='color:#64748B;font-size:13px;'>📄 File</div>"
        f"<div style='font-weight:600;color:#0F1E40;font-size:14px;'>{st.session_state[K_UPLOAD_NAME]}</div>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"<div style='color:#64748B;font-size:13px;'>📋 Sheet</div>"
        f"<div style='font-weight:600;color:#0F1E40;font-size:14px;'>{sheet}</div>",
        unsafe_allow_html=True,
    )
with c3:
    if df is not None:
        st.markdown(
            f"<div style='color:#64748B;font-size:13px;'>📑 Dòng</div>"
            f"<div style='font-weight:600;color:#0F1E40;font-size:14px;'>{len(df):,}</div>",
            unsafe_allow_html=True,
        )
with c4:
    has_code = "code" in mapping
    color = "#16A34A" if has_code else "#D97706"
    text = "✅ Đã có cột mã" if has_code else "⚠ Chưa có cột mã"
    st.markdown(
        f"<div style='color:#64748B;font-size:13px;'>🔗 Mapping</div>"
        f"<div style='font-weight:600;color:{color};font-size:14px;'>{text}</div>",
        unsafe_allow_html=True,
    )

st.write("")

if has_code:
    st.success(
        f"✅ **Tự động phát hiện**: sheet `{sheet}` · header `{header_row}` · "
        f"map {len(mapping)} cột. Bấm **Import** ngay."
    )
else:
    st.warning("⚠ Chưa tìm được cột mã. Vào **Tinh chỉnh mapping** chọn thủ công.")

# === AUTO mode: preview phân loại các dòng theo cột NỘI DUNG ===
auto_split_info = None  # {nd_col, n_fur, n_dgrp, n_other, df_fur, df_dgrp}
if chosen_code == "AUTO" and df is not None and has_code:
    nd_col = _find_noidung_column(df.columns)
    if not nd_col:
        st.error(
            "⚠ Mode **Tự động** cần cột NỘI DUNG / Loại NT trong file. "
            "File này không có. Hãy chọn loại Fit-up hoặc Final thủ công."
        )
    else:
        # Classify từng dòng
        row_classes = df[nd_col].apply(_classify_inspection_row)
        df_fur_split = df[row_classes == "FUR"]
        df_dgrp_split = df[row_classes == "DGRP"]
        df_other = df[row_classes == ""]

        auto_split_info = {
            "nd_col": nd_col,
            "n_fur": len(df_fur_split),
            "n_dgrp": len(df_dgrp_split),
            "n_other": len(df_other),
            "df_fur": df_fur_split,
            "df_dgrp": df_dgrp_split,
        }

        # Hiển thị phân loại
        c_a, c_b, c_c, c_d = st.columns(4)
        with c_a:
            st.metric("🔨 Fit-up", auto_split_info["n_fur"])
        with c_b:
            st.metric("✅ Final", auto_split_info["n_dgrp"])
        with c_c:
            st.metric("⚪ Bỏ qua", auto_split_info["n_other"],
                      help="Dòng không nhận diện được loại (vd NDT, header phụ)")
        with c_d:
            st.metric("📋 Cột nhận dạng", nd_col[:20] + ("..." if len(nd_col) > 20 else ""))

        if auto_split_info["n_other"] > 0:
            with st.expander(f"Xem {auto_split_info['n_other']} dòng bị bỏ qua"):
                _other_summary = df_other[nd_col].value_counts().head(20)
                st.dataframe(
                    _other_summary.reset_index().rename(
                        columns={nd_col: "Nội dung", "count": "Số dòng"}
                    ),
                    hide_index=True, use_container_width=True,
                )

c_nfi, c_date, c_dateinfo = st.columns([2, 2, 3])
with c_nfi:
    manual_nfi = st.text_input("🔢 Số NFI", value="",
                                placeholder="vd: NFI-2026-0123")
with c_date:
    auto_date = extract_date_from_filename(st.session_state.get(K_UPLOAD_NAME, "") or "")
    manual_date = st.text_input("📅 Ngày kiểm tra",
                                 value=auto_date or "",
                                 placeholder="DD/MM/YYYY")
    manual_date_iso = parse_date_input(manual_date) if manual_date else ""
with c_dateinfo:
    st.write("")
    st.write("")
    if manual_date_iso:
        st.caption(f"📌 Lưu: `{manual_date_iso}` *(hiển thị {format_date_vn(manual_date_iso)})*")

st.write("")

c_dbg, c_imp = st.columns([2, 5])
with c_dbg:
    do_debug = st.button("🔍 Debug Match", use_container_width=True)
with c_imp:
    do_import = st.button(
        f"▶ Import {chosen_opt['label']} ({len(df):,} dòng) vào DB" if df is not None else "▶ Import",
        type="primary", use_container_width=True,
        disabled=("code" not in mapping or df is None),
    )

st.write("")

if do_debug:
    report = debug_match_service.debug_match(db, pid, df, mapping.get("code"))
    with st.container(border=True):
        st.markdown(f"#### 🔍 Debug Match — [{proj['code']}]")
        cl, cr = st.columns(2)
        with cl:
            st.markdown(f"**Master DB:** {report.master_total:,} cấu kiện")
            st.code("\n".join(f"• {c}" for c in report.master_samples) or "(không có)")
        with cr:
            if not report.daily_results:
                st.warning("Chưa đọc file daily hoặc chưa map cột 'code'.")
            else:
                st.markdown(f"**Daily:** {report.daily_total} dòng")
                df_dbg = pd.DataFrame([
                    {"Match": "✅" if d["found"] else "❌",
                     "Mã gốc": d["raw"], "Sau strip": d["stripped"],
                     "Match với": d["matched_with"] or "—"}
                    for d in report.daily_results
                ])
                st.dataframe(df_dbg, hide_index=True, use_container_width=True)

with st.expander("Tinh chỉnh sheet, header row, mapping cột", expanded=False):
    cc1, cc2, cc3 = st.columns([3, 2, 3])
    with cc1:
        sheets_local = st.session_state.get(K_SHEETS, [])
        new_sheet = st.selectbox("Sheet", sheets_local,
                                 index=sheets_local.index(sheet) if sheet in sheets_local else 0)
    with cc2:
        new_hr = st.number_input("Dòng tiêu đề", min_value=0, max_value=30, value=header_row)
    with cc3:
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
                st.session_state[K_MAPPING] = _detect_columns(headers_new, chosen_code)
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")

    st.write("")
    options = ["(bỏ qua)"] + headers
    new_mapping = {}
    DAILY_FIELDS = [
        ("code", "🔑 Mã cấu kiện", True),
        ("inspection_date", "Ngày kiểm tra", False),
        ("inspector", "Người kiểm tra", False),
        ("result", "Kết quả", False),
        ("report_no", "Số báo cáo", False),
        ("note", "Ghi chú / Remark", False),
    ]
    edit_cols = st.columns(2)
    for i, (field, desc, required) in enumerate(DAILY_FIELDS):
        target = edit_cols[0] if i < 3 else edit_cols[1]
        with target:
            current = mapping.get(field, "")
            idx = options.index(current) if current in options else 0
            label = f"**{desc}**{' *(bắt buộc)*' if required else ''}"
            chosen = st.selectbox(label, options, index=idx, key=f"daily_map_{field}_{chosen_code}")
            if chosen and chosen != "(bỏ qua)":
                new_mapping[field] = chosen
    st.session_state[K_MAPPING] = new_mapping

with st.expander("Xem trước 5 dòng đầu", expanded=False):
    if df is not None and mapping:
        preview_cols = list(dict.fromkeys(c for c in mapping.values() if c in df.columns))
        if preview_cols:
            st.dataframe(df[preview_cols].head(5), use_container_width=True, height=220)

# Khi chọn Final, check trước xem có cấu kiện nào chưa Fit-up không
if do_import and "code" in mapping and chosen_code == "DGRP":
    code_col = mapping["code"]
    codes_in_file = []
    for _, row in df.iterrows():
        v = row.get(code_col)
        if pd.isna(v):
            continue
        code = str(v).strip()
        if not code or code.lower() == "nan" or len(code) <= 2:
            continue
        # ✋ Lọc các giá trị thuần số (vd "0.0", "1", "123") — không phải mã cấu kiện
        try:
            float(code)
            continue  # là số → bỏ qua
        except ValueError:
            pass
        # Strip prefix giống logic match
        import re as _re
        m = _re.match(r"^\d+-(.+)$", code)
        if m:
            code = m.group(1)
        codes_in_file.append(code)
    codes_in_file = list(set(codes_in_file))

    missing_fitup = component_service.get_components_missing_fitup(db, pid, codes_in_file)
    if missing_fitup:
        st.session_state["_missing_fitup"] = missing_fitup
        st.session_state["_pending_import"] = True
        do_import = False  # tạm ngừng — chờ confirm

if st.session_state.get("_pending_import") and st.session_state.get("_missing_fitup"):
    missing = st.session_state["_missing_fitup"]
    with st.container(border=True):
        st.warning(
            f"⚠ **Cảnh báo quy trình QC**: có **{len(missing)}** cấu kiện CHƯA có Fit-up PASS "
            f"nhưng đang được import Final. Theo quy trình, nên Fit-up trước rồi mới Final."
        )
        # Hiển thị bảng đầy đủ: Mã | Bản vẽ | Xưởng | Tình trạng
        import pandas as _pd
        df_missing = _pd.DataFrame(missing)
        # Đổi tên cột tiếng Việt
        df_disp = df_missing.rename(columns={
            "code": "Mã cấu kiện",
            "name": "Bản vẽ",
            "workshop": "Xưởng",
        })
        # Thêm cột Tình trạng dựa vào in_master
        if "in_master" in df_disp.columns:
            df_disp["Tình trạng"] = df_disp["in_master"].apply(
                lambda x: "Có trong master, chưa Fit-up" if x else "⚠ Không có trong master"
            )
            df_disp = df_disp.drop(columns=["in_master"])

        st.markdown(f"**📋 Danh sách {len(missing)} cấu kiện chưa Fit-up:**")
        st.dataframe(
            df_disp,
            use_container_width=True,
            hide_index=True,
            height=min(400, 50 + len(df_disp) * 35),
        )
        # Cho phép tải CSV để truy xuất đầy đủ
        csv_content = df_disp.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Tải danh sách CSV (đầy đủ)",
            csv_content,
            file_name=f"missing_fitup_{proj['code']}.csv",
            mime="text/csv",
        )

        cw1, cw2 = st.columns(2)
        with cw1:
            if st.button("⚠ Vẫn import Final", type="primary", use_container_width=True):
                do_import = True
                st.session_state.pop("_missing_fitup", None)
                st.session_state.pop("_pending_import", None)
        with cw2:
            if st.button("❌ Huỷ — về Fit-up trước", use_container_width=True):
                st.session_state.pop("_missing_fitup", None)
                st.session_state.pop("_pending_import", None)
                st.info("Đã huỷ. Hãy import file Fit-up trước rồi mới Final.")
                st.rerun()

if do_import and "code" in mapping:
    try:
        source_file = st.session_state.get(K_UPLOAD_NAME, "uploaded.xlsx")
        user_name = st.session_state[S_CURRENT_USER]

        # === MODE AUTO: chia file thành 2 nhóm rồi import 2 lần ===
        if chosen_code == "AUTO":
            if auto_split_info is None:
                st.error("⚠ Không phát hiện được cột NỘI DUNG. Hãy chọn Fit-up hoặc Final thủ công.")
            else:
                results = {}
                with st.spinner("🤖 Đang import song song Fit-up + Final..."):
                    # 1) Import Fit-up
                    if auto_split_info["n_fur"] > 0:
                        results["FUR"] = daily_import_service.import_daily(
                            db, pid=pid, df=auto_split_info["df_fur"],
                            mapping=mapping, inspection_type="FUR",
                            source_file=source_file,
                            manual_date=manual_date_iso,
                            manual_nfi=manual_nfi.strip(),
                            user_name=user_name,
                        )
                    # 2) Import Final
                    if auto_split_info["n_dgrp"] > 0:
                        results["DGRP"] = daily_import_service.import_daily(
                            db, pid=pid, df=auto_split_info["df_dgrp"],
                            mapping=mapping, inspection_type="DGRP",
                            source_file=source_file,
                            manual_date=manual_date_iso,
                            manual_nfi=manual_nfi.strip(),
                            user_name=user_name,
                        )

                # Tổng hợp kết quả
                total_matched = sum(r.matched_components for r in results.values())
                total_records = sum(r.inspections_added for r in results.values())
                total_notfound = sum(r.not_found for r in results.values())

                if total_matched > 0:
                    st.balloons()

                st.success(
                    f"🤖 **Import Tự động hoàn tất** · "
                    f"{total_matched} cấu kiện cập nhật · "
                    f"{total_records} inspection records · "
                    f"không khớp {total_notfound}"
                )

                # Chi tiết theo từng loại
                cdt1, cdt2 = st.columns(2)
                with cdt1:
                    if "FUR" in results:
                        r = results["FUR"]
                        st.info(
                            f"🔨 **Fit-up**: {r.matched_components}/{auto_split_info['n_fur']} "
                            f"cấu kiện · {r.inspections_added} records · "
                            f"không khớp {r.not_found}"
                        )
                with cdt2:
                    if "DGRP" in results:
                        r = results["DGRP"]
                        st.info(
                            f"✅ **Final**: {r.matched_components}/{auto_split_info['n_dgrp']} "
                            f"cấu kiện · {r.inspections_added} records · "
                            f"không khớp {r.not_found}"
                        )
        else:
            # === MODE BÌNH THƯỜNG: import 1 loại ===
            with st.spinner(f"Đang import..."):
                result = daily_import_service.import_daily(
                    db, pid=pid, df=df, mapping=mapping,
                    inspection_type=chosen_code,
                    source_file=source_file,
                    manual_date=manual_date_iso,
                    manual_nfi=manual_nfi.strip(),
                    user_name=user_name,
                )
            if result.matched_components > 0:
                st.balloons()
            next_status_label = "Đã nghiệm thu" if chosen_code == "DGRP" else "Đã Fit-up"
            st.success(
                f"**Import {chosen_opt['label']} thành công** · "
                f"{result.matched_components} cấu kiện cập nhật · "
                f"{result.inspections_added} inspection records · "
                f"không khớp {result.not_found} · "
                f"→ status mới: **{next_status_label}**"
            )
    except Exception as e:
        st.error(f"Lỗi import: {e}")
        import traceback
        with st.expander("Chi tiết"):
            st.code(traceback.format_exc())
