"""Turn parsed observations into the dataset the website renders.

All arithmetic happens here (and is unit-tested), so the browser only displays
numbers and never derives new ones.  Every derived figure is computed from
inputs of the SAME period: a year's average wage is converted with that year's
average exchange rate and that year's average gold price, and compared with
that year's prices.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from .catalog import G20, US_ITEMS
from .config import GRAMS_PER_TROY_OUNCE
from .model import Obs, Store, annual_mean
from .sources import ilostat

WEEKS_PER_MONTH = 52 / 12  # 4.333…: converts weekly hours to monthly hours
# The earlier conversation converted Chinese annual wages to hourly with 250 days × 8 h.
# Shown only as that conversation's assumption; the site's own figures use NBS's survey hours.
ASSUMED_HOURS_CN = 2000
COHD_GROUPS = ["staples", "vegetables", "fruits", "animal", "legumes", "oils"]


@dataclass
class WageVariant:
    key: str
    label: str
    concept: str
    source: str  # human-readable source line
    monthly_lcu: float | None  # average (or median) monthly earnings
    hourly_lcu: float | None
    hours_week: float | None  # hours used for the hourly conversion (None when the source is hourly)
    method: str
    snapshots: list[str]
    caveat: str = ""
    restricted: bool = False  # coverage limited, as the publisher states (e.g. urban units, private sector only)
    currency: str | None = None  # currency the publisher states for the figure
    label_hourly: str | None = None  # label when the hourly figure is derived from a monthly one
    series_id: str = ""  # the publisher's series and the notes defining it (a change between years is a change of concept or source)
    source_id: str = ""  # publisher and survey, e.g. "ILOSTAT BA:463", "OECD", "NBS"
    series_key: str = ""  # publisher's series, e.g. "ILOSTAT ilo_monthly_mean@BA:463"
    notes_sig: list[str] = field(default_factory=list)  # labels of the notes that define what the figure measures
    quote: str = ""  # the publisher's own definitions, verbatim (caveat holds notes written by this project)


# --------------------------------------------------------------------------------------
# Gold
# --------------------------------------------------------------------------------------

def gold_tables(store: Store) -> dict:
    monthly = store.series("gold_usd_oz", "WLD")
    if not monthly:
        raise ValueError("no gold prices")
    years = sorted({p[:4] for p in monthly})
    annual = {}
    for y in years:
        m = annual_mean(monthly, y)
        if m:
            annual[y] = {"usd_oz": m[0], "usd_g": m[0] / GRAMS_PER_TROY_OUNCE}
    latest = max(monthly)
    return {
        "monthly": [[p, monthly[p].value] for p in sorted(monthly)],
        "annual": annual,
        "latest": {"period": latest, "usd_oz": monthly[latest].value, "usd_g": monthly[latest].value / GRAMS_PER_TROY_OUNCE},
    }


# --------------------------------------------------------------------------------------
# Currency units, proven year by year
#
# Every figure divides a number from one publisher by a number from another: a wage
# (ILOSTAT, OECD, NBS, BLS) by an exchange rate or a PPP (World Bank WDI), a gold
# price by a diet cost (World Bank food-price team).  The two must be in the SAME
# currency unit, and the exchange rate must be the one actually used for that year's
# money.  Redenominations, euro changeovers and multiple exchange-rate regimes break
# that silently, and no list of countries can be trusted to catch them all.
#
# L is the unit of WDI's local-currency series (national accounts, PPP), one per
# economy.  The exchange rate F and the PPP P are proven to be in L only by identities
# inside the World Bank's own data:
#
#   F ~ L  WDI official exchange rate = WDI GDP in LCU ÷ GDP in US$ (the factor the
#          World Bank itself applies to that year's LCU figures)
#   P ~ L  WDI household PPP = WDI household consumption in LCU ÷ in international $
#   P ~ F  in the ICP benchmark year (2021), where WDI lacks those totals: WDI household
#          PPP ÷ WDI exchange rate = ICP's household price level relative to the US (a
#          ratio without currency unit, so it cannot share a unit error with WDI)
#
# or, in a year without any of these, by carrying over an adjacent year's proof (in
# either direction) when the value moved by less than MAX_FACTOR: its unit cannot have
# changed in between.
#
# Other inputs are then attached to a proven F or P:
#
#   C ~ P  healthy-diet cost in LCU ÷ the same cost in PPP $ = WDI PPP
#   W ~ F  ILOSTAT wage in LCU ÷ WDI exchange rate = ILOSTAT's own US$ figure
#   W ~ P  ILOSTAT wage in LCU ÷ WDI PPP = ILOSTAT's own PPP figure
#   W ~ L  OECD constant-price wage in national currency ÷ the same in US$ PPP =
#          WDI PPP of OECD's base year; or the currency a publisher states (OECD unit
#          code, NBS 元, BLS dollars) equals a currency proven for L
#
# A publisher's own conversion only shows that it divided by the same factor; it can
# never prove F or P, and when a wage agrees both with a factor proven in L and with
# one proven NOT in L (ILOSTAT divided a colón wage by a dollar-based PPP), the wage's
# unit is undetermined and it is left out.  The currency code of L is what ILOSTAT's
# currency notes (T30) say for records attached to L, or OECD's unit when its PPP
# identity holds.  Only figures attached to L are then compared for their time unit
# (_check_time_units), so that a currency difference is never mistaken for a time-unit
# error.  A figure is computed only when all its inputs are attached to L; everything
# else is left out with the reason and the numbers (dataset["exclusions"]).
# --------------------------------------------------------------------------------------

# A currency-unit mismatch shows up as a fixed conversion factor.  The smallest one
# among the redenominations and euro changeovers since 2000 is Latvia's
# 1 EUR = 0.702804 LVL (×1.42); every other is ×1.7 or more (Cyprus ×1.71, BGN ×1.96,
# HRK ×7.53, redenominations ×5 to ×1,000,000).  So two numbers whose ratio lies
# within ×/÷1.4 cannot differ by a currency unit, and anything outside cannot be
# trusted to be in the same unit.  Differences inside the bound are not unit errors:
# PPP vintages, fiscal-year conversion (the World Bank converts fiscal-year national
# accounts at fiscal-year average rates: Australia, Egypt, …), publishers' own rates.
# The bound proves a UNIT, not that two exchange rates are the same rate: where the
# official rate and the factor the World Bank applied to GDP differ, both are published
# (fx, fx_gdp_factor) and the page states the difference.
MAX_FACTOR = 1.4

# The smallest confusion of time units is a week for a month (×52/12 = ×4.33).
# - The same figure in two time units (one survey's monthly and hourly mean) implies the
#   hours worked; against that survey's measured hours a ratio nearer to ×1 than to
#   ×4.33 (in log terms: within ×/÷√4.33 ≈ 2.08) means the same time unit.  The same
#   bound compares two measurements of weekly hours.
# - Figures of different concepts (another survey, mean vs median, OECD's full-time-
#   equivalent wage) can differ by a factor of two or more for the same economy and
#   year; a gap smaller than a whole time-unit factor (×4.33) may be such a difference
#   of concept, so only a larger one shows a time-unit or scale error.
TIME_FACTOR = math.sqrt(52 / 12)
UNIT_GAP = 52 / 12


def same_unit(a: float, b: float, bound: float = MAX_FACTOR) -> bool:
    return 1 / bound <= a / b <= bound


def factor(a: float, b: float) -> str:
    r = a / b
    return f"×{r:.3g}" if r >= 1 else f"÷{1 / r:.3g}"


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, a: str) -> str:
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)

    def linked(self, a: str, b: str = "L") -> bool:
        return self.find(a) == self.find(b)


@dataclass
class IloRecord:
    """One ILOSTAT earnings observation with what its note codes say about it."""
    series: str  # e.g. "ilo_monthly_mean@BA:595"
    base: str  # e.g. "ilo_monthly_mean"
    source: str  # ILOSTAT source id
    unit: str  # "hour" | "month"
    concept: str  # "mean" | "median" (from note T8 when present)
    obs: Obs
    usd: Obs | None
    ppp: Obs | None
    unusable: str | None  # what ILOSTAT's own notes or status say makes the value unusable
    restricted: bool  # coverage limited (area, population, establishment size, sector, activity, group, working time)
    currency: str | None
    signature: tuple  # concept-defining notes; a change between years breaks a series
    break_in_series: bool
    status: str | None  # ILOSTAT's observation status label, if any
    rejected: str | None = None  # left out by this project's magnitude / time-unit checks (with the numbers)
    unsure: str | None = None  # kept, but its time unit could not be confirmed against another source

    @property
    def usable(self) -> bool:
        return not (self.unusable or self.rejected)


# ILOSTAT note types that define what an earnings figure measures (not just where it
# comes from): central tendency, value type, gross/net, job coverage, reference period,
# coverage of area / population / establishment size / institutional sector / economic
# activity / reference group / working time, working-time concept, components of
# earnings, minimum-wage type, employment definition.
COVERAGE_NOTES = ("S4", "S5", "S6", "S7", "S8", "S9", "T12")
CONCEPT_NOTES = ("T8", "T9", "T10", "T11", "T33", "T34", "S3", *COVERAGE_NOTES, "I19", "I20")


def restricts(prefix: str, label: str) -> bool:
    """Whether a coverage note limits a figure to part of a country's employees, read from
    ILOSTAT's label.  Every area, establishment-size, sector, activity, reference-group,
    population or working-time note does, except those stating the full scope - the
    whole national territory, all employees (or all employment), full- and part-time
    workers, full-time equivalents (which re-weight all employees rather than select
    some), establishments of every size (the smaller ones by a sample) - and the
    exclusions every household survey has (people in institutions or collective
    quarters, armed forces), which do not change who the figure is about."""
    text = label.split(":", 1)[-1].strip().lower()
    if prefix == "S4":
        return not text.startswith("total national")
    if prefix == "S9":
        return not (text == "employees" or text.startswith("total"))
    if prefix == "T12":
        return not ("equivalent" in text or ("full" in text and "part" in text))
    if prefix == "S6":
        return "a sample of those with less than" not in text
    if prefix == "S5":
        rest = text
        for frame in ("institutional population", "collective living quarters", "armed forces", "conscripts"):
            rest = rest.replace(frame, " ")
        return bool(set(re.findall(r"[a-z]+", rest)) - {"excluding", "both", "and", "or", "persons", "in"})
    return True


def ilo_record(store: Store, series: str, obs: Obs, ilo_dic: dict) -> IloRecord:
    base, source = series.split("@", 1)
    unit = "hour" if base.startswith("ilo_hourly") else "month"
    concept = "median" if base.endswith("_median") else "mean"
    unusable = None
    lab = lambda c: ilostat.label(c, ilo_dic)  # noqa: E731
    for c in ilostat.note_of(obs, "T8"):
        if lab(c).endswith(": Median"):
            concept = "median"
        elif lab(c).endswith(": Mean") or lab(c).endswith(": Weighted mean"):
            concept = "mean"
        else:  # minimum wages and other measures are not average earnings
            unusable = f"ILOSTAT 注明该值为“{lab(c)}”，不是平均或中位工资"
    for c in ilostat.note_of(obs, "I19"):
        unusable = f"ILOSTAT 注明该值为“{lab(c)}”，是最低工资，不是平均或中位工资"
    for c in ilostat.note_of(obs, "T9"):
        if not lab(c).endswith("Nominal values"):
            unusable = f"ILOSTAT 注明该值为“{lab(c)}”（不是当年名义值），不能按当年汇率和金价换算"
    for c in ilostat.note_of(obs, "T7"):
        if not lab(c).endswith("Per hour" if unit == "hour" else "Per month"):
            unusable = f"ILOSTAT 注明该值的时间单位为“{lab(c)}”，与指标（{'每小时' if unit == 'hour' else '每月'}）不符"
    st = store.get(f"{base}__status@{source}", obs.area, obs.period)
    status = ilostat.status_label(st.note, ilo_dic) if st else None
    if status and "reliab" in status.lower():  # "Unreliable" / "Low reliability"
        unusable = f"ILOSTAT 将该值的观测状态标为“{status}”"
    elif status and "real value" in status.lower():
        unusable = f"ILOSTAT 将该值的观测状态标为“{status}”（不是当年名义值），不能按当年汇率和金价换算"
    restricted = any(restricts(p, lab(c)) for p in COVERAGE_NOTES for c in ilostat.note_of(obs, p))
    signature = tuple(sorted(c for c in ilostat.codes(obs) if c.split(":", 1)[0] in CONCEPT_NOTES))
    return IloRecord(
        series=series, base=base, source=source, unit=unit, concept=concept, obs=obs,
        usd=store.get(f"{base}_usd@{source}", obs.area, obs.period),
        ppp=store.get(f"{base}_ppp@{source}", obs.area, obs.period),
        unusable=unusable, restricted=restricted, currency=ilostat.currency(obs, ilo_dic),
        signature=signature, break_in_series=bool(ilostat.note_of(obs, "I11")) or (st is not None and st.note == "B"),
        status=status,
    )


def ilo_note_labels(codes: list[str], ilo_dic: dict) -> list[str]:
    """ILOSTAT's own labels for note codes (English, verbatim), coverage notes first, then
    remarks, then the rest; the currency note (shown separately) and unlabelled codes
    are left out."""
    def order(c: str) -> int:
        p = c.split(":", 1)[0]
        return 0 if p in COVERAGE_NOTES else 1 if p == "I13" else 2
    labels = [(c, ilostat.label(c, ilo_dic)) for c in sorted(codes, key=order) if c.split(":", 1)[0] != "T30"]
    return list(dict.fromkeys(lab for c, lab in labels if lab and lab != c and lab != "None"))


def ilo_notes(rec: IloRecord, ilo_dic: dict) -> str:
    """All of ILOSTAT's notes on a figure, plus its observation status."""
    labels = ilo_note_labels(ilostat.codes(rec.obs), ilo_dic) + ([f"Observation status: {rec.status}"] if rec.status else [])
    return "；".join(labels)


HOURS_IN_MONTH = 31 * 24  # 744: no monthly wage can be earned in more hours than a month has
HOURS_IN_WEEK = 7 * 24


@dataclass
class _Point:
    """A wage figure taking part in the time-unit check, with its value on a monthly basis."""
    unit: str  # "hour" | "month"
    concept: str
    value: float
    source: str  # ILOSTAT source id, or "OECD"
    rec: IloRecord | None  # None for OECD's reference figure
    monthly: float | None  # value on a monthly basis (hourly × weekly hours × 52/12), if it can be put on one
    desc: str  # how the figure is described in reasons
    own_hours: bool = True  # the monthly basis uses the same survey's hours (False: other sources' hours)


Jump = Callable[[IloRecord], tuple[float, str] | None]


def _check_time_units(points: list[_Point], jump: Jump) -> None:
    """Figures of one economy-year, all proven to be in the same currency unit, must
    agree on the time unit and scale.  Pairs are compared on a monthly basis, and only
    where a time-unit or scale error can be told from a difference of concept:

    - one survey's monthly and hourly figure of one central tendency: monthly ÷ hourly
      must lie between 1 and the 744 hours a month has, and agree with the survey's own
      measured hours within TIME_FACTOR (with other sources' hours, within UNIT_GAP);
    - the same central tendency (mean with mean, median with median) from different
      sources, OECD's full-time-equivalent wage included.  Within TIME_FACTOR (closer to
      the same time unit than to a week-for-month mix-up) the two vouch for each other;
      UNIT_GAP or more apart (a whole week-month factor) they contradict each other; in
      between, a difference of concept and a time-unit error cannot be told apart, and a
      figure no other source vouches for is kept with that said.  Means and medians are
      not compared across sources: their ratio depends on how skewed pay is and can
      itself exceed a time-unit factor.

    Only another source can vouch for a figure's scale: one survey's monthly and hourly
    figures come from the same data and share any scale error.  A figure that disagrees
    with one that another source vouches for (or with OECD's reference, whose time unit
    is explicit: an annual wage), and that no other source vouches for, is left out.
    When figures only contradict each other, each disagreeing pair is decided on its own
    gap: the one whose own series also jumps by at least half that gap (in log terms)
    while the other's does not is the wrong one.  Whatever stays undecided is left out
    on both sides - the data cannot say which is wrong.  Verdicts are taken on the same
    evidence for all, then applied."""
    disputes: dict[int, list[tuple[_Point, float, str]]] = defaultdict(list)
    vouched: dict[int, bool] = defaultdict(bool)
    unsure: dict[int, list[str]] = defaultdict(list)

    def note(p: _Point, q: _Point, gap: float, why: str) -> None:
        disputes[id(p)].append((q, gap, why))
        disputes[id(q)].append((p, gap, why))

    for i, p in enumerate(points):
        for q in points[i + 1:]:
            if p.rec is None and q.rec is None:
                continue
            if p.source == q.source and p.concept == q.concept and p.unit != q.unit:
                m, h = (p, q) if p.unit == "month" else (q, p)
                implied = m.value / h.value
                if not 1 <= implied <= HOURS_IN_MONTH:
                    note(p, q, implied / HOURS_IN_MONTH if implied > HOURS_IN_MONTH else 1 / implied,
                         f"{m.desc} ÷ {h.desc} = 每月 {implied:,.0f} 小时，不在 1 到 {HOURS_IN_MONTH} 小时（一个月的总小时数）之间")
                elif h.monthly is not None:
                    gap = max(m.value / h.monthly, h.monthly / m.value)
                    if (gap > TIME_FACTOR) if h.own_hours else (gap >= UNIT_GAP):
                        note(p, q, gap,
                             f"{h.desc}与{m.desc}相差 {factor(h.monthly, m.value)}"
                             + ("（同一调查的两种时间单位按其实测工时应在 ×/÷2.08 以内）" if h.own_hours else
                                "（按其他来源的工时折算，达到 ×/÷4.33，即一个“周”与“月”之差）"))
            elif p.source != q.source and p.concept == q.concept and p.monthly is not None and q.monthly is not None:
                gap = max(p.monthly / q.monthly, q.monthly / p.monthly)
                if gap <= TIME_FACTOR:
                    vouched[id(p)] = vouched[id(q)] = True
                elif gap >= UNIT_GAP:
                    note(p, q, gap, f"{p.desc}与{q.desc}相差 {factor(p.monthly, q.monthly)}（达到 ×/÷4.33，即一个“周”与“月”之差）")
                else:
                    for a, b in ((p, q), (q, p)):
                        unsure[id(a)].append(f"与{b.desc}相差 {factor(a.monthly, b.monthly)}")
    trusted = lambda q: q.rec is None or vouched[id(q)]  # noqa: E731
    out: dict[int, str] = {}
    for p in points:
        if p.rec is None or not disputes[id(p)] or vouched[id(p)]:
            continue
        against = disputes[id(p)]
        why = "；".join(dict.fromkeys(t for _q, _g, t in against[:2]))
        if any(trusted(q) for q, _g, _t in against):
            out[id(p)] = f"{why}；对照的数值有其他来源佐证（或是 OECD 按年薪发布的参照），该数值没有，因此判断是该数值有误"
            continue
        mine = jump(p.rec)
        verdicts = []
        for q, gap, _t in against:
            theirs = jump(q.rec)
            half = math.log(gap) / 2
            p_odd, q_odd = mine is not None and mine[0] >= half, theirs is not None and theirs[0] >= half
            verdicts.append((p_odd, q_odd, theirs))
        if all(q_odd and not p_odd for p_odd, q_odd, _t in verdicts):
            continue  # the figures it contradicts are the odd ones and are left out themselves
        if any(p_odd and not q_odd for p_odd, q_odd, _t in verdicts):
            other = ("对照的数值没有" if all(t is not None for _p, _q, t in verdicts)
                     else "对照的数值没有相邻年份可核对")
            out[id(p)] = f"{why}；该数值与同一来源相邻年份也相差同一量级（{mine[1]}），{other}，因此判断是该数值有误"
        else:
            out[id(p)] = f"{why}；仅凭这些数无法判断哪一个有误，一并不用"
    # Whatever still contradicts each other after the verdicts is undecided: leave out both.
    decided = set(out)
    for p in points:
        if p.rec is None or id(p) in decided or vouched[id(p)]:
            continue
        for q, _g, t in disputes[id(p)]:
            if q.rec is None or id(q) not in decided:
                out[id(p)] = f"{t}；仅凭这些数无法判断哪一个有误，一并不用"
                break
    for p in points:
        if p.rec is None:
            continue
        if id(p) in out:
            p.rec.rejected = out[id(p)]
        elif unsure[id(p)] and not vouched[id(p)]:
            p.rec.unsure = ("；".join(unsure[id(p)]) + "：大于同一时间单位的数值通常的差异（×/÷2.08），又不到一个“周”与“月”之差（×/÷4.33），"
                            "可能是口径不同，也可能是时间单位有误，无法确认")


def _wage_scope(rec: IloRecord) -> str:
    """How an ILOSTAT record is named in the exclusions: by time unit and by the central
    tendency ILOSTAT's note gives it (an indicator named "mean" can carry a median)."""
    return f"wage:ilo_{'hourly' if rec.unit == 'hour' else 'monthly'}_{rec.concept}"


class UnitGraph:
    def __init__(self, store: Store, ilo_dic: dict, years: list[str], meta: dict):
        self.store, self.ilo_dic, self.years = store, ilo_dic, years
        self.log: list[dict] = []
        self._areas: dict[str, dict] = {}
        self._ilo_code = self._match_ilo_areas(meta)
        self._icp_code = icp_codes(store, meta)
        self.level_bounds = self._level_bounds()

    # ---- bookkeeping
    def _exclude(self, area: str, year: str, scope: str, detail: str, kind: str) -> None:
        """kind: unit (cannot be shown to be in the same currency unit), identity (an
        identity fails although the unit is the same, cause unknown), missing (the
        publisher has no value), notes (by the publisher's own notes not a nominal
        average or median wage of the year, or its status is unreliable), check (fails
        this project's magnitude, time-unit or hours checks), area."""
        self.log.append({"area": area, "year": year, "scope": scope, "kind": kind, "detail": detail})

    def _match_ilo_areas(self, meta: dict) -> dict[str, str]:
        """ILOSTAT economy codes are ISO3 except a few (Kosovo is KOS, WDI uses XKX).
        Codes not in WDI's list are matched by the economy's name; any still unmatched
        is logged rather than silently dropped."""
        ilo_areas = sorted({a for (s, a, _p) in self.store.items if s.startswith("ilo_")})
        names = {info["name_en"]: iso for iso, info in meta.items() if info.get("is_economy")}
        out = {}
        for code in ilo_areas:
            if meta.get(code, {}).get("is_economy"):
                continue
            name = self.ilo_dic.get("ref_area", {}).get(code)
            if name in names:
                out[names[name]] = code
            elif not meta.get(code):  # WDI aggregates are not economies: nothing to log
                self._exclude(code, "全部年份", "area",
                              f"ILOSTAT 的地区代码 {code}（{name or '无名称'}）不在世界银行经济体名录中，按名称也无法对应", "area")
        return out

    def ilo_area(self, area: str) -> str:
        return self._ilo_code.get(area, area)

    def ilo_records(self, area: str) -> dict[str, list[IloRecord]]:
        """By year, every ILOSTAT earnings record of the economy (all indicators and sources)."""
        src = self.ilo_area(area)
        out: dict[str, list[IloRecord]] = defaultdict(list)
        for series in self.store.series_names(src, "ilo_"):
            base = series.split("@", 1)[0]
            if base.endswith(("_usd", "_ppp", "__status")) or base == "ilo_weekly_hours":
                continue
            for y, o in self.store.series(series, src).items():
                out[y].append(ilo_record(self.store, series, o, self.ilo_dic))
        return out

    # ---- hours
    def _hours(self, area: str) -> tuple[dict[str, dict[str, float]], list[tuple[str, str]]]:
        """Weekly hours that can be used, by year and source ("OECD" for OECD's usual
        hours of full-time employees), and the reasons for those that cannot.  An
        ILOSTAT value must be a possible number of hours in a week, and agree within
        TIME_FACTOR with at least one other source's possible hours of the same year
        (OECD's included) - hours concepts (actual or usual, all or full-time workers)
        differ by far less than a time-unit factor.  Only where no other source has that
        year are the same series' nearest possible years used instead (they would share
        a scale error that persists across years, so they never outvote another source).
        A value that agrees with none of them cannot be confirmed and is not used."""
        src = self.ilo_area(area)
        ilo = {s.split("@", 1)[1]: self.store.series(s, src) for s in self.store.series_names(src, "ilo_weekly_hours@")}
        oecd = {y: o.value for y, o in self.store.series("oecd_usual_weekly_hours_ft", area).items()}
        out: dict[str, dict[str, float]] = defaultdict(dict)
        bad: list[tuple[str, str]] = []
        for y, v in oecd.items():
            out[y]["OECD"] = v
        possible = {s: {y: o.value for y, o in series.items() if 0 < o.value <= HOURS_IN_WEEK} for s, series in ilo.items()}
        for s, series in ilo.items():
            for y, o in sorted(series.items()):
                v = o.value
                if y not in possible[s]:
                    bad.append((y, f"ILOSTAT {s} 每周工时 {v:g} 小时，不可能（一周只有 {HOURS_IN_WEEK} 小时），不使用"))
                    continue
                others = [(f"{t} {possible[t][y]:g}", possible[t][y]) for t in sorted(possible) if t != s and y in possible[t]]
                others += [(f"OECD {oecd[y]:g}", oecd[y])] if y in oecd else []
                if not others:
                    ys = sorted(possible[s])
                    i = ys.index(y)
                    others = [(f"{n} 年 {possible[s][n]:g}", possible[s][n]) for n in ys[max(0, i - 1):i + 2] if n != y]
                if others and not any(same_unit(v, w, TIME_FACTOR) for _d, w in others):
                    bad.append((y, f"ILOSTAT {s} 每周工时 {v:g} 小时，与可对照的工时（{'、'.join(d for d, _w in others)}）都相差 ×/÷2.08 以上，"
                                   "无法确认其时间单位或数量级，不使用"))
                    continue
                out[y][s] = v
        return out, bad

    def _time_check(self, area: str, year: str, recs: list[IloRecord], oecd_monthly: float | None,
                    hours: dict[str, float], jump: Jump) -> None:
        def monthly_hours(source: str) -> tuple[float, str, bool] | None:
            if source in hours:
                return hours[source] * WEEKS_PER_MONTH, f"同一调查实测每周 {hours[source]:g} 小时", True
            if hours:
                vals = sorted(hours.values())
                mid = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
                return mid * WEEKS_PER_MONTH, (f"该年其他来源每周工时的中位数 {mid:g} 小时"
                                               + ("（含 OECD 全职雇员通常工时）" if "OECD" in hours else "")), False
            return None

        cname = {"mean": "平均", "median": "中位"}
        points = []
        for r in recs:
            what = f"ILOSTAT {r.source} {cname[r.concept]}{'时薪' if r.unit == 'hour' else '月薪'} {r.obs.value:,.6g}"
            if r.unit == "month":
                points.append(_Point("month", r.concept, r.obs.value, r.source, r, r.obs.value, what))
            else:
                h = monthly_hours(r.source)
                points.append(_Point("hour", r.concept, r.obs.value, r.source, r, r.obs.value * h[0] if h else None,
                                     what + (f"（按{h[1]}折合月薪 {r.obs.value * h[0]:,.6g}）" if h else ""), h[2] if h else True))
        # Magnitude: a month's pay must lie between a week's worth of household consumption
        # per head and a year's worth of GDP per head - beyond either, the figure is most
        # likely a weekly or an annual one (the week/month and month/year factors).  The
        # verdict covers every figure of that survey in that time unit (mean and median
        # share it).
        s = self.store
        pop = s.get("population", area, year)
        gdp, hfce = s.get("gdp_lcu", area, year), s.get("hfce_lcu", area, year)
        top = gdp.value / pop.value if gdp and pop else None
        floor = hfce.value / pop.value / 12 / WEEKS_PER_MONTH if hfce and pop else None
        groups: dict[tuple[str, str], str] = {}
        for p in points:
            if p.monthly is None:
                continue
            if top is not None and p.monthly > top:
                groups.setdefault((p.source, p.unit), f"{p.desc} 超过该年人均全年 GDP（{top:,.6g}），一个月的工资多于全年人均产出，"
                                                      "最可能是年薪被标成了月薪")
            elif floor is not None and p.monthly < floor:
                groups.setdefault((p.source, p.unit), f"{p.desc} 不到该年人均一周的居民消费（{floor:,.6g}），"
                                                      "一个月的工资少于一周的人均消费，最可能是周薪或数量级有误")
        for p in points:
            if (p.source, p.unit) in groups:
                p.rec.rejected = groups[(p.source, p.unit)] + "；该调查同一时间单位的数字（平均数和中位数）时间单位或数量级都无法确定，一并不用"
        points = [p for p in points if p.rec.rejected is None]
        if oecd_monthly is not None:
            points.append(_Point("month", "mean", oecd_monthly, "OECD", None, oecd_monthly,
                                 f"OECD 全职当量平均年薪 ÷ 12 = {oecd_monthly:,.6g}"))
        _check_time_units(points, jump)

    # ---- continuity of a series
    YARDSTICKS = (("hfce_lcu", "人均居民消费"), ("gdp_lcu", "人均 GDP"))

    def nominal_growth(self, area: str, y0: str, y1: str, gdp: bool = True) -> tuple[float, str] | None:
        """Growth of nominal income per head from y0 to y1, in WDI's local-currency
        series: household consumption per head, or GDP per head where WDI has no
        household consumption for both years."""
        g = self._growths(area, y0, y1)
        for series, what in self.YARDSTICKS[:2 if gdp else 1]:
            if series in g:
                return g[series], what
        return None

    def _growths(self, area: str, y0: str, y1: str) -> dict[str, float]:
        s = self.store
        p0, p1 = s.get("population", area, y0), s.get("population", area, y1)
        out = {}
        for series, _what in self.YARDSTICKS:
            a, b = s.get(series, area, y0), s.get(series, area, y1)
            if p0 and p1 and a and b and a.value > 0 and b.value > 0:
                out[series] = (b.value / p1.value) / (a.value / p0.value)
        return out

    def _level_bounds(self) -> dict[str, dict[int, float]]:
        """How far a wage series can move against nominal income per head without a
        change in what it measures, by yardstick (household consumption or GDP per head)
        and by number of years apart: the widest such move seen in OECD's harmonised
        average-wage series (same currency) over that many years or fewer, in the archive."""
        widest: dict[str, dict[int, float]] = {series: {} for series, _w in self.YARDSTICKS}
        for area in sorted(self.store.areas("oecd_avg_annual_wage")):
            w = self.store.series("oecd_avg_annual_wage", area)
            ys = sorted(w)
            for i, y in enumerate(ys):
                for n in ys[i + 1:]:
                    if w[n].note != w[y].note:
                        break
                    for series, g in self._growths(area, y, n).items():
                        k = int(n) - int(y)
                        r = abs(math.log((w[n].value / w[y].value) / g))
                        widest[series][k] = max(widest[series].get(k, 0.0), r)
        out: dict[str, dict[int, float]] = {}
        for series, by_k in widest.items():
            running, out[series] = 0.0, {}
            for k in sorted(by_k):
                running = max(running, by_k[k])
                out[series][k] = math.exp(running)
        return out

    def level_bound(self, series: str, years_apart: int) -> float | None:
        """The bound for a span (the widest OECD move over that many years or fewer;
        beyond the longest span in the archive, the widest of all)."""
        b = self.level_bounds.get(series) or {}
        spans = [k for k in b if k <= years_apart]
        return b[max(spans)] if spans else (b[min(b)] if b else None)

    def shift(self, area: str, y0: str, v0: float, y1: str, v1: float, same_concept: bool = True) -> tuple[bool | None, str]:
        """Whether a change from y0 to y1 within one series is in line with nominal income
        per head.  For the same concept in both years: within the widest move OECD's own
        same-concept wage series made against the same yardstick over as many years; a
        move is flagged only if it is out of line with every yardstick available
        (household consumption and GDP per head), so that a break in one yardstick is not
        read as one in the wage.  Across a noted change of concept or a break: within
        TIME_FACTOR, beyond which the change may as well be a different time unit."""
        g = self._growths(area, y0, y1)
        k = int(y1) - int(y0)
        bounds = {series: self.level_bound(series, k) if same_concept else TIME_FACTOR for series in g}
        g = {series: v for series, v in g.items() if bounds[series] is not None}
        if not g:
            return None, (f"{y0}→{y1} 年缺少世界银行的名义人均收入数据，或档案中没有 OECD 同口径工资可用来确定变化幅度的上限，无法核对")
        r = v1 / v0
        parts, flags = [], []
        for series, what in self.YARDSTICKS:
            if series not in g:
                continue
            bound = bounds[series]
            flags.append(not same_unit(r, g[series], bound))
            parts.append(f"同期{what}（名义）{factor(g[series], 1.0)}"
                         + (f"，OECD 同口径工资 {k} 年内相对它的最大偏离 ×/÷{bound:.2f}" if same_concept else ""))
        detail = (f"同一来源 {y0}→{y1} 年 {factor(v1, v0)}，" + "；".join(parts)
                  + ("" if same_concept else "；两年的口径注释不同或注明序列中断，相差超过 ×/÷2.08 时可能是口径变化，也可能是时间单位不同"))
        return (not all(flags)), detail


    def _neighbours(self, rec: IloRecord, ilo: dict[str, list[IloRecord]], graphs: dict[str, _UnionFind],
                    final: bool) -> list[IloRecord]:
        """The nearest earlier and later records of rec's series that are themselves
        usable and attached to L in their own year (so in the same proven currency);
        with final=False, before the time-unit checks of other years are applied."""
        def ok(r: IloRecord) -> bool:
            g = graphs.get(r.obs.period)
            return bool(g and g.linked(f"ilo:{r.series}")) and not r.unusable and (not final or r.rejected is None)
        series = sorted((r for recs in ilo.values() for r in recs if r.series == rec.series), key=lambda r: r.obs.period)
        before = [r for r in series if r.obs.period < rec.obs.period and ok(r)]
        after = [r for r in series if r.obs.period > rec.obs.period and ok(r)]
        return before[-1:] + after[:1]

    def series_consistent(self, area: str, rec: IloRecord, final: bool = True) -> tuple[bool | None, str]:
        """rec against its series' nearest usable years: True if every one agrees, False
        if one does not (with the change), None if none can be checked."""
        a = self.area(area)
        return self._consistent(area, rec, a["ilo"], a["years"], final)

    def _consistent(self, area, rec, ilo, graphs, final) -> tuple[bool | None, str]:
        verdicts = []
        for n in self._neighbours(rec, ilo, graphs, final):
            first, second = sorted([n, rec], key=lambda r: r.obs.period)
            same = first.signature == second.signature and not second.break_in_series
            verdicts.append(self.shift(area, first.obs.period, first.obs.value, second.obs.period, second.obs.value, same))
        if any(v[0] is False for v in verdicts):
            return False, "；".join(v[1] for v in verdicts if v[0] is False)
        if verdicts and all(v[0] for v in verdicts):
            return True, ""
        return None, ""

    def _jump(self, area, ilo, graphs) -> Jump:
        """For the time-unit tie-break: the largest move (in log terms) of a record against
        its series' nearest usable years, relative to nominal income per head."""
        def jump(rec: IloRecord) -> tuple[float, str] | None:
            out = None
            for n in self._neighbours(rec, ilo, graphs, final=False):
                first, second = sorted([n, rec], key=lambda r: r.obs.period)
                g = self.nominal_growth(area, first.obs.period, second.obs.period)
                if g is None:
                    continue
                size = abs(math.log((second.obs.value / first.obs.value) / g[0]))
                if out is None or size > out[0]:
                    out = (size, f"{first.obs.period}→{second.obs.period} 年 {factor(second.obs.value, first.obs.value)}，"
                                 f"同期{g[1]}（名义）{factor(g[0], 1.0)}")
            return out
        return jump

    # ---- per economy
    def area(self, area: str) -> dict:
        if area not in self._areas:
            self._areas[area] = self._build(area)
        return self._areas[area]

    def year(self, area: str, year: str) -> _UnionFind:
        return self.area(area)["years"].get(year) or _UnionFind()

    def currency(self, area: str) -> str | None:
        codes = self.area(area)["codes"]
        return next(iter(codes)) if len(codes) == 1 else None

    def _prove(self, values: dict[str, float], direct: dict[str, tuple[bool | None, str]],
               failed: str) -> dict[str, tuple[bool | None, str, str]]:
        """Year-by-year verdict on whether a factor (F or P) is in L, as (verdict, detail,
        kind): that year's identity, or else an adjacent year's proof carried over when the
        value moved by less than MAX_FACTOR (first forwards, then backwards).

        direct[y] holds the identity's verdict and numbers (or why it cannot be checked).
        A year whose identity fails although its value is linked to a proven year by
        year-to-year moves within MAX_FACTOR cannot be in another unit (the premise of the
        carry-over): the failure has another cause, unknown, and the year is left out as
        such (kind "identity"), not as a unit failure (kind "unit", with ``failed``)."""
        out = {y: (ok, d, "unit") for y, (ok, d) in direct.items()}
        for step, order in ((1, self.years), (-1, self.years[::-1])):
            for y in order:
                n = str(int(y) - step)
                if y in values and out[y][0] is None and n in values and out[n][0] is True \
                        and same_unit(values[y], values[n]):
                    out[y] = (True, "", "")
        # Identity failures linked to a proven year by moves of less than MAX_FACTOR.
        anchor = {y: y for y, v in out.items() if v[0] is True}
        changed = True
        while changed:
            changed = False
            for y, (ok, detail, _k) in sorted(out.items()):
                if ok is not False or y in anchor:
                    continue
                close = [n for n in (str(int(y) - 1), str(int(y) + 1)) if n in anchor and same_unit(values[y], values[n])]
                if close:
                    n = close[0]
                    a = anchor[n]
                    link = f"{n} 年已证明" if a == n else f"{n} 年经逐年变化都不到 ×/÷1.4 与已证明的 {a} 年相连"
                    out[y] = (None, f"{detail}，恒等关系不成立；但该值与 {n} 年的 {values[n]:.6g} 只差 {factor(values[y], values[n])}，"
                                    f"而 {link}，货币单位不可能在其间改变，所以这一不一致另有原因（原因不明），该年不使用", "identity")
                    anchor[y] = a
                    changed = True
        for y, (ok, detail, kind) in list(out.items()):
            if ok is False:
                out[y] = (False, f"{detail}，超出 ×/÷1.4：{failed}", "unit")
            elif ok is None and kind == "unit":
                near = [n for n in (str(int(y) - 1), str(int(y) + 1)) if n in values and out[n][0] is True]
                out[y] = (None, detail + ("".join(f"；与 {n} 年的 {values[n]:.6g} 相比 {factor(values[y], values[n])}，"
                                                  "超出货币单位不可能改变的范围，不能沿用该年的核对" for n in near)
                                          or "；相邻年份也未能核对"), "unit")
        return out

    def _factors(self, area: str) -> tuple[dict, dict]:
        """Verdicts for F and P by year: (True = in L, False = cannot be in L, None = unknown; detail; kind)."""
        s = self.store
        fx = {y: o.value for y in self.years if (o := s.get("fx_lcu_usd", area, y))}
        ppp = {y: o.value for y in self.years if (o := s.get("ppp_hfce", area, y))}

        def identity(val, num, den, what, missing):
            if num and den and den.value > 0:
                implied = num.value / den.value
                return (same_unit(val, implied), what.format(v=val, i=implied, f=factor(val, implied)))
            return (None, missing)

        f = self._prove(fx, {y: identity(
            v, s.get("gdp_lcu", area, y), s.get("gdp_usd", area, y),
            "WDI 官方汇率 {v:.6g}，世界银行 GDP 本币值 ÷ 美元值 = {i:.6g}（{f}）",
            "缺少世界银行 GDP 本币值或美元值，无法核对官方汇率") for y, v in fx.items()},
            "无法证明官方汇率与世界银行本币序列同一货币单位（可能是货币单位不同，也可能是世界银行换算该年美元数据时用的不是官方汇率）")
        direct = {}
        for y, v in ppp.items():
            ok, detail = identity(v, s.get("hfce_lcu", area, y), s.get("hfce_intl", area, y),
                                  "WDI 居民消费 PPP {v:.6g}，居民消费本币值 ÷ 国际元值 = {i:.6g}（{f}）",
                                  "缺少世界银行居民消费本币值或国际元值，无法核对购买力平价")
            if ok is None and y == ICP_YEAR:
                lvl = self.icp_price_level(area)
                if lvl is None:
                    detail += f"；ICP {ICP_YEAR} 也没有该经济体的居民消费价格水平"
                elif f.get(y, (None,))[0] is not True:
                    detail += f"；{y} 年的官方汇率未能证明与世界银行本币序列同一单位，也无法用 ICP 价格水平核对"
                else:
                    implied = lvl * fx[y]
                    ok = same_unit(v, implied)
                    detail = (f"WDI 居民消费 PPP {v:.6g}，ICP {ICP_YEAR} 居民消费价格水平（美国 = 1）{lvl:.4g} × 官方汇率 {fx[y]:.6g} = "
                              f"{implied:.6g}（{factor(v, implied)}）")
            direct[y] = (ok, detail)
        return f, self._prove(ppp, direct, "无法证明购买力平价与世界银行本币序列同一货币单位（可能是货币单位不同，也可能是世界银行这几项数据的口径或版本不一致）")

    def icp_price_level(self, area: str) -> float | None:
        """ICP 2021 household-consumption price level relative to the United States."""
        code = self._icp_code.get(area)
        o = self.store.get("icp21_pli_wl_hfce", code, ICP_YEAR) if code else None
        us = self.store.get("icp21_pli_wl_hfce", "USA", ICP_YEAR)
        return o.value / us.value if o and us else None

    def _build(self, area: str) -> dict:
        s = self.store
        ilo = self.ilo_records(area)
        oecd_ppp = self._oecd_ppp_identity(area)
        f_ok, p_ok = self._factors(area)
        graphs: dict[str, _UnionFind] = {}
        checks: dict[str, dict] = {}
        ambiguous: dict[tuple[str, str], str] = {}
        for y in self.years:
            g = _UnionFind()
            c: dict = {}
            fx, ppp = s.get("fx_lcu_usd", area, y), s.get("ppp_hfce", area, y)
            for node, verdicts in (("F", f_ok), ("P", p_ok)):
                if y in verdicts:
                    c[node] = verdicts[y]  # (verdict, detail, kind)
                    if verdicts[y][0]:
                        g.union(node, "L")
            lcu, cost_ppp = s.get("cohd_total", area, y), s.get("cohd_total_ppp", area, y)
            if lcu:
                if cost_ppp and ppp and cost_ppp.value > 0:
                    implied = lcu.value / cost_ppp.value
                    ok = same_unit(implied, ppp.value)
                    c["C"] = (ok, f"健康饮食成本本币值 ÷ PPP 值 = {implied:.6g}，WDI 购买力平价 {ppp.value:.6g}（{factor(implied, ppp.value)}），"
                                  "超出 ×/÷1.4：无法证明同一货币单位")
                    if ok:
                        g.union("C", "P")
                else:
                    c["C"] = (None, "世界银行未发布该年按 PPP 计的健康饮食成本，无法核对其货币单位" if not cost_ppp
                              else "缺少该年 WDI 购买力平价，无法核对健康饮食成本的货币单位")
            # W: attach a wage to a proven F or P.
            f_in, p_in = g.linked("F"), g.linked("P")
            f_out, p_out = c.get("F", (None,))[0] is False, c.get("P", (None,))[0] is False
            for rec in ilo.get(y, []):
                node = f"ilo:{rec.series}"
                g.find(node)
                if rec.unusable:
                    continue
                agrees_f = bool(rec.usd and fx and same_unit(rec.obs.value / fx.value, rec.usd.value))
                agrees_p = bool(rec.ppp and ppp and same_unit(rec.obs.value / ppp.value, rec.ppp.value))
                if (agrees_f and f_out and agrees_p and p_in) or (agrees_p and p_out and agrees_f and f_in):
                    ambiguous[(y, rec.series)] = (
                        "ILOSTAT 的美元换算与官方汇率一致、PPP 换算与购买力平价一致，但这一年官方汇率和购买力平价中一个已证明与世界银行本币序列"
                        "同一单位，另一个与之相差超出 ×/÷1.4（见该年的核对），这条记录的货币单位无法确定")
                    continue
                if (agrees_f and f_in) or (agrees_p and p_in):
                    g.union(node, "L")
            graphs[y], checks[y] = g, c
        # Currency of L, from ILOSTAT records attached to it.
        codes: set[str] = set()
        for y, g in graphs.items():
            codes |= {r.currency for r in ilo.get(y, []) if r.currency and not r.unusable and g.linked(f"ilo:{r.series}")}
        oecd_unit = {y: o.note for y, o in s.series("oecd_avg_annual_wage", area).items()}
        base_unit = oecd_ppp[2]
        if oecd_ppp[0] and base_unit:
            codes.add(base_unit)
        # Publishers that state their currency.
        for y, g in graphs.items():
            u = oecd_unit.get(y)
            if u and ((oecd_ppp[0] and u == base_unit) or (u in codes and len(codes) == 1)):
                g.union("oecd", "L")
            for node, code in (("cn", "CNY"), ("bls", "USD")):
                if codes == {code}:
                    g.union(node, "L")
        if len(codes) > 1:
            self._exclude(area, "全部年份", "currency",
                          f"与世界银行本币序列相符的记录给出了不同的货币代码：{', '.join(sorted(codes))}；不使用按货币代码对应的数据（OECD、国家统计机构）", "unit")
        # Hours, then magnitudes and time units, among figures now known to be in the same
        # currency unit (decided for every year on the same evidence, then applied).
        hours, bad_hours = self._hours(area)
        for y, why in bad_hours:
            if ilo.get(y):
                self._exclude(area, y, "hours", why, "check")
        jump = self._jump(area, ilo, graphs)
        for y, g in graphs.items():
            attached = [r for r in ilo.get(y, []) if not r.unusable and g.linked(f"ilo:{r.series}")]
            w = s.get("oecd_avg_annual_wage", area, y) if g.linked("oecd") else None
            self._time_check(area, y, attached, w.value / 12 if w else None, hours.get(y, {}), jump)
        return {"years": graphs, "checks": checks, "codes": codes, "ilo": ilo, "oecd_ppp": oecd_ppp,
                "oecd_unit": oecd_unit, "ambiguous": ambiguous, "hours": hours}

    def _oecd_ppp_identity(self, area: str) -> tuple[bool | None, str, str | None]:
        """OECD national-currency wages at constant prices ÷ the same in US$ PPPs is the
        PPP of OECD's base year; it must equal WDI's household PPP of that year.
        Returns (verdict, detail, unit of OECD's national-currency series)."""
        s = self.store
        q, qp = s.series("oecd_avg_annual_wage_q", area), s.series("oecd_avg_annual_wage_q_usdppp", area)
        common = sorted(set(q) & set(qp))
        if not common:
            return (None, "OECD 未发布该经济体按购买力平价换算的工资", None)
        y = common[-1]
        unit, base = q[y].note.split()
        implied = q[y].value / qp[y].value
        ppp = s.get("ppp_hfce", area, base)
        hl, hi = s.get("hfce_lcu", area, base), s.get("hfce_intl", area, base)
        if not (ppp and hl and hi) or not same_unit(ppp.value, hl.value / hi.value):
            return (None, f"无法核对 {base} 年的 WDI 购买力平价", unit)
        return (same_unit(implied, ppp.value), f"OECD 工资（{base} 年不变价）本币值 ÷ PPP 美元值 = {implied:.6g}，"
                                                f"WDI {base} 年居民消费 PPP {ppp.value:.6g}（{factor(implied, ppp.value)}）", unit)

    # ---- reasons for what is left out
    def explain(self, area: str, year: str, has_data: bool) -> None:
        a = self.area(area)
        c, g = a["checks"].get(year, {}), a["years"].get(year)
        if not has_data or g is None:
            return
        s = self.store
        for k, scope, series, what in (("F", "fx", "fx_lcu_usd", "官方汇率（PA.NUS.FCRF）"),
                                       ("P", "ppp", "ppp_hfce", "居民消费购买力平价（PA.NUS.PRVT.PP）")):
            if not s.get(series, area, year):
                self._exclude(area, year, scope, f"世界银行未发布该年{what}", "missing")
                continue
            ok, detail, kind = c.get(k, (True, "", ""))
            if not g.linked(k) and ok is not True and detail:
                self._exclude(area, year, scope, detail, kind)
        if "C" in c and not g.linked("C"):
            ok, detail = c["C"]
            if ok is True:  # the diet cost matches the PPP, but the PPP itself is not proven
                detail = "健康饮食成本与购买力平价同一货币单位，但该年购买力平价未能证明与世界银行本币序列同一单位"
            self._exclude(area, year, "cohd", detail, "missing" if detail.startswith("世界银行未发布") else "unit")
        if s.get("oecd_avg_annual_wage", area, year) and not g.linked("oecd"):
            unit = a["oecd_unit"].get(year)
            self._exclude(area, year, "wage:oecd", "OECD 工资未能证明与世界银行本币序列同一货币单位：" + a["oecd_ppp"][1]
                          + f"；OECD 标注的货币 {unit}，与世界银行本币序列相符的记录给出的货币 {', '.join(sorted(a['codes'])) or '无'}", "unit")
        for node, code, series, who in (("cn", "CNY", ("cn_wage_nonprivate", "cn_wage_private", "cn_wage_large_ent", "cn_migrant_monthly"), "国家统计局"),
                                         ("bls", "USD", ("us_ahe_all_nsa",), "美国劳工统计局")):
            has = any(s.get(x, area, year) for x in series) or any(p.startswith(year) for x in series for p in s.series(x, area))
            if has and not g.linked(node):
                self._exclude(area, year, f"wage:{node}",
                              f"{who}的工资以 {code} 发布，但与世界银行本币序列相符的记录给出的货币代码为 "
                              f"{', '.join(sorted(a['codes'])) or '无'}，无法确认同一货币单位", "unit")
        fx, ppp = s.get("fx_lcu_usd", area, year), s.get("ppp_hfce", area, year)
        for rec in a["ilo"].get(year, []):
            if rec.unusable or rec.rejected:
                self._exclude(area, year, _wage_scope(rec), f"{rec.series}：{rec.unusable or rec.rejected}",
                              "notes" if rec.unusable else "check")
            elif (year, rec.series) in a["ambiguous"]:
                self._exclude(area, year, _wage_scope(rec), f"{rec.series}：{a['ambiguous'][(year, rec.series)]}", "unit")
            elif not g.linked(f"ilo:{rec.series}"):
                parts = []
                if not fx:
                    parts.append("世界银行未发布该年官方汇率")
                elif not rec.usd:
                    parts.append("ILOSTAT 未发布美元换算值")
                elif same_unit(rec.obs.value / fx.value, rec.usd.value):
                    parts.append("与 ILOSTAT 自己的美元换算一致，但该年官方汇率未能证明与世界银行本币序列同一单位")
                else:
                    parts.append(f"本币 {rec.obs.value:,.6g} ÷ WDI 汇率 = {rec.obs.value / fx.value:,.4g} 美元，ILOSTAT 自身折合 {rec.usd.value:,.4g} 美元")
                if not ppp:
                    parts.append("世界银行未发布该年购买力平价")
                elif not rec.ppp:
                    parts.append("ILOSTAT 未发布 PPP 换算值")
                elif same_unit(rec.obs.value / ppp.value, rec.ppp.value):
                    parts.append("与 ILOSTAT 自己的 PPP 换算一致，但该年购买力平价未能证明与世界银行本币序列同一单位")
                else:
                    parts.append(f"÷ WDI 购买力平价 = {rec.obs.value / ppp.value:,.4g}，ILOSTAT 自身折合 {rec.ppp.value:,.4g} 国际元")
                self._exclude(area, year, _wage_scope(rec), f"{rec.series}：无法证明与世界银行本币序列同一货币单位。" + "；".join(parts), "unit")


# --------------------------------------------------------------------------------------
# Wages
# --------------------------------------------------------------------------------------

def _usable_linked(units: UnitGraph, area: str) -> dict[str, list[IloRecord]]:
    a = units.area(area)
    return {y: [r for r in recs if r.usable and a["years"][y].linked(f"ilo:{r.series}")]
            for y, recs in a["ilo"].items() if y in a["years"]}


def ilo_variants(store: Store, units: UnitGraph, area: str, year: str, ilo_dic: dict) -> list[WageVariant]:
    usable = _usable_linked(units, area)
    # One source per (concept, unit) is preferred across years so that a country's
    # figures do not jump between surveys: the one with the latest and longest
    # history of usable records.  In a given year an unrestricted record comes first.
    # A median comes from the same survey as the mean of its time unit when that survey
    # has one, so that mean and median describe one distribution.
    history: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for y, recs in usable.items():
        for r in recs:
            history[(r.concept, r.unit)][r.source].append(y)
    main = {k: max(v, key=lambda src: (max(v[src]), len(v[src]), src)) for k, v in history.items()}
    chosen: dict[tuple[str, str], IloRecord] = {}
    for concept in ("mean", "median"):
        for r in usable.get(year, []):
            if r.concept != concept:
                continue
            k = (r.concept, r.unit)
            mean = chosen.get(("mean", r.unit))

            def rank(x: IloRecord) -> tuple:
                return (concept == "median" and mean is not None and x.source != mean.source,
                        x.restricted, x.source != main[k], -len(history[k][x.source]), x.source)
            if k not in chosen or rank(r) < rank(chosen[k]):
                chosen[k] = r

    def src_label(r: IloRecord) -> str:
        return f"ILOSTAT · {ilo_dic.get('source', {}).get(r.source, r.source)}"

    def caveat(r: IloRecord) -> str:
        ok, why = units.series_consistent(area, r)
        shift = (f"与同一来源最近的其他年份相比变化过大（{why}）：该来源的口径或数量级可能有变化，与其他年份比较须谨慎"
                 if ok is False else "")
        mean = chosen.get(("mean", r.unit))
        above = (f"同一来源同年的中位数（{r.obs.value:,.6g}）高于平均数（{mean.obs.value:,.6g}）"
                 if r.concept == "median" and mean is not None and mean.source == r.source and r.obs.value > mean.obs.value else "")
        return _join([shift, r.unsure or "", above, ilo_notes(r, ilo_dic)])

    def ids(r: IloRecord) -> dict:
        return {"source_id": f"ILOSTAT {r.source}", "series_key": f"ILOSTAT {r.series}",
                "notes_sig": ilo_note_labels(list(r.signature), ilo_dic),
                "series_id": " ".join(("ILOSTAT", r.series, *r.signature))}

    hours_by_source = units.area(area)["hours"].get(year, {})
    out: list[WageVariant] = []
    for concept in ("mean", "median"):
        direct = chosen.get((concept, "hour"))
        monthly = chosen.get((concept, "month"))
        cname = "平均" if concept == "mean" else "中位"
        if direct:
            out.append(WageVariant(
                key=f"ilo_{concept}_hourly", label=f"雇员{cname}时薪" + ("（覆盖范围有限）" if direct.restricted else ""),
                concept=concept, source=src_label(direct), monthly_lcu=None, hourly_lcu=direct.obs.value, hours_week=None,
                method="ILOSTAT 直接发布的时薪", snapshots=[direct.obs.snapshot], caveat=caveat(direct),
                restricted=direct.restricted, currency=direct.currency, **ids(direct),
            ))
        if monthly:
            # Hours only from the same survey (same ILOSTAT source) as the earnings, and
            # only hours that passed UnitGraph._hours.
            hours = hours_by_source.get(monthly.source)
            hours_obs = store.get(f"ilo_weekly_hours@{monthly.source}", units.ilo_area(area), year) if hours else None
            derive = hours is not None and direct is None
            label = f"雇员{cname}月薪" + ("（覆盖范围有限）" if monthly.restricted else "")
            out.append(WageVariant(
                key=f"ilo_{concept}_monthly", label=label, concept=concept, source=src_label(monthly),
                monthly_lcu=monthly.obs.value,
                hourly_lcu=monthly.obs.value / (hours * WEEKS_PER_MONTH) if derive else None,
                hours_week=hours if derive else None,
                method=("月薪 ÷（同一调查的每周实际工时 × 52/12）" if derive else
                        "仅用于月薪口径（同口径时薪已直接发布）" if direct else
                        "同一调查没有可用的工时数据，不折算时薪，只用于月薪口径"),
                snapshots=[monthly.obs.snapshot] + ([hours_obs.snapshot] if derive else []),
                caveat=caveat(monthly), restricted=monthly.restricted, currency=monthly.currency,
                label_hourly=f"{label}（按同一调查的工时折算为时薪）" if derive else None, **ids(monthly),
            ))
    return out


def oecd_variant(store: Store, units: UnitGraph, area: str, year: str) -> WageVariant | None:
    w = store.get("oecd_avg_annual_wage", area, year)
    if not w or not units.year(area, year).linked("oecd"):
        return None
    h = store.get("oecd_usual_weekly_hours_ft", area, year)
    zero = store.get("oecd_usual_weekly_hours_ft__zero", area, year)
    return WageVariant(
        key="oecd_fte", label="全职当量平均工资（OECD）", concept="mean", source="OECD · Average annual wages",
        monthly_lcu=w.value / 12,
        hourly_lcu=w.value / (h.value * 52) if h else None,
        hours_week=h.value if h else None,
        method=(f"全职当量平均年薪 ÷（全职雇员通常周工时 {h.value:.1f} 小时 × 52）" if h else
                "OECD 公布的该国全职雇员通常周工时为 0（视为缺失），只用于月薪口径" if zero else
                "OECD 未公布该国该年全职雇员通常周工时，只用于月薪口径"),
        snapshots=[w.snapshot] + ([h.snapshot] if h else []),
        caveat="国民经济核算口径：工资总额 ÷ 全职当量雇员数，含高收入者；时薪按全职雇员通常工时折算（含带薪假期）",
        currency=w.note, series_id="OECD AV_AN_WAGE", source_id="OECD", series_key="OECD AV_AN_WAGE",
    )


CN_SERIES = (
    ("cn_wage_nonprivate", "城镇非私营单位平均工资"),
    ("cn_wage_private", "城镇私营单位平均工资"),
    ("cn_wage_large_ent", "规模以上企业就业人员平均工资"),
)


def china_variants(store: Store, units: UnitGraph, year: str, definitions: dict) -> list[WageVariant]:
    """NBS national sources for China, each described by the release it comes from:
    NBS's own title and definitions are quoted verbatim (quote); what this project adds
    is kept apart (caveat)."""
    if not units.year("CHN", year).linked("cn"):
        return []
    hours = china_annual_hours(store, year)
    n_months = len([p for p in store.series("cn_weekly_hours_enterprise", "CHN") if p.startswith(year + "-")])
    no_hours = (f"本项目存档的国家统计局发布中，该年只有 {n_months} 个月的企业就业人员周平均工作时间（少于 6 个月），不折算时薪" if n_months
                else "本项目存档的国家统计局发布中没有该年的企业就业人员周平均工作时间，不折算时薪")
    hours_note = "时薪按国家统计局月度发布的“全国企业就业人员周平均工作时间”折算；该工时是全国企业就业人员的平均，与这一工资口径的覆盖面不完全一致"

    def source(o: Obs) -> str:
        d = definitions.get(o.snapshot)
        return f"国家统计局《{d['title']}》" if d else "国家统计局"

    out = []
    for series, label in CN_SERIES:
        o = store.get(series, "CHN", year)
        if not o:
            continue
        d = definitions.get(o.snapshot, {})
        monthly = o.value / 12
        scope = [x for x in d.get("scope", []) if x["series"] is None or series in x["series"]]
        notes = []
        comp = store.get(f"{series}__comparable_growth", "CHN", year)
        if comp:
            nominal = float(o.note.split("growth_pct=")[1]) if "growth_pct=" in o.note else None
            notes.append("国家统计局注明该年统计覆盖范围有变化：" + (f"名义{_rate(nominal)}，" if nominal is not None else "")
                         + f"按可比口径{_rate(comp.value)}" + ("（可比口径的定义见原文摘录）" if d.get("comparable") else ""))
        if hours:
            notes.append(hours_note)
        quote = excerpts_quote(scope + [d.get("gross"), d.get("comparable") if comp else None])
        out.append(WageVariant(
            key=series, label=label, concept="mean", source=source(o),
            monthly_lcu=monthly,
            hourly_lcu=monthly / (hours["mean"] * WEEKS_PER_MONTH) if hours else None,
            hours_week=hours["mean"] if hours else None,
            method=(f"年工资 ÷ 12 ÷（企业就业人员周平均工作时间 {hours['mean']:.1f} 小时 × 52/12）" if hours else no_hours),
            snapshots=[o.snapshot] + (hours["snapshots"] if hours else []),
            caveat=_join(notes), quote=quote, restricted=True, currency="CNY",
            series_id=f"NBS {series}", source_id="NBS", series_key=f"NBS {series}",
        ))
    o = store.get("cn_migrant_monthly", "CHN", year)
    if o:
        out.append(WageVariant(
            key="cn_migrant", label="农民工月均收入", concept="mean", source=source(o),
            monthly_lcu=o.value,
            hourly_lcu=o.value / (hours["mean"] * WEEKS_PER_MONTH) if hours else None,
            hours_week=hours["mean"] if hours else None,
            method=(f"月均收入 ÷（企业就业人员周平均工作时间 {hours['mean']:.1f} 小时 × 52/12）" if hours else no_hours),
            snapshots=[o.snapshot] + (hours["snapshots"] if hours else []),
            caveat=(hours_note + "；本项目存档的农民工监测调查报告未公布农民工工时") if hours else "",
            quote=excerpts_quote([definitions.get(o.snapshot, {}).get("definition")]),
            restricted=True, currency="CNY", series_id="NBS cn_migrant_monthly", source_id="NBS",
            series_key="NBS cn_migrant_monthly",
        ))
    return out


def _rate(pct: float) -> str:
    """A growth rate in NBS's wording: 增长 x% / 下降 x%."""
    x = abs(pct)
    return f"{'增长' if pct >= 0 else '下降'} {x:.1f}%" if round(x, 1) == x else f"{'增长' if pct >= 0 else '下降'} {x:g}%"


def excerpts_quote(excerpts: list[dict | None]) -> str:
    """Verbatim pieces of one release in the order they appear in it, each section
    labelled (统计范围：“…”), with "……" where text between two pieces of a section is
    left out.  Sections are separate quotations: nothing is joined that is not adjacent
    in the release."""
    out: list[str] = []
    prev = None
    for x in sorted((x for x in excerpts if x), key=lambda x: x["pos"]):
        if prev is not None and prev["section"] == x["section"]:
            out[-1] += ("" if prev["end"] == x["pos"] else "……") + x["text"]
        else:
            out.append(f"{x['section']}：“{x['text']}")
        prev = x
    return "；".join(o + "”" for o in out)


def _join(parts: list[str]) -> str:
    """Notes joined with "；", without doubling the "。" a quoted sentence ends with."""
    out = ""
    for x in (p for p in parts if p):
        out += ("" if not out or out.endswith("。") else "；") + x
    return out


def china_annual_hours(store: Store, year: str) -> dict | None:
    """Mean of the monthly survey values NBS published for that year (NBS does not
    publish a separate January figure, so up to 11 months); at least 6 months."""
    monthly = store.series("cn_weekly_hours_enterprise", "CHN")
    vals = [monthly[p] for p in sorted(monthly) if p.startswith(year + "-")]
    if len(vals) < 6:
        return None
    return {
        "mean": math.fsum(v.value for v in vals) / len(vals),
        "months": [v.period for v in vals],
        "snapshots": sorted({v.snapshot for v in vals}),
    }


def us_bls_variant(store: Store, units: UnitGraph, year: str) -> WageVariant | None:
    m = annual_mean(store.series("us_ahe_all_nsa", "USA"), year)
    if not m or not units.year("USA", year).linked("bls"):
        return None
    snaps = sorted({o.snapshot for p, o in store.series("us_ahe_all_nsa", "USA").items() if p.startswith(year)})
    return WageVariant(
        key="bls_ces_ahe", label="私营非农雇员平均时薪（BLS CES）", concept="mean",
        source="美国劳工统计局 BLS · Current Employment Statistics", monthly_lcu=None, hourly_lcu=m[0], hours_week=None,
        method="CEU0500000003 十二个月（未季调）的简单平均", snapshots=snaps,
        caveat="按企业工资单统计的每小时工资（含带薪休假小时），不含农业、政府雇员和自雇", restricted=True, currency="USD",
        series_id="BLS CEU0500000003", source_id="BLS", series_key="BLS CEU0500000003",
    )


# --------------------------------------------------------------------------------------
# Country-year table
# --------------------------------------------------------------------------------------

def country_years(store: Store, gold: dict, meta: dict, ilo_dic: dict, years: list[str], units: UnitGraph,
                  cn_definitions: dict) -> dict:
    out = {}
    for area, info in sorted(meta.items()):
        if not info.get("is_economy"):
            continue
        rec_years = {}
        for y in years:
            g = gold["annual"].get(y)
            if not g:
                continue
            u = units.year(area, y)
            fx = store.get("fx_lcu_usd", area, y)
            fx = fx if fx and u.linked("F") else None
            ppp = store.get("ppp_hfce", area, y)
            ppp = ppp if ppp and u.linked("P") else None
            cohd = {k: store.get(f"cohd_{k}", area, y) if u.linked("C") else None for k in ["total"] + COHD_GROUPS}
            variants = []
            if area == "CHN":
                variants += china_variants(store, units, y, cn_definitions)
            if area == "USA":
                v = us_bls_variant(store, units, y)
                variants += [v] if v else []
            ov = oecd_variant(store, units, area, y)
            variants += [ov] if ov else []
            variants += ilo_variants(store, units, area, y, ilo_dic)
            has_data = bool(store.get("oecd_avg_annual_wage", area, y) or units.area(area)["ilo"].get(y)
                            or store.get("cohd_total", area, y) or (area == "CHN" and store.get("cn_wage_nonprivate", "CHN", y)))
            units.explain(area, y, has_data)
            if not variants and not cohd["total"]:
                continue
            gold_lcu_g = g["usd_g"] * fx.value if fx else None
            pli = ppp.value / fx.value if ppp and fx else None
            wages = [wage_metrics(v, gold_lcu_g, fx.value if fx else None, ppp.value if ppp else None,
                                  cohd["total"].value if cohd["total"] else None) for v in variants]
            mark_roles(wages)
            gdp_lcu, gdp_usd = store.get("gdp_lcu", area, y), store.get("gdp_usd", area, y)
            rec_years[y] = {
                "fx": fx.value if fx else None,
                # the factor the World Bank applied to the year's GDP (fiscal-year or other rates
                # can differ from the official calendar-year rate); shown next to fx
                "fx_gdp_factor": gdp_lcu.value / gdp_usd.value if fx and gdp_lcu and gdp_usd and gdp_usd.value > 0 else None,
                "fx_vs_gdp_factor": fx.value / (gdp_lcu.value / gdp_usd.value) if fx and gdp_lcu and gdp_usd and gdp_usd.value > 0 else None,
                "ppp_hfce": ppp.value if ppp else None,
                "pli_hfce": pli,
                "population": _v(store.get("population", area, y)),
                "gold_lcu_g": gold_lcu_g,
                "gold_usd_g": g["usd_g"],
                # what 1 g of gold buys locally, in US-dollars' worth of US-priced household consumption
                "gold_usdeq_g": g["usd_g"] / pli if pli else None,
                "cohd": {k: _v(o) for k, o in cohd.items()},
                "cohd_days_per_g": gold_lcu_g / cohd["total"].value if cohd["total"] and gold_lcu_g else None,
                "wages": wages,
                "snapshots": sorted({o.snapshot for o in [fx, ppp, cohd["total"]] if o}),
            }
        mark_switches(rec_years)
        for row in rec_years.values():  # identifiers used only to find switches
            for w in row["wages"]:
                for k in ("series_id", "series_key", "notes_sig"):
                    w.pop(k)
        if rec_years:
            out[area] = {
                "name_en": info["name_en"],
                "name_zh": info.get("name_zh") or info["name_en"],
                "iso2": info["iso2"],
                "region": info["region"],
                "income": info["income"],
                "g20": area in G20,
                "currency": units.currency(area),
                "years": rec_years,
            }
    return out


def oecd_vs_survey(countries: dict) -> dict | None:
    """How far OECD's full-time-equivalent wage and an ILOSTAT survey's mean monthly
    earnings differ for the same economy and year (both published): ILOSTAT ÷ OECD."""
    ratios = []
    for iso, c in sorted(countries.items()):
        for y, row in sorted(c["years"].items()):
            o = next((w for w in row["wages"] if w["key"] == "oecd_fte"), None)
            i = next((w for w in row["wages"] if w["key"] == "ilo_mean_monthly"), None)
            if o and i and o["monthly_lcu"] and i["monthly_lcu"]:
                ratios.append((i["monthly_lcu"] / o["monthly_lcu"], iso, y))
    if not ratios:
        return None
    lo, hi = min(ratios), max(ratios)
    return {"n": len(ratios), "min": lo[0], "min_at": [lo[1], lo[2]], "max": hi[0], "max_at": [hi[1], hi[2]]}


# Which variant leads each economy's row.  Cross-country comparability first: OECD's
# harmonised FTE wage, then ILOSTAT figures covering the whole country and all
# sectors, then national statistical offices' own series, then ILOSTAT figures whose
# notes restrict their coverage (e.g. urban areas or the private sector only).
def _primary_rank(w: dict) -> tuple | None:
    k = w["key"]
    if k == "oecd_fte":
        return (0, 0)
    if k in ("ilo_mean_hourly", "ilo_mean_monthly"):
        return (3 if w["restricted"] else 1, 0 if k.endswith("hourly") else 1)
    national = ["cn_wage_nonprivate", "cn_wage_private", "bls_ces_ahe"]
    if k in national:
        return (2, national.index(k))
    return None


def _typical_rank(w: dict) -> tuple | None:
    k = w["key"]
    if k in ("ilo_median_hourly", "ilo_median_monthly"):
        return (1 if w["restricted"] else 0, 0 if k.endswith("hourly") else 1)
    return None


def mark_roles(wages: list[dict]) -> None:
    """role = primary / typical for the hourly view; mrole = primary / typical for the
    monthly view.  The typical (median) figure is shown only when it comes from the same
    survey as the primary one: a median from another publisher or survey says nothing
    about how the primary figure's distribution is skewed."""
    for field_, need in (("role", "hourly_lcu"), ("mrole", "monthly_lcu")):
        cands = [w for w in wages if w[need] and _primary_rank(w) is not None]
        if not cands:
            continue
        primary = min(cands, key=_primary_rank)
        primary[field_] = "primary"
        typ = [w for w in wages if w[need] and _typical_rank(w) is not None and w["source_id"] == primary["source_id"]]
        if typ:
            min(typ, key=_typical_rank)[field_] = "typical"


def mark_switches(rec_years: dict[str, dict]) -> None:
    """Where an economy's primary figure differs from the one of its previous year with
    data, say how on the new primary figure (role_switch / mrole_switch), so that the
    change is not read as a change in pay: another publisher series ("source"), or the
    same series with different notes on what it measures ("notes", with the notes
    present only in one of the two years)."""
    for field_ in ("role", "mrole"):
        prev = None
        for y in sorted(rec_years):
            cur = next((w for w in rec_years[y]["wages"] if w[field_] == "primary"), None)
            if cur is None:
                continue
            if prev is not None and prev[1]["series_id"] != cur["series_id"]:
                p = prev[1]
                same = p["series_key"] == cur["series_key"]
                cur[f"{field_}_switch"] = {
                    "year": prev[0], "label": p["label"], "source": p["source"], "kind": "notes" if same else "source",
                    "only_before": [n for n in p["notes_sig"] if n not in cur["notes_sig"]] if same else [],
                    "only_now": [n for n in cur["notes_sig"] if n not in p["notes_sig"]] if same else [],
                }
            prev = (y, cur)


def wage_metrics(v: WageVariant, gold_lcu_g: float | None, fx: float | None, ppp: float | None, cohd: float | None) -> dict:
    d = {
        "role": None, "mrole": None, "role_switch": None, "mrole_switch": None, "key": v.key, "label": v.label, "label_hourly": v.label_hourly,
        "concept": v.concept, "source": v.source, "method": v.method, "caveat": v.caveat,
        "restricted": v.restricted, "currency": v.currency, "series_id": v.series_id, "source_id": v.source_id,
        "series_key": v.series_key, "notes_sig": v.notes_sig, "quote": v.quote, "snapshots": v.snapshots,
        "monthly_lcu": v.monthly_lcu, "hourly_lcu": v.hourly_lcu, "hours_week": v.hours_week,
        "monthly_gold_g": v.monthly_lcu / gold_lcu_g if v.monthly_lcu and gold_lcu_g else None,
        "monthly_ppp": v.monthly_lcu / ppp if v.monthly_lcu and ppp else None,
        "cohd_days_per_month": v.monthly_lcu / cohd if v.monthly_lcu and cohd else None,
    }
    h = v.hourly_lcu
    d.update({
        "hourly_gold_g": h / gold_lcu_g if h and gold_lcu_g else None,
        "hourly_usd_mkt": h / fx if h and fx else None,
        "hourly_ppp": h / ppp if h and ppp else None,
        "minutes_per_cohd_day": cohd / h * 60 if h and cohd else None,
    })
    return d


def _v(o: Obs | None):
    return o.value if o else None


# --------------------------------------------------------------------------------------
# ICP 2021 category price levels (United States = 1)
# --------------------------------------------------------------------------------------

ICP_YEAR = "2021"


def icp_codes(store: Store, meta: dict) -> dict[str, str]:
    """WDI economy -> ICP economy code.  ICP's codes are matched by code, or else by the
    economy's name (ICP codes Russia as RUT); ICP aggregates such as regions and income
    groups match no economy and are left out."""
    by_name = {info["name_en"]: iso for iso, info in meta.items() if info.get("is_economy")}
    out = {}
    for (series, area, _p), o in sorted(store.items.items()):
        if series.startswith("icp21_"):
            iso = area if meta.get(area, {}).get("is_economy") else by_name.get(o.note)
            if iso:
                out[iso] = area
    return out


def icp_levels(store: Store, meta: dict) -> dict:
    """Category price levels of economies relative to the United States."""
    cats = sorted({s for (s, _a, _p) in store.items if s.startswith("icp21_pli_wl_")})
    out: dict[str, dict] = defaultdict(dict)
    for iso, code in sorted(icp_codes(store, meta).items()):
        for series in cats:
            us, o = store.get(series, "USA", ICP_YEAR), store.get(series, code, ICP_YEAR)
            if us and o:
                out[iso][series.removeprefix("icp21_pli_wl_")] = o.value / us.value
    return dict(out)


# --------------------------------------------------------------------------------------
# United States monthly (long history) and supermarket items
# --------------------------------------------------------------------------------------

def us_monthly(store: Store, gold: dict) -> dict:
    gm = dict((p, v) for p, v in gold["monthly"])
    series = {}
    for key in ("us_ahe_pns_sa", "us_ahe_all_sa"):
        rows = []
        for p, o in sorted(store.series(key, "USA").items()):
            if p in gm:
                rows.append([p, o.value, o.value / (gm[p] / GRAMS_PER_TROY_OUNCE), "preliminary" in o.note])
        series[key] = rows
    return series


def us_items(store: Store, gold: dict) -> dict:
    gm = dict((p, v) for p, v in gold["monthly"])
    ahe = store.series("us_ahe_all_sa", "USA")
    out = {}
    for item, (label, bls_unit, unit, factor) in US_ITEMS.items():
        s = store.series(item, "USA")
        if not s:
            continue
        rows = []
        for p, o in sorted(s.items()):
            price = o.value * factor
            wage = ahe.get(p)
            g = gm.get(p)
            rows.append({
                "period": p, "price_bls_unit": o.value, "price": price,
                "minutes": price / wage.value * 60 if wage else None,
                "gold_mg": price / (g / GRAMS_PER_TROY_OUNCE) * 1000 if g else None,
                "preliminary": "preliminary" in o.note,
                "wage_preliminary": bool(wage and "preliminary" in wage.note),
            })
        out[item] = {"label": label, "bls_unit": bls_unit, "unit": unit, "series_id": next(iter(s.values())).note.split("|")[0], "rows": rows}
    return out


# --------------------------------------------------------------------------------------
# Monthly wage in grams of gold, by year (for the "gold is a moving ruler" chart)
# --------------------------------------------------------------------------------------

def wage_gold_history(store: Store, gold: dict, meta: dict, ilo_dic: dict, units: UnitGraph) -> dict:
    """One average monthly wage series per economy, converted to grams of gold with each
    year's average gold price and exchange rate.  Points are [year, monthly wage, grams,
    source, break, why]: break = True where the line must not be drawn from the previous
    point - the publisher notes a break in series or a change of coverage, the notes that
    define the figure change, OECD's currency changes, or the level moves against nominal
    income per head beyond what the series can move without changing what it measures
    (UnitGraph.shift; also when that cannot be checked).

    Candidates: OECD's average annual wage ÷ 12, and each ILOSTAT survey's mean monthly
    earnings, with at least three usable years; the one with the most usable years not
    restricted in coverage is drawn (then the most usable years, then the latest).  For China ILOSTAT's series is NBS's
    urban private-unit wage ÷ 12 (validate.china_ilo_equals_nbs); years NBS published
    itself come from NBS.  The label and notes say what the drawn records cover.
    """
    out = {}
    for area, info in meta.items():
        if not info.get("is_economy"):
            continue
        a = units.area(area)
        cands: dict[str, list[dict]] = defaultdict(list)
        for y, recs in _usable_linked(units, area).items():
            if not a["years"][y].linked("F"):
                continue
            for r in recs:
                if r.concept == "mean" and r.unit == "month":
                    cands[f"ILOSTAT {r.source}"].append({"y": y, "v": r.obs.value, "rec": r, "restricted": r.restricted})
        for y, o in store.series("oecd_avg_annual_wage", area).items():
            g = a["years"].get(y)
            if g and g.linked("oecd") and g.linked("F"):
                cands["OECD"].append({"y": y, "v": o.value / 12, "rec": None, "restricted": False, "unit": o.note})
        pts: dict[str, dict] = {}
        chosen = None
        cands = {k: v for k, v in cands.items() if len(v) >= 3}  # a series needs three years to be drawn
        if cands:
            chosen = max(cands, key=lambda k: (sum(not c["restricted"] for c in cands[k]), len(cands[k]),
                                               max(c["y"] for c in cands[k]), k))
            prev = None
            for c in sorted(cands[chosen], key=lambda c: c["y"]):
                r = c["rec"]
                if r is not None:
                    why = ("ILOSTAT 注明序列中断" if r.break_in_series else
                           "ILOSTAT 对该值的口径注释与上一个点不同" if prev is not None and r.signature != prev["rec"].signature else "")
                    src = f"ILOSTAT · {ilo_dic.get('source', {}).get(r.source, r.source)}"
                else:
                    why = "OECD 标注的货币与上一个点不同" if prev is not None and c["unit"] != prev["unit"] else ""
                    src = "OECD · Average annual wages ÷ 12"
                pts[c["y"]] = {"v": c["v"], "src": src, "why": why, "rec": r}
                prev = c
        if area == "CHN":
            for y, o in store.series("cn_wage_private", "CHN").items():
                if a["years"].get(y) and a["years"][y].linked("cn") and a["years"][y].linked("F"):
                    why = "国家统计局注明该年统计覆盖范围有变化" if store.get("cn_wage_private__comparable_growth", "CHN", y) else ""
                    pts[y] = {"v": o.value / 12, "src": "国家统计局 · 城镇私营单位平均工资 ÷ 12", "why": why, "rec": None}
        rows, drawn = [], []
        for y in sorted(pts):
            fx = store.get("fx_lcu_usd", area, y)
            g = gold["annual"].get(y)
            if not (fx and g):
                continue
            p = pts[y]
            why = p["why"]
            if rows and not why:
                ok, detail = units.shift(area, rows[-1][0], rows[-1][1], y, p["v"])
                why = "" if ok else (f"与上一个点相比的变化，超出 OECD 同口径工资在同样年数内相对名义人均收入出现过的最大偏离，不能确认可比：{detail}"
                                     if ok is False else detail)
            rows.append([y, p["v"], p["v"] / (g["usd_g"] * fx.value), p["src"], bool(why and rows), why if rows else ""])
            drawn.append(p["rec"])
        if len(rows) >= 3:
            recs = [r for r in drawn if r is not None]
            restricted = any(r.restricted for r in recs)
            # Coverage notes with the years they apply to, when not to every point.
            years_of: dict[str, list[str]] = defaultdict(list)
            for r in recs:
                for note in ilo_note_labels([c for c in ilostat.codes(r.obs) if c.split(":", 1)[0] in COVERAGE_NOTES + ("I13",)], ilo_dic):
                    years_of[note].append(r.obs.period)
            notes = [note if len(ys) == len(rows) else f"{note}（{'、'.join(ys)} 年）" for note, ys in years_of.items()]
            if area == "CHN":
                label = "城镇私营单位平均工资（国家统计局；更早年份为 ILOSTAT 转载的同一序列）"
            elif chosen == "OECD":
                label = "全职当量平均工资 ÷ 12（OECD）"
            else:
                scope = ("" if not restricted else "（覆盖范围有限）" if len(recs) == len(rows) and all(r.restricted for r in recs)
                         else "（部分年份覆盖范围有限）")
                label = (f"雇员平均月薪{scope}"
                         f"（ILOSTAT · {ilo_dic.get('source', {}).get(chosen.split(' ', 1)[1], chosen)}）")
            out[area] = {"label": label, "source_id": chosen,
                         "restricted": restricted, "notes": notes, "points": rows}
    return out


# --------------------------------------------------------------------------------------
# Latest month (United States and China)
# --------------------------------------------------------------------------------------

def latest_block(store: Store, gold: dict) -> dict:
    """Gold, CNY rate and US wage for the latest month with all three available.

    China publishes wages once a year, so the Chinese hourly figures here pair the
    latest annual wage with the latest month's gold price; the periods are stated
    explicitly in the output instead of being blended into one number."""
    gm = dict((p, v) for p, v in gold["monthly"])
    cny = store.series("fx_lcu_usd_ecb", "CHN")
    ahe = store.series("us_ahe_all_sa", "USA")
    months = sorted(p for p in gm if p in cny and p in ahe)
    if not months:
        return {}
    p = months[-1]
    usd_g = gm[p] / GRAMS_PER_TROY_OUNCE
    cny_g = usd_g * cny[p].value
    out = {
        "period": p,
        "gold_usd_oz": gm[p],
        "gold_usd_g": usd_g,
        "cny_per_usd": cny[p].value,
        "gold_cny_g": cny_g,
        "us_ahe": ahe[p].value,
        "us_ahe_preliminary": "preliminary" in ahe[p].note,
        "us_gold_g_per_hour": ahe[p].value / usd_g,
        "cn": [],
    }
    for wage_year in sorted({y for (s, a, y) in store.items if s in ("cn_wage_nonprivate", "cn_wage_private") and a == "CHN"}):
        hours = china_annual_hours(store, wage_year)
        for series, label in (("cn_wage_nonprivate", "城镇非私营单位"), ("cn_wage_private", "城镇私营单位")):
            o = store.get(series, "CHN", wage_year)
            if not o:
                continue
            for basis, hrs in (("assumed", ASSUMED_HOURS_CN), ("actual", hours["mean"] * 52 if hours else None)):
                if hrs is None:
                    continue
                hourly = o.value / hrs
                out["cn"].append({"series": series, "label": label, "wage_year": wage_year, "annual": o.value,
                                  "basis": basis, "hours_year": hrs, "hours_months": hours["months"] if basis == "actual" else None,
                                  "hourly": hourly, "gold_g_per_hour": hourly / cny_g})
    return out


def fx_recent(store: Store, months: int = 36) -> dict:
    out = {}
    for area in sorted(store.areas("fx_lcu_usd_ecb")):
        s = store.series("fx_lcu_usd_ecb", area)
        out[area] = [[p, s[p].value] for p in sorted(s)[-months:]]
    return out


def finite(x):
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError("non-finite number in dataset")
    return x
