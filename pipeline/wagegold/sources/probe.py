"""Temporary: archive the publishers' own definitions needed to decide how section ④ reads
ICP 2021 housing and how it states the period of household consumption (this project's
sandbox cannot reach them; the pipeline in GitHub Actions can).  Nothing here is parsed or
published: the snapshots (keys "probe/...") belong to no source in sources_meta.  To be
removed once the decision is made."""
from __future__ import annotations

from ..fetch import Fetcher, FetchError
from ..model import Obs

API = "https://api.worldbank.org/v2"
PROBES: list[tuple[str, str]] = [
    # ICP 2021 (source 90): definitions of the aggregates read or considered.
    *[(f"probe/icp/meta_{s}", f"{API}/sources/90/series/{s}/metadata?format=json")
      for s in ("9260000", "9060000", "9100000", "9020000", "1300000", "1113000")],
    ("probe/icp/meta_all", f"{API}/sources/90/series/9260000;9060000;9100000/metadata?format=json"),
    ("probe/icp/cn_9260000", f"{API}/sources/90/country/all/series/9260000;9100000;9060000/classification/CN/time/YR2021?format=json&per_page=20000"),
    # WDI (source 2): the definition of household consumption, and the reporting period of
    # each economy's national accounts (fiscal or calendar year).
    ("probe/wdi/meta_hfce", f"{API}/sources/2/series/NE.CON.PRVT.CN/metadata?format=json"),
    ("probe/wdi/country_meta_EGY", f"{API}/sources/2/country/EGY/metadata?format=json"),
    ("probe/wdi/country_meta_all", f"{API}/sources/2/country/all/metadata?format=json&per_page=500"),
    ("probe/wdi/country_series_EGY", f"{API}/sources/2/country/EGY;IND;BGD/series/NE.CON.PRVT.CN/metadata?format=json"),
    ("probe/wdi/metatypes", f"{API}/sources/2/metatypes?format=json"),
    ("probe/wdi/country_EGY", f"{API}/country/EGY?format=json"),
]


def collect(f: Fetcher) -> list[Obs]:
    if f.offline:
        return []
    for key, url in PROBES:
        try:
            snap = f.get(key, url, ext="json", retries=1)
        except FetchError as exc:
            print(f"[probe] {key}: {exc}", flush=True)
            continue
        print(f"[probe] {key}: {len(snap.read())} bytes", flush=True)
    return []
