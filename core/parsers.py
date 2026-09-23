from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .models import (
    BankStatement,
    LedgerSummary,
    OutsideCashCategory,
    OutsideCashStatement,
    Transaction,
    WorkbookData,
)
from .utils import compact, find_row, money, next_nonempty, parse_datetime, text


def _main_rows(book: WorkbookData) -> list[list[Any]]:
    if not book.sheets:
        return []
    return next(iter(book.sheets.values()))


def _index_by_contains(row: list[Any], term: str) -> int | None:
    target = compact(term)
    for i, value in enumerate(row):
        if target in compact(value):
            return i
    return None


def _value_after_label(rows: list[list[Any]], label: str) -> Any:
    target = compact(label)
    for row in rows[:30]:
        for i, value in enumerate(row):
            if compact(value) == target:
                return next_nonempty(row, i, 8)
    return None


def _find_label_text(rows: list[list[Any]], label: str) -> str:
    target = compact(label)
    for row in rows[:30]:
        for i, value in enumerate(row):
            v = compact(value)
            if target in v:
                # label and value can live in the same cell
                raw = text(value)
                rest = re.sub(re.escape(label), "", raw, count=1).strip(" :")
                if rest:
                    return rest
                nxt = next_nonempty(row, i, 8)
                return text(nxt)
    return ""


def parse_bank_statement(book: WorkbookData) -> BankStatement:
    rows = _main_rows(book)
    account = text(_value_after_label(rows, "계좌번호"))
    holder = text(_value_after_label(rows, "예금주명"))
    account_type = text(_value_after_label(rows, "예금종류"))
    period = text(_value_after_label(rows, "조회기간"))
    current_balance = money(_value_after_label(rows, "현재통화잔액"))

    generated_at = None
    generated_raw = _find_label_text(rows, "현재시간")
    if generated_raw:
        m = re.search(
            r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(\d{1,2})시\s*(\d{1,2})분(?:\s*(\d{1,2})초)?",
            generated_raw,
        )
        if m:
            generated_at = datetime(*[int(x or 0) for x in m.groups()])

    header_hit = find_row(rows, ["거래일자", "출금금액", "입금금액", "거래후잔액", "거래내용"])
    if not header_hit:
        raise ValueError("농협 거래내역의 거래 표 머리글을 찾지 못했습니다.")
    header_idx, header = header_hit
    col_date = _index_by_contains(header, "거래일자")
    col_out = _index_by_contains(header, "출금금액")
    col_in = _index_by_contains(header, "입금금액")
    col_bal = _index_by_contains(header, "거래후잔액")
    col_desc = _index_by_contains(header, "거래내용")
    col_memo = _index_by_contains(header, "거래기록사항")
    col_branch = _index_by_contains(header, "거래점")

    txs: list[Transaction] = []
    for row in rows[header_idx + 1 :]:
        def cell(idx: int | None) -> Any:
            return row[idx] if idx is not None and idx < len(row) else None

        occurred = parse_datetime(cell(col_date))
        if occurred is None:
            continue
        txs.append(
            Transaction(
                occurred_at=occurred,
                withdrawal=money(cell(col_out)),
                deposit=money(cell(col_in)),
                balance=money(cell(col_bal)),
                description=text(cell(col_desc)),
                memo=text(cell(col_memo)),
                branch=text(cell(col_branch)),
            )
        )

    txs.sort(key=lambda x: x.occurred_at or datetime.min, reverse=True)
    closing = txs[0].balance if txs else current_balance
    closing_at = txs[0].occurred_at if txs else None
    return BankStatement(
        filename=book.filename,
        account_number=account,
        account_holder=holder,
        account_type=account_type,
        period=period,
        generated_at=generated_at,
        current_balance=current_balance,
        closing_balance=closing,
        closing_at=closing_at,
        transactions=txs,
    )


def parse_school_ledger(book: WorkbookData) -> LedgerSummary:
    rows = _main_rows(book)
    header_hit = find_row(rows, ["일자", "제목", "수입액", "지출액", "잔액"])
    if not header_hit:
        raise ValueError("학교회계 현금출납부 머리글을 찾지 못했습니다.")
    header_idx, header = header_hit
    ci = _index_by_contains(header, "수입액")
    ce = _index_by_contains(header, "지출액")
    cb = _index_by_contains(header, "잔액")

    total_row = None
    for row in reversed(rows[header_idx + 1 :]):
        labels = [compact(v) for v in row[:3]]
        if "누계" in labels:
            total_row = row
            break
    if total_row is None:
        raise ValueError("학교회계 현금출납부의 누계 행을 찾지 못했습니다.")

    last_date = None
    for row in reversed(rows[header_idx + 1 :]):
        if row:
            last_date = parse_datetime(row[0])
            if last_date:
                break

    return LedgerSummary(
        filename=book.filename,
        kind="school",
        income=money(total_row[ci]) if ci is not None else 0,
        expense=money(total_row[ce]) if ce is not None else 0,
        balance=money(total_row[cb]) if cb is not None else 0,
        as_of=last_date,
        source_format="excel",
    )


def parse_outside_ledger(book: WorkbookData) -> LedgerSummary:
    rows = _main_rows(book)
    header_hit = find_row(rows, ["종목", "수입액(1)", "지급액(2)", "잔액(1)-(2)"])
    if not header_hit:
        raise ValueError("세입세출외현금 현금출납부 머리글을 찾지 못했습니다.")
    header_idx, header = header_hit
    ci = _index_by_contains(header, "수입액(1)")
    ce = _index_by_contains(header, "지급액(2)")
    cb = _index_by_contains(header, "잔액(1)-(2)")

    total_row = None
    for row in reversed(rows[header_idx + 1 :]):
        joined = "".join(compact(v) for v in row[:4])
        if "총누계" in joined:
            total_row = row
            break
    if total_row is None:
        raise ValueError("세입세출외현금 현금출납부의 총누계 행을 찾지 못했습니다.")

    last_date = None
    for row in reversed(rows[header_idx + 1 :]):
        if row:
            last_date = parse_datetime(row[0])
            if last_date:
                break

    return LedgerSummary(
        filename=book.filename,
        kind="outside",
        income=money(total_row[ci]) if ci is not None else 0,
        expense=money(total_row[ce]) if ce is not None else 0,
        balance=money(total_row[cb]) if cb is not None else 0,
        as_of=last_date,
        source_format="excel",
    )


def _outside_group(name: str) -> str:
    n = compact(name)
    if any(k in n for k in ("계약보증", "하자보증", "입찰보증", "보증금", "기타보관금")):
        return "계약보증금 및 기타보관금"
    return "4대보험 및 기타세금"


def parse_outside_statement(book: WorkbookData) -> OutsideCashStatement:
    rows = _main_rows(book)
    header_hit = find_row(rows, ["세외종목", "반환금액", "잔액"])
    if not header_hit:
        raise ValueError("세입세출외현금 출납계산서 머리글을 찾지 못했습니다.")
    header_idx, header = header_hit
    cat_idx = _index_by_contains(header, "세외종목")
    bal_idx = _index_by_contains(header, "잔액")

    categories: list[OutsideCashCategory] = []
    total_balance = 0
    for row in rows[header_idx + 1 :]:
        cat = text(row[cat_idx]) if cat_idx is not None and cat_idx < len(row) else ""
        extra = text(row[cat_idx + 1]) if cat_idx is not None and cat_idx + 1 < len(row) else ""
        name = f"{cat} {extra}".strip()
        bal = money(row[bal_idx]) if bal_idx is not None and bal_idx < len(row) else 0
        normalized = compact(name)
        if "합계" in normalized:
            total_balance = bal
            break
        if cat and bal_idx is not None:
            categories.append(OutsideCashCategory(name=name, balance=bal, group=_outside_group(name)))

    as_of = None
    for row in rows[:12]:
        for value in row:
            dt = parse_datetime(value)
            if dt:
                as_of = dt
    if total_balance == 0 and categories:
        total_balance = sum(x.balance for x in categories)

    return OutsideCashStatement(
        filename=book.filename,
        total_balance=total_balance,
        categories=categories,
        as_of=as_of,
        source_format="excel",
    )
