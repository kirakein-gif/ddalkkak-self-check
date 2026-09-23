"""Local validation helper.

Usage (sample files are intentionally NOT committed):
  python scripts/validate_samples.py /path/to/sample-folder
"""
from __future__ import annotations

from pathlib import Path
import sys

from core.detector import detect_type
from core.parsers import parse_outside_ledger, parse_outside_statement, parse_school_ledger
from core.pdf_parsers import parse_kedufine_pdf
from core.workbook_reader import read_workbook


class LocalFile:
    def __init__(self, path: Path):
        self.name = path.name
        self._data = path.read_bytes()
    def getvalue(self):
        return self._data


def main(folder: Path):
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() == ".pdf" and "현금" in path.name:
            try:
                kind, obj = parse_kedufine_pdf(path.read_bytes(), path.name)
                print(path.name, "=>", kind, obj)
            except Exception as exc:
                print(path.name, "=> PDF skip/error:", exc)
        elif path.suffix.lower() == ".xlsx" and ("현금출납" in path.name or "출납계산" in path.name):
            try:
                book = read_workbook(LocalFile(path))
                kind = detect_type(book)
                if "학교회계" in kind:
                    obj = parse_school_ledger(book)
                elif "출납계산서" in kind:
                    obj = parse_outside_statement(book)
                else:
                    obj = parse_outside_ledger(book)
                print(path.name, "=>", kind, obj)
            except Exception as exc:
                print(path.name, "=> Excel error:", exc)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
