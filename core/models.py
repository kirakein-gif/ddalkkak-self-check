from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
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
    account_holder: str = ""
    account_type: str = ""
    period: str = ""
    generated_at: datetime | None = None
    current_balance: int | None = None
    closing_balance: int | None = None
    closing_at: datetime | None = None
    transactions: list[Transaction] = field(default_factory=list)

    @property
    def is_card_account(self) -> bool:
        for tx in self.transactions:
            joined = f"{tx.description} {tx.memo}".replace(" ", "").upper()
            if "NH비씨대금" in joined or "NHBC기업카드" in joined or "비씨대금" in joined:
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
    source_format: str = "excel"


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
    source_format: str = "excel"


@dataclass
class FileResult:
    filename: str
    detected_type: str
    detail: str = ""
    error: str = ""
    source_format: str = "excel"
    preferred: bool = True


@dataclass
class ReportSettings:
    check_date: date
    inspector_title: str = ""
    inspector_name: str = ""
    confirmer_title: str = ""
    confirmer_name: str = ""
    co_manager_name: str = ""
    system_check_count: str = ""
    promotion_count: str = ""
    promotion_public_date: date | None = None
    evidence_binders: str = ""
    training_date: date | None = None
    training_target: str = "전교직원"
    training_content: str = "감사지적 사례 공유"
