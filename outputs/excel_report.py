from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from core.reconcile import Reconciliation


def _won(value: int | None) -> int | None:
    return value


def build_reconciliation_xlsx(rec: Reconciliation) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "잔액대조"

    title_fill = PatternFill("solid", fgColor="2563EB")
    header_fill = PatternFill("solid", fgColor="EAF2FF")
    ok_fill = PatternFill("solid", fgColor="EAF7EF")
    bad_fill = PatternFill("solid", fgColor="FDECEC")
    thin = Side(style="thin", color="D1D5DB")

    ws["A1"] = "자율적 내부점검 - 통장잔액 대조 결과"
    ws["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    ws["A1"].fill = title_fill
    ws.merge_cells("A1:F1")
    ws["A1"].alignment = Alignment(horizontal="left")

    headers = ["구분", "장부잔액", "통장잔액", "차이", "결과", "비고"]
    for c, value in enumerate(headers, 1):
        cell = ws.cell(3, c, value)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = Border(bottom=thin)

    for r, check in enumerate(rec.checks, 4):
        values = [
            check.item,
            _won(check.ledger),
            _won(check.bank),
            _won(check.difference),
            "일치" if check.ok else "확인 필요",
            check.note,
        ]
        for c, value in enumerate(values, 1):
            ws.cell(r, c, value)
        ws.cell(r, 5).fill = ok_fill if check.ok else bad_fill

    for col in ("B", "C", "D"):
        for cell in ws[col][3:]:
            cell.number_format = '#,##0"원"'

    row = max(7, 4 + len(rec.checks) + 2)
    ws.cell(row, 1, "법인카드 대금결제 확인").font = Font(bold=True, size=12)
    card_headers = ["결제일", "결제액", "결제후 잔액", "결과", "원본파일"]
    for c, value in enumerate(card_headers, 1):
        cell = ws.cell(row + 1, c, value)
        cell.font = Font(bold=True)
        cell.fill = header_fill
    for i, card in enumerate(rec.card_checks, row + 2):
        ws.cell(i, 1, card.date)
        ws.cell(i, 2, card.payment).number_format = '#,##0"원"'
        ws.cell(i, 3, card.balance_after).number_format = '#,##0"원"'
        ws.cell(i, 4, "정상" if card.ok else "확인 필요")
        ws.cell(i, 4).fill = ok_fill if card.ok else bad_fill
        ws.cell(i, 5, card.source)

    widths = {"A": 22, "B": 18, "C": 18, "D": 16, "E": 16, "F": 30}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A4"

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
