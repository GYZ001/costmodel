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
# For 2021 and 2022 NBS published the two urban-unit averages and the large-enterprise
# figures as separate releases, e.g. "2022年城镇非私营单位就业人员年平均工资114029元".
WAGE_PART_TITLE = re.compile(r"^(\d{4})年城镇(非私营|私营)单位就业人员年平均工资\d+元$")
LARGE_ENT_TITLE = re.compile(r"^(\d{4})年规模以上企业就业人员年平均工资情况$")
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

# "…年平均工资为 X 元，比上年增加（减少）Y 元，名义增长（下降）Z%" - wording varies slightly by
# year ("为 120698 元" vs "129441 元"; optional footnote markers).
_CHANGE = r"\s*元\s*，\s*比上年(增加|减少)\s*(\d+)\s*元\s*，\s*名义(增长|下降)\s*(?:\[\d+\])?\s*([\d.]+)\s*%"
WAGE_RE = {
    "cn_wage_nonprivate": re.compile(r"全国城镇非私营单位就业人员年平均工资\s*为?\s*(\d+)" + _CHANGE),
    "cn_wage_private": re.compile(r"全国城镇私营单位就业人员年平均工资\s*为?\s*(\d+)" + _CHANGE),
}
# Headline of the large-enterprise average, in the combined releases ("规模以上企业就业
# 人员年平均工资为98096元") and the separate 2021/2022 ones ("全国规模以上企业…为92492元").
LARGE_ENT_RE = re.compile(r"规模以上企业就业人员年平均工资\s*为\s*(\d+)\s*元")
# Inside the headline sentence: "…名义增长4.4%，按可比口径增长4.2%" (or 下降) - NBS flags a
# change in statistical coverage (the comparable basis is explained in the release's notes).
NOMINAL_RE = re.compile(r"名义(增长|下降)\s*(?:\[\d+\])?\s*([\d.]+)\s*%")
COMPARABLE_RE = re.compile(r"按可比口径\s*(?:\[\d+\])?\s*(增长|下降)\s*([\d.]+)\s*%")
POSITION_RE = re.compile(
    r"规模以上企业就业人员年平均工资为\s*(\d+)\s*元，其中，?\s*中层及以上管理人员\s*(\d+)\s*元，专业技术人员\s*(\d+)\s*元，"
    r"办事人员和有关人员\s*(\d+)\s*元，社会生产服务和生活服务人员\s*(\d+)\s*元，生产制造及有关人员\s*(\d+)\s*元"
)
POSITION_KEYS = ["cn_wage_large_ent", "cn_wage_large_ent_managers", "cn_wage_large_ent_professionals",
                 "cn_wage_large_ent_clerks", "cn_wage_large_ent_services", "cn_wage_large_ent_production"]
MIGRANT_RE = re.compile(r"农民工月均收入\s*为?\s*(\d+)\s*元\s*，\s*比上年(增加|减少)\s*(\d+)\s*元\s*，\s*(增长|下降)\s*([\d.]+)\s*%")
MIGRANT_DEF_RE = re.compile(r"(农民工月均收入[：:]指[^。]+。)")
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


def page_text(html: str, paragraphs: bool = False) -> str:
    """Visible text with whitespace collapsed; with ``paragraphs``, each paragraph (or
    other block) on its own line, so that a heading is never read as part of the
    sentence after it."""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    if paragraphs:
        text = re.sub(r"</(?:p|div|h\d|li|tr|td|th)\s*>|<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = INVISIBLE_RE.sub("", text.replace("&nbsp;", " ").replace("&emsp;", " "))
    if paragraphs:
        text = re.sub(r"[^\S\n]+", " ", text)
        return re.sub(r"\s*\n\s*", "\n", text).strip()
    return re.sub(r"\s+", " ", text)


def discover(f: Fetcher, pages: int = 64) -> list[Release]:
    seen: dict[str, Release] = {}
    for p in range(pages):
        url = LIST_URL + ("" if p == 0 else f"index_{p}.html")
        html = f.get_transient(url).decode("utf-8", "replace")
        for ym, tid, day, title in LINK_RE.findall(html):
            title = title.strip()
            if tid not in seen and (WAGE_TITLE.match(title) or WAGE_PART_TITLE.match(title) or LARGE_ENT_TITLE.match(title)
                                    or MIGRANT_TITLE.match(title) or is_economy_release(title)):
                seen[tid] = Release(f"{LIST_URL}{ym}/{tid}.html", f"nbs/release/{ym}/{tid}", title, day)
    return list(seen.values())


def collect(f: Fetcher) -> list[Obs]:
    snaps: list[tuple[Snapshot, str]] = []
    if f.offline:
        snaps = [(s, _title_of(s)) for s in f.committed("nbs/release/")]
    else:
        for rel in discover(f):
            # A published release does not change, so an existing snapshot is reused as is.
            snap = f.get(rel.key, rel.url, ext="html", check=_check_release(rel.title), immutable=True)
            snaps.append((snap, rel.title))
        # Releases that have moved beyond the listing pages scanned stay in the archive and
        # are still used (as the offline rebuild does).
        seen = {snap.key for snap, _t in snaps}
        snaps += [(snap, _title_of(snap)) for snap in f.committed("nbs/release/") if snap.key not in seen]
    out: list[Obs] = []
    for snap, title in snaps:
        out += parse_release(snap.read().decode("utf-8", "replace"), title, snap.key)
    write_wage_definitions(snaps)
    return out


# The release's own notes: "2、统计范围…" (or "2.统计范围…") up to the next numbered note.
SCOPE_RE = re.compile(r"2[、.]统计范围(.+?。)(?=3[、.])")
# Definitions quoted from a release, by where they sit in it: a sentence of the
# indicator notes ("指标解释"), and the footnote defining the comparable basis ("[2]可比口径是指…").
GROSS_RE = re.compile(r"工资总额是税前工资")
COMPARABLE_DEF_RE = re.compile(r"(\[\d+\])?(可比口径是指[^。]+。)")


def _excerpt(section: str, text: str, start: int, end: int) -> dict:
    """A verbatim piece of a release's text (whitespace removed), with where it sits."""
    return {"section": section, "text": text[start:end], "pos": start, "end": end}


def _sentence(text: str, i: int) -> tuple[int, int]:
    """The whole sentence around position i (from after the previous "。" to its own)."""
    return text.rfind("。", 0, i) + 1, text.index("。", i) + 1


def scope_series(sentence: str) -> list[str] | None:
    """Which series a sentence of a release's scope note is about, from the names NBS
    uses for them; None = all series of that release."""
    if "规模以上" in sentence:
        return ["cn_wage_large_ent"]
    if "非私营" in sentence:
        return ["cn_wage_nonprivate"]
    if "私营" in sentence:
        return ["cn_wage_private"]
    if "城镇" in sentence:
        return ["cn_wage_nonprivate", "cn_wage_private"]
    return None


def write_wage_definitions(snaps: list[tuple[Snapshot, str]]) -> None:
    """Title and NBS's own definitions of every wage and migrant-worker release, by
    snapshot, so that each figure is described by the release it comes from (coverage
    and wording change between years, and in 2021-2022 between releases)."""
    import json

    from ..config import DATA_DIR

    rows: dict[str, dict] = {}
    for snap, title in sorted(snaps, key=lambda st: st[0].key):
        m = WAGE_TITLE.match(title) or WAGE_PART_TITLE.match(title) or LARGE_ENT_TITLE.match(title) or MIGRANT_TITLE.match(title)
        if not m:
            continue
        row = {"title": title, "url": snap.url, "year": m.group(1)}
        text = re.sub(r"\s+", "", body_text(snap.read().decode("utf-8", "replace")))
        if MIGRANT_TITLE.match(title):
            hit = MIGRANT_DEF_RE.search(text)
            row["definition"] = _excerpt("指标解释", text, hit.start(1), hit.end(1)) if hit else None
        else:
            # A release about one measure (2021, 2022) describes only that measure.
            part = WAGE_PART_TITLE.match(title)
            only = (["cn_wage_nonprivate" if part.group(2) == "非私营" else "cn_wage_private"] if part
                    else ["cn_wage_large_ent"] if LARGE_ENT_TITLE.match(title) else None)
            row["scope"] = []
            if scope := SCOPE_RE.search(text):
                start = scope.start(1)
                for x in scope.group(1).split("。"):
                    if x:
                        row["scope"].append({**_excerpt("统计范围", text, start, start + len(x) + 1),
                                             "series": only or scope_series(x)})
                    start += len(x) + 1
            hit = GROSS_RE.search(text)
            row["gross"] = _excerpt("指标解释", text, *_sentence(text, hit.start())) if hit else None
            hit = COMPARABLE_DEF_RE.search(text)
            row["comparable"] = (_excerpt(f"注{hit.group(1) or ''}", text, hit.start(2), hit.end(2)) if hit else None)
        rows[snap.key] = row
    path = DATA_DIR / "derived" / "nbs_wage_definitions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


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
    j = html.find('class="mobile-content', i) if i >= 0 else -1
    body = html if i < 0 else html[html.index(">", i) + 1 : j if j >= 0 else len(html)]
    return page_text(body, paragraphs=True)


def _title_of(snap: Snapshot) -> str:
    m = re.search(r"<title>\s*([^<]*?)\s*(?:-\s*国家统计局)?\s*</title>", snap.read().decode("utf-8", "replace"))
    return m.group(1).strip() if m else ""


def _check_release(title: str):
    def check(body: bytes) -> None:
        if title not in body.decode("utf-8", "replace"):
            raise ValueError(f"release page does not contain its title {title!r}")

    return check


def _signed(hit: re.Match) -> tuple[int, int, float]:
    """(value, change on the previous year, growth %) from a WAGE_RE / MIGRANT_RE match,
    with the sign NBS's wording gives (增加/减少, 增长/下降)."""
    value, up, change, rise, pct = hit.groups()
    return int(value), int(change) * (1 if up == "增加" else -1), float(pct) * (1 if rise == "增长" else -1)


def _rate(hit: re.Match) -> float:
    """A NOMINAL_RE / COMPARABLE_RE match as a signed percentage."""
    rise, pct = hit.groups()
    return float(pct) * (1 if rise == "增长" else -1)


def _comparable(series: str, year: int, text: str, hit: re.Match, snapshot: str) -> list[Obs]:
    """The comparable-basis growth NBS states in the same sentence as a headline figure.
    A sentence that speaks of the comparable basis without a rate this parser reads is
    an error: the coverage change it flags must not be lost."""
    sentence = text[hit.start():text.find("。", hit.start())]
    comp = COMPARABLE_RE.search(sentence)
    if comp is None and "可比口径" in sentence:
        raise ValueError(f"{snapshot}: {series} sentence mentions 可比口径 but no rate was read: {sentence!r}")
    return [Obs(f"{series}__comparable_growth", "CHN", str(year), _rate(comp), snapshot)] if comp else []


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
            value, increase, growth = _signed(hit)
            out.append(Obs(series, "CHN", str(year), value, snapshot, note=f"growth_pct={growth}"))
            # Kept apart from the direct series: validate.py checks it against the previous year's own release.
            out.append(Obs(f"{series}__implied_prev", "CHN", str(year - 1), value - increase, snapshot))
            out += _comparable(series, year, text, hit, snapshot)
        # The figure is stated more than once (with the breakdown by position, and with its
        # growth); every statement must give the same value, and the growth comes from
        # whichever sentence states it.
        if hits := list(LARGE_ENT_RE.finditer(text)):
            if len({h.group(1) for h in hits}) != 1:
                raise ValueError(f"{snapshot}: large-enterprise wage stated with different values {sorted({h.group(1) for h in hits})}")
            with_growth = next((h for h in hits if NOMINAL_RE.search(text[h.start():text.find("。", h.start())])), hits[0])
            nominal = NOMINAL_RE.search(text[with_growth.start():text.find("。", with_growth.start())])
            out.append(Obs("cn_wage_large_ent", "CHN", str(year), int(hits[0].group(1)), snapshot,
                           note=f"growth_pct={_rate(nominal)}" if nominal else ""))
            out += _comparable("cn_wage_large_ent", year, text, with_growth, snapshot)
        elif LARGE_ENT_TITLE.match(title):
            raise ValueError(f"{snapshot}: no large-enterprise wage sentence")
        # By position (in a sentence only in the combined releases; its total is the
        # headline figure above, checked by the LARGE_ENT_RE statements agreeing).
        if hit := POSITION_RE.search(text):
            for key, v in zip(POSITION_KEYS[1:], hit.groups()[1:]):
                out.append(Obs(key, "CHN", str(year), int(v), snapshot))
    elif m := MIGRANT_TITLE.match(title):
        year = int(m.group(1))
        hit = MIGRANT_RE.search(text)
        if not hit:
            raise ValueError(f"{snapshot}: no migrant-worker income sentence")
        value, increase, growth = _signed(hit)
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
