from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WorkbookData:
    filename: str
    sheets: dict[str, list[list[Any]]]


@dataclass
class Transaction:
    occurred_at: datetime | None
    withdrawal: int = 0
    deposit: int = 0
    balance: int = 0
    description: str = ""
    memo: str = ""
    branch: str = ""


@dataclass
class BankStatement:
    filename: str
    account_number: str = ""
    period: str = ""
    current_balance: int | None = None
    closing_balance: int | None = None
    closing_at: datetime | None = None
    transactions: list[Transaction] = field(default_factory=list)

    @property
    def is_card_account(self) -> bool:
        for tx in self.transactions:
            text = f"{tx.description} {tx.memo}".replace(" ", "").upper()
            if "NH비씨대금" in text or "NHBC기업카드" in text or "비씨대금" in text:
                return True
        return False


@dataclass
class LedgerSummary:
    filename: str
    kind: str
    income: int
    expense: int
    balance: int
    as_of: datetime | None = None


@dataclass
class OutsideCashCategory:
    name: str
    balance: int
    group: str


@dataclass
class OutsideCashStatement:
    filename: str
    total_balance: int
    categories: list[OutsideCashCategory] = field(default_factory=list)
    as_of: datetime | None = None


@dataclass
class FileResult:
    filename: str
    detected_type: str
    detail: str = ""
    error: str = ""
