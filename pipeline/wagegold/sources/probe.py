"""Temporary: archive candidate pages and files of survey publishers' own releases, so
that their readers can be written against the real files (this project's sandbox cannot
reach them; the pipeline in GitHub Actions can).  Nothing here is parsed or published:
the snapshots (keys "probe/...") belong to no source in sources_meta.  To be removed
once the readers exist."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from ..fetch import Fetcher, FetchError
from ..model import Obs

# (key, url, ext, follow: regex of links to fetch too (group 1 = href), at most n)
PROBES: list[tuple[str, str, str, str | None, int]] = [
    # World Bank ICP 2021 (source 90): which measures ("Classification") and categories
    # ("Series") the API offers, to read household expenditure by category.
    ("probe/icp/concepts", "https://api.worldbank.org/v2/sources/90/concepts?format=json", "json", None, 0),
    ("probe/icp/classification", "https://api.worldbank.org/v2/sources/90/classification?format=json&per_page=500", "json", None, 0),
    ("probe/icp/series", "https://api.worldbank.org/v2/sources/90/series?format=json&per_page=2000", "json", None, 0),
    ("probe/icp/source", "https://api.worldbank.org/v2/sources/90?format=json", "json", None, 0),
    # ICP 2017 (for a second benchmark year, if it has the same measures)
    ("probe/icp/sources_list", "https://api.worldbank.org/v2/sources?format=json&per_page=200", "json", None, 0),
]


def collect(f: Fetcher) -> list[Obs]:
    if f.offline:
        return []
    for key, url, ext, follow, n in PROBES:
        try:
            snap = f.get(key, url, ext=ext, retries=1)
        except FetchError as exc:
            print(f"[probe] {key}: {exc}", flush=True)
            continue
        body = snap.read()
        print(f"[probe] {key}: {len(body)} bytes", flush=True)
        if not follow:
            continue
        links = []
        for href in re.findall(follow, body.decode("utf-8", "replace")):
            u = urljoin(url, href.replace("&amp;", "&"))
            if u not in links:
                links.append(u)
        for i, u in enumerate(links[:n]):
            sub = re.sub(r"[^A-Za-z0-9._-]+", "_", u.rsplit("/", 1)[-1])[:80] or str(i)
            ext2 = next((e for e in ("xlsx", "xls", "csv", "json", "pdf") if f".{e}" in u.lower()), "bin")
            try:
                s2 = f.get(f"{key}/{i:02d}_{sub}", u, ext=ext2, retries=1)
                print(f"[probe]   {u} -> {len(s2.read())} bytes", flush=True)
            except FetchError as exc:
                print(f"[probe]   {u}: {exc}", flush=True)
    return []
