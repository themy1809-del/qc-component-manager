# -*- coding: utf-8 -*-
"""
Theme & global CSS cho QC Component Manager Web v2.0.

Tone Corporate Navy + Gold accent:
- Navy primary:    #0F1E40
- Navy lighter:    #1E3A8A
- Gold accent:     #D4A744
- Gold soft:       #FCE7A1
- Off-white bg:    #FAFBFC
- Slate text:      #0F172A
- Slate muted:     #64748B
"""
from __future__ import annotations

import streamlit as st

# ====================================================================
# COLOR TOKENS — dùng làm tham chiếu trong code Python
# ====================================================================
NAVY = "#0F1E40"
NAVY_LIGHT = "#1E3A8A"
NAVY_DARK = "#0A1428"
GOLD = "#D4A744"
GOLD_SOFT = "#FCE7A1"
GOLD_DARK = "#9F7B1F"
BG = "#FAFBFC"
SURFACE = "#FFFFFF"
BORDER = "#E2E8F0"
TEXT = "#0F172A"
TEXT_MUTED = "#64748B"
SUCCESS = "#16A34A"
WARNING = "#D97706"
DANGER = "#DC2626"
TEAL = "#0F766E"


_CSS = f"""
<style>
/* ====================================================================
   Global typography + background
==================================================================== */
.stApp {{
    background: {BG};
}}

html, body, [class*="st-"] {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter',
                 'Helvetica Neue', Arial, sans-serif;
    color: {TEXT};
}}

/* Heading màu navy */
h1, h2, h3, h4 {{
    color: {NAVY} !important;
    letter-spacing: -0.01em;
}}
h1 {{ font-weight: 700; }}
h2, h3 {{ font-weight: 600; }}

/* Caption muted */
[data-testid="stCaptionContainer"] {{
    color: {TEXT_MUTED} !important;
}}

/* ====================================================================
   Hide Streamlit default chrome (cleaner look)
==================================================================== */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{
    background: transparent;
    height: 0;
}}

/* ====================================================================
   Sidebar: ẨN HOÀN TOÀN (navigation đã chuyển lên top bar)
==================================================================== */
section[data-testid="stSidebar"] {{
    display: none !important;
}}
[data-testid="collapsedControl"] {{
    display: none !important;
}}
/* Main content area mở rộng hết khi không có sidebar */
[data-testid="stMain"] .block-container {{
    max-width: 1400px !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}}

/* Style cho st.page_link buttons (top nav) */
[data-testid="stPageLink"],
a[data-testid="stPageLink-NavLink"] {{
    background: #FFFFFF !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    text-align: center !important;
    font-weight: 500 !important;
    color: {NAVY} !important;
    transition: all .15s ease;
    text-decoration: none !important;
}}
[data-testid="stPageLink"]:hover,
a[data-testid="stPageLink-NavLink"]:hover {{
    background: {GOLD_SOFT} !important;
    border-color: {GOLD} !important;
    color: {NAVY_DARK} !important;
    transform: translateY(-1px);
}}

/* Legacy sidebar styles - giữ làm fallback ====================== */
section[data-testid="stSidebar"]_LEGACY {{
    background: linear-gradient(180deg, {NAVY_DARK} 0%, {NAVY} 100%);
    border-right: 1px solid {NAVY_DARK};
}}
section[data-testid="stSidebar"] * {{
    color: #E2E8F0 !important;
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4,
section[data-testid="stSidebar"] h5,
section[data-testid="stSidebar"] h6 {{
    color: #FFFFFF !important;
}}
/* Sidebar navigation links - các page */
section[data-testid="stSidebarNav"] {{
    background: transparent;
    padding-top: 8px;
}}
section[data-testid="stSidebarNav"] a {{
    border-radius: 8px;
    margin: 2px 8px;
    padding: 8px 12px;
    transition: all .15s ease;
}}
section[data-testid="stSidebarNav"] a:hover {{
    background: rgba(212, 167, 68, 0.15) !important;
}}
section[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {GOLD} !important;
    color: {NAVY_DARK} !important;
    font-weight: 600;
}}
section[data-testid="stSidebarNav"] a[aria-current="page"] * {{
    color: {NAVY_DARK} !important;
}}

/* ==== Sidebar inputs: bg trắng + text ĐEN (như Excel) cho dễ đọc khi nhập ====
   Dùng nhiều selectors + boost specificity + -webkit-text-fill-color
   để đảm bảo override mọi Streamlit DOM variants */
html body section[data-testid="stSidebar"] input,
html body section[data-testid="stSidebar"] textarea,
html body section[data-testid="stSidebar"] input[type="text"],
html body section[data-testid="stSidebar"] input[type="password"],
html body section[data-testid="stSidebar"] [data-baseweb="input"] input,
html body section[data-testid="stSidebar"] [data-baseweb="textarea"] textarea,
html body section[data-testid="stSidebar"] [data-testid="stTextInput"] input,
html body section[data-testid="stSidebar"] [data-testid="stTextArea"] textarea,
html body section[data-testid="stSidebar"] [data-testid="stForm"] input,
html body section[data-testid="stSidebar"] [data-testid="stForm"] textarea {{
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    color: #0F1E40 !important;
    -webkit-text-fill-color: #0F1E40 !important;
    caret-color: #0F1E40 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}}

/* Cha của input đôi khi cũng có bg → force trắng */
html body section[data-testid="stSidebar"] [data-baseweb="input"],
html body section[data-testid="stSidebar"] [data-baseweb="textarea"],
html body section[data-testid="stSidebar"] [data-baseweb="base-input"] {{
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
}}

/* Placeholder text: xám đậm rõ ràng */
section[data-testid="stSidebar"] input::placeholder,
section[data-testid="stSidebar"] textarea::placeholder {{
    color: #94A3B8 !important;
    opacity: 1 !important;
}}

/* Focus state: viền gold */
section[data-testid="stSidebar"] input:focus,
section[data-testid="stSidebar"] textarea:focus {{
    border-color: {GOLD} !important;
    box-shadow: 0 0 0 3px rgba(212, 167, 68, .2) !important;
}}

/* Selectbox sidebar: bg trắng + text đen */
section[data-testid="stSidebar"] [data-baseweb="select"] {{
    background: #FFFFFF !important;
    border-radius: 8px !important;
}}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {{
    background: #FFFFFF !important;
    color: #0F1E40 !important;
}}
section[data-testid="stSidebar"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stMarkdownContainer"] p {{
    color: #0F1E40 !important;
}}

/* Expander trong sidebar */
section[data-testid="stSidebar"] [data-testid="stExpander"] {{
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
}}

section[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.12) !important;
}}

/* Form trong sidebar: bg trong suốt, kế thừa nền navy */
section[data-testid="stSidebar"] [data-testid="stForm"] {{
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    padding: 12px !important;
}}

/* Labels trong sidebar: TRẮNG đậm để nổi trên nền navy */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    color: #FFFFFF !important;
    font-weight: 600 !important;
    font-size: 13px !important;
}}

/* ====================================================================
   Buttons
==================================================================== */
.stButton > button {{
    border-radius: 8px;
    font-weight: 500;
    padding: 6px 16px;
    border: 1px solid {BORDER};
    background: {SURFACE};
    color: {TEXT};
    transition: all .15s ease;
}}
.stButton > button:hover {{
    border-color: {NAVY};
    background: #F1F5F9;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(15, 30, 64, 0.08);
}}
.stButton > button[kind="primary"],
.stButton > button[kind="primary"] *,
.stButton > button[kind="primary"] p,
.stButton > button[kind="primary"] span,
button[data-testid="baseButton-primary"],
button[data-testid="baseButton-primary"] * {{
    background: {NAVY} !important;
    border-color: {NAVY} !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover * {{
    background: {NAVY_LIGHT} !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(15, 30, 64, 0.25);
}}
.stButton > button[kind="primary"]:active {{
    background: {NAVY_DARK} !important;
}}

/* Sidebar buttons */
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
    background: {GOLD} !important;
    border-color: {GOLD} !important;
    color: {NAVY_DARK} !important;
    font-weight: 600;
}}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
    background: {GOLD_SOFT} !important;
}}

/* ====================================================================
   Input fields
==================================================================== */
[data-testid="stTextInput"] > div > div > input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {{
    border-radius: 8px !important;
    border: 1px solid {BORDER} !important;
    background: {SURFACE} !important;
    transition: border-color .15s ease, box-shadow .15s ease;
}}
[data-testid="stTextInput"] > div > div > input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: {NAVY} !important;
    box-shadow: 0 0 0 3px rgba(15, 30, 64, 0.1) !important;
}}

[data-testid="stSelectbox"] > div > div {{
    border-radius: 8px !important;
    border: 1px solid {BORDER} !important;
}}

/* ====================================================================
   File uploader - drag drop đẹp
==================================================================== */
[data-testid="stFileUploader"] section {{
    border: 2px dashed {BORDER} !important;
    border-radius: 12px !important;
    background: {SURFACE} !important;
    padding: 28px !important;
    transition: all .2s ease;
}}
[data-testid="stFileUploader"] section:hover {{
    border-color: {GOLD} !important;
    background: #FFFCF1 !important;
}}

/* ====================================================================
   Metrics + custom KPI cards
==================================================================== */
[data-testid="stMetric"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}}
[data-testid="stMetric"] label {{
    color: {TEXT_MUTED} !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}}
[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    color: {NAVY} !important;
    font-size: 28px !important;
    font-weight: 700 !important;
}}

/* ====================================================================
   Dataframe + data editor
==================================================================== */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
    border-radius: 10px !important;
    overflow: hidden;
    border: 1px solid {BORDER};
}}

/* ====================================================================
   Tabs
==================================================================== */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    background: transparent;
    border-bottom: 1px solid {BORDER};
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px 8px 0 0;
    padding: 8px 16px;
    font-weight: 500;
    color: {TEXT_MUTED};
}}
.stTabs [aria-selected="true"] {{
    background: {NAVY} !important;
    color: white !important;
}}
.stTabs [aria-selected="true"] * {{ color: white !important; }}

/* ====================================================================
   Alerts: success/warning/error/info
==================================================================== */
[data-testid="stAlert"] {{
    border-radius: 10px !important;
    border-width: 1px !important;
    border-left-width: 4px !important;
}}

/* ====================================================================
   Expander
==================================================================== */
[data-testid="stExpander"] {{
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    background: {SURFACE} !important;
}}
[data-testid="stExpander"] summary {{
    font-weight: 500;
}}

/* ====================================================================
   Divider tinh tế
==================================================================== */
hr {{
    border: none;
    border-top: 1px solid {BORDER};
    margin: 16px 0 !important;
}}

/* ====================================================================
   Block container - tăng max-width
==================================================================== */
.block-container {{
    max-width: 1400px !important;
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
}}

/* ====================================================================
   Progress bar - gold accent
==================================================================== */
[data-testid="stProgress"] > div > div > div > div {{
    background: linear-gradient(90deg, {GOLD} 0%, {NAVY_LIGHT} 100%) !important;
}}

/* ====================================================================
   Form border
==================================================================== */
[data-testid="stForm"] {{
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    padding: 20px !important;
    background: {SURFACE} !important;
}}

/* ====================================================================
   FIX: Material Symbols font fallback
   Khi font Material Symbols không load (network/firewall block),
   Streamlit hiện tên icon dạng text "arrow_right", "expand_more",...
   → ẨN text và thay bằng Unicode chevron tự vẽ.
==================================================================== */

/* Ẩn text fallback của Material icon (chỉ giữ font Material Symbols).
   Nếu font không load → text invisible thay vì hiện shortcode lằng nhằng. */
[data-testid="stIconMaterial"],
.st-emotion-cache-1pbsqtx,
[class*="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded', 'Material Icons',
                 'Material Symbols Outlined' !important;
    font-size: 18px;
    line-height: 1;
    /* Khi font không load, các kí tự text trở thành ô vuông → ẩn luôn */
    font-feature-settings: 'liga';
}}

/* Trường hợp font Material vẫn fail → font-size:0 để text không hiện ra,
   rồi vẽ chevron Unicode đè lên qua ::after */
@font-face {{
    font-family: 'Material Symbols Rounded';
    font-style: normal;
    font-weight: 400;
    src: local('Material Symbols Rounded'),
         local('Material Icons'),
         url('https://fonts.gstatic.com/s/materialsymbolsrounded/v200/sykg-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190FjpZIvDmUSVOK7BDB_Qb9vUSzq3wzLK-P0J-V_Zs-QtQth3-jOcbTCVpeRL2w5rwZu2rIelXxc.woff2') format('woff2');
    font-display: swap;
}}

/* Expander: ẩn icon mặc định của Streamlit + tự vẽ chevron */
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{
    /* Ẩn text fallback bằng cách thu nhỏ font + transparent */
    font-size: 0 !important;
    color: transparent !important;
    width: 18px;
    height: 18px;
    position: relative;
}}

/* Vẽ chevron tự bằng pseudo-element */
[data-testid="stExpander"] summary [data-testid="stIconMaterial"]::after {{
    content: "▸";
    font-family: 'Segoe UI', Arial, sans-serif !important;
    font-size: 13px;
    color: {TEXT_MUTED};
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    transition: transform .2s ease;
}}

/* Khi expander mở → chevron chỉ xuống */
[data-testid="stExpander"] details[open] summary [data-testid="stIconMaterial"]::after {{
    content: "▾";
}}

/* Ẩn các Material icon text fallback ở các chỗ khác (vd: file upload, alert) */
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons {{
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    font-size: inherit;
}}

/* Catch-all: nếu thấy text dạng "arrow_right", "expand_more", "tune",
   "visibility", "folder", "warning" — coi như font không load → font-size:0 */
[data-testid="stIconMaterial"]:not(:has(svg)) {{
    font-size: 0 !important;
}}

/* ====================================================================
   📱 MOBILE RESPONSIVE — màn hình < 768px
==================================================================== */
@media (max-width: 768px) {{
    .block-container {{
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-top: 0.5rem !important;
        padding-bottom: 2rem !important;
    }}
    h1 {{ font-size: 1.4rem !important; }}
    h2 {{ font-size: 1.2rem !important; }}
    h3 {{ font-size: 1.05rem !important; }}

    [data-testid="stHorizontalBlock"] {{
        flex-direction: column !important;
        gap: 8px !important;
    }}
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
        width: 100% !important;
        min-width: 100% !important;
        flex: 1 0 100% !important;
    }}

    .stButton > button,
    .stDownloadButton > button {{
        min-height: 44px !important;
        font-size: 13px !important;
        padding: 8px 12px !important;
    }}

    .stSelectbox > div > div,
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {{
        min-height: 44px !important;
        font-size: 14px !important;
    }}

    [data-testid="stDataFrame"] {{
        font-size: 11px !important;
    }}

    .hero, .exec-hero, .cp-hero {{
        padding: 12px 14px !important;
        flex-direction: column !important;
        align-items: flex-start !important;
        text-align: left !important;
    }}
    .hero .pct, .exec-hero .pct-big, .cp-hero .pct {{
        font-size: 28px !important;
    }}
    .hero .name, .cp-hero .name {{
        font-size: 16px !important;
    }}

    .mini-kpi, .kpi-card {{
        height: auto !important;
        min-height: 80px !important;
        padding: 10px 12px !important;
    }}
    .mini-kpi .mk-value, .kpi-card .value {{
        font-size: 22px !important;
    }}

    .ws, .proj-mini {{
        min-height: 70px !important;
        padding: 10px 12px !important;
    }}
    .ws .pc {{ font-size: 20px !important; }}
    .ws .nm {{ font-size: 15px !important; }}

    .ws-detail, .panel, .alert-box {{
        box-shadow: none !important;
        padding: 12px !important;
    }}

    .section-title .sub, .sec .sub {{
        display: none !important;
    }}
}}

@media (max-width: 480px) {{
    .block-container {{
        padding-left: 0.3rem !important;
        padding-right: 0.3rem !important;
    }}
    h1 {{ font-size: 1.2rem !important; }}
    h2 {{ font-size: 1.05rem !important; }}
    .hero .pct, .cp-hero .pct {{
        font-size: 24px !important;
    }}
}}
</style>
"""


def apply_theme() -> None:
    """Inject custom CSS vào page. Gọi đầu mỗi page (sau st.set_page_config)."""
    st.markdown(_CSS, unsafe_allow_html=True)
