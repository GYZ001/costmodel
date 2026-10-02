"""National Bureau of Statistics of China (国家统计局): its own release of the series ILOSTAT
republishes for China as FX:216 ("ADM - Labour and Social Security Records") - the
average wage of employed persons in urban private units (城镇私营单位), annual ÷ 12.

ILOSTAT republishes it with a delay; NBS's yearly release (each May) continues it
(build.UnitGraph._extend, which first checks that the two agree on the years both have).
NBS's database API refuses requests from outside mainland China, but its press releases
on www.stats.gov.cn are reachable: they are discovered from the "数据发布 / 最新发布"
listing by their official titles and saved as snapshots.

* 「YYYY年城镇单位就业人员年平均工资情况」: both urban averages in one release;
* 「YYYY年城镇私营单位就业人员年平均工资NNNNN元」: for 2021 and 2022 NBS published the
  private-unit average as a release of its own.

Each release states the year's average and its increase on the previous year ("比上年增加
N元"), so it also gives the previous year's figure; a year's own release is preferred.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..fetch import Fetcher, Snapshot
from ..model import Obs

PUBLISHER = "nbs"  # catalog keys src.nbs.*
SERIES = "ext_ilo_monthly_mean@FX:216"  # continues ILOSTAT's ilo_monthly_mean@FX:216 for CHN
LIST_URL = "https://www.stats.gov.cn/sj/zxfb/"
LINK_RE = re.compile(r"href=\"\./(\d{6})/(t(\d{8})_\d+)\.html\"[^>]*title='([^']+)'")
WAGE_TITLE = re.compile(r"^(\d{4})年城镇单位就业人员年平均工资情况$")
PRIVATE_TITLE = re.compile(r"^(\d{4})年城镇私营单位就业人员年平均工资\d+元$")
# "全国城镇私营单位就业人员年平均工资为 X 元，比上年增加（减少） Y 元" - the wording varies
# slightly by year ("为 68340 元" or "65237元"; optional footnote markers).
PRIVATE_RE = re.compile(r"全国城镇私营单位就业人员年平均工资\s*为?\s*(\d+)\s*元\s*，\s*比上年(增加|减少)\s*(\d+)\s*元")
# Invisible formatting characters NBS pages sometimes carry inside numbers.
INVISIBLE_RE = re.compile("[­​-‍⁠﻿]|&shy;")
PAGES = 12  # listing pages scanned for new releases; older ones stay in the archive


@dataclass
class Release:
    url: str
    key: str
    title: str


def is_wage_release(title: str) -> bool:
    return bool(WAGE_TITLE.match(title) or PRIVATE_TITLE.match(title))


def page_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = INVISIBLE_RE.sub("", text.replace("&nbsp;", " ").replace("&emsp;", " "))
    return re.sub(r"\s+", " ", text)


def discover(f: Fetcher) -> list[Release]:
    seen: dict[str, Release] = {}
    for p in range(PAGES):
        url = LIST_URL + ("" if p == 0 else f"index_{p}.html")
        html = f.get_transient(url).decode("utf-8", "replace")
        for ym, tid, _day, title in LINK_RE.findall(html):
            title = title.strip()
            if tid not in seen and is_wage_release(title):
                seen[tid] = Release(f"{LIST_URL}{ym}/{tid}.html", f"nbs/release/{ym}/{tid}", title)
    return list(seen.values())


def collect(f: Fetcher) -> list[Obs]:
    snaps: list[tuple[Snapshot, str]] = []
    if not f.offline:
        for rel in discover(f):
            # A published release does not change: an existing snapshot is reused as is.
            snaps.append((f.get(rel.key, rel.url, ext="html", check=_check_release(rel.title), immutable=True), rel.title))
    seen = {snap.key for snap, _t in snaps}
    # Releases no longer on the listing pages scanned stay in the archive and are used.
    snaps += [(snap, _title_of(snap)) for snap in f.committed("nbs/release/") if snap.key not in seen]
    direct: dict[str, Obs] = {}
    implied: dict[str, Obs] = {}
    for snap, title in snaps:
        if not is_wage_release(title):
            continue
        year, value, prev = parse_release(snap.read().decode("utf-8", "replace"), title, snap.key)
        direct[str(year)] = Obs(SERIES, "CHN", str(year), value / 12, snap.key, PUBLISHER)
        implied[str(year - 1)] = Obs(SERIES, "CHN", str(year - 1), prev / 12, snap.key, PUBLISHER)
    # A year's own release first; the next year's statement of it only where there is none.
    return list({**implied, **direct}.values())


def parse_release(html: str, title: str, snapshot: str) -> tuple[int, int, int]:
    """(year, the year's annual average, the previous year's annual average)."""
    m = WAGE_TITLE.match(title) or PRIVATE_TITLE.match(title)
    if not m:
        raise ValueError(f"{snapshot}: not a wage release: {title!r}")
    hit = PRIVATE_RE.search(page_text(html))
    if not hit:
        raise ValueError(f"{snapshot}: no urban private-unit average wage sentence")
    value, up, change = int(hit.group(1)), hit.group(2), int(hit.group(3))
    return int(m.group(1)), value, value - change if up == "增加" else value + change


def _title_of(snap: Snapshot) -> str:
    m = re.search(r"<title>\s*([^<]*?)\s*(?:-\s*国家统计局)?\s*</title>", snap.read().decode("utf-8", "replace"))
    return m.group(1).strip() if m else ""


def _check_release(title: str):
    def check(body: bytes) -> None:
        if title not in body.decode("utf-8", "replace"):
            raise ValueError(f"release page does not contain its title {title!r}")

    return check
