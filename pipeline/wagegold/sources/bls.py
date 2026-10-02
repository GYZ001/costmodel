"""U.S. Bureau of Labor Statistics public API v2.

CES (Current Employment Statistics), total private:
  CEU0500000003  average hourly earnings, all employees (NSA), since 2006-03 - the annual
                 mean of the 12 months is the U.S. national-source wage figure
  CES0500000003  the same, seasonally adjusted - only to cross-check FRED's republication

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
}
# Average hourly earnings of all private employees start in 2006-03.
FIRST_YEAR = 2006


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
        name = mapping.get(s["seriesID"])
        if name is None:  # a series this module no longer uses (in an older snapshot)
            continue
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
    # Ten-year windows on the grid the archive's snapshots were requested on (from 1964),
    # skipping windows that end before the series starts.
    for y0, y1 in _windows(1964, year):
        if y1 >= FIRST_YEAR:
            snap = _request(f, f"bls/ces_from_{y0}", list(CES_SERIES), y0, y1)
            out += _parse(snap, CES_SERIES)
    return out
