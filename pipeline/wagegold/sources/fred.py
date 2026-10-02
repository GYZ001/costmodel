"""FRED (Federal Reserve Bank of St. Louis) CSV downloads.

Used for long history that the BLS API cannot return in one request
(production & nonsupervisory average hourly earnings since 1964) and for
Federal Reserve H.10 monthly exchange rates as an independent FX cross-check.
FRED republishes these series unchanged from BLS and the Federal Reserve Board.
"""
from __future__ import annotations

import csv
import io

from ..fetch import Fetcher
from ..model import Obs
from .common import to_float

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"

# FRED id -> (series, area, invert).  H.10 quotes some currencies as US$ per unit.
SERIES = {
    "AHETPI": ("us_ahe_pns_sa", "USA", False),
    "CES0500000003": ("us_ahe_all_sa_fred", "USA", False),
    "EXCHUS": ("fx_lcu_usd_h10", "CHN", False),
    "EXJPUS": ("fx_lcu_usd_h10", "JPN", False),
    "EXKOUS": ("fx_lcu_usd_h10", "KOR", False),
    "EXINUS": ("fx_lcu_usd_h10", "IND", False),
    "EXBZUS": ("fx_lcu_usd_h10", "BRA", False),
    "EXMXUS": ("fx_lcu_usd_h10", "MEX", False),
    "EXSFUS": ("fx_lcu_usd_h10", "ZAF", False),
    "EXCAUS": ("fx_lcu_usd_h10", "CAN", False),
    "EXSZUS": ("fx_lcu_usd_h10", "CHE", False),
    "EXUSUK": ("fx_lcu_usd_h10", "GBR", True),
    "EXUSEU": ("fx_lcu_usd_h10", "EUR", True),
    "EXUSAL": ("fx_lcu_usd_h10", "AUS", True),
}


def collect(f: Fetcher) -> list[Obs]:
    out: list[Obs] = []
    for fred_id, (series, area, invert) in SERIES.items():
        snap = f.get(f"fred/{fred_id}", URL.format(id=fred_id), ext="csv", check=_check(fred_id))
        for row in csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig"))):
            v = to_float(row[fred_id])
            if v is None:
                continue
            period = row["observation_date"][:7]
            out.append(Obs(series, area, period, 1 / v if invert else v, snap.key, note=fred_id))
    return out


def _check(fred_id: str):
    def check(body: bytes) -> None:
        head = body[:200].decode("utf-8-sig", "replace").splitlines()[0]
        if head != f"observation_date,{fred_id}":
            raise ValueError(f"unexpected FRED header {head!r}")

    return check
