from __future__ import annotations

from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from core.models import BankStatement, Transaction
from core.reconcile import Reconciliation, balance_at_or_before
from .pdf_utils import FONT, register_korean_font, styles


BLUE = colors.HexColor("#168BC4")
LIGHT = colors.HexColor("#F5F8FB")


def _p(text: str, style):
    text = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text.replace("\n", "<br/>"), style)


def _money(v: int | None) -> str:
    return "" if v is None else f"{v:,}원"


def _day_transactions(bank: BankStatement, day: datetime) -> list[Transaction]:
    rows = [tx for tx in bank.transactions if tx.occurred_at and tx.occurred_at.date() == day.date()]
    return sorted(rows, key=lambda x: x.occurred_at or datetime.min, reverse=True)


def _bank_page(story, role: str, bank: BankStatement, day: datetime, txs: list[Transaction], page_no: int, total_pages: int):
    st = styles()
    ref_bal = None
    if txs:
        ref_bal = max(txs, key=lambda x: x.occurred_at or datetime.min).balance

    title_tbl = Table([
        [_p(f"입출금거래내역({role})", st["title"]), _p("NH Bank", st["title"])],
    ], colWidths=[190*mm, 70*mm])
    title_tbl.setStyle(TableStyle([
        ("ALIGN", (0,0), (0,0), "LEFT"), ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("TEXTCOLOR", (1,0), (1,0), BLUE), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(title_tbl)
    line = Table([[""]], colWidths=[260*mm], rowHeights=[1.2*mm])
    line.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),BLUE)]))
    story.append(line)
    story.append(Spacer(1, 4*mm))

    generated = bank.generated_at.strftime("%Y년 %m월 %d일 %H시 %M분 %S초") if bank.generated_at else ""
    meta = [
        ["계좌번호", bank.account_number, "예금종류", bank.account_type],
        ["예금주명", bank.account_holder, "", ""],
        ["조회기간", bank.period, "현재시간", generated],
        ["현재통화잔액", _money(bank.current_balance), "점검기준일 잔액", _money(ref_bal)],
    ]
    mt = Table(meta, colWidths=[32*mm, 88*mm, 36*mm, 104*mm], rowHeights=[9*mm]*4)
    mt.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),FONT), ("FONTSIZE",(0,0),(-1,-1),8.5),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#AAB3BB")),
        ("BACKGROUND",(0,0),(0,-1),LIGHT), ("BACKGROUND",(2,0),(2,-1),LIGHT),
        ("ALIGN",(0,0),(0,-1),"CENTER"), ("ALIGN",(2,0),(2,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(mt)
    story.append(Spacer(1, 4*mm))

    story.append(_p(f"전체  (기준일: {day:%Y-%m-%d})", st["body"]))
    headers = ["구분", "거래일자", "출금금액", "입금금액", "거래후잔액", "거래내용", "거래기록사항", "거래점"]
    data = [headers]
    for i, tx in enumerate(txs, 1):
        data.append([
            str(i),
            tx.occurred_at.strftime("%Y/%m/%d\n%H:%M:%S") if tx.occurred_at else "",
            _money(tx.withdrawal) if tx.withdrawal else "",
            _money(tx.deposit) if tx.deposit else "",
            _money(tx.balance),
            tx.description,
            tx.memo,
            tx.branch,
        ])
    if len(data) == 1:
        data.append(["-", day.strftime("%Y/%m/%d"), "", "", _money(ref_bal), "거래 없음", "", ""])

    widths = [12*mm, 30*mm, 31*mm, 31*mm, 34*mm, 28*mm, 45*mm, 28*mm]
    tb = Table([[ _p(str(v), st["small_center"]) for v in row ] for row in data], colWidths=widths, repeatRows=1)
    tb.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),FONT), ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("GRID",(0,0),(-1,-1),0.45,colors.HexColor("#B4B9BF")),
        ("BACKGROUND",(0,0),(-1,0),LIGHT),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(tb)
    story.append(Spacer(1, 3*mm))
    story.append(_p("※ 농협 원본 거래내역을 자율적 내부점검용으로 자동 정리한 자료입니다.", st["small"]))
    story.append(_p(f"{page_no}/{total_pages}", st["small_center"]))


def build_bank_copy_pdf(rec: Reconciliation) -> bytes:
    register_korean_font()
    bio = BytesIO()
    doc = SimpleDocTemplate(
        bio, pagesize=landscape(A4),
        leftMargin=10*mm, rightMargin=10*mm, topMargin=9*mm, bottomMargin=8*mm,
        title="통장잔액 정리본",
    )
    pages: list[tuple[str, BankStatement, datetime, list[Transaction]]] = []
    ref = rec.reference_date
    if ref and rec.school_bank:
        pages.append(("학교회계", rec.school_bank, ref, _day_transactions(rec.school_bank, ref)))
    if ref and rec.outside_bank:
        pages.append(("세입세출외현금", rec.outside_bank, ref, _day_transactions(rec.outside_bank, ref)))

    # One page per corporate-card payment day. Monthly file and split-day files are both supported.
    for card in rec.card_checks:
        day = datetime.strptime(card.date, "%Y-%m-%d")
        source = next((b for b in rec.card_banks if b.filename == card.source), None)
        if source:
            pages.append((f"법인카드({day.day}일분)", source, day, _day_transactions(source, day)))

    story = []
    total = len(pages)
    for idx, (role, bank, day, txs) in enumerate(pages, 1):
        _bank_page(story, role, bank, day, txs, idx, total)
        if idx != total:
            story.append(PageBreak())
    doc.build(story)
    return bio.getvalue()
