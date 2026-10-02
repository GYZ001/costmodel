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


def to_float(text: str | None) -> float | None:
    if text is None:
        return None
    text = str(text).strip()
    if text in {"", ".", "-", "NA", "N/A", "NaN", "nan"}:
        return None
    return float(text.replace(",", ""))
