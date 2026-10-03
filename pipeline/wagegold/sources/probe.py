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
    # Korea, MOEL Survey on Labor Conditions by Employment Type (ILOSTAT DA:224)
    ("probe/kor/laborstat_lss108", "https://laborstat.moel.go.kr/lsm/bbs/selectBbsList.do?bbsId=LSS108&leftMenuId=0010001100116"
     "&menuId=0010001100116115&pageIndex=1&searchCtgryCode=004&subCtgryCode=004", "html", None, 0),
    ("probe/kor/datagokr_3038238", "https://www.data.go.kr/data/3038238/fileData.do", "html", None, 0),
    ("probe/kor/kosis_pay0004", "https://kosis.kr/statHtml/statHtml.do?orgId=118&tblId=DT_118N_PAY0004", "html", None, 0),
    # Russia, Rosstat October survey of wages by occupation (ILOSTAT DA:122)
    ("probe/rus/rosstat_labour_costs", "https://rosstat.gov.ru/labour_costs", "html", None, 0),
    ("probe/rus/rosstat_salaries", "https://rosstat.gov.ru/labor_market_employment_salaries", "html", None, 0),
    ("probe/rus/rosstat_compendium_60671", "https://rosstat.gov.ru/compendium/document/60671", "html", None, 0),
    # Saudi Arabia, GASTAT Labour Force Survey (ILOSTAT BA:627)
    ("probe/sau/gastat_home", "https://www.stats.gov.sa/en", "html", None, 0),
    ("probe/sau/gastat_814", "https://www.stats.gov.sa/en/814", "html", None, 0),
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
