from __future__ import annotations

from .models import WorkbookData
from .utils import compact

BANK = "농협 입출금거래내역"
SCHOOL_LEDGER = "학교회계 현금출납부"
OUTSIDE_LEDGER = "세입세출외현금 현금출납부"
OUTSIDE_STATEMENT = "세입세출외현금 출납계산서"
UNKNOWN = "확인 필요"


def _sample_text(book: WorkbookData) -> str:
    parts: list[str] = []
    for name, rows in book.sheets.items():
        parts.append(name)
        for row in rows[:40]:
            parts.extend(str(v) for v in row if v not in (None, ""))
    return compact(" ".join(parts))


def _count_markers(sample: str, markers: tuple[str, ...]) -> int:
    return sum(1 for marker in markers if compact(marker) in sample)


def detect_type(book: WorkbookData) -> str:
    """파일명이나 금액 규모가 아니라 문서 내부 구조로 자료 종류를 판별한다."""
    sample = _sample_text(book)

    bank_markers = ("계좌번호", "조회기간", "거래일자", "거래후잔액", "거래내용")
    statement_markers = (
        "전년도이월금액(1)",
        "현년도수납금액(2)",
        "세외종목",
        "반환금액(3)",
        "잔액(1+2-3)",
    )
    outside_markers = (
        "종목",
        "채권자",
        "수입액(1)",
        "지급액(2)",
        "잔액(1)-(2)",
        "결의번호",
    )
    school_markers = (
        "세부사업명",
        "세부항목명",
        "원가비목",
        "미결재금액",
        "납입금명",
    )

    if _count_markers(sample, bank_markers) >= 4:
        return BANK

    if (
        "세입세출외현금출납계산서" in sample
        or _count_markers(sample, statement_markers) >= 4
    ):
        return OUTSIDE_STATEMENT

    if _count_markers(sample, outside_markers) >= 5:
        return OUTSIDE_LEDGER

    # 학교회계/세외 모두 시트명이 '현금출납부'일 수 있으므로
    # 시트명 대신 학교회계 고유 열 이름을 사용한다.
    if (
        _count_markers(sample, school_markers) >= 2
        and "수입액" in sample
        and "지출액" in sample
        and "잔액" in sample
    ):
        return SCHOOL_LEDGER

    return UNKNOWN
