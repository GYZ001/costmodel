"""IMF Primary Commodity Price System: monthly gold price, used to cross-check the Pink Sheet.

Series G001.PGOLD.USD.M - "Gold (UK), 99.5% fine, London afternoon fixing",
US$ per troy ounce, monthly average.
"""
from __future__ import annotations

import re

from ..fetch import Fetcher
from ..model import Obs

URL = "https://api.imf.org/external/sdmx/2.1/data/IMF.RES,PCPS,9.0.0/G001.PGOLD.USD.M?startPeriod=1990-01"
OBS_RE = re.compile(r'<Obs\b[^>]*\bTIME_PERIOD="(\d{4})-M(\d{2})"[^>]*\bOBS_VALUE="([0-9.]+)"')


def _check(body: bytes) -> None:
    if not OBS_RE.search(body.decode("utf-8", "replace")):
        raise ValueError("no PGOLD observations in IMF response")


def collect(f: Fetcher) -> list[Obs]:
    snap = f.get("imf/pcps_pgold_monthly", URL, ext="xml", check=_check, timeout=60, retries=2)
    text = snap.read().decode("utf-8", "replace")
    return [Obs("gold_usd_oz_imf", "WLD", f"{y}-{m}", float(v), snap.key) for y, m, v in OBS_RE.findall(text)]
