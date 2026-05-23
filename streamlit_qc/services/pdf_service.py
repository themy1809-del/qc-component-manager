# -*- coding: utf-8 -*-
"""
Service: Xuất PDF biên bản nghiệm thu cấu kiện.

Dùng reportlab — bộ lib pure Python, không cần system deps,
chạy được trên Streamlit Cloud.

Layout 1 trang/cấu kiện:
- Header: logo + tên công ty + tiêu đề "BIÊN BẢN NGHIỆM THU"
- Project info: mã, tên, location, owner
- Component info: mã cấu kiện, tên bản vẽ, xưởng, material, section, length, weight
- Inspection table: Fit-up + Final + NDT (nếu có) với ngày, RFI, kết quả, inspector
- Result box: ACCEPTED / PASSED / IN_PROGRESS / FAILED
- Signature section: QC Đại Dũng | Khách hàng
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from streamlit_qc.core.date_utils import format_date_vn
from streamlit_qc.core.db import DB


# Color palette — phối Navy + Gold (đồng nhất với app theme)
NAVY = colors.HexColor("#0F1E40")
GOLD = colors.HexColor("#D4A744")
GOLD_LIGHT = colors.HexColor("#FCE7A1")
SLATE = colors.HexColor("#475569")
SUCCESS = colors.HexColor("#0F766E")
WARNING = colors.HexColor("#D97706")
DANGER = colors.HexColor("#DC2626")
LIGHT_BG = colors.HexColor("#F8FAFC")
BORDER = colors.HexColor("#E2E8F0")

# Font: dùng built-in Helvetica (Latin) — không hỗ trợ đầy đủ tiếng Việt
# nhưng đủ cho hầu hết text. Nếu muốn full UTF-8 → cần TTF của Roboto/DejaVu.
DEFAULT_FONT = "Helvetica"
DEFAULT_FONT_BOLD = "Helvetica-Bold"


def _status_label_color(status: str) -> tuple[str, colors.HexColor]:
    """Map status → (label tiếng Việt, color)."""
    return {
        "ACCEPTED":    ("DA NGHIEM THU (ACCEPTED)", SUCCESS),
        "PASSED":      ("DAT (PASSED)", colors.HexColor("#16A34A")),
        "IN_PROGRESS": ("DA FIT-UP, CHO FINAL", WARNING),
        "FAILED":      ("KHONG DAT (FAILED)", DANGER),
        "PENDING":     ("CHUA KIEM TRA", SLATE),
    }.get(status, (status, SLATE))


def _safe(value, default: str = "—") -> str:
    """Convert value → string an toàn cho PDF, replace None/empty."""
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def _build_single_component(
    db: DB,
    pid: int,
    cid: int,
    project: dict,
    inspector_signoff: str = "",
    customer_signoff: str = "",
) -> List:
    """Build flowable list cho 1 cấu kiện. Trả về list paragraph/table/spacer."""
    styles = getSampleStyleSheet()

    # Custom styles
    style_title = ParagraphStyle(
        "TitleVN", parent=styles["Title"],
        fontName=DEFAULT_FONT_BOLD, fontSize=16, alignment=TA_CENTER,
        textColor=NAVY, spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontName=DEFAULT_FONT, fontSize=10, alignment=TA_CENTER,
        textColor=SLATE, spaceAfter=10,
    )
    style_section = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        fontName=DEFAULT_FONT_BOLD, fontSize=11, textColor=NAVY,
        spaceBefore=6, spaceAfter=4,
    )
    style_normal = ParagraphStyle(
        "NormalSmall", parent=styles["Normal"],
        fontName=DEFAULT_FONT, fontSize=9, textColor=colors.black,
    )

    # Lấy data component
    comp_row = db.conn.execute(
        "SELECT * FROM components WHERE id=?", (cid,)
    ).fetchone()
    if not comp_row:
        return [Paragraph(f"Component ID {cid} not found", style_normal)]

    comp_data = json.loads(comp_row["data_json"])
    code = comp_row["code"]
    status = comp_row["status"]

    # Inspections
    ins_rows = db.conn.execute(
        """SELECT * FROM inspections WHERE component_id=?
           ORDER BY inspection_date DESC, id DESC""",
        (cid,),
    ).fetchall()
    inspections = [dict(r) for r in ins_rows]

    # ==========================================================
    # HEADER — Company + Title
    # ==========================================================
    flow = []
    flow.append(Paragraph("DAI DUNG GROUP - QC DEPARTMENT", style_subtitle))
    flow.append(Paragraph("BIEN BAN NGHIEM THU CAU KIEN", style_title))
    flow.append(Paragraph("Component Inspection Certificate", style_subtitle))

    # ==========================================================
    # PROJECT + COMPONENT INFO (2 cột)
    # ==========================================================
    flow.append(Paragraph("1. THONG TIN DU AN & CAU KIEN", style_section))

    info_table_data = [
        ["Du an / Project:", _safe(project.get("name")),
         "Ma du an / Code:", _safe(project.get("code"))],
        ["Dia diem / Location:", _safe(project.get("location")),
         "Chu dau tu / Owner:", _safe(project.get("owner"))],
        ["Ma cau kien / Component Code:", code,
         "Xuong / Workshop:", _safe(comp_data.get("workshop"))],
        ["Ten ban ve / Drawing:",
         _safe(comp_data.get("drawing") or comp_data.get("manual_drawing")),
         "Revision:", _safe(comp_data.get("rev_no"))],
        ["Vat lieu / Material:", _safe(comp_data.get("material")),
         "Tiet dien / Section:", _safe(comp_data.get("section"))],
        ["Length [mm]:", _safe(comp_data.get("length_mm")),
         "Weight [kg]:", _safe(comp_data.get("weight_kg"))],
    ]
    info_table = Table(info_table_data, colWidths=[4.2*cm, 5.5*cm, 4.2*cm, 4.5*cm])
    info_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), DEFAULT_FONT, 9),
        ("FONT", (0, 0), (0, -1), DEFAULT_FONT_BOLD, 9),  # cột label trái
        ("FONT", (2, 0), (2, -1), DEFAULT_FONT_BOLD, 9),  # cột label giữa
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("TEXTCOLOR", (0, 0), (0, -1), SLATE),
        ("TEXTCOLOR", (2, 0), (2, -1), SLATE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
    ]))
    flow.append(info_table)
    flow.append(Spacer(1, 6))

    # ==========================================================
    # INSPECTION RECORDS
    # ==========================================================
    flow.append(Paragraph("2. LICH SU KIEM TRA / Inspection Records", style_section))

    if not inspections:
        flow.append(Paragraph(
            "<i>Chua co inspection nao cho cau kien nay.</i>",
            style_normal,
        ))
    else:
        ins_table_data = [
            ["#", "Loai NT", "Ngay KT", "RFI No.", "Ket qua", "Inspector", "Nguon"],
        ]
        for idx, ins in enumerate(inspections, start=1):
            itype = ins.get("inspection_type", "")
            type_label = {
                "FUR": "Fit-up", "DGRP": "Final",
                "DIR": "Dim", "VIR": "Visual", "NDT": "NDT",
                "TAIR": "Trial", "MB": "Mill", "MTR": "MTR",
            }.get(itype, itype)
            date_show = format_date_vn(ins.get("inspection_date", ""))
            rfi = _safe(ins.get("rfi_no"), "")
            result = _safe(ins.get("result"), "")
            inspector = _safe(ins.get("inspector"), "")
            src = "Master" if ins.get("source_file") == "MASTER" else "Daily"

            ins_table_data.append([
                str(idx), type_label, date_show, rfi[:18],
                result, inspector[:18], src,
            ])

        ins_table = Table(ins_table_data, colWidths=[0.8*cm, 2.0*cm, 2.2*cm, 3.5*cm, 2.0*cm, 3.5*cm, 1.8*cm])
        ins_table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), DEFAULT_FONT, 8.5),
            ("FONT", (0, 0), (-1, 0), DEFAULT_FONT_BOLD, 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BG),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (4, 0), (4, -1), "CENTER"),
            ("ALIGN", (6, 0), (6, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
        ]))
        flow.append(ins_table)

    flow.append(Spacer(1, 8))

    # ==========================================================
    # RESULT BOX
    # ==========================================================
    flow.append(Paragraph("3. KET QUA / Result", style_section))
    status_label, status_color = _status_label_color(status)
    result_table = Table(
        [[Paragraph(
            f'<font color="white" size="13"><b>{status_label}</b></font>',
            style_normal)]],
        colWidths=[18.4*cm],
    )
    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), status_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))
    flow.append(result_table)
    flow.append(Spacer(1, 18))

    # ==========================================================
    # SIGNATURE SECTION
    # ==========================================================
    flow.append(Paragraph("4. XAC NHAN / Signatures", style_section))

    sig_data = [
        ["QC Đại Dũng", "", "Khach hang / Customer"],
        ["", "", ""],
        ["", "", ""],
        ["", "", ""],
        [
            f"_____________________\n{_safe(inspector_signoff, 'Inspector Name')}",
            "",
            f"_____________________\n{_safe(customer_signoff, 'Customer Name')}",
        ],
        [f"Date: {datetime.now().strftime('%d/%m/%Y')}", "",
         f"Date: ____/____/______"],
    ]
    sig_table = Table(sig_data, colWidths=[8*cm, 2.4*cm, 8*cm])
    sig_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), DEFAULT_FONT, 9),
        ("FONT", (0, 0), (0, 0), DEFAULT_FONT_BOLD, 10),
        ("FONT", (2, 0), (2, 0), DEFAULT_FONT_BOLD, 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(sig_table)

    # Footer
    flow.append(Spacer(1, 12))
    footer = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontName=DEFAULT_FONT, fontSize=7, textColor=SLATE, alignment=TA_CENTER,
    )
    flow.append(Paragraph(
        f"Generated by QC Component Manager v2.x · {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        footer,
    ))

    return flow


def generate_certificate(
    db: DB,
    pid: int,
    component_ids: list[int],
    inspector_signoff: str = "",
    customer_signoff: str = "",
) -> bytes:
    """
    Tạo PDF biên bản nghiệm thu cho 1 hoặc nhiều cấu kiện.

    Args:
        db: DB instance.
        pid: project id.
        component_ids: list ID cấu kiện cần xuất.
        inspector_signoff: tên QC ký.
        customer_signoff: tên khách hàng ký (optional).

    Returns:
        Bytes của file PDF.
    """
    project_row = db.conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    project = dict(project_row) if project_row else {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
        title="Bien ban nghiem thu cau kien",
    )

    story = []
    for i, cid in enumerate(component_ids):
        if i > 0:
            story.append(PageBreak())
        story.extend(_build_single_component(
            db, pid, cid, project,
            inspector_signoff=inspector_signoff,
            customer_signoff=customer_signoff,
        ))

    doc.build(story)
    return buffer.getvalue()
