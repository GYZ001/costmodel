"""Living costs: what households consume, compared with the wage.

* Every year (measured): household final consumption per resident per month, WDI
  NE.CON.PRVT.CN ÷ SP.POP.TOTL ÷ 12, in WDI's local-currency unit - what households and
  the non-profit institutions serving them consume, bought or imputed (food, rent
  including the rental value of owner-occupied homes, energy, household goods, clothing,
  transport and all else); services the government provides free are not in it.
  Compared with a wage that its publisher assigns to the same year, in the same unit
  (UnitGraph node H), so no exchange rate or PPP is involved.  Where WDI's country notes
  say the national accounts are kept by fiscal year, that is shown with the figure.
* The ICP 2021 benchmark only: how that consumption divides into groups, from ICP's
  nominal expenditure by heading (unit-free shares of the same release).  Other years'
  composition is not known from these sources and is not estimated.
* Context, never multiplied into the ratio: residents per employed person (from ILO's
  modelled employment-to-population ratio and the World Bank's population) and
  employees' share of employment (an ILO modelled estimate), via WDI.

The same rules for every economy; an input that fails a check is left out with its reason
(UnitGraph.log, scopes "living:consumption", "living:split" and "living:context").
"""
from __future__ import annotations

from math import fsum  # exactly rounded: the same result on every Python version

from .model import Obs, Store
from .msg import M

ICP_YEAR = "2021"
# Groups of household consumption shown as their own segments (catalog keys liv.g.<key>),
# each one of ICP's published household headings - except rent, which is household
# consumption minus ICP's "consumption without housing" (9260000): rent paid by tenants and
# the rental value of owner-occupied homes, of households and NPISHs.  ICP's "actual"
# housing (9060000) is not a segment: it also counts water, energy, repairs of the dwelling
# and housing services the government provides, which are not household spending.
# The rest of domestic household consumption is "other" (liv.g.other).
GROUPS = {
    "food": "food_nonalc",
    "rent": None,
    "furnishings": "furnishings",
    "clothing": "clothing",
    "transport": "transport",
    "communication": "communication",
}
OTHER_PARTS = ("restaurants_hotels", "alcohol_tobacco")  # published parts of "other"
# The parts of actual individual consumption (AIC) in ICP 2021: household spending on
# food, alcohol & tobacco, clothing, furnishings, transport, communication, restaurants &
# hotels and net purchases abroad, and the "actual" (household + provided) housing,
# health, recreation, education and miscellaneous.
AIC_PARTS = ("food_nonalc", "alcohol_tobacco", "clothing", "housing", "furnishings", "health", "transport",
             "communication", "recreation", "education", "restaurants_hotels", "misc")
NET_ABROAD = "net_purchases_abroad"
ICP_TOL = 0.001  # ICP's published parts add up to its totals within rounding


def consumption_month(store: Store, area: str, year: str) -> tuple[float | None, list[str]]:
    """Household final consumption per resident per month (WDI LCU), and its snapshots."""
    hf, pop = store.get("hfce_lcu", area, year), store.get("population", area, year)
    if not hf or not pop or hf.value <= 0 or pop.value <= 0:
        return None, []
    return hf.value / pop.value / 12, sorted({hf.snapshot, pop.snapshot})


def context(store: Store, area: str, year: str, log) -> dict:
    """Residents per employed person = population ÷ (employment-to-population ratio 15+ ×
    population aged 15+): the ratio is an ILO modelled estimate, the populations are the
    World Bank's; and employees (wage and salaried workers) as a share of the employed, an
    ILO modelled estimate - all published in WDI.  A value outside what the definitions
    allow is left out (log(year, detail))."""
    pop, young = store.get("population", area, year), store.get("population_0_14", area, year)
    emp, work = store.get("emp_to_pop_15plus", area, year), store.get("employees_pct_emp", area, year)
    out: dict = {"residents_per_employed": None, "employees_share": None, "snapshots": []}
    if pop and young and emp:
        if not 0 < emp.value <= 100:
            log(year, M("d.liv.ctx_emp", emp=emp.value))
        elif not 0 <= young.value < pop.value:
            log(year, M("d.liv.ctx_pop", young=young.value, pop=pop.value))
        else:
            out["residents_per_employed"] = pop.value / (emp.value / 100 * (pop.value - young.value))
            out["snapshots"] += [pop.snapshot, young.snapshot, emp.snapshot]
    if work:
        if 0 <= work.value <= 100:
            out["employees_share"] = work.value / 100
            out["snapshots"].append(work.snapshot)
        else:
            log(year, M("d.liv.ctx_employees", v=work.value))
    out["snapshots"] = sorted(set(out["snapshots"]))
    return out


def icp_spending(store: Store, code: str, exclude) -> dict | None:
    """The 2021 composition of household consumption for one economy (ICP code `code`), as
    shares of ICP's household consumption (households and NPISHs, the concept of WDI's
    total), or None with the reason logged (exclude(detail, kind)).

    Checks, the same for every economy: every part is published and non-negative (net
    purchases abroad may be negative; where ICP publishes none it is taken as zero, so
    the identity below checks the other parts on their own); the parts add up to actual
    individual consumption; household consumption + government individual consumption =
    actual individual consumption; rent is not negative and not more than ICP's actual
    housing; the domestic rest ("other") and the part of it ICP does not itemise are not
    negative.  Within ICP_TOL these hold up to ICP's rounding; the shares are published
    exactly as ICP's figures give them (no rounding is moved between parts)."""
    def get(k: str) -> Obs | None:
        return store.get(f"icp21_cn_{k}", code, ICP_YEAR)

    totals = {k: get(k) for k in ("aic", "hfce", "gov_individual", "hfce_no_housing")}
    parts = {k: get(k) for k in AIC_PARTS}
    missing = [k for k, o in {**totals, **parts}.items() if o is None]
    if missing:
        exclude(M("d.liv.icp_missing", parts=[M(f"liv.part.{k}") for k in missing]), "missing")
        return None
    aic, hfce, gov, no_housing = (totals[k].value for k in ("aic", "hfce", "gov_individual", "hfce_no_housing"))
    x = {k: o.value for k, o in parts.items()}
    negative = [k for k, v in {**x, "hfce_no_housing": no_housing}.items() if v < 0] + (["hfce"] if hfce <= 0 else [])
    if negative:
        exclude(M("d.liv.icp_negative", parts=[M(f"liv.part.{k}") for k in negative]), "icp")
        return None
    na = get(NET_ABROAD)
    net_abroad = na.value if na else 0.0
    total = fsum([*x.values(), net_abroad])
    if abs(total / aic - 1) > ICP_TOL or abs((hfce + gov) / aic - 1) > ICP_TOL:
        exclude(M("d.liv.icp_identity", parts=total, hfce=hfce, gov=gov, aic=aic, tol=ICP_TOL,
                  abroad=M("d.liv.icp_abroad_published" if na else "d.liv.icp_abroad_zero")), "icp")
        return None
    rent = hfce - no_housing
    if rent / hfce < -ICP_TOL or (rent - x["housing"]) / hfce > ICP_TOL:
        exclude(M("d.liv.icp_rent", rent=rent / hfce, housing=x["housing"] / hfce, tol=ICP_TOL), "icp")
        return None
    shares = {g: (x[k] if k else rent) / hfce for g, k in GROUPS.items()}
    # Domestic household consumption without rent, less the named groups.
    other = fsum([no_housing, -net_abroad, *(-x[k] for k in GROUPS.values() if k)]) / hfce
    known = {k: x[k] / hfce for k in OTHER_PARTS}
    rest = fsum([other, *(-v for v in known.values())])
    if other < -ICP_TOL or rest < -ICP_TOL:
        exclude(M("d.liv.icp_other_negative", other=other, known=fsum(known.values()), tol=ICP_TOL), "icp")
        return None
    return {
        "shares": {**shares, "other": other},
        "other_parts": {**known, "rest": rest},
        "net_abroad": net_abroad / hfce,
        # "published"; "zero": published as zero, which per ICP may mean it is allocated under
        # other headings (so not known); "none": not published (taken as zero for the identity)
        "net_abroad_status": "none" if na is None else "zero" if na.value == 0 else "published",
        "housing_actual": x["housing"] / hfce,
        "government": gov / hfce,
        "icp_hfce": hfce,
        "snapshots": sorted({o.snapshot for o in (*totals.values(), na, *parts.values()) if o}),
    }


def revision(store: Store, code: str, area: str, icp_hfce: float, bound: float) -> dict:
    """ICP's 2021 household consumption as a multiple of WDI's current 2021 figure, in
    WDI's current currency unit: {"revision": (low, high) or None, "converted": {measure:
    factor} or None, "raw", "factors", "snapshots"}.

    Whether the two are in the same currency unit is decided as the unit checks decide it
    (a change of unit moves a figure by more than ×/÷bound), from the ratio between the
    two publishers' 2021 units measured two ways: their household PPPs ("ppp"), and their
    US-dollar rates ("fx": ICP's market exchange rate = its PPP × the US price level ÷ its
    price level; WDI's = its GDP in local currency ÷ in dollars).  Every available ratio
    within the bound: the same unit (a PPP revised since ICP, e.g. by Eurostat-OECD,
    changes nothing), and the revision is the totals' ratio ("raw").  All beyond it and
    agreeing with each other: a change of unit; neither ratio is the exact conversion
    factor (each also carries what differs between the publishers' PPPs or rates), so the
    revision is given under each, as a range.  No ratio at all: the totals themselves
    within the bound are taken to be in the same unit.  Otherwise unknown (None)."""
    out: dict = {"revision": None, "raw": None, "converted": None, "factors": {}, "snapshots": []}
    wdi = store.get("hfce_lcu", area, ICP_YEAR)
    if not wdi or wdi.value <= 0:
        return out
    raw = out["raw"] = icp_hfce * 1e9 / wdi.value  # ICP CN is in billions
    p_icp, p_wdi = store.get("icp21_ppp_hfce", code, ICP_YEAR), store.get("ppp_hfce", area, ICP_YEAR)
    pli, pli_us = store.get("icp21_pli_wl_hfce", code, ICP_YEAR), store.get("icp21_pli_wl_hfce", "USA", ICP_YEAR)
    g_lcu, g_usd = store.get("gdp_lcu", area, ICP_YEAR), store.get("gdp_usd", area, ICP_YEAR)
    used = [wdi]
    factors: dict[str, float] = {}
    if p_icp and pli and pli_us and g_lcu and g_usd and min(p_icp.value, pli.value, pli_us.value, g_lcu.value, g_usd.value) > 0:
        factors["fx"] = (p_icp.value * pli_us.value / pli.value) / (g_lcu.value / g_usd.value)
        used += [p_icp, pli, pli_us, g_lcu, g_usd]
    if p_icp and p_wdi and p_icp.value > 0 and p_wdi.value > 0:
        factors["ppp"] = p_icp.value / p_wdi.value
        used += [p_icp, p_wdi]
    out["factors"] = factors
    out["snapshots"] = sorted({o.snapshot for o in used})

    def within(v: float) -> bool:
        return 1 / bound <= v <= bound

    if not factors:
        if within(raw):
            out["revision"] = (raw, raw)
    elif all(within(k) for k in factors.values()):
        out["revision"] = (raw, raw)
    elif not any(within(k) for k in factors.values()) and (len(factors) == 1 or within(factors["fx"] / factors["ppp"])):
        values = [raw / k for k in factors.values()]
        out["revision"], out["converted"] = (min(values), max(values)), dict(factors)
    return out
