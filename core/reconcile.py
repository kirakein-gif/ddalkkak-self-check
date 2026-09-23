from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import BankStatement, LedgerSummary, OutsideCashStatement


@dataclass
class CheckLine:
    item: str
    ledger: int | None
    bank: int | None
    difference: int | None
    ok: bool
    note: str = ""


@dataclass
class CardCheck:
    date: str
    payment: int
    balance_after: int
    ok: bool
    source: str


@dataclass
class Reconciliation:
    school_bank: BankStatement | None = None
    outside_bank: BankStatement | None = None
    card_banks: list[BankStatement] = field(default_factory=list)
    unknown_banks: list[BankStatement] = field(default_factory=list)
    checks: list[CheckLine] = field(default_factory=list)
    card_checks: list[CardCheck] = field(default_factory=list)
    reference_date: datetime | None = None

    @property
    def all_ok(self) -> bool:
        required = len(self.checks) >= 2
        return required and all(x.ok for x in self.checks) and all(x.ok for x in self.card_checks)


def _reference_date(
    school: LedgerSummary | None,
    outside: LedgerSummary | None,
    outside_statement: OutsideCashStatement | None,
) -> datetime | None:
    dates = [
        value
        for value in (
            school.as_of if school else None,
            outside.as_of if outside else None,
            outside_statement.as_of if outside_statement else None,
        )
        if value is not None
    ]
    if not dates:
        return None
    return max(dates)


def _balance_at_or_before(bank: BankStatement, target: datetime | None) -> int | None:
    """현재통화잔액이 아니라 점검 기준일의 마지막 거래후잔액을 사용한다."""
    if target is None:
        return bank.closing_balance

    eligible = [
        tx
        for tx in bank.transactions
        if tx.occurred_at is not None and tx.occurred_at <= target.replace(hour=23, minute=59, second=59)
    ]
    if not eligible:
        return None

    latest = max(eligible, key=lambda tx: tx.occurred_at or datetime.min)
    return latest.balance


def reconcile(
    banks: list[BankStatement],
    school: LedgerSummary | None,
    outside: LedgerSummary | None,
    outside_statement: OutsideCashStatement | None,
    fixed_deposit: int = 0,
) -> Reconciliation:
    result = Reconciliation()
    result.reference_date = _reference_date(school, outside, outside_statement)

    non_card: list[BankStatement] = []
    for bank in banks:
        if bank.is_card_account:
            result.card_banks.append(bank)
        else:
            non_card.append(bank)

    bank_balances: dict[str, int | None] = {
        bank.filename: _balance_at_or_before(bank, result.reference_date)
        for bank in non_card
    }

    for bank in non_card:
        bal = bank_balances[bank.filename]

        # 금액 "규모"로 유형을 추정하지 않는다.
        # 장부의 기준일 잔액과 정확히 일치하는 통장을 매칭한다.
        if (
            school
            and bal is not None
            and bal + fixed_deposit == school.balance
            and result.school_bank is None
        ):
            result.school_bank = bank
        elif (
            outside
            and bal is not None
            and bal == outside.balance
            and result.outside_bank is None
        ):
            result.outside_bank = bank
        elif (
            outside_statement
            and bal is not None
            and bal == outside_statement.total_balance
            and result.outside_bank is None
        ):
            result.outside_bank = bank
        else:
            result.unknown_banks.append(bank)

    if school:
        bank_balance = (
            _balance_at_or_before(result.school_bank, result.reference_date)
            if result.school_bank
            else None
        )
        bank_total = None if bank_balance is None else bank_balance + fixed_deposit
        diff = None if bank_total is None else school.balance - bank_total
        result.checks.append(
            CheckLine(
                item="학교회계",
                ledger=school.balance,
                bank=bank_total,
                difference=diff,
                ok=(diff == 0),
                note=(
                    f"기준일 거래후잔액 + 정기예금 {fixed_deposit:,}원"
                    if fixed_deposit
                    else "기준일 마지막 거래후잔액"
                ),
            )
        )

    if outside:
        bank_total = (
            _balance_at_or_before(result.outside_bank, result.reference_date)
            if result.outside_bank
            else None
        )
        diff = None if bank_total is None else outside.balance - bank_total
        statement_note = ""
        ok = diff == 0
        if outside_statement:
            statement_diff = outside.balance - outside_statement.total_balance
            ok = ok and statement_diff == 0
            statement_note = f"출납계산서 차이 {statement_diff:,}원"
        result.checks.append(
            CheckLine(
                item="세입세출외현금",
                ledger=outside.balance,
                bank=bank_total,
                difference=diff,
                ok=ok,
                note=statement_note or "기준일 마지막 거래후잔액",
            )
        )

    seen: set[tuple[str, int, str]] = set()
    for bank in result.card_banks:
        for tx in bank.transactions:
            if tx.occurred_at is None:
                continue

            # 월 전체 법인카드 파일 1개를 넣어도 기준월의 결제 건만 사용한다.
            if result.reference_date and (
                tx.occurred_at.year != result.reference_date.year
                or tx.occurred_at.month != result.reference_date.month
            ):
                continue

            joined = f"{tx.description} {tx.memo}".replace(" ", "").upper()
            if not ("비씨대금" in joined or "NHBC기업카드" in joined):
                continue

            d = tx.occurred_at.strftime("%Y-%m-%d")
            key = (d, tx.withdrawal, bank.filename)
            if key in seen:
                continue
            seen.add(key)
            result.card_checks.append(
                CardCheck(
                    date=d,
                    payment=tx.withdrawal,
                    balance_after=tx.balance,
                    ok=(tx.withdrawal > 0 and tx.balance == 0),
                    source=bank.filename,
                )
            )

    result.card_checks.sort(key=lambda x: x.date)
    return result
