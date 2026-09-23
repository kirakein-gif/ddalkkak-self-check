from __future__ import annotations

from io import BytesIO
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

from core.models import ReportSettings
from core.reconcile import Reconciliation
from .pdf_utils import FONT, register_korean_font, styles


def _weekday_ko(d: date | None) -> str:
    if not d:
        return ""
    return "월화수목금토일"[d.weekday()]


def _date_text(d: date | None, weekday: bool = False) -> str:
    if not d:
        return ""
    base = f"{d.year}. {d.month}. {d.day}."
    return f"{base}({_weekday_ko(d)})" if weekday else base


def _p(text: str, style):
    # ReportLab XML escapes are only needed for free text with &, <, >.
    text = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text.replace("\n", "<br/>"), style)


def build_internal_check_pdf(rec: Reconciliation, settings: ReportSettings) -> bytes:
    register_korean_font()
    st = styles()
    bio = BytesIO()
    doc = SimpleDocTemplate(
        bio, pagesize=A4,
        leftMargin=8*mm, rightMargin=8*mm, topMargin=9*mm, bottomMargin=9*mm,
        title="자율적 내부점검표",
    )
    story = []
    ref = rec.reference_date.date() if rec.reference_date else settings.check_date

    story.append(_p("매월 둘째 주 금요일은 내부통제의 날!", st["subtitle"]))
    story.append(Spacer(1, 2*mm))
    title_style = st["title"]
    story.append(_p("자 율 적  내 부 점 검 표", title_style))
    story.append(Spacer(1, 3*mm))

    target = f"- 점검대상 : {ref.year}년 {ref.month}월"
    checked = f"점검일자 : {settings.check_date.year}-{settings.check_date.month}-{settings.check_date.day}"
    top = Table([[ _p(target, st["body"]), _p(checked, st["body"]) ]], colWidths=[95*mm, 85*mm])
    top.setStyle(TableStyle([("ALIGN",(1,0),(1,0),"RIGHT"), ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(top)
    story.append(Spacer(1, 2*mm))

    manager_pair = "\n".join(x for x in [settings.inspector_name, settings.co_manager_name] if x)
    system_note = f"{settings.system_check_count}건" if settings.system_check_count else ""
    promo_note = ""
    if settings.promotion_count:
        promo_note = f"{settings.promotion_count}건"
        if settings.promotion_public_date:
            promo_note += f"\n({_date_text(settings.promotion_public_date)})"
    binder_note = f"총 {settings.evidence_binders}권" if settings.evidence_binders else ""
    cash_result = "○" if rec.cashbook_ok else "×"
    card_result = "○" if rec.card_ok else "×"

    area1 = "투\n명\n하\n고\n공\n정\n한\n회\n계\n집\n행\n상\n황\n점\n검"
    rows = [
        ["영 역", "항    목", "결과\n(○,×)", "업 무\n담당자", "비 고\n(특이사항)"],
        [area1, "에듀파인/클린재정시스템을 월 1회 점검하였는가?", "", manager_pair, system_note],
        ["", "현금출납부와 통장잔액은 일치하는가?", cash_result, manager_pair, ""],
        ["", "업무추진비는 규정에 맞게 집행하였으며 내역을 홈페이지 등을 통해 공개하였는가?", "", settings.inspector_name, promo_note],
        ["", "공사, 물품, 용역 등 계약 시 추정가격별 계약방법을 준수하였는가?", "", settings.inspector_name, ""],
        ["", "증빙서는 편철 하였는가?(익월 15일이내)", "", settings.inspector_name, binder_note],
        ["", "신용카드대금 결제 후 통장잔액이 0원인지 확인하였는가?", card_result, settings.inspector_name, ""],
        ["업 무\n연 찬\n\n(감사지적\n사례 공유\n등)",
         f"감사사례 공유 등 업무 연찬을 하였는가?\n\n- 일 자 : {_date_text(settings.training_date, True)}\n- 교육대상 : {settings.training_target}\n- 주요내용 : {settings.training_content}",
         "", settings.inspector_name, ""],
    ]

    formatted = []
    for r, row in enumerate(rows):
        formatted.append([_p(str(v), st["body_center"] if c != 1 else st["body"]) for c, v in enumerate(row)])

    table = Table(formatted, colWidths=[18*mm, 105*mm, 18*mm, 22*mm, 27*mm], rowHeights=[13*mm, 21*mm, 21*mm, 26*mm, 24*mm, 21*mm, 22*mm, 42*mm])
    commands = [
        ("FONTNAME", (0,0), (-1,-1), FONT),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), 0.8, colors.black),
        ("BOX", (0,0), (-1,-1), 1.0, colors.black),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F2F2")),
        ("SPAN", (0,1), (0,6)),
    ]
    table.setStyle(TableStyle(commands))
    story.append(table)
    story.append(Spacer(1, 7*mm))
    story.append(_p(_date_text(settings.check_date), st["subtitle"]))
    story.append(Spacer(1, 9*mm))

    sign = Table([
        [f"점검자  직  {settings.inspector_title}", f"성명  {settings.inspector_name}", "(서명)"],
        [f"확인자  직  {settings.confirmer_title}", f"성명  {settings.confirmer_name}", "(서명)"],
    ], colWidths=[70*mm, 60*mm, 28*mm], rowHeights=[12*mm, 12*mm])
    sign.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), FONT),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(sign)

    doc.build(story)
    return bio.getvalue()
