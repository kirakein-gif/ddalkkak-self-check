from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED


def build_zip(files: dict[str, bytes]) -> bytes:
    bio = BytesIO()
    with ZipFile(bio, "w", compression=ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return bio.getvalue()
