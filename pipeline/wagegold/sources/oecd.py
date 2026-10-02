"""OECD Data Explorer: average annual wages per full-time-equivalent employee.

Used as an independent reference for the LEVEL of ILOSTAT earnings in OECD
members: both are official national figures in national currency, so a large
mismatch (e.g. a factor of 4) reveals a currency-unit error in one of them.
The concepts differ (per FTE, national accounts based vs. survey based), so the
comparison only screens for unit errors, it is not used to replace values.
"""
from __future__ import annotations

import csv
import io

from ..fetch import Fetcher
from ..model import Obs
from .common import check_csv_header, to_float

URL = ("https://sdmx.oecd.org/public/rest/data/OECD.ELS.SAE,DSD_EARNINGS@AV_AN_WAGE,1.0/all"
       "?startPeriod=2000&format=csvfilewithlabels")


def collect(f: Fetcher) -> list[Obs]:
    snap = f.get("oecd/av_an_wage", URL, ext="csv", check=check_csv_header("REF_AREA", "UNIT_MEASURE", "PRICE_BASE", "OBS_VALUE"),
                 timeout=90, retries=2)
    out = []
    for r in csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig"))):
        v = to_float(r["OBS_VALUE"])
        # national currency, current prices; skip the USD-PPP and constant-price variants
        if v is None or r["PRICE_BASE"] != "V" or r["UNIT_MEASURE"].startswith("USD_PPP"):
            continue
        out.append(Obs("oecd_avg_annual_wage", r["REF_AREA"], r["TIME_PERIOD"], v, snap.key, note=r["UNIT_MEASURE"]))
    return out
