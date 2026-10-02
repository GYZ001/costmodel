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
* Monthly 「YYYY年M月份居民消费价格…」 releases - the sentences that report
  year-on-year CPI changes, kept verbatim so statements about them can be checked
  against the archived original text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..fetch import Fetcher, Snapshot
from ..model import Obs

LIST_URL = "https://www.stats.gov.cn/sj/zxfb/"
LINK_RE = re.compile(r"href=\"\./(\d{6})/(t(\d{8})_\d+)\.html\"[^>]*title='([^']+)'")

WAGE_TITLE = re.compile(r"^(\d{4})年城镇单位就业人员年平均工资情况$")
# For 2021 and 2022 NBS published the two urban-unit averages and the large-enterprise
# figures as separate releases, e.g. "2022年城镇非私营单位就业人员年平均工资114029元".
WAGE_PART_TITLE = re.compile(r"^(\d{4})年城镇(非私营|私营)单位就业人员年平均工资\d+元$")
LARGE_ENT_TITLE = re.compile(r"^(\d{4})年规模以上企业就业人员年平均工资情况$")
MIGRANT_TITLE = re.compile(r"^(\d{4})年农民工监测调查报告$")
CPI_TITLE = re.compile(r"^(\d{4})年(\d{1,2})月份居民消费价格")
# Monthly "national economy" releases; the title fixes the reference month.
ECONOMY_TITLES = [
    (re.compile(r"^(\d{1,2})月份国民经济"), lambda m: int(m.group(1))),
    (re.compile(r"^1[—–-](\d{1,2})月份国民经济"), lambda m: int(m.group(1))),
    (re.compile(r"^一季度国民经济"), lambda m: 3),
    (re.compile(r"^上半年国民经济"), lambda m: 6),
    (re.compile(r"^前三季度国民经济"), lambda m: 9),
    (re.compile(r"^\d{4}年国民经济(?!和社会发展统计公报)"), lambda m: 12),
]


def is_economy_release(title: str) -> bool:
    """Monthly/quarterly/annual economic-performance releases.  Their titles vary
    ("8月份国民经济…", "前三季度经济…"), so any title about the economy is taken,
    except statistical communiqués and census bulletins, which never carry the
    monthly hours figure.  The reference month itself comes from the text."""
    return "经济" in title and not re.search(r"公报|普查", title)


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
COMPARABLE_RE = re.compile(r"\s*，\s*按可比口径\s*(?:\[\d+\])?\s*增长\s*([\d.]+)\s*%")
POSITION_RE = re.compile(
    r"规模以上企业就业人员年平均工资为\s*(\d+)\s*元，其中，中层及以上管理人员\s*(\d+)\s*元，专业技术人员\s*(\d+)\s*元，"
    r"办事人员和有关人员\s*(\d+)\s*元，社会生产服务和生活服务人员\s*(\d+)\s*元，生产制造及有关人员\s*(\d+)\s*元"
)
POSITION_KEYS = ["cn_wage_large_ent", "cn_wage_large_ent_managers", "cn_wage_large_ent_professionals",
                 "cn_wage_large_ent_clerks", "cn_wage_large_ent_services", "cn_wage_large_ent_production"]
MIGRANT_RE = re.compile(r"农民工月均收入\s*为?\s*(\d+)\s*元\s*，\s*比上年增加\s*(\d+)\s*元\s*，\s*增长\s*([\d.]+)\s*%")
HOURS_RE = re.compile(r"全国企业就业人员周平均工作时间为\s*([\d.]+)\s*小时")
PUBDATE_META_RE = re.compile(r'name="PubDate"\s+content="(\d{4})/(\d{2})/(\d{2})')
PUBDATE_TEXT_RE = re.compile(r"(20\d\d)/(\d\d)/(\d\d) \d\d:\d\d")


def reference_month(html: str, text: str) -> tuple[int, int]:
    """Reference month of a monthly economic-performance release.  NBS publishes
    them in the month after the reference month (January-February combined in
    March, reported as February; December/annual in January), so the month comes
    from the page's own publication date.  The text alone is not enough: quarterly
    and half-year releases recap earlier months ("4月份，全国城镇调查失业率为6.1%；
    5、6月份连续回落") right before the hours sentence, which refers to the latest month."""
    ry, rm = published(html, text)
    return (ry, rm - 1) if rm > 1 else (ry - 1, 12)


def published(html: str, text: str) -> tuple[int, int]:
    """Publication date as stated on the page itself.  The URL date is not used:
    pages re-posted during NBS's 2023 site migration carry the migration date in
    their URL but keep the original publication time on the page."""
    m = PUBDATE_META_RE.search(html) or PUBDATE_TEXT_RE.search(text)
    if not m:
        raise ValueError("no publication date on the page")
    return int(m.group(1)), int(m.group(2))


@dataclass
class Release:
    url: str
    key: str
    title: str
    released: str  # YYYYMMDD


# Invisible formatting characters (soft hyphen, zero-width spaces/joiners, BOM) that
# NBS pages sometimes carry inside numbers, e.g. "1\u00ad\u00ad—7月".
INVISIBLE_RE = re.compile("[\u00ad\u200b-\u200d\u2060\ufeff]|&shy;")


def page_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = INVISIBLE_RE.sub("", text.replace("&nbsp;", " ").replace("&emsp;", " "))
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
            if re.search(r"价格|工资|收入", title):
                price_titles[tid] = {"date": f"{day[:4]}-{day[4:6]}-{day[6:]}", "title": title, "url": f"{LIST_URL}{ym}/{tid}.html"}
            if tid not in seen and (WAGE_TITLE.match(title) or WAGE_PART_TITLE.match(title) or LARGE_ENT_TITLE.match(title)
                                    or MIGRANT_TITLE.match(title) or CPI_TITLE.match(title) or is_economy_release(title)):
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
    write_cpi_quotes(snaps)
    write_wage_definitions(snaps)
    return out


DEFINITIONS = {
    # key -> pattern capturing NBS's own wording in the wage release's notes
    "scope": re.compile(r"统计范围((?:[^。]*法人单位[^。]*。)(?:调查对象不包括[^。]*。)?)"),
    "cn_wage_nonprivate": re.compile(r"城镇地区非私营法人单位（[^）]*）具体包括：([^。]+)。"),
    "cn_wage_private": re.compile(r"城镇地区私营法人单位（[^）]*）具体包括：([^。]+)。"),
    "cn_wage_large_ent": re.compile(r"规模以上企业具体是指：([^。]+)。"),
    "comparable": re.compile(r"可比口径是指([^。]+)。"),
    "gross": re.compile(r"(工资总额是税前工资[^。]*。)"),
}


def write_wage_definitions(snaps: list[tuple[Snapshot, str]]) -> None:
    """NBS's own definitions, quoted from each annual wage release (by wage year)."""
    import json

    from ..config import DATA_DIR

    rows: dict[str, dict] = {}
    for snap, title in sorted(snaps, key=lambda st: st[0].key):
        if m := (WAGE_TITLE.match(title) or WAGE_PART_TITLE.match(title) or LARGE_ENT_TITLE.match(title)):
            text = re.sub(r"\s+", "", body_text(snap.read().decode("utf-8", "replace")))
            row = rows.setdefault(m.group(1), {"releases": []})
            row["releases"].append({"title": title, "url": snap.url, "snapshot": snap.key})
            for k, rx in DEFINITIONS.items():  # a year published in several releases: first wording found
                if row.get(k) is None:
                    hit = rx.search(text)
                    row[k] = hit.group(1) if hit else None
    path = DATA_DIR / "derived" / "nbs_wage_definitions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(rows.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def wage_definitions() -> dict:
    import json

    from ..config import DATA_DIR

    path = DATA_DIR / "derived" / "nbs_wage_definitions.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def body_text(html: str) -> str:
    """Text of the release body without page chrome.  Release pages carry the
    article twice - a desktop copy ('txt-content') followed by a mobile copy
    ('mobile-content') - so the desktop copy is taken, up to where the mobile one starts."""
    i = html.find('class="txt-content"')
    if i < 0:
        return page_text(html)
    j = html.find('class="mobile-content', i)
    return page_text(html[html.index(">", i) + 1 : j if j >= 0 else len(html)])


# Period phrases that open a statement: a single month ("8月份", "2026年8月份") or a
# cumulative period ("1—8月份", "1—8月平均", "上半年", "一季度", "前三季度", "全年").
PERIOD_RE = re.compile(r"\d{1,2}\s*[—–-]\s*\d{1,2}\s*月|上半年|下半年|[一二三四]季度|前三季度|全年|\d{1,2}\s*月份")
HEADING_RE = re.compile(r"^[一二三四五六七八九十]+、")


def _period(s: str) -> str | None:
    kinds = {"month" if re.fullmatch(r"\d{1,2}\s*月份", m.group(0)) else "cumulative" for m in PERIOD_RE.finditer(s)}
    if not kinds:
        return None
    return kinds.pop() if len(kinds) == 1 else "ambiguous"


def _comparison(s: str) -> str | None:
    kinds = ({"mom"} if "环比" in s else set()) | ({"yoy"} if "同比" in s or "比上年同期" in s else set())
    if not kinds:
        return None
    return kinds.pop() if len(kinds) == 1 else "ambiguous"


def yoy_sentences(text: str, topic: str | None = None) -> list[dict]:
    """Sentences reporting THIS MONTH's year-on-year price changes, as
    {"text": the sentence verbatim, "yoy": its clauses that do so}.

    NBS names the period ("8月份" vs "1—8月份"/"1—8月平均"/"上半年"/"全年") and the
    comparison ("同比" year-on-year vs "环比" month-on-month) once, and what follows
    inherits both until they are named again: "1—7月份，全国居民消费价格同比上涨0.9%。
    分类别看，食品烟酒…价格同比下降0.2%" is still January-July cumulative, and in
    "核心CPI同比上涨0.8%，其中2月份同比上涨1.2%" only the second clause is February's.
    Both are therefore tracked clause by clause (clauses end at "，", "；" and "。"); a
    clause naming two periods or two comparisons is ambiguous, and so is what inherits
    from it, until a single one is named again.

    With ``topic`` (e.g. "居民消费价格"), only text inside that topic is kept: it starts
    at a sentence naming the topic and ends at the next numbered heading ("八、…") or
    sentence about producer prices that does not name it.  Used for the monthly economy
    releases, which cover CPI in one paragraph among many."""
    out: list[dict] = []
    period = comparison = None
    inside = topic is None
    for raw in text.split("。"):
        sentence = re.sub(r"\s+", "", raw)
        if topic is not None:
            if topic in sentence:
                inside = True
            elif HEADING_RE.match(sentence) or "工业生产者" in sentence:
                inside = False
        hits = []
        for clause in re.split(r"(?<=[，；])", sentence):
            period = _period(clause) or period
            comparison = _comparison(clause) or comparison
            if inside and period == "month" and comparison == "yoy" and "%" in clause:
                hits.append(clause.rstrip("，；"))
        if hits:
            out.append({"text": sentence + "。", "yoy": hits})
    return out


def write_cpi_quotes(snaps: list[tuple[Snapshot, str]]) -> None:
    """Verbatim year-on-year CPI sentences, per reference month, from the CPI release
    itself and from the monthly economy release (which names some items, e.g. grain,
    that the CPI release does not)."""
    import json

    from ..config import DATA_DIR

    rows = []
    for snap, title in snaps:
        html = snap.read().decode("utf-8", "replace")
        if m := CPI_TITLE.match(title):
            kind, period = "cpi", f"{m.group(1)}-{int(m.group(2)):02d}"
            sentences = yoy_sentences(body_text(html))
        elif is_economy_release(title) and HOURS_RE.search(page_text(html)):
            year, month = reference_month(html, page_text(html))
            kind, period = "economy", f"{year}-{month:02d}"
            sentences = yoy_sentences(body_text(html), topic="居民消费价格")
        else:
            continue
        if sentences:
            rows.append({"period": period, "kind": kind, "title": title, "url": snap.url,
                         "snapshot": snap.key, "sha256": snap.sha256, "sentences": sentences})
    path = DATA_DIR / "derived" / "nbs_cpi_yoy_sentences.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: (r["period"], r["kind"] != "cpi", r["snapshot"]))
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cpi_quotes() -> list[dict]:
    import json

    from ..config import DATA_DIR

    path = DATA_DIR / "derived" / "nbs_cpi_yoy_sentences.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def write_price_index(rows: list[dict]) -> None:
    import json

    from ..config import DATA_DIR

    path = DATA_DIR / "derived" / "nbs_price_release_index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "listing": LIST_URL,
        "note": "Every release on the NBS '最新发布' listing pages scanned in this run whose title contains 价格, 工资 or 收入 "
                "(the listing pages themselves are not archived).",
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
        if "价格" not in r["title"]:
            continue
        name = _re.sub(r"^\d{4}年|^\d{1,2}月份?|^[上中下]旬|\s", "", _re.sub(r"^\d{4}年\d{1,2}月(份|[上中下]旬)", "", r["title"]))
        kind = name[: name.index("价格") + 2] if "价格" in name else name
        g = groups.setdefault(kind, {"kind": kind, "count": 0, "first": r["date"], "last": r["date"], "example": r["url"]})
        g["count"] += 1
        g["first"] = min(g["first"], r["date"])
        g["last"] = max(g["last"], r["date"])
    dates = [r["date"] for r in idx["releases"] if "价格" in r["title"]]
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
    if (m := WAGE_TITLE.match(title)) or (m := WAGE_PART_TITLE.match(title)) or (m := LARGE_ENT_TITLE.match(title)):
        year = int(m.group(1))
        # Which averages the release must contain, from its title.
        want = (list(WAGE_RE) if WAGE_TITLE.match(title) else
                ["cn_wage_nonprivate" if m.group(2) == "非私营" else "cn_wage_private"] if WAGE_PART_TITLE.match(title) else [])
        for series in want:
            rx = WAGE_RE[series]
            hit = rx.search(text)
            if not hit:
                raise ValueError(f"{snapshot}: no match for {series}")
            value, increase, growth = int(hit.group(1)), int(hit.group(2)), float(hit.group(3))
            out.append(Obs(series, "CHN", str(year), value, snapshot, note=f"growth_pct={growth}"))
            # Kept apart from the direct series: validate.py checks it against the previous year's own release.
            out.append(Obs(f"{series}__implied_prev", "CHN", str(year - 1), value - increase, snapshot))
            # "名义增长2.8%，按可比口径增长2.6%": NBS flags a change in statistical coverage.
            if comp := COMPARABLE_RE.match(text, hit.end()):
                out.append(Obs(f"{series}__comparable_growth", "CHN", str(year), float(comp.group(1)), snapshot))
        if hit := POSITION_RE.search(text):
            for key, v in zip(POSITION_KEYS, hit.groups()):
                out.append(Obs(key, "CHN", str(year), int(v), snapshot))
        elif LARGE_ENT_TITLE.match(title):
            raise ValueError(f"{snapshot}: no large-enterprise wage sentence")
    elif m := MIGRANT_TITLE.match(title):
        year = int(m.group(1))
        hit = MIGRANT_RE.search(text)
        if not hit:
            raise ValueError(f"{snapshot}: no migrant-worker income sentence")
        value, increase, growth = int(hit.group(1)), int(hit.group(2)), float(hit.group(3))
        out.append(Obs("cn_migrant_monthly", "CHN", str(year), value, snapshot, note=f"growth_pct={growth}"))
        out.append(Obs("cn_migrant_monthly__implied_prev", "CHN", str(year - 1), value - increase, snapshot))
    elif is_economy_release(title):
        hit = HOURS_RE.search(text)
        if hit:
            year, month = reference_month(html, text)
            stated = economy_month(title)
            if stated is not None and stated != month:
                raise ValueError(f"{snapshot}: title says month {stated}, publication date implies {month}")
            if not re.search(rf"(?<!\d){month}\s*月份", text):
                raise ValueError(f"{snapshot}: publication date implies month {month}, but the text never mentions {month}月份")
            out.append(Obs("cn_weekly_hours_enterprise", "CHN", f"{year}-{month:02d}", float(hit.group(1)), snapshot))
    return out
