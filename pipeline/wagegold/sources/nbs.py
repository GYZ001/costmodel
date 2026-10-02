"""National Bureau of Statistics of China (国家统计局) press releases.

NBS's database API refuses requests from outside mainland China, but its press
releases on www.stats.gov.cn are reachable.  Releases are discovered from the
"数据发布 / 最新发布" listing by their official titles, saved as snapshots, and
parsed with patterns anchored on the sentences NBS uses every year:

* 「YYYY年城镇单位就业人员年平均工资情况」 - annual average wages of employed
  persons in urban non-private units (城镇非私营单位) and urban private units
  (城镇私营单位).
* 「YYYY年农民工监测调查报告」 - average monthly income of migrant workers.
* Monthly 「…国民经济…」 releases - 全国企业就业人员周平均工作时间 (average weekly
  hours actually worked by enterprise employees, from the monthly labour force survey).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..fetch import Fetcher, Snapshot
from ..model import Obs

LIST_URL = "https://www.stats.gov.cn/sj/zxfb/"
LINK_RE = re.compile(r"href=\"\./(\d{6})/(t(\d{8})_\d+)\.html\"[^>]*title='([^']+)'")

WAGE_TITLE = re.compile(r"^(\d{4})年城镇单位就业人员年平均工资情况$")
MIGRANT_TITLE = re.compile(r"^(\d{4})年农民工监测调查报告$")
# Monthly "national economy" releases; the title fixes the reference month.
ECONOMY_TITLES = [
    (re.compile(r"^(\d{1,2})月份国民经济"), lambda m: int(m.group(1))),
    (re.compile(r"^1[—–-](\d{1,2})月份国民经济"), lambda m: int(m.group(1))),
    (re.compile(r"^一季度国民经济"), lambda m: 3),
    (re.compile(r"^上半年国民经济"), lambda m: 6),
    (re.compile(r"^前三季度国民经济"), lambda m: 9),
    (re.compile(r"^\d{4}年国民经济(?!和社会发展统计公报)"), lambda m: 12),
]


def economy_month(title: str) -> int | None:
    for rx, month in ECONOMY_TITLES:
        if m := rx.match(title):
            return month(m)
    return None

WAGE_RE = {
    # Wording varies slightly by year ("年平均工资为 120698 元" vs "年平均工资 129441 元"; optional footnote markers).
    "cn_wage_nonprivate": re.compile(r"全国城镇非私营单位就业人员年平均工资\s*为?\s*(\d+)\s*元\s*，\s*比上年增加\s*(\d+)\s*元\s*，\s*名义增长\s*(?:\[\d+\])?\s*([\d.]+)\s*%"),
    "cn_wage_private": re.compile(r"全国城镇私营单位就业人员年平均工资\s*为?\s*(\d+)\s*元\s*，\s*比上年增加\s*(\d+)\s*元\s*，\s*名义增长\s*(?:\[\d+\])?\s*([\d.]+)\s*%"),
}
POSITION_RE = re.compile(
    r"规模以上企业就业人员年平均工资为\s*(\d+)\s*元，其中，中层及以上管理人员\s*(\d+)\s*元，专业技术人员\s*(\d+)\s*元，"
    r"办事人员和有关人员\s*(\d+)\s*元，社会生产服务和生活服务人员\s*(\d+)\s*元，生产制造及有关人员\s*(\d+)\s*元"
)
POSITION_KEYS = ["cn_wage_large_ent", "cn_wage_large_ent_managers", "cn_wage_large_ent_professionals",
                 "cn_wage_large_ent_clerks", "cn_wage_large_ent_services", "cn_wage_large_ent_production"]
MIGRANT_RE = re.compile(r"农民工月均收入\s*为?\s*(\d+)\s*元\s*，\s*比上年增加\s*(\d+)\s*元\s*，\s*增长\s*([\d.]+)\s*%")
HOURS_RE = re.compile(r"全国企业就业人员周平均工作时间为\s*([\d.]+)\s*小时")
HOURS_MONTH_RE = re.compile(r"(\d{1,2})\s*月份，全国城镇调查失业率")


@dataclass
class Release:
    url: str
    key: str
    title: str
    released: str  # YYYYMMDD


def page_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&emsp;", " ")
    return re.sub(r"\s+", " ", text)


def discover(f: Fetcher, pages: int = 64) -> tuple[list[Release], list[dict]]:
    """Wanted releases, plus an index of every listed release whose title mentions
    价格 (prices) - the evidence for which price statistics NBS currently publishes."""
    seen: dict[str, Release] = {}
    price_titles: dict[str, dict] = {}
    for p in range(pages):
        url = LIST_URL + ("" if p == 0 else f"index_{p}.html")
        html = f.get_transient(url).decode("utf-8", "replace")
        for ym, tid, day, title in LINK_RE.findall(html):
            title = title.strip()
            if "价格" in title:
                price_titles[tid] = {"date": f"{day[:4]}-{day[4:6]}-{day[6:]}", "title": title, "url": f"{LIST_URL}{ym}/{tid}.html"}
            if tid not in seen and (WAGE_TITLE.match(title) or MIGRANT_TITLE.match(title) or economy_month(title)):
                seen[tid] = Release(f"{LIST_URL}{ym}/{tid}.html", f"nbs/release/{ym}/{tid}", title, day)
    return list(seen.values()), sorted(price_titles.values(), key=lambda r: r["date"])


def collect(f: Fetcher) -> list[Obs]:
    snaps: list[tuple[Snapshot, str]] = []
    if f.offline:
        snaps = [(s, _title_of(s)) for s in f.committed("nbs/release/")]
    else:
        releases, price_titles = discover(f)
        write_price_index(price_titles)
        for rel in releases:
            # A published release does not change, so an existing snapshot is reused as is.
            snap = f.get(rel.key, rel.url, ext="html", check=_check_release(rel.title), immutable=True)
            snaps.append((snap, rel.title))
    out: list[Obs] = []
    for snap, title in snaps:
        out += parse_release(snap.read().decode("utf-8", "replace"), title, snap.key)
    return out


def write_price_index(rows: list[dict]) -> None:
    import json

    from ..config import DATA_DIR

    path = DATA_DIR / "derived" / "nbs_price_release_index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "listing": LIST_URL,
        "note": "Every release on the NBS '最新发布' listing pages scanned in this run whose title contains 价格.",
        "releases": rows,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def price_release_summary() -> dict | None:
    """Group the committed index by release type (title with dates and numbers removed)."""
    import json
    import re as _re

    from ..config import DATA_DIR

    path = DATA_DIR / "derived" / "nbs_price_release_index.json"
    if not path.exists():
        return None
    idx = json.loads(path.read_text(encoding="utf-8"))
    groups: dict[str, dict] = {}
    for r in idx["releases"]:
        kind = _re.sub(r"\d{4}年|\d{1,2}月份?|[上中下]旬|[一二三四]季度|同比|环比|上涨|下降|持平|[\d.]+%|\s", "", r["title"])
        g = groups.setdefault(kind, {"kind": kind, "count": 0, "first": r["date"], "last": r["date"], "example": r["url"]})
        g["count"] += 1
        g["first"] = min(g["first"], r["date"])
        g["last"] = max(g["last"], r["date"])
    dates = [r["date"] for r in idx["releases"]]
    return {"listing": idx["listing"], "from": min(dates) if dates else None,
            "to": max(dates) if dates else None, "groups": sorted(groups.values(), key=lambda g: -g["count"])}


def _title_of(snap: Snapshot) -> str:
    m = re.search(r"<title>\s*([^<]*?)\s*(?:-\s*国家统计局)?\s*</title>", snap.read().decode("utf-8", "replace"))
    return m.group(1).strip() if m else ""


def _check_release(title: str):
    def check(body: bytes) -> None:
        if title not in body.decode("utf-8", "replace"):
            raise ValueError(f"release page does not contain its title {title!r}")

    return check


def parse_release(html: str, title: str, snapshot: str) -> list[Obs]:
    text = page_text(html)
    out: list[Obs] = []
    if m := WAGE_TITLE.match(title):
        year = int(m.group(1))
        for series, rx in WAGE_RE.items():
            hit = rx.search(text)
            if not hit:
                raise ValueError(f"{snapshot}: no match for {series}")
            value, increase, growth = int(hit.group(1)), int(hit.group(2)), float(hit.group(3))
            out.append(Obs(series, "CHN", str(year), value, snapshot, note=f"growth_pct={growth}"))
            # Kept apart from the direct series: validate.py checks it against the previous year's own release.
            out.append(Obs(f"{series}__implied_prev", "CHN", str(year - 1), value - increase, snapshot))
        if hit := POSITION_RE.search(text):
            for key, v in zip(POSITION_KEYS, hit.groups()):
                out.append(Obs(key, "CHN", str(year), int(v), snapshot))
    elif m := MIGRANT_TITLE.match(title):
        year = int(m.group(1))
        hit = MIGRANT_RE.search(text)
        if not hit:
            raise ValueError(f"{snapshot}: no migrant-worker income sentence")
        value, increase, growth = int(hit.group(1)), int(hit.group(2)), float(hit.group(3))
        out.append(Obs("cn_migrant_monthly", "CHN", str(year), value, snapshot, note=f"growth_pct={growth}"))
        out.append(Obs("cn_migrant_monthly__implied_prev", "CHN", str(year - 1), value - increase, snapshot))
    elif (month := economy_month(title)) is not None:
        hit = HOURS_RE.search(text)
        if hit:
            near = list(HOURS_MONTH_RE.finditer(text[: hit.start()]))
            if not near or int(near[-1].group(1)) != month:
                raise ValueError(f"{snapshot}: title says month {month}, text near the hours sentence says "
                                 f"{near[-1].group(1) if near else 'nothing'}")
            released = re.search(r"/t(\d{4})(\d{2})\d{2}_", snapshot)
            ry, rm = int(released.group(1)), int(released.group(2))
            year = ry if month <= rm else ry - 1
            out.append(Obs("cn_weekly_hours_enterprise", "CHN", f"{year}-{month:02d}", float(hit.group(1)), snapshot))
    return out
