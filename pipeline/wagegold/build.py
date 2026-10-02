"""Turn parsed observations into the dataset the website renders.

All arithmetic happens here (and is unit-tested), so the browser only displays
numbers and never derives new ones.  Every derived figure is computed from
inputs of the SAME period: a year's average wage is converted with that year's
average exchange rate and that year's average gold price, and compared with
that year's prices.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .catalog import CURRENCY, G20, US_ITEMS
from .config import GRAMS_PER_TROY_OUNCE
from .model import Obs, Store, annual_mean

WEEKS_PER_MONTH = 52 / 12  # 4.333…: converts weekly hours to monthly hours
STATUTORY_HOURS_CN = 2000  # 250 statutory working days × 8 hours (China's standard working-time rules)
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
# Wages
# --------------------------------------------------------------------------------------

def pick_source(store: Store, base: str, area: str) -> str | None:
    """Among ILOSTAT sources for one indicator and economy, keep ONE source for all
    years: the one with the most recent observation (ties: the longest history).
    Mixing sources across years would mix concepts."""
    cands = defaultdict(list)
    for (s, a, p) in store.items:
        if a == area and s.startswith(base + "@"):
            cands[s].append(p)
    if not cands:
        return None
    return max(cands, key=lambda s: (max(cands[s]), len(cands[s])))


def ilo_variants(store: Store, area: str, year: str, ilo_dic: dict) -> list[WageVariant]:
    out: list[WageVariant] = []
    hours_series = pick_source(store, "ilo_weekly_hours", area)
    hours = store.get(hours_series, area, year) if hours_series else None

    def src_label(series: str) -> str:
        code = series.split("@", 1)[1]
        return f"ILOSTAT · {ilo_dic.get('source', {}).get(code, code)}"

    for base, label, concept in (
        ("ilo_hourly_mean", "平均时薪", "mean"),
        ("ilo_hourly_median", "中位时薪", "median"),
    ):
        s = pick_source(store, base, area)
        o = store.get(s, area, year) if s else None
        if o:
            out.append(WageVariant(
                key=f"ilo_{concept}_hourly", label=f"雇员{label}", concept=concept, source=src_label(s),
                monthly_lcu=None, hourly_lcu=o.value, hours_week=None,
                method="ILOSTAT 直接发布的时薪", snapshots=[o.snapshot], caveat=_notes(o, ilo_dic),
            ))
    for base, label, concept in (
        ("ilo_monthly_mean", "平均月薪", "mean"),
        ("ilo_monthly_median", "中位月薪", "median"),
    ):
        s = pick_source(store, base, area)
        o = store.get(s, area, year) if s else None
        if not o:
            continue
        has_direct = any(v.concept == concept and v.hourly_lcu is not None and v.hours_week is None for v in out)
        hourly = o.value / (hours.value * WEEKS_PER_MONTH) if hours else None
        out.append(WageVariant(
            key=f"ilo_{concept}_monthly", label=f"雇员{label}", concept=concept, source=src_label(s),
            monthly_lcu=o.value,
            hourly_lcu=None if has_direct else hourly,
            hours_week=None if has_direct or not hours else hours.value,
            method=("月薪 ÷（每周实际工时 × 52/12）" if hours and not has_direct else
                    "仅用于月薪口径（同口径时薪已直接发布）" if has_direct else "缺少同年工时数据，不折算时薪"),
            snapshots=[o.snapshot] + ([hours.snapshot] if hours and not has_direct else []),
            caveat=_notes(o, ilo_dic),
        ))
    return out


def _notes(o: Obs, ilo_dic: dict) -> str:
    labels = []
    for code in filter(None, o.note.split("|")):
        for part in code.split("_"):
            lab = ilo_dic.get("note_source", {}).get(part) or ilo_dic.get("note_indicator", {}).get(part)
            if lab and not lab.startswith("Repository: ILO-STATISTICS"):
                labels.append(lab)
    return "；".join(dict.fromkeys(labels))


def china_variants(store: Store, year: str) -> list[WageVariant]:
    """NBS national sources for China (ILOSTAT has no hours for China and lags NBS)."""
    hours = china_annual_hours(store, year)
    out = []
    for series, label, concept in (
        ("cn_wage_nonprivate", "城镇非私营单位平均工资", "mean"),
        ("cn_wage_private", "城镇私营单位平均工资", "mean"),
    ):
        o = store.get(series, "CHN", year)
        if not o:
            continue
        monthly = o.value / 12
        out.append(WageVariant(
            key=series, label=label, concept=concept, source="国家统计局《城镇单位就业人员年平均工资情况》",
            monthly_lcu=monthly,
            hourly_lcu=monthly / (hours["mean"] * WEEKS_PER_MONTH) if hours else None,
            hours_week=hours["mean"] if hours else None,
            method=(f"年工资 ÷ 12 ÷（企业就业人员周平均工作时间 {hours['mean']:.1f} 小时 × 52/12）" if hours
                    else "缺少同年工时数据，不折算时薪"),
            snapshots=[o.snapshot] + (hours["snapshots"] if hours else []),
            caveat="仅覆盖城镇单位就业人员；非私营单位含国有、集体、股份制、外资等单位，私营单位为城镇私营企业",
        ))
    o = store.get("cn_migrant_monthly", "CHN", year)
    if o:
        out.append(WageVariant(
            key="cn_migrant", label="农民工月均收入", concept="mean", source="国家统计局《农民工监测调查报告》",
            monthly_lcu=o.value,
            hourly_lcu=o.value / (hours["mean"] * WEEKS_PER_MONTH) if hours else None,
            hours_week=hours["mean"] if hours else None,
            method=(f"月均收入 ÷（企业就业人员周平均工作时间 {hours['mean']:.1f} 小时 × 52/12）" if hours
                    else "缺少同年工时数据，不折算时薪"),
            snapshots=[o.snapshot] + (hours["snapshots"] if hours else []),
            caveat="工时采用全国企业就业人员周平均工作时间，农民工自身工时未单独公布",
        ))
    return out


def china_annual_hours(store: Store, year: str) -> dict | None:
    """Mean of the monthly survey values NBS published for that year (NBS does not
    publish a separate January figure, so up to 11 months)."""
    monthly = store.series("cn_weekly_hours_enterprise", "CHN")
    vals = [monthly[p] for p in sorted(monthly) if p.startswith(year + "-")]
    if len(vals) < 6:
        return None
    return {
        "mean": sum(v.value for v in vals) / len(vals),
        "months": [v.period for v in vals],
        "snapshots": sorted({v.snapshot for v in vals}),
    }


def us_bls_variant(store: Store, year: str) -> WageVariant | None:
    m = annual_mean(store.series("us_ahe_all_nsa", "USA"), year)
    if not m:
        return None
    snaps = sorted({o.snapshot for p, o in store.series("us_ahe_all_nsa", "USA").items() if p.startswith(year)})
    return WageVariant(
        key="bls_ces_ahe", label="私营非农雇员平均时薪（BLS CES）", concept="mean",
        source="美国劳工统计局 BLS · Current Employment Statistics", monthly_lcu=None, hourly_lcu=m[0], hours_week=None,
        method="CEU0500000003 十二个月（未季调）的简单平均，即 BLS 年度均值的算法", snapshots=snaps,
        caveat="按企业工资单统计的每小时工资（含带薪休假小时），不含农业、政府雇员和自雇",
    )


# --------------------------------------------------------------------------------------
# Country-year table
# --------------------------------------------------------------------------------------

def country_years(store: Store, gold: dict, meta: dict, ilo_dic: dict, years: list[str]) -> dict:
    out = {}
    for area, info in sorted(meta.items()):
        if not info.get("is_economy"):
            continue
        rec_years = {}
        for y in years:
            fx = store.get("fx_lcu_usd", area, y)
            g = gold["annual"].get(y)
            if not fx or not g:
                continue
            ppp = store.get("ppp_hfce", area, y)
            gold_lcu_g = g["usd_g"] * fx.value
            cohd = {k: store.get(f"cohd_{k}", area, y) for k in ["total"] + COHD_GROUPS}
            variants = []
            if area == "CHN":
                variants += china_variants(store, y)
            if area == "USA":
                v = us_bls_variant(store, y)
                variants += [v] if v else []
            variants += ilo_variants(store, area, y, ilo_dic)
            if not variants and not cohd["total"]:
                continue
            pli = ppp.value / fx.value if ppp else None
            wages = [wage_metrics(v, gold_lcu_g, fx.value, ppp.value if ppp else None,
                                  cohd["total"].value if cohd["total"] else None) for v in variants]
            mark_roles(wages)
            row = {
                "fx": fx.value,
                "ppp_hfce": ppp.value if ppp else None,
                "pli_hfce": pli,
                "population": _v(store.get("population", area, y)),
                "gold_lcu_g": gold_lcu_g,
                "gold_usd_g": g["usd_g"],
                # what 1 g of gold buys locally, in US-dollars' worth of US-priced household consumption
                "gold_usdeq_g": g["usd_g"] / pli if pli else None,
                "cohd": {k: _v(o) for k, o in cohd.items()},
                "cohd_days_per_g": gold_lcu_g / cohd["total"].value if cohd["total"] else None,
                "wages": wages,
                "snapshots": sorted({o.snapshot for o in [fx, ppp, cohd["total"]] if o}),
            }
            rec_years[y] = row
        if rec_years:
            out[area] = {
                "name_en": info["name_en"],
                "name_zh": info.get("name_zh") or info["name_en"],
                "iso2": info["iso2"],
                "region": info["region"],
                "income": info["income"],
                "g20": area in G20,
                "currency": CURRENCY.get(area),
                "years": rec_years,
            }
    return out


# Which variant leads each economy's row: the cross-country ILOSTAT concept first,
# then national sources where ILOSTAT has no usable hourly figure for that year.
PRIMARY_ORDER = ["ilo_mean_hourly", "ilo_mean_monthly", "cn_wage_nonprivate", "cn_wage_private", "bls_ces_ahe"]
TYPICAL_ORDER = ["ilo_median_hourly", "ilo_median_monthly"]


def mark_roles(wages: list[dict]) -> None:
    for order, role in ((PRIMARY_ORDER, "primary"), (TYPICAL_ORDER, "typical")):
        for key in order:
            hit = next((w for w in wages if w["key"] == key and w["hourly_lcu"]), None)
            if hit:
                hit["role"] = role
                break


def wage_metrics(v: WageVariant, gold_lcu_g: float, fx: float, ppp: float | None, cohd: float | None) -> dict:
    d = {
        "role": None, "key": v.key, "label": v.label, "concept": v.concept, "source": v.source, "method": v.method,
        "caveat": v.caveat, "snapshots": v.snapshots,
        "monthly_lcu": v.monthly_lcu, "hourly_lcu": v.hourly_lcu, "hours_week": v.hours_week,
        "monthly_gold_g": v.monthly_lcu / gold_lcu_g if v.monthly_lcu else None,
    }
    h = v.hourly_lcu
    d.update({
        "hourly_gold_g": h / gold_lcu_g if h else None,
        "hourly_usd_mkt": h / fx if h else None,
        "hourly_ppp": h / ppp if h and ppp else None,
        "minutes_per_cohd_day": cohd / h * 60 if h and cohd else None,
    })
    return d


def _v(o: Obs | None):
    return o.value if o else None


# --------------------------------------------------------------------------------------
# ICP 2021 category price levels (United States = 1)
# --------------------------------------------------------------------------------------

def icp_levels(store: Store) -> dict:
    by_series = store.by_series()
    cats = sorted({s.removeprefix("icp21_pli_wl_") for s in by_series if s.startswith("icp21_pli_wl_")})
    out: dict[str, dict] = defaultdict(dict)
    for cat in cats:
        us = store.get(f"icp21_pli_wl_{cat}", "USA", "2021")
        if not us:
            continue
        for o in by_series[f"icp21_pli_wl_{cat}"]:
            out[o.area][cat] = o.value / us.value
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
                rows.append([p, o.value, o.value / (gm[p] / GRAMS_PER_TROY_OUNCE)])
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
            })
        out[item] = {"label": label, "bls_unit": bls_unit, "unit": unit, "series_id": next(iter(s.values())).note.split("|")[0], "rows": rows}
    return out


# --------------------------------------------------------------------------------------
# Monthly wage in grams of gold, by year (for the "gold is a moving ruler" chart)
# --------------------------------------------------------------------------------------

def wage_gold_history(store: Store, gold: dict, meta: dict, ilo_dic: dict) -> dict:
    """One consistent monthly-earnings series per economy, converted to grams of gold
    with each year's average gold price and exchange rate.

    ILOSTAT mean monthly earnings, single source per economy (see pick_source).  For
    China, ILOSTAT's series is NBS's urban private-unit average wage / 12 (identical
    values); later years come straight from NBS releases of the same series.
    """
    out = {}
    for area, info in meta.items():
        if not info.get("is_economy"):
            continue
        pts: dict[str, tuple[float, str]] = {}
        s = pick_source(store, "ilo_monthly_mean", area)
        if s:
            code = s.split("@", 1)[1]
            for p, o in store.series(s, area).items():
                pts[p] = (o.value, f"ILOSTAT · {ilo_dic.get('source', {}).get(code, code)}")
        if area == "CHN":
            for p, o in store.series("cn_wage_private", "CHN").items():
                pts[p] = (o.value / 12, "国家统计局 · 城镇私营单位平均工资 ÷ 12")
        rows = []
        for y in sorted(pts):
            fx = store.get("fx_lcu_usd", area, y)
            g = gold["annual"].get(y)
            if fx and g:
                lcu, src = pts[y]
                rows.append([y, lcu, lcu / (g["usd_g"] * fx.value), src])
        if len(rows) >= 3:
            label = "城镇私营单位平均工资（国家统计局；ILOSTAT 转载同一序列）" if area == "CHN" else "雇员平均月薪（ILOSTAT）"
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
        for basis, hrs in (("statutory", STATUTORY_HOURS_CN), ("actual", hours["mean"] * 52 if hours else None)):
            if hrs is None:
                continue
            hourly = o.value / hrs
            out["cn"].append({"series": series, "label": label, "wage_year": wage_year, "annual": o.value,
                              "basis": basis, "hours_year": hrs, "hourly": hourly, "gold_g_per_hour": hourly / cny_g})
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
