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
    # Saudi Arabia: GASTAT labour market statistics, fourth-quarter tables
    ("probe/sau/q4_2025", "https://www.stats.gov.sa/documents/20117/2435273/Labor_Market_Statistics_Q4_2025_EN_%281%29.xlsx_fixed_13014566/e0ebf178-e440-3e12-3db6-01a7bd902dae?t=1774932638196", "xlsx", None, 0),
    ("probe/sau/q4_2024", "https://www.stats.gov.sa/documents/20117/2435273/Labor_Market_Statistics_Q4_2024_-__EN_%281%29.xlsx_fixed_3685174/fddd476e-2227-cfa8-00db-dc215427a816?t=1756667905812", "xlsx", None, 0),
    ("probe/sau/q4_2023", "https://www.stats.gov.sa/documents/20117/2435273/LM_tables_Q4_2023_EN%28%25%29_0.xlsx_fixed_2499279/8fd76bfe-26a6-7b67-bdfb-528b26657782?t=1735232107331", "xlsx", None, 0),
    ("probe/sau/q4_2022", "https://www.stats.gov.sa/documents/20117/2435273/LM_tables_Q4_2022_EN_0_%28%25%29.xlsx_fixed_2499393/5e35d086-48cd-719c-9984-6c45e931a5d2?t=1735232855019", "xlsx", None, 0),
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
