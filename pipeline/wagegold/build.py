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
from dataclasses import dataclass

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
    restricted: bool = False  # coverage limited (e.g. urban areas or private sector only)
    currency: str | None = None  # currency the publisher states for the figure
    label_hourly: str | None = None  # label when the hourly figure is derived from a monthly one


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
MAX_FACTOR = 1.4

# The smallest confusion of time units is a week for a month (×52/12 = ×4.33).  A
# monthly and an hourly wage imply the hours worked in a month; compared with measured
# hours, a ratio nearer to ×1 than to ×4.33 (in log terms: within ×/÷√4.33 ≈ 2.08)
# means the same time unit, and anything beyond means a time-unit or scale error.
TIME_FACTOR = math.sqrt(52 / 12)


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
    unusable: str | None  # reason the value cannot be used at all
    restricted: bool  # coverage limited (area, population, establishment size, sector, activity, group)
    currency: str | None
    signature: tuple  # concept-defining notes; a change between years breaks a series
    break_in_series: bool
    status: str | None  # ILOSTAT's observation status label, if any


# ILOSTAT note types that define what an earnings figure measures (not just where it
# comes from): central tendency, value type, gross/net, job coverage, working-time
# coverage, reference period, coverage of area / population / establishment size /
# institutional sector / economic activity / reference group, minimum-wage type,
# employment definition.
COVERAGE_NOTES = ("S4", "S5", "S6", "S7", "S8", "S9", "T12")
CONCEPT_NOTES = ("T8", "T9", "T10", "T11", "S3", *COVERAGE_NOTES, "I19", "I20")


def restricts(prefix: str, label: str) -> bool:
    """Whether a coverage note limits a figure to part of a country's employees, read from
    ILOSTAT's label: every area, establishment-size, sector, activity, reference-group,
    population or working-time note does, except the ones stating the full scope (the
    whole national territory, all employees, full- and part-time workers) and the
    exclusions every household survey has (people in institutions or collective
    quarters, armed forces), which do not change who an employee earnings figure is about."""
    text = label.split(":", 1)[-1].strip().lower()
    if prefix == "S4":
        return not text.startswith("total national")
    if prefix == "S9":
        return text != "employees"
    if prefix == "T12":
        return "part time" not in text and "part-time" not in text
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


def ilo_notes(rec: IloRecord, ilo_dic: dict) -> str:
    """ILOSTAT's own labels for the notes that qualify a figure (English, verbatim);
    coverage notes first, since they matter most for comparing figures."""
    codes = [c for c in ilostat.codes(rec.obs) if c.split(":", 1)[0] in CONCEPT_NOTES + ("I11",)]
    codes.sort(key=lambda c: c.split(":", 1)[0] not in COVERAGE_NOTES)
    labels = [ilostat.label(c, ilo_dic) for c in codes] + ([f"Observation status: {rec.status}"] if rec.status else [])
    return "；".join(dict.fromkeys(l for l in labels if not l.startswith("Repository")))


HOURS_IN_MONTH = 31 * 24  # 744: no monthly wage can be earned in more hours than a month has


@dataclass
class _Point:
    """A monthly or hourly earnings figure taking part in the time-unit check."""
    unit: str
    concept: str
    value: float
    source: str
    rec: IloRecord | None  # None for the OECD reference figures


def _check_time_units(recs: list[IloRecord], hours: list[float], oecd: list[_Point]) -> None:
    """Monthly and hourly figures of one economy-year, all proven to be in the same
    currency unit, must agree on the hours worked.

    1. Same source, same central tendency: monthly ÷ hourly is the hours worked in a
       month; below 1 or above the 744 hours a month has, one of the two is in a wrong
       unit and nothing in these two numbers tells which - both are left out.
    2. Across sources (OECD's FTE wage included): a figure is kept if, with at least one
       figure of the other time unit and one measured weekly-hours value of that year,
       the implied hours agree with the measured ones within TIME_FACTOR.  A figure that
       agrees with none of them while having some to compare with is left out; if its
       counterparts agree with nothing either, all of them are (the data cannot say
       which is wrong)."""
    usable = [r for r in recs if not r.unusable]
    by_key: dict[tuple[str, str], dict[str, IloRecord]] = defaultdict(dict)
    for r in usable:
        by_key[(r.source, r.concept)][r.unit] = r
    for pair in by_key.values():
        if "hour" in pair and "month" in pair:
            h = pair["month"].obs.value / pair["hour"].obs.value
            if not 1 <= h <= HOURS_IN_MONTH:
                why = (f"同一来源同年的月薪 {pair['month'].obs.value:,.6g} ÷ 时薪 {pair['hour'].obs.value:,.6g} = 每月 {h:,.0f} 小时，"
                       f"不在 1 到 {HOURS_IN_MONTH} 小时（一个月的总小时数）之间，至少其中一个数值的单位有误，仅凭这两个数无法判断是哪一个")
                pair["hour"].unusable = pair["month"].unusable = why
    if not hours:
        return
    points = [_Point(r.unit, r.concept, r.obs.value, r.source, r) for r in recs if not r.unusable] + oecd
    for concept in ("mean", "median"):
        months = [p for p in points if p.concept == concept and p.unit == "month"]
        hrs = [p for p in points if p.concept == concept and p.unit == "hour"]
        if not months or not hrs:
            continue

        ok: dict[int, bool] = {}
        for m in months:
            for h in hrs:
                if m.rec is None and h.rec is None:
                    continue  # OECD's monthly and hourly figures are derived from each other
                if any(same_unit(m.value / h.value, w * WEEKS_PER_MONTH, TIME_FACTOR) for w in hours):
                    ok[id(m)] = ok[id(h)] = True
        for p in months + hrs:
            if p.rec is None or ok.get(id(p)):
                continue
            others = hrs if p.unit == "month" else months
            implied = sorted((m.value / h.value) for m in ([p] if p.unit == "month" else others)
                             for h in (others if p.unit == "month" else [p]))
            whose = "、".join(sorted({"OECD" if o.rec is None else f"ILOSTAT {o.source}" for o in others}))
            # OECD's figures are a reference: their time unit is explicit (an annual wage and
            # the hours it is paid for), so only ILOSTAT figures are ever left out here.
            p.rec.unusable = (f"与同年可对照的{'时薪' if p.unit == 'month' else '月薪'}（{whose}）以及实测每周工时都对不上："
                              f"隐含每月工作 {', '.join(f'{x:,.0f}' for x in implied[:3])} 小时，实测约 "
                              f"{', '.join(f'{w * WEEKS_PER_MONTH:,.0f}' for w in sorted(hours)[:3])} 小时"
                              f"（超出 ×/÷{TIME_FACTOR:.2f}，即时间单位或数量级有误）"
                              + ("；可对照的 ILOSTAT 数值也与实测工时对不上，无法判断哪一个有误，一并不用"
                                 if not any(ok.get(id(o)) for o in others) and any(o.rec for o in others) else ""))


class UnitGraph:
    def __init__(self, store: Store, ilo_dic: dict, years: list[str], meta: dict):
        self.store, self.ilo_dic, self.years = store, ilo_dic, years
        self.log: list[dict] = []
        self._areas: dict[str, dict] = {}
        self._ilo_code = self._match_ilo_areas(meta)
        self._icp_code = icp_codes(store, meta)

    # ---- bookkeeping
    def _exclude(self, area: str, year: str, scope: str, detail: str) -> None:
        self.log.append({"area": area, "year": year, "scope": scope, "detail": detail})

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
                              f"ILOSTAT 的地区代码 {code}（{name or '无名称'}）不在世界银行经济体名录中，按名称也无法对应")
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

    def _time_check(self, area: str, year: str, recs: list[IloRecord], oecd_linked: bool) -> None:
        src = self.ilo_area(area)
        hours = [o.value for s in self.store.series_names(src, "ilo_weekly_hours@")
                 for p, o in self.store.series(s, src).items() if p == year]
        oecd_h = self.store.get("oecd_usual_weekly_hours_ft", area, year)
        hours += [oecd_h.value] if oecd_h else []
        w = self.store.get("oecd_avg_annual_wage", area, year) if oecd_linked else None
        oecd = [_Point("month", "mean", w.value / 12, "OECD", None)] if w else []
        if w and oecd_h:
            oecd.append(_Point("hour", "mean", w.value / (oecd_h.value * 52), "OECD", None))
        _check_time_units(recs, hours, oecd)

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

    def _prove(self, values: dict[str, float], direct: dict[str, tuple[bool | None, str]]) -> dict[str, tuple[bool | None, str]]:
        """Year-by-year verdict on whether a factor (F or P) is in L: that year's identity,
        or else an adjacent year's proof carried over when the value moved by less than
        MAX_FACTOR (first forwards, then backwards)."""
        out = dict(direct)
        for step, order in ((1, self.years), (-1, self.years[::-1])):
            for y in order:
                n = str(int(y) - step)
                if y in values and out[y][0] is None and n in values and out[n][0] is True \
                        and same_unit(values[y], values[n]):
                    out[y] = (True, "")
        for y, (ok, detail) in out.items():
            if ok is None:
                near = [n for n in (str(int(y) - 1), str(int(y) + 1)) if n in values and out[n][0] is True]
                out[y] = (None, detail + ("".join(f"；与 {n} 年的 {values[n]:.6g} 相比 {factor(values[y], values[n])}，"
                                                  "超出货币单位不可能改变的范围，不能沿用该年的核对" for n in near)
                                          or "；相邻年份也未能核对"))
        return out

    def _factors(self, area: str) -> tuple[dict, dict]:
        """Verdicts for F and P by year: (True = in L, False = proven not in L, None = unknown; detail)."""
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
            "WDI 官方汇率 {v:.6g}，世界银行 GDP 本币值 ÷ 美元值 = {i:.6g}（{f}）：官方汇率与世界银行本币序列的货币单位不同，"
            "或世界银行换算该年美元数据时用的不是官方汇率（官方汇率与实际交易汇率严重脱节）",
            "缺少世界银行 GDP 本币值或美元值，无法核对官方汇率") for y, v in fx.items()})
        direct = {}
        for y, v in ppp.items():
            ok, detail = identity(v, s.get("hfce_lcu", area, y), s.get("hfce_intl", area, y),
                                  "WDI 居民消费 PPP {v:.6g}，居民消费本币值 ÷ 国际元值 = {i:.6g}（{f}）：货币单位不同",
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
                              f"{implied:.6g}（{factor(v, implied)}）：货币单位不同")
            direct[y] = (ok, detail)
        return f, self._prove(ppp, direct)

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
                    c[node] = verdicts[y]
                    if verdicts[y][0]:
                        g.union(node, "L")
            lcu, cost_ppp = s.get("cohd_total", area, y), s.get("cohd_total_ppp", area, y)
            if lcu:
                if cost_ppp and ppp and cost_ppp.value > 0:
                    implied = lcu.value / cost_ppp.value
                    ok = same_unit(implied, ppp.value)
                    c["C"] = (ok, f"健康饮食成本本币值 ÷ PPP 值 = {implied:.6g}，WDI 购买力平价 {ppp.value:.6g}（{factor(implied, ppp.value)}）：货币单位不同")
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
                        "ILOSTAT 的美元换算与官方汇率一致、PPP 换算与购买力平价一致，但官方汇率和购买力平价本身不是同一货币单位"
                        "（见该年的汇率或购买力平价核对），这条记录的货币单位无法确定")
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
                          f"与世界银行本币序列相符的记录给出了不同的货币代码：{', '.join(sorted(codes))}；不使用按货币代码对应的数据（OECD、国家统计机构）")
        # Time units, among figures now known to be in the same currency unit.
        for y, g in graphs.items():
            attached = [r for r in ilo.get(y, []) if not r.unusable and g.linked(f"ilo:{r.series}")]
            self._time_check(area, y, attached, g.linked("oecd"))
        return {"years": graphs, "checks": checks, "codes": codes, "ilo": ilo, "oecd_ppp": oecd_ppp,
                "oecd_unit": oecd_unit, "ambiguous": ambiguous}

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
        for k, scope in (("F", "fx"), ("P", "ppp")):
            ok, detail = c.get(k, (True, ""))
            if not g.linked(k) and ok is not True and detail:
                self._exclude(area, year, scope, detail)
        if "C" in c and not g.linked("C"):
            ok, detail = c["C"]
            if ok is True:  # the diet cost matches the PPP, but the PPP itself is not proven
                detail = "健康饮食成本与购买力平价同一货币单位，但该年购买力平价未能证明与世界银行本币序列同一单位"
            self._exclude(area, year, "cohd", detail)
        if self.store.get("oecd_avg_annual_wage", area, year) and not g.linked("oecd"):
            unit = a["oecd_unit"].get(year)
            self._exclude(area, year, "wage:oecd", "OECD 工资未能证明与世界银行本币序列同一货币单位：" + a["oecd_ppp"][1]
                          + f"；OECD 标注的货币 {unit}，与世界银行本币序列相符的记录给出的货币 {', '.join(sorted(a['codes'])) or '无'}")
        fx, ppp = self.store.get("fx_lcu_usd", area, year), self.store.get("ppp_hfce", area, year)
        for rec in a["ilo"].get(year, []):
            if rec.unusable:
                self._exclude(area, year, f"wage:{rec.base}", f"{rec.series}：{rec.unusable}")
            elif (year, rec.series) in a["ambiguous"]:
                self._exclude(area, year, f"wage:{rec.base}", f"{rec.series}：{a['ambiguous'][(year, rec.series)]}")
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
                self._exclude(area, year, f"wage:{rec.base}", f"{rec.series}：无法证明与世界银行本币序列同一货币单位。" + "；".join(parts))


# --------------------------------------------------------------------------------------
# Wages
# --------------------------------------------------------------------------------------

def pick_source(store: Store, base: str, area: str) -> str | None:
    """Among ILOSTAT sources for one indicator and economy, the one with the most recent
    observation (ties: the longest history)."""
    cands = {s: list(store.series(s, area)) for s in store.series_names(area, base + "@")}
    if not cands:
        return None
    return max(cands, key=lambda s: (max(cands[s]), len(cands[s]), s))


def _usable_linked(units: UnitGraph, area: str) -> dict[str, list[IloRecord]]:
    a = units.area(area)
    return {y: [r for r in recs if not r.unusable and a["years"][y].linked(f"ilo:{r.series}")]
            for y, recs in a["ilo"].items() if y in a["years"]}


def ilo_variants(store: Store, units: UnitGraph, area: str, year: str, ilo_dic: dict) -> list[WageVariant]:
    usable = _usable_linked(units, area)
    # One source per (concept, unit) is preferred across years so that a country's
    # figures do not jump between surveys: the one with the latest and longest
    # history of usable records.  In a given year an unrestricted record comes first.
    history: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for y, recs in usable.items():
        for r in recs:
            history[(r.concept, r.unit)][r.source].append(y)
    main = {k: max(v, key=lambda src: (max(v[src]), len(v[src]), src)) for k, v in history.items()}
    out: list[WageVariant] = []
    chosen: dict[tuple[str, str], IloRecord] = {}
    for r in usable.get(year, []):
        k = (r.concept, r.unit)
        rank = (r.restricted, r.source != main[k], -len(history[k][r.source]), r.source)
        cur = chosen.get(k)
        if cur is None or rank < (cur.restricted, cur.source != main[k], -len(history[k][cur.source]), cur.source):
            chosen[k] = r

    def src_label(r: IloRecord) -> str:
        return f"ILOSTAT · {ilo_dic.get('source', {}).get(r.source, r.source)}"

    for concept in ("mean", "median"):
        direct = chosen.get((concept, "hour"))
        monthly = chosen.get((concept, "month"))
        cname = "平均" if concept == "mean" else "中位"
        if direct:
            out.append(WageVariant(
                key=f"ilo_{concept}_hourly", label=f"雇员{cname}时薪" + ("（覆盖范围有限）" if direct.restricted else ""),
                concept=concept, source=src_label(direct), monthly_lcu=None, hourly_lcu=direct.obs.value, hours_week=None,
                method="ILOSTAT 直接发布的时薪", snapshots=[direct.obs.snapshot], caveat=ilo_notes(direct, ilo_dic),
                restricted=direct.restricted, currency=direct.currency,
            ))
        if monthly:
            # Hours only from the same survey (same ILOSTAT source) as the earnings.
            hours = store.get(f"ilo_weekly_hours@{monthly.source}", units.ilo_area(area), year)
            derive = hours is not None and direct is None
            label = f"雇员{cname}月薪" + ("（覆盖范围有限）" if monthly.restricted else "")
            out.append(WageVariant(
                key=f"ilo_{concept}_monthly", label=label, concept=concept, source=src_label(monthly),
                monthly_lcu=monthly.obs.value,
                hourly_lcu=monthly.obs.value / (hours.value * WEEKS_PER_MONTH) if derive else None,
                hours_week=hours.value if derive else None,
                method=("月薪 ÷（同一调查的每周实际工时 × 52/12）" if derive else
                        "仅用于月薪口径（同口径时薪已直接发布）" if direct else
                        "同一调查没有工时数据，不折算时薪，只用于月薪口径"),
                snapshots=[monthly.obs.snapshot] + ([hours.snapshot] if derive else []),
                caveat=ilo_notes(monthly, ilo_dic), restricted=monthly.restricted, currency=monthly.currency,
                label_hourly=f"{label}（按同一调查的工时折算为时薪）" if derive else None,
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
        currency=w.note,
    )


CN_SERIES = (
    ("cn_wage_nonprivate", "城镇非私营单位平均工资"),
    ("cn_wage_private", "城镇私营单位平均工资"),
    ("cn_wage_large_ent", "规模以上企业就业人员平均工资"),
)


def china_variants(store: Store, units: UnitGraph, year: str, definitions: dict) -> list[WageVariant]:
    """NBS national sources for China, with NBS's own definitions quoted."""
    if not units.year("CHN", year).linked("cn"):
        return []
    hours = china_annual_hours(store, year)
    n_months = len([p for p in store.series("cn_weekly_hours_enterprise", "CHN") if p.startswith(year + "-")])
    no_hours = (f"该年已公布的企业就业人员周平均工作时间只有 {n_months} 个月（少于 6 个月），不折算时薪" if n_months
                else "该年没有企业就业人员周平均工作时间数据，不折算时薪")
    d = definitions.get(year, {})  # never borrowed from another year: coverage changes between years

    def release_title(series: str) -> str:
        """The NBS release the figure comes from (one combined release, or one per measure)."""
        marker = {"cn_wage_nonprivate": "城镇非私营", "cn_wage_private": "城镇私营", "cn_wage_large_ent": "规模以上企业"}[series]
        titles = [r["title"] for r in d.get("releases", [])]
        hit = next((t for t in titles if marker in t), None) or next((t for t in titles if "城镇单位" in t), None)
        return f"国家统计局《{hit}》" if hit else "国家统计局"
    out = []
    for series, label in CN_SERIES:
        o = store.get(series, "CHN", year)
        if not o:
            continue
        monthly = o.value / 12
        notes = [f"国家统计局：{d['scope']}" if d.get("scope") else "",
                 f"范围：{d[series]}" if d.get(series) else "",
                 d.get("gross") or ""]
        comp = store.get(f"{series}__comparable_growth", "CHN", year)
        if comp:
            notes.append(f"国家统计局注明该年统计覆盖范围有变化（名义增长 {o.note.split('growth_pct=')[1]}%，按可比口径增长 {comp.value}%"
                         + (f"；可比口径是指{d['comparable']}" if d.get("comparable") else "") + "）")
        out.append(WageVariant(
            key=series, label=label, concept="mean", source=release_title(series),
            monthly_lcu=monthly,
            hourly_lcu=monthly / (hours["mean"] * WEEKS_PER_MONTH) if hours else None,
            hours_week=hours["mean"] if hours else None,
            method=(f"年工资 ÷ 12 ÷（企业就业人员周平均工作时间 {hours['mean']:.1f} 小时 × 52/12）" if hours else no_hours),
            snapshots=[o.snapshot] + (hours["snapshots"] if hours else []),
            caveat="；".join(x for x in notes if x), currency="CNY",
        ))
    o = store.get("cn_migrant_monthly", "CHN", year)
    if o:
        out.append(WageVariant(
            key="cn_migrant", label="农民工月均收入", concept="mean", source="国家统计局《农民工监测调查报告》",
            monthly_lcu=o.value,
            hourly_lcu=o.value / (hours["mean"] * WEEKS_PER_MONTH) if hours else None,
            hours_week=hours["mean"] if hours else None,
            method=(f"月均收入 ÷（企业就业人员周平均工作时间 {hours['mean']:.1f} 小时 × 52/12）" if hours else no_hours),
            snapshots=[o.snapshot] + (hours["snapshots"] if hours else []),
            caveat="工时采用全国企业就业人员周平均工作时间；本项目存档的农民工监测调查报告未公布农民工工时",
            currency="CNY",
        ))
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
        caveat="按企业工资单统计的每小时工资（含带薪休假小时），不含农业、政府雇员和自雇", currency="USD",
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
            rec_years[y] = {
                "fx": fx.value if fx else None,
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
    """role = primary / typical for the hourly view; mrole = primary / typical for the monthly view."""
    for field, need in (("role", "hourly_lcu"), ("mrole", "monthly_lcu")):
        for rank, role in ((_primary_rank, "primary"), (_typical_rank, "typical")):
            cands = [w for w in wages if w[need] and rank(w) is not None and w[field] is None]
            if cands:
                min(cands, key=rank)[field] = role

def wage_metrics(v: WageVariant, gold_lcu_g: float | None, fx: float | None, ppp: float | None, cohd: float | None) -> dict:
    d = {
        "role": None, "mrole": None, "key": v.key, "label": v.label, "label_hourly": v.label_hourly,
        "concept": v.concept, "source": v.source, "method": v.method, "caveat": v.caveat,
        "restricted": v.restricted, "currency": v.currency, "snapshots": v.snapshots,
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
    """One monthly-earnings series per economy, converted to grams of gold with each
    year's average gold price and exchange rate.  Points carry ``break`` = True where
    the series' concept changes (ILOSTAT's break-in-series note, or a change in the
    notes that define what the figure measures; NBS's own coverage-change note), so
    the chart does not draw a line across a break.

    Source: ILOSTAT mean monthly earnings, one source per economy (latest and longest
    history of usable records).  For China ILOSTAT's series is NBS's urban private-unit
    wage ÷ 12 (validate.china_ilo_equals_nbs); years NBS published itself come from NBS.
    """
    out = {}
    for area, info in meta.items():
        if not info.get("is_economy"):
            continue
        a = units.area(area)
        usable = _usable_linked(units, area)
        cands = defaultdict(list)
        for y, recs in usable.items():
            for r in recs:
                if r.concept == "mean" and r.unit == "month" and a["years"][y].linked("F"):
                    cands[r.source].append(r)
        pts: dict[str, list] = {}
        src_name = None
        if cands:
            src = max(cands, key=lambda k: (max(r.obs.period for r in cands[k]), len(cands[k]), k))
            src_name = ilo_dic.get("source", {}).get(src, src)
            prev = None
            for r in sorted(cands[src], key=lambda r: r.obs.period):
                brk = prev is not None and (r.break_in_series or r.signature != prev.signature)
                pts[r.obs.period] = [r.obs.value, f"ILOSTAT · {src_name}", brk]
                prev = r
        if area == "CHN":
            for y, o in store.series("cn_wage_private", "CHN").items():
                if a["years"].get(y) and a["years"][y].linked("cn") and a["years"][y].linked("F"):
                    brk = store.get("cn_wage_private__comparable_growth", "CHN", y) is not None
                    pts[y] = [o.value / 12, "国家统计局 · 城镇私营单位平均工资 ÷ 12", brk]
        rows = []
        for y in sorted(pts):
            fx = store.get("fx_lcu_usd", area, y)
            g = gold["annual"].get(y)
            if fx and g:
                lcu, src_line, brk = pts[y]
                rows.append([y, lcu, lcu / (g["usd_g"] * fx.value), src_line, bool(brk and rows)])
        if len(rows) >= 3:
            label = ("城镇私营单位平均工资（国家统计局；更早年份为 ILOSTAT 转载的同一序列）" if area == "CHN"
                     else f"雇员平均月薪（ILOSTAT · {src_name}）")
            out[area] = {"label": label, "points": rows}
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
    wage_year = max((y for (s, a, y) in store.items if s == "cn_wage_nonprivate" and a == "CHN"), default=None)
    hours = china_annual_hours(store, wage_year) if wage_year else None
    for series, label in (("cn_wage_nonprivate", "城镇非私营单位"), ("cn_wage_private", "城镇私营单位")):
        o = store.get(series, "CHN", wage_year) if wage_year else None
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
