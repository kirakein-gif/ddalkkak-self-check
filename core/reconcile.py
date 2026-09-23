from __future__ import annotations

from dataclasses import dataclass, field

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

    @property
    def all_ok(self) -> bool:
        required = len(self.checks) >= 2
        return required and all(x.ok for x in self.checks) and all(x.ok for x in self.card_checks)


def reconcile(
    banks: list[BankStatement],
    school: LedgerSummary | None,
    outside: LedgerSummary | None,
    outside_statement: OutsideCashStatement | None,
    fixed_deposit: int = 0,
) -> Reconciliation:
    result = Reconciliation()

    non_card: list[BankStatement] = []
    for bank in banks:
        if bank.is_card_account:
            result.card_banks.append(bank)
        else:
            non_card.append(bank)

    for bank in non_card:
        bal = bank.closing_balance
        if school and bal == school.balance and result.school_bank is None:
            result.school_bank = bank
        elif outside and bal == outside.balance and result.outside_bank is None:
            result.outside_bank = bank
        elif outside_statement and bal == outside_statement.total_balance and result.outside_bank is None:
            result.outside_bank = bank
        else:
            result.unknown_banks.append(bank)

    if school:
        bank_total = None
        if result.school_bank and result.school_bank.closing_balance is not None:
            bank_total = result.school_bank.closing_balance + fixed_deposit
        diff = None if bank_total is None else school.balance - bank_total
        result.checks.append(
            CheckLine(
                item="학교회계",
                ledger=school.balance,
                bank=bank_total,
                difference=diff,
                ok=(diff == 0),
                note="통장잔액 + 정기예금" if fixed_deposit else "통장잔액",
            )
        )

    if outside:
        bank_total = result.outside_bank.closing_balance if result.outside_bank else None
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
                note=statement_note,
            )
        )

    seen: set[tuple[str, int, str]] = set()
    for bank in result.card_banks:
        for tx in bank.transactions:
            joined = f"{tx.description} {tx.memo}".replace(" ", "").upper()
            if not ("비씨대금" in joined or "NHBC기업카드" in joined):
                continue
            d = tx.occurred_at.strftime("%Y-%m-%d") if tx.occurred_at else ""
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
