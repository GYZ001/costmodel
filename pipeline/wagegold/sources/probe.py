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
    # Japan, MHLW Basic Survey on Wage Structure (ILOSTAT DA:260)
    ("probe/jpn/mhlw_en_ordinary2020", "https://www.mhlw.go.jp/english/database/db-l/ordinary2020.html", "html",
     r'href="([^"]+\.(?:xlsx|xls|csv))"', 12),
    ("probe/jpn/estat_list", "https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00450091&tstat=000001011429", "html", None, 0),
    ("probe/jpn/estat_2025_ippan_sangyo",
     "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00450091&tstat=000001011429&cycle=0"
     "&tclass1=000001229845&tclass2=000001229849&tclass3=000001229868&tclass4val=0", "html",
     r'href="([^"]*file-download\?[^"]*statInfId=\d+[^"]*fileKind=0[^"]*)"', 4),
    ("probe/jpn/mhlw_z2025", "https://www.mhlw.go.jp/toukei/itiran/roudou/chingin/kouzou/z2025/index.html", "html", None, 0),
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
