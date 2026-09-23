from __future__ import annotations

from .models import WorkbookData
from .utils import compact

BANK = "농협 입출금거래내역"
SCHOOL_LEDGER = "학교회계 현금출납부"
OUTSIDE_LEDGER = "세입세출외현금 현금출납부"
OUTSIDE_STATEMENT = "세입세출외현금 출납계산서"
UNKNOWN = "확인 필요"


def detect_type(book: WorkbookData) -> str:
    sample_parts: list[str] = []
    for name, rows in book.sheets.items():
        sample_parts.append(name)
        for row in rows[:30]:
            sample_parts.extend(str(v) for v in row if v not in (None, ""))
    sample = compact(" ".join(sample_parts))

    if "현재통화잔액" in sample and "거래일자" in sample and "계좌번호" in sample:
        return BANK
    if "세입세출외현금출납계산서" in sample:
        return OUTSIDE_STATEMENT
    if "수입액(1)" in sample and "지급액(2)" in sample and "잔액(1)-(2)" in sample:
        return OUTSIDE_LEDGER
    if "현금출납부" in sample and "세부사업명" in sample and "원가비목" in sample:
        return SCHOOL_LEDGER
    return UNKNOWN
