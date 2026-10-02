"""FRED (Federal Reserve Bank of St. Louis) CSV downloads.

Used only for cross-checks: FRED's republication of BLS average hourly earnings
(checked against the BLS API) and the Federal Reserve H.10 monthly exchange rates
(checked against the ECB reference rates).  Nothing from FRED enters a computed
figure, so FRED series are stored under their own keys.
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
    "AHETPI": ("us_ahe_pns_sa_fred", "USA", False),
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
        snap = f.get(f"fred/{fred_id}", URL.format(id=fred_id), ext="csv", check=_check(fred_id), timeout=30, retries=1)
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
