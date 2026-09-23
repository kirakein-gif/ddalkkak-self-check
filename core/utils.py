from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any


def text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def compact(value: Any) -> str:
    return re.sub(r"\s+", "", text(value))


def money(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    s = text(value).replace(",", "").replace("원", "").replace("₩", "")
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s or s in {"-", "."}:
        return 0
    return int(round(float(s)))


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, (int, float)) and 30000 <= float(value) <= 70000:
        return datetime(1899, 12, 30) + timedelta(days=float(value))
    s = text(value)
    for fmt in (
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def find_row(rows: list[list[Any]], required_terms: list[str]) -> tuple[int, list[Any]] | None:
    wanted = [compact(t) for t in required_terms]
    for idx, row in enumerate(rows):
        joined = "|".join(compact(v) for v in row)
        if all(term in joined for term in wanted):
            return idx, row
    return None


def next_nonempty(row: list[Any], start_index: int, max_lookahead: int = 6) -> Any:
    end = min(len(row), start_index + max_lookahead + 1)
    for i in range(start_index + 1, end):
        if text(row[i]):
            return row[i]
    return None
