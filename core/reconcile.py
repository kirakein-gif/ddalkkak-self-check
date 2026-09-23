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
    def cashbook_ok(self) -> bool:
        return len(self.checks) >= 2 and all(x.ok for x in self.checks)

    @property
    def card_ok(self) -> bool:
        return bool(self.card_checks) and all(x.ok for x in self.card_checks)

    @property
    def all_ok(self) -> bool:
        return self.cashbook_ok and self.card_ok


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
    return max(dates) if dates else None


def balance_at_or_before(bank: BankStatement | None, target: datetime | None) -> int | None:
    if bank is None:
        return None
    if target is None:
        return bank.closing_balance
    cutoff = target.replace(hour=23, minute=59, second=59)
    eligible = [tx for tx in bank.transactions if tx.occurred_at is not None and tx.occurred_at <= cutoff]
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
    result = Reconciliation(reference_date=_reference_date(school, outside, outside_statement))

    non_card: list[BankStatement] = []
    for bank in banks:
        if bank.is_card_account:
            result.card_banks.append(bank)
        else:
            non_card.append(bank)

    unmatched = list(non_card)

    # 1) 정확 일치 매칭: 금액 규모 추정은 하지 않는다.
    if school:
        for bank in list(unmatched):
            bal = balance_at_or_before(bank, result.reference_date)
            if bal is not None and bal + fixed_deposit == school.balance:
                result.school_bank = bank
                unmatched.remove(bank)
                break

    if outside:
        for bank in list(unmatched):
            bal = balance_at_or_before(bank, result.reference_date)
            if bal is not None and bal == outside.balance:
                result.outside_bank = bank
                unmatched.remove(bank)
                break

    if result.outside_bank is None and outside_statement:
        for bank in list(unmatched):
            bal = balance_at_or_before(bank, result.reference_date)
            if bal is not None and bal == outside_statement.total_balance:
                result.outside_bank = bank
                unmatched.remove(bank)
                break

    # If exactly one of the two non-card accounts matched, the one remaining account
    # can be assigned by elimination. This is not a money-size guess and allows
    # school-account fixed deposits to be entered after upload.
    if result.school_bank is None and result.outside_bank is not None and len(unmatched) == 1:
        result.school_bank = unmatched.pop(0)
    elif result.outside_bank is None and result.school_bank is not None and len(unmatched) == 1:
        result.outside_bank = unmatched.pop(0)

    result.unknown_banks.extend(unmatched)

    if school:
        base = balance_at_or_before(result.school_bank, result.reference_date)
        bank_total = None if base is None else base + fixed_deposit
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
        bank_total = balance_at_or_before(result.outside_bank, result.reference_date)
        diff = None if bank_total is None else outside.balance - bank_total
        ok = diff == 0
        statement_note = ""
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
