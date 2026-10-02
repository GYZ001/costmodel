"""World Bank Commodity Price Data (the "Pink Sheet"): monthly gold price.

Gold is the World Bank's monthly series in US$ per troy ounce.  Per the workbook's
"Description" sheet it is the spot average of daily rates from June 2025, and before
that the London afternoon fixing (99.5% fine), average of daily rates.  The download URL of the
workbook changes with every release, so it is read from the World Bank's
commodity-markets landing page each run.
"""
from __future__ import annotations

import io
import re

from ..fetch import Fetcher
from ..model import Obs
from .common import check_prefix

LANDING = "https://www.worldbank.org/en/research/commodity-markets"
LINK_RE = re.compile(r"https://thedocs\.worldbank\.org/[^\"'\s]+/CMO-Historical-Data-Monthly\.xlsx")
MONTH_RE = re.compile(r"^(\d{4})M(\d{2})$")


def _check_landing(body: bytes) -> None:
    if not LINK_RE.search(body.decode("utf-8", "replace")):
        raise ValueError("landing page has no CMO-Historical-Data-Monthly.xlsx link")


def collect(f: Fetcher) -> list[Obs]:
    landing = f.get("worldbank/commodity_markets_landing", LANDING, ext="html", check=_check_landing)
    url = LINK_RE.search(landing.read().decode("utf-8", "replace")).group(0)
    snap = f.get("worldbank/CMO-Historical-Data-Monthly", url, ext="xlsx", check=check_prefix(b"PK", "an xlsx workbook"))
    return parse(snap.read(), snap.key)


def parse(xlsx: bytes, snapshot: str) -> list[Obs]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(xlsx), read_only=True, data_only=True)
    rows = list(wb["Monthly Prices"].iter_rows(values_only=True))
    hdr_idx = next(i for i, r in enumerate(rows) if r and any(_is_gold(c) for c in r))
    col = next(j for j, c in enumerate(rows[hdr_idx]) if _is_gold(c))
    unit = str(rows[hdr_idx + 1][col] or "")
    if unit.replace(" ", "") != "($/troyoz)":
        raise ValueError(f"unexpected gold unit {unit!r} (expected '($/troy oz)')")
    out = []
    for r in rows[hdr_idx + 1 :]:
        m = MONTH_RE.match(str(r[0] or "").strip())
        if not m or r[col] in (None, "", "…", ".."):
            continue
        out.append(Obs("gold_usd_oz", "WLD", f"{m.group(1)}-{m.group(2)}", float(r[col]), snapshot))
    if not out:
        raise ValueError("no monthly gold observations parsed")
    return out


def _is_gold(cell) -> bool:
    return isinstance(cell, str) and cell.strip().lower() == "gold"


def updated_on(xlsx: bytes) -> str | None:
    """The workbook's own 'Updated on <date>' line (row 4 of 'Monthly Prices')."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(xlsx), read_only=True, data_only=True)
    for (cell,) in wb["Monthly Prices"].iter_rows(min_row=1, max_row=6, max_col=1, values_only=True):
        if isinstance(cell, str) and cell.startswith("Updated on"):
            return cell.removeprefix("Updated on").strip()
    return None
