"""Helpers shared by source modules: response checks and number parsing."""
from __future__ import annotations

import csv
import io
import json


def check_json(predicate=None, what: str = "expected JSON payload"):
    """Build a fetch check that the body is JSON and satisfies ``predicate``."""

    def _check(body: bytes) -> None:
        data = json.loads(body.decode("utf-8-sig"))
        if predicate is not None and not predicate(data):
            raise ValueError(what)

    return _check


def check_csv_header(*required: str):
    def _check(body: bytes) -> None:
        text = body.decode("utf-8-sig", errors="replace")
        header = next(csv.reader(io.StringIO(text)), [])
        missing = [c for c in required if c not in header]
        if missing:
            raise ValueError(f"CSV header lacks {missing}; got {header[:8]}")

    return _check


def check_prefix(prefix: bytes, what: str):
    def _check(body: bytes) -> None:
        if not body.startswith(prefix):
            raise ValueError(f"not {what}: starts with {body[:40]!r}")

    return _check


# Excel workbooks: Office Open XML (a zip) or the older binary format (an OLE2 file).
EXCEL_MAGIC = {b"PK\x03\x04": "xlsx", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": "xls"}


def excel_format(body: bytes) -> str:
    """"xlsx" or "xls" by the file's signature; ValueError for anything else."""
    for magic, fmt in EXCEL_MAGIC.items():
        if body.startswith(magic):
            return fmt
    raise ValueError(f"not an Excel workbook: starts with {body[:16]!r}")


def excel_rows(body: bytes) -> dict[str, list[list[object]]]:
    """Every sheet of an Excel workbook (either format) as rows of cell values."""
    if excel_format(body) == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
        return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    import xlrd

    wb = xlrd.open_workbook(file_contents=body)
    return {sh.name: [sh.row_values(i) for i in range(sh.nrows)] for sh in wb.sheets()}


def to_float(text: str | None) -> float | None:
    if text is None:
        return None
    text = str(text).strip()
    if text in {"", ".", "-", "NA", "N/A", "NaN", "nan"}:
        return None
    return float(text.replace(",", ""))
