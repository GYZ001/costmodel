"""Turn parsed observations into the dataset the website renders.

Every figure derived from the source data is computed here (its rules and checks are
unit-tested); the browser only adds display arithmetic on top (ratios, quantiles,
index lines, US-dollar values at the market rate).  Every derived figure is computed
from inputs of the SAME period: a year's average wage is converted with that year's
average exchange rate and that year's average gold price, and compared with
that year's prices.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from . import living
from .catalog import G20
from .config import GRAMS_PER_TROY_OUNCE
from .model import Obs, Store, annual_mean
from .msg import M, Msg, Part, canonical, key_of
from .sources import ilostat

WEEKS_PER_MONTH = 52 / 12  # 4.333…: converts weekly hours to monthly hours
COHD_GROUPS = ["staples", "vegetables", "fruits", "animal", "legumes", "oils"]


@dataclass
class WageVariant:
    key: str
    label: Msg
    concept: str
    source: Msg | str  # source line (a message, or the publisher's own name for its survey)
    monthly_lcu: float | None  # average (or median) monthly earnings
    hourly_lcu: float | None
    hours_week: float | None  # hours used for the hourly conversion (None when the source is hourly)
    method: Msg
    snapshots: list[str]
    caveat: list[Part] = field(default_factory=list)  # this project's notes and the publisher's note labels (verbatim)
    restricted: bool = False  # coverage limited, as the publisher states (e.g. urban units, private sector only)
    currency: str | None = None  # currency the publisher states for the figure
    label_hourly: Msg | None = None  # label when the hourly figure is derived from a monthly one
    series_id: str = ""  # the publisher's series and the notes defining it (a change between years is a change of concept or source)
    source_id: str = ""  # publisher and survey, e.g. "ILOSTAT BA:463", "OECD"
    series_key: str = ""  # publisher's series, e.g. "ILOSTAT ilo_monthly_mean@BA:463"
    notes_sig: list[str] = field(default_factory=list)  # labels of the notes that define what the figure measures


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
# (ILOSTAT, OECD) by an exchange rate or a PPP (World Bank WDI), a gold
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
# or, in a year without any of these, by carrying over an adjacent year's check (in
# either direction) when the value moved by less than MAX_FACTOR: its unit is taken not
# to have changed in between.
#
# Other inputs are then attached to a proven F or P:
#
#   C ~ P  healthy-diet cost in LCU ÷ the same cost in PPP $ = WDI PPP
#   W ~ F  ILOSTAT wage in LCU ÷ WDI exchange rate = ILOSTAT's own US$ figure
#   W ~ P  ILOSTAT wage in LCU ÷ WDI PPP = ILOSTAT's own PPP figure
#   W ~ L  OECD constant-price wage in national currency ÷ the same in US$ PPP =
#          WDI PPP of OECD's base year; or the currency OECD states (its unit code)
#          equals a currency proven for L
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

# A currency-unit mismatch shows up as a fixed conversion factor.  Since 2002 the
# smallest one among the redenominations and euro changeovers is Latvia's
# 1 EUR = 0.702804 LVL (×1.42); every other is ×1.7 or more (Cyprus ×1.71, BGN ×1.96,
# HRK ×7.53, redenominations ×5 to ×1,000,000).  In 2000-2001 the Irish pound
# (1 EUR = 0.787564 IEP, ×1.27) was still in use, which the bound cannot tell from the
# euro.  Two numbers whose ratio lies within ×/÷1.4 are taken to be in the same unit -
# a unit difference would need another difference in the opposite direction to hide
# inside the bound, which the check cannot rule out - and anything outside cannot be
# trusted to be in the same unit.  Differences inside the bound are not unit errors:
# PPP vintages, fiscal-year conversion (the World Bank converts fiscal-year national
# accounts at fiscal-year average rates: Australia, Egypt, …), publishers' own rates.
# The bound is about the UNIT, not about two exchange rates being the same rate: where the
# official rate and the factor the World Bank applied to GDP differ, both are published
# (fx, fx_gdp_factor) and the page states the difference.
MAX_FACTOR = 1.4

# A survey publisher's own release continues an ILOSTAT series (UnitGraph._extend) only if
# it equals ILOSTAT's republication of that series within this, on every year both have:
# rounding and small revisions, far below any difference of concept or coverage.
EXTENSION_TOL = 0.01

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
    source_name: str  # ILOSTAT's name for the source (survey), as it publishes it
    unit: str  # "hour" | "month"
    concept: str  # "mean" | "median" (from note T8 when present)
    obs: Obs
    usd: Obs | None
    ppp: Obs | None
    unusable: Msg | None  # what ILOSTAT's own notes or status say makes the value unusable
    restricted: bool  # coverage limited (area, population, establishment size, sector, activity, group, working time)
    currency: str | None
    signature: tuple  # concept-defining notes; a change between years breaks a series
    break_in_series: bool
    status: str | None  # ILOSTAT's observation status label, if any
    rejected: Msg | None = None  # left out by this project's magnitude / time-unit checks (with the numbers)
    unsure: Msg | None = None  # kept, but its time unit could not be confirmed against another source
    # Set when the value is not ILOSTAT's but the survey publisher's own release of the
    # same series, for a year ILOSTAT has not (yet) republished (see UnitGraph._extend):
    # the publisher's source id (catalog src.<id>) and how the series was matched.
    publisher: str | None = None
    match: Msg | None = None
    scope: Msg | None = None  # the publisher's own description of the figure (a continued year)
    break_note: Msg | None = None  # the publisher's own statement of a break in the series that year

    @property
    def usable(self) -> bool:
        return not (self.unusable or self.rejected)


# ILOSTAT note types that define what an earnings figure measures (not just where it
# comes from): central tendency, value type, gross/net, job coverage, reference period,
# coverage of area / population / establishment size / institutional sector / economic
# activity / reference group / working time / maximum age, working-time concept,
# components of earnings, minimum-wage type, employment definition.
COVERAGE_NOTES = ("S4", "S5", "S6", "S7", "S8", "S9", "T12", "T3")
CONCEPT_NOTES = ("T8", "T9", "T10", "T11", "T33", "T34", "S3", *COVERAGE_NOTES, "I19", "I20")


def restricts(prefix: str, label: str) -> bool:
    """Whether a coverage note limits a figure to part of a country's employees, read from
    ILOSTAT's label.  Every area, establishment-size, sector, activity, reference-group,
    population, working-time or maximum-age note does, except those stating the full
    scope - the whole national territory (with no area excluded but overseas territories),
    all employees (or all
    employment), full- and part-time workers, full-time equivalents (which re-weight all
    employees rather than select some), establishments of every size (the smaller ones
    by a sample) - and the exclusions every household survey has (people in institutions
    or collective quarters, armed forces), which do not change who the figure is about.
    A geographical note of "Not applicable" states no area and limits nothing.  Minimum-
    age notes are not coverage notes: every survey sets a working age, from which
    employees are counted; a maximum age leaves employed people out."""
    text = label.split(":", 1)[-1].strip().lower()
    if prefix == "S4":
        # Overseas territories are economies of their own in the World Bank's list (the
        # totals every figure is divided by), so leaving them out leaves the economy whole.
        return text not in ("total national", "total national, excluding overseas territories", "not applicable")
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
            unusable = M("d.ilo.not_average", label=lab(c))
    for c in ilostat.note_of(obs, "I19"):
        unusable = M("d.ilo.minimum_wage", label=lab(c))
    for c in ilostat.note_of(obs, "T9"):
        if not lab(c).endswith("Nominal values"):
            unusable = M("d.ilo.real_values", label=lab(c))
    for c in ilostat.note_of(obs, "T7"):
        if not lab(c).endswith("Per hour" if unit == "hour" else "Per month"):
            unusable = M(f"d.ilo.time_unit_{unit}", label=lab(c))
    st = store.get(f"{base}__status@{source}", obs.area, obs.period)
    status = ilostat.status_label(st.note, ilo_dic) if st else None
    if status and "reliab" in status.lower():  # "Unreliable" / "Low reliability"
        unusable = M("d.ilo.status", status=status)
    elif status and "real value" in status.lower():
        unusable = M("d.ilo.status_real", status=status)
    restricted = any(restricts(p, lab(c)) for p in COVERAGE_NOTES for c in ilostat.note_of(obs, p))
    signature = tuple(sorted(c for c in ilostat.codes(obs) if c.split(":", 1)[0] in CONCEPT_NOTES))
    return IloRecord(
        series=series, base=base, source=source, source_name=ilo_source_name(source, ilo_dic), unit=unit, concept=concept, obs=obs,
        usd=store.get(f"{base}_usd@{source}", obs.area, obs.period),
        ppp=store.get(f"{base}_ppp@{source}", obs.area, obs.period),
        unusable=unusable, restricted=restricted, currency=ilostat.currency(obs, ilo_dic),
        signature=signature, break_in_series=bool(ilostat.note_of(obs, "I11")) or (st is not None and st.note == "B"),
        status=status,
    )


def ilo_source_name(source: str, ilo_dic: dict) -> str:
    return ilo_dic.get("source", {}).get(source, source)


def ilo_note_labels(codes: list[str], ilo_dic: dict) -> list[str]:
    """ILOSTAT's own labels for note codes (English, verbatim), coverage notes first, then
    remarks, then the rest; the currency note (shown separately) and unlabelled codes
    are left out."""
    def order(c: str) -> int:
        p = c.split(":", 1)[0]
        return 0 if p in COVERAGE_NOTES else 1 if p == "I13" else 2
    labels = [(c, ilostat.label(c, ilo_dic)) for c in sorted(codes, key=order) if c.split(":", 1)[0] != "T30"]
    return list(dict.fromkeys(lab for c, lab in labels if lab and lab != c and lab != "None"))


def ilo_notes(rec: IloRecord, ilo_dic: dict) -> list[str]:
    """All of ILOSTAT's notes on a figure, plus its observation status (English, verbatim)."""
    return ilo_note_labels(ilostat.codes(rec.obs), ilo_dic) + ([f"Observation status: {rec.status}"] if rec.status else [])


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
    desc: Msg  # how the figure is described in reasons
    own_hours: bool = True  # the monthly basis uses the same survey's hours (False: other sources' hours)


Jump = Callable[[IloRecord], tuple[float, Msg] | None]


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
    disputes: dict[int, list[tuple[_Point, float, Msg]]] = defaultdict(list)
    vouched: dict[int, bool] = defaultdict(bool)
    unsure: dict[int, list[Msg]] = defaultdict(list)

    def note(p: _Point, q: _Point, gap: float, why: Msg) -> None:
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
                         M("d.tu.hours_range", m=m.desc, h=h.desc, implied=implied, max=HOURS_IN_MONTH))
                elif h.monthly is not None:
                    gap = max(m.value / h.monthly, h.monthly / m.value)
                    if (gap > TIME_FACTOR) if h.own_hours else (gap >= UNIT_GAP):
                        note(p, q, gap, M("d.tu.same_survey" if h.own_hours else "d.tu.other_hours",
                                          h=h.desc, m=m.desc, r=h.monthly / m.value,
                                          bound=TIME_FACTOR if h.own_hours else UNIT_GAP))
            elif p.source != q.source and p.concept == q.concept and p.monthly is not None and q.monthly is not None:
                gap = max(p.monthly / q.monthly, q.monthly / p.monthly)
                if gap <= TIME_FACTOR:
                    vouched[id(p)] = vouched[id(q)] = True
                elif gap >= UNIT_GAP:
                    note(p, q, gap, M("d.tu.cross", p=p.desc, q=q.desc, r=p.monthly / q.monthly, bound=UNIT_GAP))
                else:
                    for a, b in ((p, q), (q, p)):
                        unsure[id(a)].append(M("d.tu.unsure_part", q=b.desc, r=a.monthly / b.monthly))
    trusted = lambda q: q.rec is None or vouched[id(q)]  # noqa: E731
    out: dict[int, Msg] = {}
    for p in points:
        if p.rec is None or not disputes[id(p)] or vouched[id(p)]:
            continue
        against = disputes[id(p)]
        why = list({canonical(t): t for _q, _g, t in against[:2]}.values())
        if any(trusted(q) for q, _g, _t in against):
            out[id(p)] = M("d.tu.verdict_vouched", this=p.desc, why=why)
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
            out[id(p)] = M("d.tu.verdict_jump" if all(t is not None for _p, _q, t in verdicts) else "d.tu.verdict_jump_no_series",
                           this=p.desc, why=why, jump=mine[1])
        else:
            out[id(p)] = M("d.tu.verdict_undecided", this=p.desc, why=why)
    # Whatever still contradicts each other after the verdicts is undecided: leave out both.
    decided = set(out)
    for p in points:
        if p.rec is None or id(p) in decided or vouched[id(p)]:
            continue
        for q, _g, t in disputes[id(p)]:
            if q.rec is None or id(q) not in decided:
                out[id(p)] = M("d.tu.verdict_undecided", this=p.desc, why=[t])
                break
    for p in points:
        if p.rec is None:
            continue
        if id(p) in out:
            p.rec.rejected = out[id(p)]
        elif unsure[id(p)] and not vouched[id(p)]:
            p.rec.unsure = M("d.tu.unsure", parts=unsure[id(p)], low=TIME_FACTOR, high=UNIT_GAP)


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
    def _exclude(self, area: str, year: str, scope: str, detail: Part, kind: str) -> None:
        """kind: unit (cannot be shown to be in the same currency unit), identity (an
        identity fails although the unit is the same, cause unknown), missing (the
        publisher has no value), notes (by the publisher's own notes not a nominal
        average or median wage of the year, or its status is unreliable), check (fails
        this project's magnitude, time-unit or hours checks), area, chosen (usable, but
        another figure of the same kind comes first).  year "*" = every year."""
        self.log.append({"area": area, "year": year, "scope": scope, "kind": kind, "detail": detail})

    def log_not_chosen(self, area: str, year: str, scope: str, detail: Msg) -> None:
        """A usable figure another figure of the same kind was preferred to (ilo_variants)."""
        self._exclude(area, year, scope, detail, "chosen")

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
                self._exclude(code, "*", "area", M("d.area.unmatched", code=code, name=name) if name
                              else M("d.area.unmatched_unnamed", code=code), "area")
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
        self._extend(area, out)
        return out

    # ---- a series continued with its publisher's own release
    def _extend(self, area: str, out: dict[str, list[IloRecord]]) -> None:
        """ILOSTAT republishes national surveys with a delay.  Where a reader of the
        survey publisher's own release supplies the same series (store series
        "ext_<ILOSTAT series>", e.g. ext_ilo_monthly_mean@FX:216), its values for the
        years ILOSTAT has not republished continue the ILOSTAT series - the same rule for
        every economy and survey.  They are used only if, for every year both have, the
        two agree within EXTENSION_TOL (the evidence that it is the same series); a
        continued year is described by what the series measures - the notes of its latest
        ILOSTAT year that define the concept (CONCEPT_NOTES), its currency and time unit,
        not the notes about that year itself (a break in series, remarks, repository
        notes): a break in the publisher's series comes from the publisher ("__break") -
        and is then checked like any other record."""
        src = self.ilo_area(area)
        for ext in self.store.series_names(area, "ext_ilo_"):
            if ext.endswith("__break"):
                continue  # read with the series it marks, below
            series = ext[len("ext_"):]
            theirs = {y: o for y, o in self.store.series(ext, area).items()}
            ours = {y: r for y, recs in out.items() for r in recs if r.series == series}
            common = sorted(set(theirs) & set(ours))
            scope = _wage_scope(next(iter(ours.values()))) if ours else "wage:extension"
            publisher = next(iter(theirs.values())).note
            if not common:
                self._exclude(area, "*", scope, M("d.ext.no_overlap", publisher=M(f"src.{publisher}.publisher"),
                                                  series=series.split("@", 1)[1]), "check")
                continue
            worst = max(common, key=lambda y: abs(math.log(theirs[y].value / ours[y].obs.value)))
            r = theirs[worst].value / ours[worst].obs.value
            if not (1 / (1 + EXTENSION_TOL) <= r <= 1 + EXTENSION_TOL):
                self._exclude(area, "*", scope, M("d.ext.disagree", publisher=M(f"src.{publisher}.publisher"), year=worst,
                                                  theirs=theirs[worst].value, ilo=ours[worst].obs.value, tol=EXTENSION_TOL), "check")
                continue
            last = max(ours)
            template = ours[last]
            concept = " ".join(c for c in ilostat.codes(template.obs) if c.split(":", 1)[0] in (*CONCEPT_NOTES, "T30", "T7"))
            gap = max(abs(theirs[y].value / ours[y].obs.value - 1) for y in common)
            match = M("d.ext.match", publisher=M(f"src.{publisher}.publisher"), years=common, worst=gap)
            for y, o in sorted(theirs.items()):
                if y in ours or y < last:
                    continue
                rec = ilo_record(self.store, series, Obs(series, src, y, o.value, o.snapshot, concept), self.ilo_dic)
                rec.publisher, rec.match = publisher, match
                # What the publisher says the figure is, next to ILOSTAT's notes on the series
                # (which describe ILOSTAT's figures and may word the coverage differently).
                rec.scope = M("d.ext.scope", publisher=M(f"src.{publisher}.publisher"), scope=M(f"src.{publisher}.series"))
                if self.store.get(ext + "__break", area, y):
                    rec.break_in_series = True
                    rec.break_note = M("d.ext.break", publisher=M(f"src.{publisher}.publisher"))
                out[y].append(rec)

    # ---- hours
    def _hours(self, area: str) -> tuple[dict[str, dict[str, float]], list[tuple[str, Msg]]]:
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
        name = lambda s: ilo_source_name(s, self.ilo_dic)  # noqa: E731
        oecd = {y: o.value for y, o in self.store.series("oecd_usual_weekly_hours_ft", area).items()}
        out: dict[str, dict[str, float]] = defaultdict(dict)
        bad: list[tuple[str, Msg]] = []
        for y, v in oecd.items():
            out[y]["OECD"] = v
        possible = {s: {y: o.value for y, o in series.items() if 0 < o.value <= HOURS_IN_WEEK} for s, series in ilo.items()}
        for s, series in ilo.items():
            for y, o in sorted(series.items()):
                v = o.value
                if y not in possible[s]:
                    bad.append((y, M("d.hours.impossible", source=name(s), v=v, max=HOURS_IN_WEEK)))
                    continue
                others = [(M("d.hours.cmp", source=M("d.hours.src_ilo", source=name(t)), v=possible[t][y]), possible[t][y])
                          for t in sorted(possible) if t != s and y in possible[t]]
                others += [(M("d.hours.cmp", source=M("d.hours.src_oecd"), v=oecd[y]), oecd[y])] if y in oecd else []
                if not others:
                    ys = sorted(possible[s])
                    i = ys.index(y)
                    others = [(M("d.hours.cmp_year", year=n, v=possible[s][n]), possible[s][n]) for n in ys[max(0, i - 1):i + 2] if n != y]
                if others and not any(same_unit(v, w, TIME_FACTOR) for _d, w in others):
                    bad.append((y, M("d.hours.unconfirmed", source=name(s), v=v, others=[d for d, _w in others], bound=TIME_FACTOR)))
                    continue
                out[y][s] = v
        return out, bad

    def _time_check(self, area: str, year: str, recs: list[IloRecord], oecd_monthly: float | None,
                    hours: dict[str, float], jump: Jump) -> None:
        def monthly_hours(source: str) -> tuple[float, Msg, bool] | None:
            if source in hours:
                return hours[source] * WEEKS_PER_MONTH, M("d.hours.own", h=hours[source]), True
            if hours:
                vals = sorted(hours.values())
                mid = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
                return mid * WEEKS_PER_MONTH, M("d.hours.median_with_oecd" if "OECD" in hours else "d.hours.median", h=mid), False
            return None

        points = []
        for r in recs:
            what = M(f"d.pt.ilo_{r.concept}_{r.unit}", source=r.source_name, v=r.obs.value)
            if r.unit == "month":
                points.append(_Point("month", r.concept, r.obs.value, r.source, r, r.obs.value, what))
            else:
                h = monthly_hours(r.source)
                points.append(_Point("hour", r.concept, r.obs.value, r.source, r, r.obs.value * h[0] if h else None,
                                     M("d.pt.with_hours", pt=what, hours=h[1], m=r.obs.value * h[0]) if h else what,
                                     h[2] if h else True))
        # Magnitude: a month's pay must lie between a week's worth of household consumption
        # per head and a year's worth of GDP per head - beyond either, the figure's time unit
        # or scale is taken to be wrong.  The verdict covers every figure of that survey in
        # that time unit (mean and median share it).
        s = self.store
        pop = s.get("population", area, year)
        gdp, hfce = s.get("gdp_lcu", area, year), s.get("hfce_lcu", area, year)
        top = gdp.value / pop.value if gdp and pop else None
        floor = hfce.value / pop.value / 12 / WEEKS_PER_MONTH if hfce and pop else None
        groups: dict[tuple[str, str], Msg] = {}
        for p in points:
            if p.monthly is None:
                continue
            if top is not None and p.monthly > top:
                groups.setdefault((p.source, p.unit), M("d.mag.above_gdp", p=p.desc, top=top))
            elif floor is not None and p.monthly < floor:
                groups.setdefault((p.source, p.unit), M("d.mag.below_consumption", p=p.desc, floor=floor))
        for p in points:
            if (p.source, p.unit) in groups:
                p.rec.rejected = M(f"d.mag.survey_{p.unit}", reason=groups[(p.source, p.unit)])
        points = [p for p in points if p.rec.rejected is None]
        if oecd_monthly is not None:
            points.append(_Point("month", "mean", oecd_monthly, "OECD", None, oecd_monthly, M("d.pt.oecd", v=oecd_monthly)))
        _check_time_units(points, jump)

    # ---- continuity of a series
    # Message describing each yardstick: d.yard.hfce_lcu (household consumption per head),
    # d.yard.gdp_lcu (GDP per head).
    YARDSTICKS = ("hfce_lcu", "gdp_lcu")

    def nominal_growth(self, area: str, y0: str, y1: str, gdp: bool = True) -> tuple[float, str] | None:
        """Growth of nominal income per head from y0 to y1, in WDI's local-currency
        series: household consumption per head, or GDP per head where WDI has no
        household consumption for both years."""
        g = self._growths(area, y0, y1)
        for series in self.YARDSTICKS[:2 if gdp else 1]:
            if series in g:
                return g[series], series
        return None

    def _growths(self, area: str, y0: str, y1: str) -> dict[str, float]:
        s = self.store
        p0, p1 = s.get("population", area, y0), s.get("population", area, y1)
        out = {}
        for series in self.YARDSTICKS:
            a, b = s.get(series, area, y0), s.get(series, area, y1)
            if p0 and p1 and a and b and a.value > 0 and b.value > 0:
                out[series] = (b.value / p1.value) / (a.value / p0.value)
        return out

    def _level_bounds(self) -> dict[str, dict[int, float]]:
        """How far a wage series can move against nominal income per head without a
        change in what it measures, by yardstick (household consumption or GDP per head)
        and by number of years apart: the widest such move seen in OECD's harmonised
        average-wage series (same currency) over that many years or fewer, in the archive."""
        widest: dict[str, dict[int, float]] = {series: {} for series in self.YARDSTICKS}
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

    def shift(self, area: str, y0: str, v0: float, y1: str, v1: float, same_concept: bool = True) -> tuple[bool | None, Msg]:
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
            return None, M("d.shift.no_data", y0=y0, y1=y1)
        r = v1 / v0
        parts, flags = [], []
        for series in self.YARDSTICKS:
            if series not in g:
                continue
            bound = bounds[series]
            flags.append(not same_unit(r, g[series], bound))
            yard = M(f"d.yard.{series}")
            parts.append(M("d.shift.vs_bound", yard=yard, g=g[series], n=k, bound=bound) if same_concept
                         else M("d.shift.vs", yard=yard, g=g[series]))
        if not same_concept:
            parts.append(M("d.shift.concept_changed", bound=TIME_FACTOR))
        return (not all(flags)), M("d.shift", y0=y0, y1=y1, r=r, parts=parts)


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

    def _consistent(self, area, rec, ilo, graphs, final) -> tuple[bool | None, list[Msg]]:
        verdicts = []
        for n in self._neighbours(rec, ilo, graphs, final):
            first, second = sorted([n, rec], key=lambda r: r.obs.period)
            same = first.signature == second.signature and not second.break_in_series
            verdicts.append(self.shift(area, first.obs.period, first.obs.value, second.obs.period, second.obs.value, same))
        if any(v[0] is False for v in verdicts):
            return False, [v[1] for v in verdicts if v[0] is False]
        if verdicts and all(v[0] for v in verdicts):
            return True, []
        return None, []

    def _jump(self, area, ilo, graphs) -> Jump:
        """For the time-unit tie-break: the largest move (in log terms) of a record against
        its series' nearest usable years, relative to nominal income per head."""
        def jump(rec: IloRecord) -> tuple[float, Msg] | None:
            out = None
            for n in self._neighbours(rec, ilo, graphs, final=False):
                first, second = sorted([n, rec], key=lambda r: r.obs.period)
                g = self.nominal_growth(area, first.obs.period, second.obs.period)
                if g is None:
                    continue
                size = abs(math.log((second.obs.value / first.obs.value) / g[0]))
                if out is None or size > out[0]:
                    out = (size, M("d.jump", y0=first.obs.period, y1=second.obs.period, r=second.obs.value / first.obs.value,
                                   yard=M(f"d.yard.{g[1]}"), g=g[0]))
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

    def _prove(self, values: dict[str, float], direct: dict[str, tuple[bool | None, list[Msg]]],
               failed: Msg, carry=None) -> dict[str, tuple[bool | None, list[Msg], str]]:
        """Year-by-year verdict on whether a factor (F or P) is in L, as (verdict, detail,
        kind): that year's identity, or else an adjacent year's proof carried over when the
        value moved by less than MAX_FACTOR (first forwards, then backwards).

        direct[y] holds the identity's verdict and numbers (or why it cannot be checked), as
        a list of messages.
        A year whose identity fails although its value is linked to a proven year by
        year-to-year moves within MAX_FACTOR cannot be in another unit (the premise of the
        carry-over): the failure has another cause, unknown, and the year is left out as
        such (kind "identity"), not as a unit failure (kind "unit", with ``failed``).

        carry(y, n), if given, is a second way to link year y to year n, for the carry-over
        and for the chain alike (it returns (holds, message describing the comparison, or
        None where it does not apply)); its message is added where neither way links."""
        out = {y: (ok, d, "unit") for y, (ok, d) in direct.items()}
        for step, order in ((1, self.years), (-1, self.years[::-1])):
            for y in order:
                n = str(int(y) - step)
                if y in values and out[y][0] is None and n in values and out[n][0] is True \
                        and (same_unit(values[y], values[n]) or (carry is not None and carry(y, n)[0])):
                    out[y] = (True, [], "")
        # Identity failures linked to a proven year by moves of less than MAX_FACTOR.  Each
        # linked year records its proven year and whether any step on the way used carry
        # (so the message names what the steps compared).
        anchor = {y: (y, False) for y, v in out.items() if v[0] is True}
        changed = True
        while changed:
            changed = False
            for y, (ok, detail, _k) in sorted(out.items()):
                if ok is not False or y in anchor:
                    continue
                close = [n for n in (str(int(y) - 1), str(int(y) + 1)) if n in anchor
                         and (same_unit(values[y], values[n]) or (carry is not None and carry(y, n)[0]))]
                if close:
                    n = close[0]
                    a, carried = anchor[n]
                    via = (M("d.prove.link_direct", n=n) if a == n
                           else M("d.prove.link_chain_share" if carried else "d.prove.link_chain", n=n, a=a, bound=MAX_FACTOR))
                    by_value = same_unit(values[y], values[n])
                    msg = (M("d.prove.chain", detail=detail, n=n, vn=values[n], r=values[y] / values[n], link=via)
                           if by_value
                           else M("d.prove.chain_link", detail=detail, why=carry(y, n)[1], link=via))
                    out[y] = (None, [msg], "identity")
                    anchor[y] = (a, carried or not by_value)
                    changed = True
        for y, (ok, detail, kind) in list(out.items()):
            if ok is False:
                out[y] = (False, [M("d.prove.failed", detail=detail, bound=MAX_FACTOR, failed=failed)], "unit")
            elif ok is None and kind == "unit":
                near = [n for n in (str(int(y) - 1), str(int(y) + 1)) if n in values and out[n][0] is True]
                msgs = []
                for n in near:
                    msgs.append(M("d.prove.no_carry", n=n, vn=values[n], r=values[y] / values[n]))
                    if carry is not None and (m := carry(y, n)[1]) is not None:
                        msgs.append(m)
                out[y] = (None, detail + (msgs or [M("d.prove.no_neighbour")]), "unit")
        return out

    def _factors(self, area: str) -> tuple[dict, dict, dict]:
        """Verdicts for F, P and H by year: (True = in L, False = cannot be in L, None = unknown; detail; kind).

        H is WDI's household consumption in local currency.  It is in L where it divides
        into WDI's international-dollar figure as the PPP does (the PPP's own identity),
        and is carried over between years like F and P - by its own value, or by its share
        of GDP in local currency between two years in which that GDP is itself shown to be
        in L by the exchange rate's identity (a change of unit in consumption alone would
        move the share by more than MAX_FACTOR; under high inflation the value itself moves
        that much while the share does not).  An ICP price level that proves the PPP says
        nothing about H."""
        s = self.store
        fx = {y: o.value for y in self.years if (o := s.get("fx_lcu_usd", area, y))}
        ppp = {y: o.value for y in self.years if (o := s.get("ppp_hfce", area, y))}

        def identity(val, num, den, what, missing) -> tuple[bool | None, list[Msg]]:
            if num and den and den.value > 0:
                implied = num.value / den.value
                return same_unit(val, implied), [M(what, v=val, i=implied, r=val / implied)]
            return None, [M(missing)]

        f_direct = {y: identity(v, s.get("gdp_lcu", area, y), s.get("gdp_usd", area, y), "d.fx.identity", "d.fx.missing_gdp")
                    for y, v in fx.items()}
        f = self._prove(fx, f_direct, M("d.fx.failed"))
        direct, h_direct = {}, {}
        for y, v in ppp.items():
            ok, detail = identity(v, s.get("hfce_lcu", area, y), s.get("hfce_intl", area, y), "d.ppp.identity", "d.ppp.missing_hfce")
            h_direct[y] = (ok, list(detail))
            if ok is None and y == ICP_YEAR:
                lvl = self.icp_price_level(area)
                if lvl is None:
                    detail.append(M("d.ppp.no_icp", icp=ICP_YEAR))
                elif f.get(y, (None,))[0] is not True:
                    detail.append(M("d.ppp.icp_fx_unproven", year=y))
                else:
                    implied = lvl * fx[y]
                    ok = same_unit(v, implied)
                    detail = [M("d.ppp.icp", v=v, icp=ICP_YEAR, lvl=lvl, fx=fx[y], i=implied, r=v / implied)]
            direct[y] = (ok, detail)
        hfce = {y: o.value for y in self.years if (o := s.get("hfce_lcu", area, y)) and o.value > 0}
        h_direct = {y: h_direct.get(y, (None, [M("d.hfce.no_ppp")])) for y in hfce}
        # GDP in local currency is in L in the years the exchange rate's own identity holds.
        gdp = {y: o.value for y in hfce if f_direct.get(y, (None,))[0] is True and (o := s.get("gdp_lcu", area, y)) and o.value > 0}

        def share_link(y: str, n: str) -> tuple[bool, Msg | None]:
            if y not in gdp or n not in gdp:
                return False, None
            sy, sn = hfce[y] / gdp[y], hfce[n] / gdp[n]
            return same_unit(sy, sn), M("d.hfce.share", n=n, sn=sn, sy=sy, r=sy / sn)
        return f, self._prove(ppp, direct, M("d.ppp.failed")), self._prove(hfce, h_direct, M("d.hfce.failed"), share_link)

    def consumption(self, area: str, year: str) -> tuple[float | None, list[str], tuple | None]:
        """Household consumption per resident per month in L (living.consumption_month), its
        snapshots, and - where WDI publishes the year's figure but it is not shown to be in L
        - the verdict that says why (verdict, detail, kind)."""
        cons, snaps = living.consumption_month(self.store, area, year)
        if cons is None or self.year(area, year).linked("H"):
            return cons, snaps, None
        return None, [], self.area(area)["checks"].get(year, {}).get("H", (None, [M("d.hfce.no_ppp")], "unit"))

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
        f_ok, p_ok, h_ok = self._factors(area)
        graphs: dict[str, _UnionFind] = {}
        checks: dict[str, dict] = {}
        ambiguous: dict[tuple[str, str], Msg] = {}
        attached: dict[str, tuple[str, float]] = {}  # series -> its latest year attached to L, and value
        carried: dict[tuple[str, str], Msg] = {}  # (year, series) of a continued year not attached, why
        for y in self.years:
            g = _UnionFind()
            c: dict = {}
            fx, ppp = s.get("fx_lcu_usd", area, y), s.get("ppp_hfce", area, y)
            for node, verdicts in (("F", f_ok), ("P", p_ok), ("H", h_ok)):
                if y in verdicts:
                    c[node] = verdicts[y]  # (verdict, detail, kind)
                    if verdicts[y][0]:
                        g.union(node, "L")
            lcu, cost_ppp = s.get("cohd_total", area, y), s.get("cohd_total_ppp", area, y)
            if lcu:
                if cost_ppp and ppp and cost_ppp.value > 0:
                    implied = lcu.value / cost_ppp.value
                    ok = same_unit(implied, ppp.value)
                    c["C"] = (ok, M("d.cohd.failed", i=implied, ppp=ppp.value, r=implied / ppp.value, bound=MAX_FACTOR))
                    if ok:
                        g.union("C", "P")
                else:
                    c["C"] = (None, M("d.cohd.missing_ppp_cost") if not cost_ppp else M("d.cohd.missing_ppp"))
            # W: attach a wage to a proven F or P.
            f_in, p_in = g.linked("F"), g.linked("P")
            f_out, p_out = c.get("F", (None,))[0] is False, c.get("P", (None,))[0] is False
            for rec in ilo.get(y, []):
                node = f"ilo:{rec.series}"
                g.find(node)
                if rec.unusable:
                    continue
                if rec.publisher:
                    # A continued year has no ILOSTAT conversions to check its currency unit
                    # against; it is attached to L through the same series' latest earlier
                    # year that is attached, when the value moved by no more than MAX_FACTOR.
                    prev = attached.get(rec.series)
                    if prev and same_unit(rec.obs.value, prev[1]):
                        g.union(node, "L")
                    else:
                        carried[(y, rec.series)] = (M("d.ext.carried", year=prev[0], prev=prev[1], v=rec.obs.value,
                                                      r=rec.obs.value / prev[1], bound=MAX_FACTOR) if prev
                                                    else M("d.ext.not_carried"))
                    if g.linked(node):
                        attached[rec.series] = (y, rec.obs.value)
                    continue
                agrees_f = bool(rec.usd and fx and same_unit(rec.obs.value / fx.value, rec.usd.value))
                agrees_p = bool(rec.ppp and ppp and same_unit(rec.obs.value / ppp.value, rec.ppp.value))
                if (agrees_f and f_out and agrees_p and p_in) or (agrees_p and p_out and agrees_f and f_in):
                    ambiguous[(y, rec.series)] = M("d.ilo.ambiguous", bound=MAX_FACTOR)
                    continue
                if (agrees_f and f_in) or (agrees_p and p_in):
                    g.union(node, "L")
                    attached[rec.series] = (y, rec.obs.value)
            graphs[y], checks[y] = g, c
        # Currency of L, from ILOSTAT records attached to it.
        codes: set[str] = set()
        for y, g in graphs.items():
            codes |= {r.currency for r in ilo.get(y, []) if r.currency and not r.unusable and g.linked(f"ilo:{r.series}")}
        oecd_unit = {y: o.note for y, o in s.series("oecd_avg_annual_wage", area).items()}
        base_unit = oecd_ppp[2]
        if oecd_ppp[0] and base_unit:
            codes.add(base_unit)
        # OECD states its currency unit.
        for y, g in graphs.items():
            u = oecd_unit.get(y)
            if u and ((oecd_ppp[0] and u == base_unit) or (u in codes and len(codes) == 1)):
                g.union("oecd", "L")
        if len(codes) > 1:
            self._exclude(area, "*", "currency", M("d.currency.conflict", codes=sorted(codes)), "unit")
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
                "oecd_unit": oecd_unit, "ambiguous": ambiguous, "hours": hours, "carried": carried}

    def _oecd_ppp_identity(self, area: str) -> tuple[bool | None, Msg, str | None]:
        """OECD national-currency wages at constant prices ÷ the same in US$ PPPs is the
        PPP of OECD's base year; it must equal WDI's household PPP of that year.
        Returns (verdict, detail, unit of OECD's national-currency series)."""
        s = self.store
        q, qp = s.series("oecd_avg_annual_wage_q", area), s.series("oecd_avg_annual_wage_q_usdppp", area)
        common = sorted(set(q) & set(qp))
        if not common:
            return (None, M("d.oecd.no_ppp"), None)
        y = common[-1]
        unit, base = q[y].note.split()
        implied = q[y].value / qp[y].value
        ppp = s.get("ppp_hfce", area, base)
        hl, hi = s.get("hfce_lcu", area, base), s.get("hfce_intl", area, base)
        if not (ppp and hl and hi) or not same_unit(ppp.value, hl.value / hi.value):
            return (None, M("d.oecd.base_unverified", base=base), unit)
        return (same_unit(implied, ppp.value), M("d.oecd.identity", base=base, i=implied, ppp=ppp.value, r=implied / ppp.value), unit)

    # ---- reasons for what is left out
    def explain(self, area: str, year: str, has_data: bool) -> None:
        a = self.area(area)
        c, g = a["checks"].get(year, {}), a["years"].get(year)
        if not has_data or g is None:
            return
        s = self.store
        for k, scope, series in (("F", "fx", "fx_lcu_usd"), ("P", "ppp", "ppp_hfce")):
            if not s.get(series, area, year):
                self._exclude(area, year, scope, M(f"d.missing.{scope}"), "missing")
                continue
            ok, detail, kind = c.get(k, (True, [], ""))
            if not g.linked(k) and ok is not True and detail:
                self._exclude(area, year, scope, detail, kind)
        if "H" in c and not g.linked("H"):
            ok, detail, kind = c["H"]
            self._exclude(area, year, "living:consumption", detail, kind)
        if "C" in c and not g.linked("C"):
            ok, detail = c["C"]
            if ok is True:  # the diet cost matches the PPP, but the PPP itself is not proven
                detail = M("d.cohd.ppp_unproven")
            self._exclude(area, year, "cohd", detail, "missing" if key_of(detail) == "d.cohd.missing_ppp_cost" else "unit")
        if s.get("oecd_avg_annual_wage", area, year) and not g.linked("oecd"):
            unit = a["oecd_unit"].get(year)
            self._exclude(area, year, "wage:oecd", M("d.oecd.unproven", detail=a["oecd_ppp"][1], unit=unit,
                                                     codes=sorted(a["codes"]) or M("d.none")), "unit")
        fx, ppp = s.get("fx_lcu_usd", area, year), s.get("ppp_hfce", area, year)
        for rec in a["ilo"].get(year, []):
            if rec.unusable or rec.rejected:
                self._exclude(area, year, _wage_scope(rec), M("d.series", source=rec.source_name, reason=rec.unusable or rec.rejected),
                              "notes" if rec.unusable else "check")
            elif (year, rec.series) in a["carried"] and not g.linked(f"ilo:{rec.series}"):
                self._exclude(area, year, _wage_scope(rec), M("d.series", source=rec.source_name, reason=a["carried"][(year, rec.series)]), "unit")
            elif (year, rec.series) in a["ambiguous"]:
                self._exclude(area, year, _wage_scope(rec), M("d.series", source=rec.source_name, reason=a["ambiguous"][(year, rec.series)]), "unit")
            elif not g.linked(f"ilo:{rec.series}"):
                parts = []
                if not fx:
                    parts.append(M("d.wage.no_fx"))
                elif not rec.usd:
                    parts.append(M("d.wage.no_usd"))
                elif same_unit(rec.obs.value / fx.value, rec.usd.value):
                    parts.append(M("d.wage.usd_agrees"))
                else:
                    parts.append(M("d.wage.usd", v=rec.obs.value, usd=rec.obs.value / fx.value, ilo=rec.usd.value))
                if not ppp:
                    parts.append(M("d.wage.no_ppp"))
                elif not rec.ppp:
                    parts.append(M("d.wage.no_ppp_value"))
                elif same_unit(rec.obs.value / ppp.value, rec.ppp.value):
                    parts.append(M("d.wage.ppp_agrees"))
                else:
                    parts.append(M("d.wage.ppp", v=rec.obs.value, i=rec.obs.value / ppp.value, ilo=rec.ppp.value))
                self._exclude(area, year, _wage_scope(rec), M("d.wage.unit", source=rec.source_name, parts=parts), "unit")


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

    # A usable record not chosen is named in the exclusions, with the one chosen instead.
    for r in usable.get(year, []):
        c = chosen.get((r.concept, r.unit))
        if c is not None and c is not r:
            units.log_not_chosen(area, year, _wage_scope(r), M("d.ilo.not_chosen", source=r.source_name, v=r.obs.value,
                                                              chosen=c.source_name))

    def src_label(r: IloRecord) -> Part:
        if r.publisher:
            return M("d.src.ext", source=r.source_name, publisher=M(f"src.{r.publisher}.publisher"))
        return f"ILOSTAT · {r.source_name}"

    def caveat(r: IloRecord) -> list[Part]:
        ok, why = units.series_consistent(area, r)
        out: list[Part] = [M("d.cav.shift", why=why)] if ok is False else []
        if r.unsure:
            out.append(r.unsure)
        mean = chosen.get(("mean", r.unit))
        if r.concept == "median" and mean is not None and mean.source == r.source and r.obs.value > mean.obs.value:
            out.append(M("d.cav.median_above_mean", median=r.obs.value, mean=mean.obs.value))
        # What the figure measures first (charts show the start of this list), where it comes
        # from last.
        return out + [m for m in (r.break_note, r.scope) if m] + ilo_notes(r, ilo_dic) + ([r.match] if r.match else [])

    def ids(r: IloRecord) -> dict:
        return {"source_id": f"ILOSTAT {r.source}", "series_key": f"ILOSTAT {r.series}",
                "notes_sig": ilo_note_labels(list(r.signature), ilo_dic),
                "series_id": " ".join(("ILOSTAT", r.series, *r.signature))}

    hours_by_source = units.area(area)["hours"].get(year, {})
    out: list[WageVariant] = []
    for concept in ("mean", "median"):
        direct = chosen.get((concept, "hour"))
        monthly = chosen.get((concept, "month"))
        if direct:
            out.append(WageVariant(
                key=f"ilo_{concept}_hourly", label=M(f"w.ilo_{concept}_hourly"),
                concept=concept, source=src_label(direct), monthly_lcu=None, hourly_lcu=direct.obs.value, hours_week=None,
                method=M("d.method.ilo_hourly"), snapshots=[direct.obs.snapshot], caveat=caveat(direct),
                restricted=direct.restricted, currency=direct.currency, **ids(direct),
            ))
        if monthly:
            # Hours only from the same survey (same ILOSTAT source) as the earnings, and
            # only hours that passed UnitGraph._hours.
            # The survey's own usable hourly figure, if ILOSTAT publishes one, makes a
            # derived one redundant (whether or not it is the hourly figure chosen); another
            # survey's hourly figure does not.
            same_survey_hourly = any(r.unit == "hour" and r.concept == concept and r.source == monthly.source
                                     for r in usable.get(year, []))
            hours = hours_by_source.get(monthly.source)
            hours_obs = store.get(f"ilo_weekly_hours@{monthly.source}", units.ilo_area(area), year) if hours else None
            derive = hours is not None and not same_survey_hourly
            label = M(f"w.ilo_{concept}_monthly")
            out.append(WageVariant(
                key=f"ilo_{concept}_monthly", label=label, concept=concept, source=src_label(monthly),
                monthly_lcu=monthly.obs.value,
                hourly_lcu=monthly.obs.value / (hours * WEEKS_PER_MONTH) if derive else None,
                hours_week=hours if derive else None,
                method=M("d.method.ilo_derived" if derive else "d.method.ilo_monthly_only" if same_survey_hourly else "d.method.ilo_no_hours"),
                snapshots=[monthly.obs.snapshot] + ([hours_obs.snapshot] if derive else []),
                caveat=caveat(monthly), restricted=monthly.restricted, currency=monthly.currency,
                label_hourly=M("w.derived_hourly", label=label) if derive else None, **ids(monthly),
            ))
    return out


def oecd_variant(store: Store, units: UnitGraph, area: str, year: str) -> WageVariant | None:
    w = store.get("oecd_avg_annual_wage", area, year)
    if not w or not units.year(area, year).linked("oecd"):
        return None
    h = store.get("oecd_usual_weekly_hours_ft", area, year)
    zero = store.get("oecd_usual_weekly_hours_ft__zero", area, year)
    return WageVariant(
        key="oecd_fte", label=M("w.oecd_fte"), concept="mean", source="OECD · Average annual wages",
        monthly_lcu=w.value / 12,
        hourly_lcu=w.value / (h.value * 52) if h else None,
        hours_week=h.value if h else None,
        method=(M("d.method.oecd", h=h.value) if h else M("d.method.oecd_zero_hours") if zero else M("d.method.oecd_no_hours")),
        snapshots=[w.snapshot] + ([h.snapshot] if h else []),
        caveat=[M("d.cav.oecd")],
        currency=w.note, series_id="OECD AV_AN_WAGE", source_id="OECD", series_key="OECD AV_AN_WAGE",
    )


# --------------------------------------------------------------------------------------
# Country-year table
# --------------------------------------------------------------------------------------

def country_years(store: Store, gold: dict, meta: dict, ilo_dic: dict, years: list[str], units: UnitGraph) -> dict:
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
            ov = oecd_variant(store, units, area, y)
            variants = ([ov] if ov else []) + ilo_variants(store, units, area, y, ilo_dic)
            has_data = bool(store.get("oecd_avg_annual_wage", area, y) or units.area(area)["ilo"].get(y)
                            or store.get("cohd_total", area, y))
            units.explain(area, y, has_data)
            if not variants and not cohd["total"]:
                continue
            gold_lcu_g = g["usd_g"] * fx.value if fx else None
            pli = ppp.value / fx.value if ppp and fx else None
            wages = [wage_metrics(v, gold_lcu_g, fx.value if fx else None, ppp.value if ppp else None,
                                  cohd["total"].value if cohd["total"] else None) for v in variants]
            mark_roles(wages)
            # Living costs: household consumption per resident per month, where it is in L (the
            # unit every wage here is attached to), and each monthly wage's ratio to it.
            cons, cons_snaps, cons_why = units.consumption(area, y)
            ctx = living.context(store, area, y, lambda yy, why, a=area: units._exclude(a, yy, "living:context", why, "range"))
            for w in wages:
                w["living_ratio"] = cons / w["monthly_lcu"] if cons and w["monthly_lcu"] else None
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
                "living": {"consumption_month": cons, "consumption_unconfirmed": cons_why is not None,
                           "residents_per_employed": ctx["residents_per_employed"], "employees_share": ctx["employees_share"]},
                "wages": wages,
                "snapshots": sorted({o.snapshot for o in [fx, ppp, cohd["total"]] if o} | set(cons_snaps) | set(ctx["snapshots"])),
            }
        mark_switches(rec_years)
        for row in rec_years.values():  # identifiers used only to find switches
            for w in row["wages"]:
                for k in ("series_id", "series_key", "notes_sig"):
                    w.pop(k)
        if rec_years:
            out[area] = {
                "name_en": info["name_en"],
                "iso2": info["iso2"],
                "g20": area in G20,
                "currency": units.currency(area),
                # WDI's country note where it says the national accounts are kept by fiscal year (verbatim)
                "na_fiscal": info.get("na_fiscal"),
                # the latest year of WDI household consumption shown to be in L (wage or not)
                "consumption_latest": next((y for y in reversed(years) if units.consumption(area, y)[0] is not None), None),
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
    rs = sorted(r for r, _a, _y in ratios)
    mid = len(rs) // 2
    return {"n": len(ratios), "min": lo[0], "min_at": [lo[1], lo[2]], "max": hi[0], "max_at": [hi[1], hi[2]],
            "median": rs[mid] if len(rs) % 2 else (rs[mid - 1] + rs[mid]) / 2,
            "below": sum(r < 1 for r in rs) / len(rs)}


# Which variant leads each economy's row, by the same rule for every economy: coverage
# first, then the compilation that covers the most economies, so that as many economies
# as possible are compared on one kind of figure.  ILOSTAT's employee averages whose
# notes do not limit their coverage; then OECD's full-time-equivalent wage (all
# employees, but a national-accounts concept that ILOSTAT's survey averages mostly fall
# below - see oecd_vs_survey); then ILOSTAT averages whose notes limit their coverage
# (e.g. urban areas or the private sector only).  Among ILOSTAT figures, one published
# per hour comes before one derived from a monthly figure.
def _primary_rank(w: dict) -> tuple | None:
    k = w["key"]
    if k == "oecd_fte":
        return (1, 0)
    if k in ("ilo_mean_hourly", "ilo_mean_monthly"):
        return (2 if w["restricted"] else 0, 0 if k.endswith("hourly") else 1)
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
                    "year": prev[0], "label": p["label"], "restricted": p["restricted"], "source": p["source"],
                    "kind": "notes" if same else "source",
                    "only_before": [n for n in p["notes_sig"] if n not in cur["notes_sig"]] if same else [],
                    "only_now": [n for n in cur["notes_sig"] if n not in p["notes_sig"]] if same else [],
                }
            prev = (y, cur)


def wage_metrics(v: WageVariant, gold_lcu_g: float | None, fx: float | None, ppp: float | None, cohd: float | None) -> dict:
    d = {
        "role": None, "mrole": None, "role_switch": None, "mrole_switch": None, "key": v.key, "label": v.label, "label_hourly": v.label_hourly,
        "concept": v.concept, "source": v.source, "method": v.method, "caveat": v.caveat,
        "restricted": v.restricted, "currency": v.currency, "series_id": v.series_id, "source_id": v.source_id,
        "series_key": v.series_key, "notes_sig": v.notes_sig, "snapshots": v.snapshots,
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
    """Category price level indices of economies as ICP publishes them (world = 100)."""
    cats = sorted({s for (s, _a, _p) in store.items if s.startswith("icp21_pli_wl_")})
    out: dict[str, dict] = defaultdict(dict)
    for iso, code in sorted(icp_codes(store, meta).items()):
        for series in cats:
            if o := store.get(series, code, ICP_YEAR):
                out[iso][series.removeprefix("icp21_pli_wl_")] = o.value
    return dict(out)


def _ratio(rev: dict) -> Msg:
    """ICP's 2021 total ÷ WDI's, and how ICP's figure was put into WDI's current currency
    unit (living.revision): each conversion with its own result."""
    k, by = rev["converted"], rev["by"]
    if not k:
        return M("d.liv.ratio_same", r=rev["raw"])
    if len(k) == 2:
        return M("d.liv.ratio_both", rf=by["fx"], kf=k["fx"], rp=by["ppp"], kp=k["ppp"])
    (m, v), = k.items()
    return M(f"d.liv.ratio_{m}", r=by[m], k=v)


def icp_spending(store: Store, meta: dict, units: UnitGraph) -> dict:
    """The ICP 2021 composition of household consumption, by WDI economy (living.icp_spending),
    with WDI's 2021 consumption per resident per month where ICP's shares divide that total:
    WDI's figure in L (UnitGraph.consumption), and ICP's and WDI's 2021 figures within
    ×/÷MAX_FACTOR of each other in the same currency unit (living.revision).  Otherwise the
    shares are still shown, but no amounts, with the reason logged (kind "amounts")."""
    out = {}
    for iso, code in sorted(icp_codes(store, meta).items()):
        def exclude(detail, kind, a=iso):
            units._exclude(a, living.ICP_YEAR, "living:split", detail, kind)

        if store.get("icp21_cn_aic", code, living.ICP_YEAR) is None and store.get("icp21_cn_hfce", code, living.ICP_YEAR) is None:
            continue  # ICP published no expenditure for this economy
        split = living.icp_spending(store, code, exclude)
        if split is None:
            continue
        rev = living.revision(store, code, iso, split.pop("icp_hfce"), MAX_FACTOR)
        cons, snaps, cons_why = units.consumption(iso, living.ICP_YEAR)
        currency = units.currency(iso)
        r = rev["revision"]
        within = r is not None and all(same_unit(x, 1.0) for x in r)
        amounts_ok = cons is not None and currency is not None and within
        if cons_why is not None:
            exclude(M("d.liv.cons_unconfirmed", detail=cons_why[1]), "amounts")
        elif cons is not None and r is None:
            exclude(M("d.liv.unit_unknown", r=rev["raw"], bound=MAX_FACTOR,
                      factors=[M(f"d.liv.k_{k}", k=v) for k, v in rev["factors"].items()] or [M("d.liv.k_none")]), "amounts")
        elif cons is not None and not within:
            exclude(M("d.liv.revised", ratio=_ratio(rev), bound=MAX_FACTOR), "amounts")
        elif cons is not None and currency is None:
            exclude(M("d.liv.no_currency"), "amounts")
        out[iso] = {**split, "year": living.ICP_YEAR, "revision": list(r) if r else None, "converted": rev["converted"],
                    "revision_by": rev["by"],
                    "consumption_month": cons if amounts_ok else None, "currency": currency if amounts_ok else None,
                    "na_fiscal": meta.get(iso, {}).get("na_fiscal"),
                    "snapshots": sorted(set(split["snapshots"]) | set(rev["snapshots"]) | (set(snaps) if amounts_ok else set()))}
    return out


# --------------------------------------------------------------------------------------
# Monthly wage in grams of gold, by year (for the "gold is a moving ruler" chart)
# --------------------------------------------------------------------------------------

HISTORY_MIN_YEARS = 3  # a series needs this many years to be drawn


def wage_gold_history(store: Store, gold: dict, meta: dict, ilo_dic: dict, units: UnitGraph) -> dict:
    """One average monthly wage series per economy, converted to grams of gold with each
    year's average gold price and exchange rate.  Points are [year, monthly wage, grams,
    source, break, why]: break = True where the line must not be drawn from the previous
    point - the publisher notes a break in series or a change of coverage, the notes that
    define the figure change, OECD's currency changes, or the level moves against nominal
    income per head beyond what the series can move without changing what it measures
    (UnitGraph.shift; also when that cannot be checked).

    Candidates, the same for every economy: OECD's average annual wage ÷ 12, and each
    ILOSTAT survey's mean monthly earnings, with at least HISTORY_MIN_YEARS usable years;
    the one with the most usable years not restricted in coverage is drawn (then the most
    usable years, then the latest).  The label and notes say what the drawn records cover.
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
        cands = {k: v for k, v in cands.items() if len(v) >= HISTORY_MIN_YEARS}
        if cands:
            chosen = max(cands, key=lambda k: (sum(not c["restricted"] for c in cands[k]), len(cands[k]),
                                               max(c["y"] for c in cands[k]), k))
            prev = None
            for c in sorted(cands[chosen], key=lambda c: c["y"]):
                r = c["rec"]
                if r is not None:
                    why = (r.break_note or M("d.hist.ilo_break") if r.break_in_series else
                           M("d.hist.ilo_notes_changed") if prev is not None and r.signature != prev["rec"].signature else None)
                    src = M("d.src.ext", source=r.source_name, publisher=M(f"src.{r.publisher}.publisher")) if r.publisher \
                        else f"ILOSTAT · {r.source_name}"
                else:
                    why = M("d.hist.oecd_currency_changed") if prev is not None and c["unit"] != prev["unit"] else None
                    src = "OECD · Average annual wages ÷ 12"
                pts[c["y"]] = {"v": c["v"], "src": src, "why": why, "rec": r}
                prev = c
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
                why = None if ok else M("d.hist.shift", detail=detail) if ok is False else detail
            rows.append([y, p["v"], p["v"] / (g["usd_g"] * fx.value), p["src"], bool(why and rows), why if rows else None])
            drawn.append(p["rec"])
        if len(rows) >= HISTORY_MIN_YEARS:
            recs = [r for r in drawn if r is not None]
            restricted = any(r.restricted for r in recs)
            # Coverage notes with the years they apply to, when not to every point.
            years_of: dict[str, list[str]] = defaultdict(list)
            for r in recs:
                for note in ilo_note_labels([c for c in ilostat.codes(r.obs) if c.split(":", 1)[0] in COVERAGE_NOTES + ("I13",)], ilo_dic):
                    years_of[note].append(r.obs.period)
            notes: list[Part] = [note if len(ys) == len(rows) else M("d.hist.note_years", note=note, years=ys)
                                 for note, ys in years_of.items()]
            if chosen == "OECD":
                label = M("w.hist_oecd")
            else:
                scope = ("" if not restricted else "_restricted" if len(recs) == len(rows) and all(r.restricted for r in recs)
                         else "_partly_restricted")
                label = M(f"w.hist_ilo{scope}", source=ilo_dic.get("source", {}).get(chosen.split(" ", 1)[1], chosen))
            out[area] = {"label": label, "source_id": chosen,
                         "restricted": restricted, "notes": notes, "points": rows}
    return out


def finite(x):
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError("non-finite number in dataset")
    return x
