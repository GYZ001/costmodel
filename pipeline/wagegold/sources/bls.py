"""U.S. Bureau of Labor Statistics public API v2.

CES (Current Employment Statistics), total private:
  CES0500000003 / CEU0500000003  average hourly earnings, all employees (SA / NSA), since 2006-03
  CES0500000008 / CEU0500000008  average hourly earnings, production & nonsupervisory (SA / NSA), since 1964
  CES0500000002 / CEU0500000002  average weekly hours, all employees (SA / NSA)
  CES0500000007 / CEU0500000007  average weekly hours, production & nonsupervisory (SA / NSA)

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
    "CES0500000007": "us_awh_pns_sa",
    "CEU0500000007": "us_awh_pns_nsa",
}

# BLS AP series id -> item key.  Labels and unit conversions live in catalog.US_ITEMS.
AP_SERIES = {
    "APU0000701111": "flour",
    "APU0000701312": "rice",
    "APU0000701322": "pasta",
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


def unavailable(snaps) -> list[dict]:
    """Months without a value inside each series' span, grouped across series:
    [{"period", "note", "series": [...]}].  A month BLS lists with "-" carries BLS's own
    footnote; a month absent from the response altogether has no note."""
    from datetime import date as _date

    seen: dict[str, set[str]] = {}
    notes: dict[tuple[str, str], str] = {}
    for snap in snaps:
        for s in json.loads(snap.read())["Results"]["series"]:
            have = seen.setdefault(s["seriesID"], set())
            for d in s["data"]:
                if not d["period"].startswith("M") or d["period"] == "M13":
                    continue
                p = f"{d['year']}-{d['period'][1:]}"
                if d["value"].strip() == "-":
                    notes[(s["seriesID"], p)] = "; ".join(fn["text"] for fn in d.get("footnotes", []) if fn and fn.get("text"))
                else:
                    have.add(p)
    groups: dict[tuple[str, str], list[str]] = {}
    for sid, have in seen.items():
        if not have:
            continue
        y, m = map(int, min(have).split("-"))
        last = max(have)
        while f"{y}-{m:02d}" < last:
            p = f"{y}-{m:02d}"
            if p not in have:
                groups.setdefault((p, notes.get((sid, p), "")), []).append(sid)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return [{"period": p, "note": n, "series": sorted(ids)} for (p, n), ids in sorted(groups.items())]


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
