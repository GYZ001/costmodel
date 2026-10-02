"""U.S. Bureau of Labor Statistics public API v2.

CES (Current Employment Statistics), total private:
  CES0500000003 / CEU0500000003  average hourly earnings, all employees (SA / NSA), since 2006-03
  CES0500000008 / CEU0500000008  average hourly earnings, production & nonsupervisory (SA / NSA), since 1964
  CES0500000002 / CEU0500000002  average weekly hours, all employees (SA / NSA)

CPI Average Price data (AP), U.S. city average: see AP_ITEMS.

Without a registration key the API serves at most 25 series and 10 years per
request (and a daily request quota per IP), so requests are split into 10-year
windows.  An optional key in the BLS_API_KEY environment variable raises the
limits; it is sent to BLS but never written to the snapshot manifest.
"""
from __future__ import annotations

import json
import os
from datetime import date

from ..fetch import Fetcher
from ..model import Obs
from .common import check_json

API = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

CES_SERIES = {
    "CES0500000003": "us_ahe_all_sa",
    "CEU0500000003": "us_ahe_all_nsa",
    "CES0500000008": "us_ahe_pns_sa",
    "CEU0500000008": "us_ahe_pns_nsa",
    "CES0500000002": "us_awh_all_sa",
    "CEU0500000002": "us_awh_all_nsa",
}

# BLS AP series id -> item key.  Labels and unit conversions live in catalog.US_ITEMS.
AP_SERIES = {
    "APU0000701111": "flour",
    "APU0000701312": "rice",
    "APU0000702111": "bread_white",
    "APU0000703112": "ground_beef",
    "APU0000703613": "sirloin_steak",
    "APU0000704111": "bacon",
    "APU0000706111": "chicken_whole",
    "APU0000FF1101": "chicken_breast",
    "APU0000708111": "eggs",
    "APU0000709112": "milk_whole",
    "APU0000710212": "cheddar",
    "APU0000FS1101": "butter",
    "APU0000711211": "bananas",
    "APU0000711311": "oranges",
    "APU0000712112": "potatoes",
    "APU0000712211": "lettuce",
    "APU0000712311": "tomatoes",
    "APU0000715211": "sugar",
    "APU0000717311": "coffee",
    "APU000074714": "gasoline",
    "APU000072610": "electricity",
}


def _ok(data) -> bool:
    return data.get("status") == "REQUEST_SUCCEEDED" and data.get("Results", {}).get("series")


def _windows(first_year: int, last_year: int, span: int = 10):
    y = first_year
    while y <= last_year:
        yield y, min(y + span - 1, last_year)
        y += span


def _request(f: Fetcher, key: str, series_ids: list[str], y0: int, y1: int):
    body = {"seriesid": series_ids, "startyear": str(y0), "endyear": str(y1)}
    send = dict(body)
    api_key = os.environ.get("BLS_API_KEY")
    if api_key:
        send["registrationkey"] = api_key
    return f.get(key, API, ext="json", json_body=send, record_body=body,
                 check=check_json(_ok, "BLS API did not return REQUEST_SUCCEEDED with data"))


def _parse(snap, mapping: dict[str, str]) -> list[Obs]:
    payload = json.loads(snap.read())
    out = []
    for s in payload["Results"]["series"]:
        name = mapping[s["seriesID"]]
        for d in s["data"]:
            if not d["period"].startswith("M") or d["period"] == "M13":
                continue
            try:
                v = float(d["value"])
            except ValueError:  # BLS marks unavailable values with "-"
                continue
            prelim = any(fn.get("code") == "P" for fn in d.get("footnotes", []) if fn)
            out.append(Obs(name, "USA", f"{d['year']}-{d['period'][1:]}", v, snap.key,
                           note=f"{s['seriesID']}{'|preliminary' if prelim else ''}"))
    return out


def collect(f: Fetcher, today: date | None = None) -> list[Obs]:
    year = (today or date.today()).year
    out: list[Obs] = []
    for y0, y1 in _windows(1964, year):
        snap = _request(f, f"bls/ces_from_{y0}", list(CES_SERIES), y0, y1)
        out += _parse(snap, CES_SERIES)
    for y0, y1 in _windows(2016, year):
        snap = _request(f, f"bls/ap_from_{y0}", list(AP_SERIES), y0, y1)
        out += _parse(snap, AP_SERIES)
    return out
