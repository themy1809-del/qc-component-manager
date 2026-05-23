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
    do_import = st.button(
        f"▶ Import {len(df):,} cấu kiện vào DB" if df is not None else "▶ Import",
        type="primary", use_container_width=True,
        disabled=("code" not in mapping or df is None),
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

    with st.expander("📋 Preview — Kiểm tra mapping trước khi import", expanded=True):
        pcol1, pcol2 = st.columns(2)
        with pcol1:
            st.markdown(f"""
**📊 Thống kê file:**
- Tổng dòng Excel: **{len(df):,}**
- Mã unique theo cột `code`: **{n_unique_code:,}** {code_check_emoji}
- Cấu kiện sẽ có Fit-up: **{n_rfi_fitup:,}** {fitup_emoji} ngày
- Cấu kiện sẽ có Final: **{n_rfi_final:,}** {final_emoji} ngày
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

st.write("")

with st.expander("Xem trước 5 dòng đầu", expanded=False):
    if df is not None and mapping:
        preview_cols = list(dict.fromkeys(c for c in mapping.values() if c in df.columns))
        if preview_cols:
            st.dataframe(df[preview_cols].head(5), use_container_width=True, height=220)

with st.expander(f"Tinh chỉnh mapping ({len(mapping)}/{len(STANDARD_FIELDS)} trường)", expanded=False):
    cc1, cc2, cc3 = st.columns([3, 2, 3])
    with cc1:
        sheets_local = st.session_state.get(K_SHEETS, [])
        new_sheet = st.selectbox("Sheet", sheets_local,
                                 index=sheets_local.index(sheet) if sheet in sheets_local else 0)
    with cc2:
        new_hr = st.number_input("Dòng tiêu đề (0-based)", min_value=0, max_value=30, value=header_row)
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
    st.session_state[K_MAPPING] = new_mapping

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
                f"🔄 **Phát hiện {n_rev} cấu kiện có REVISION THAY ĐỔI** so với master cũ.\n\n"
                f"Anh cần xem xét: bản vẽ đã update → nên kiểm tra lại Fit-up/Final cho các cấu kiện này."
            )
            with st.expander(f"Xem chi tiết {n_rev} cấu kiện đổi Rev", expanded=True):
                df_rev = _pd.DataFrame(result.rev_changed).rename(columns={
                    "code": "Mã cấu kiện",
                    "name": "Bản vẽ",
                    "old_rev": "Rev cũ",
                    "new_rev": "Rev mới",
                })
                st.dataframe(df_rev, hide_index=True, use_container_width=True, height=300)
                # Cho phép tải CSV để truy xuất
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
with st.expander("Khu vực nguy hiểm — Xoá toàn bộ cấu kiện", expanded=False):
    n_current = db.conn.execute(
        "SELECT COUNT(*) c FROM components WHERE project_id=?", (pid,)
    ).fetchone()["c"]
    st.warning(
        f"Hành động này sẽ xoá TOÀN BỘ **{n_current:,}** cấu kiện của dự án [{proj['code']}]. "
        f"Không hoàn tác được."
    )
    if st.button("🧹 Xoá toàn bộ cấu kiện", key="clear_confirm"):
        st.session_state["_confirm_clear"] = True

    if st.session_state.get("_confirm_clear"):
        st.error(f"**Xác nhận xoá toàn bộ cấu kiện của [{proj['code']}]?**")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("⚠ Xác nhận xoá", type="primary"):
                deleted = master_import_service.clear_components(
                    db, pid, st.session_state[S_CURRENT_USER]
                )
                st.session_state.pop("_confirm_clear", None)
                st.success(f"Đã xoá {deleted:,} cấu kiện.")
                st.rerun()
        with cc2:
            if st.button("Huỷ"):
                st.session_state.pop("_confirm_clear", None)
                st.rerun()
