from __future__ import annotations

from datetime import datetime
import calendar
from io import BytesIO
import re

import fitz

from .detector import OUTSIDE_LEDGER, OUTSIDE_STATEMENT, SCHOOL_LEDGER, UNKNOWN, detect_pdf_text
from .models import LedgerSummary, OutsideCashCategory, OutsideCashStatement
from .parsers import _outside_group
from .utils import money, parse_datetime


def extract_pdf_text(data: bytes) -> str:
    with fitz.open(stream=data, filetype="pdf") as doc:
        return "\n".join(page.get_text("text") for page in doc)


def detect_pdf_type(data: bytes) -> str:
    return detect_pdf_text(extract_pdf_text(data))


def _transaction_end_date(text: str) -> datetime | None:
    # Prefer the accounting period / transaction dates, not the PDF print date.
    m = re.search(r"기간\s*[:：]?\s*(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\s*~\s*(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if m:
        y, mo, d = map(int, m.groups()[3:])
        return datetime(y, mo, d)
    m = re.search(r"기간\s*[:：]?\s*(20\d{2})년\s*(\d{1,2})월\s*~\s*(20\d{2})년\s*(\d{1,2})월", text)
    if m:
        y, mo = int(m.group(3)), int(m.group(4))
        return datetime(y, mo, calendar.monthrange(y, mo)[1])
    # Fallback to the latest actual transaction-like YYYY-MM-DD before footer print dates.
    candidates = re.findall(r"(20\d{2}-\d{2}-\d{2})", text)
    parsed = [parse_datetime(x) for x in candidates]
    parsed = [x for x in parsed if x]
    return min(parsed) if len(set(x.date() for x in parsed)) == 1 and parsed else (max(parsed) if parsed else None)


def _statement_date(text: str) -> datetime | None:
    m = re.search(r"일자\s*[:：]\s*(20\d{2}-\d{1,2}-\d{1,2})", text)
    return parse_datetime(m.group(1)) if m else _transaction_end_date(text)


def _table_rows(page) -> list[list[str | None]]:
    try:
        found = page.find_tables()
    except Exception:
        return []
    rows: list[list[str | None]] = []
    for table in found.tables:
        rows.extend(table.extract())
    return rows


def parse_school_ledger_pdf(data: bytes, filename: str) -> LedgerSummary:
    with fitz.open(stream=data, filetype="pdf") as doc:
        text = "\n".join(page.get_text("text") for page in doc)
        income = expense = balance = None
        for page in reversed(doc):
            for row in reversed(_table_rows(page)):
                joined = " ".join((x or "").replace("\n", " ") for x in row)
                if re.search(r"(^|\s)누\s*계(\s|$)", joined):
                    nums = re.findall(r"-?[\d,]+", joined)
                    if len(nums) >= 3:
                        income, expense, balance = map(money, nums[-3:])
                        break
            if balance is not None:
                break
        if balance is None:
            m = re.search(r"누\s*계\s+([\d,]+)\s+([\d,]+)\s+(-?[\d,]+)", text)
            if not m:
                raise ValueError("학교회계 PDF에서 누계 금액을 찾지 못했습니다.")
            income, expense, balance = map(money, m.groups())
        return LedgerSummary(
            filename=filename,
            kind="school",
            income=int(income or 0),
            expense=int(expense or 0),
            balance=int(balance or 0),
            as_of=_transaction_end_date(text),
            source_format="pdf",
        )


def parse_outside_ledger_pdf(data: bytes, filename: str) -> LedgerSummary:
    with fitz.open(stream=data, filetype="pdf") as doc:
        text = "\n".join(page.get_text("text") for page in doc)
        income = expense = balance = None
        for row in _table_rows(doc[0]):
            joined = " ".join((x or "").replace("\n", " ") for x in row)
            if "총" in joined and "누" in joined and "계" in joined:
                nums = re.findall(r"-?[\d,]+", joined)
                if len(nums) >= 3:
                    income, expense, balance = map(money, nums[-3:])
        if balance is None:
            m = re.search(r"총\s*누\s*계\s+([\d,]+)\s+([\d,]+)\s+(-?[\d,]+)", text)
            if not m:
                raise ValueError("세입세출외현금 PDF에서 총 누계 금액을 찾지 못했습니다.")
            income, expense, balance = map(money, m.groups())
        return LedgerSummary(
            filename=filename,
            kind="outside",
            income=int(income or 0),
            expense=int(expense or 0),
            balance=int(balance or 0),
            as_of=_transaction_end_date(text),
            source_format="pdf",
        )


def parse_outside_statement_pdf(data: bytes, filename: str) -> OutsideCashStatement:
    with fitz.open(stream=data, filetype="pdf") as doc:
        text = "\n".join(page.get_text("text") for page in doc)
        categories: list[OutsideCashCategory] = []
        total_balance = 0
        tables = doc[0].find_tables().tables
        if not tables:
            raise ValueError("출납계산서 PDF의 표를 찾지 못했습니다.")
        rows = max(tables, key=lambda t: len(t.extract())).extract()
        for row in rows[2:]:
            if not row:
                continue
            joined = " ".join((x or "").replace("\n", " ") for x in row)
            if "합" in joined and "계" in joined:
                numeric = [money(x) for x in row if x not in (None, "") and re.search(r"\d", str(x))]
                if numeric:
                    total_balance = numeric[-1]
                continue
            # table shape: [이월, 수납, 계, 종목1, 종목2, 반환, 잔액, 비고]
            if len(row) >= 7:
                name = " ".join(x.strip() for x in (row[3], row[4] if len(row) > 4 else "") if x).strip()
                bal = money(row[6])
                if name:
                    categories.append(OutsideCashCategory(name=name, balance=bal, group=_outside_group(name)))
        if total_balance == 0:
            m = re.search(r"합\s*계[^\n]*?([\d,]+)\s*$", text, re.MULTILINE)
            if m:
                total_balance = money(m.group(1))
        if total_balance == 0 and categories:
            total_balance = sum(x.balance for x in categories)
        return OutsideCashStatement(
            filename=filename,
            total_balance=total_balance,
            categories=categories,
            as_of=_statement_date(text),
            source_format="pdf",
        )


def parse_kedufine_pdf(data: bytes, filename: str):
    kind = detect_pdf_type(data)
    if kind == SCHOOL_LEDGER:
        return kind, parse_school_ledger_pdf(data, filename)
    if kind == OUTSIDE_LEDGER:
        return kind, parse_outside_ledger_pdf(data, filename)
    if kind == OUTSIDE_STATEMENT:
        return kind, parse_outside_statement_pdf(data, filename)
    return UNKNOWN, None
