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
    # Korea: the attachments of MOEL's survey reports (2025 and 2022 editions)
    ("probe/kor/report2025_files", "https://laborstat.moel.go.kr/cmm/fms/selectFileInfs2.do?param_atchFileId=FILE_000000000058663", "html", None, 0),
    ("probe/kor/report2022_files", "https://laborstat.moel.go.kr/cmm/fms/selectFileInfs2.do?param_atchFileId=FILE_000000000047181", "html", None, 0),
    # Saudi Arabia: GASTAT labour market statistics (LFS) pages and their files
    ("probe/sau/gastat_lfs_q2_2026", "https://www.stats.gov.sa/en/statistics-tabs?tab=436312&category=417515", "html",
     r'href="([^"]+\.(?:xlsx|xls|csv|pdf)[^"]*)"', 6),
    ("probe/sau/gastat_labour_index", "https://www.stats.gov.sa/en/statistics?index=119025&subindex=123704", "html", None, 0),
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
