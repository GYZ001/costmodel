"""Living costs: what residents consume, compared with the wage.

* Every year (measured): household final consumption per resident per month, WDI
  NE.CON.PRVT.CN ÷ SP.POP.TOTL ÷ 12, in WDI's local-currency unit - everything residents
  consume (food, housing including the rental value of owner-occupied homes, household
  goods, clothing, transport and all else), as national accounts record it.  Compared with
  a wage of the same year in the same unit, so no exchange rate or PPP is involved.
* The ICP 2021 benchmark only: how that consumption divides into groups, from ICP's
  nominal expenditure by heading (unit-free shares of the same release).  Other years'
  composition is not known from these sources and is not estimated.
* Context, never multiplied into the ratio: residents per employed person and employees'
  share of employment (ILO modelled estimates, via WDI).

The same rules for every economy; an input that fails a check is left out with its reason
(UnitGraph.log, scopes "living:split" and "living:context").
"""
from __future__ import annotations

from .model import Obs, Store
from .msg import M

ICP_YEAR = "2021"
# Groups of household consumption shown as their own segments (catalog keys liv.g.<key>);
# the rest of domestic consumption is "other" (liv.g.other).  ICP publishes housing only
# as "actual" housing, which may include housing services the government provides.
GROUPS = {
    "food": "food_nonalc",
    "housing": "housing",
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
    population aged 15+), and employees (wage and salaried workers) as a share of the
    employed - ILO modelled estimates published in WDI.  A value outside what the
    definitions allow is left out (log(year, detail))."""
    pop, young = store.get("population", area, year), store.get("population_0_14", area, year)
    emp, work = store.get("emp_to_pop_15plus", area, year), store.get("employees_pct_emp", area, year)
    out: dict = {"residents_per_employed": None, "employees_share": None, "snapshots": []}
    if pop and young and emp:
        if 0 < emp.value <= 100 and 0 <= young.value < pop.value:
            out["residents_per_employed"] = pop.value / (emp.value / 100 * (pop.value - young.value))
            out["snapshots"] += [pop.snapshot, young.snapshot, emp.snapshot]
        else:
            log(year, M("d.liv.ctx_bounds", emp=emp.value, young=young.value, pop=pop.value))
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
    purchases abroad may be negative, and where it is not published it is the
    difference the identity leaves); the parts add up to actual individual consumption;
    household consumption + government individual consumption = actual individual
    consumption; the domestic rest ("other") is not negative."""
    def get(k: str) -> Obs | None:
        return store.get(f"icp21_cn_{k}", code, ICP_YEAR)

    aic, hfce, gov = get("aic"), get("hfce"), get("gov_individual")
    if not aic or not hfce or not gov:
        exclude(M("d.liv.icp_missing", parts=[k for k, o in (("aic", aic), ("hfce", hfce), ("gov_individual", gov)) if not o]), "missing")
        return None
    parts = {k: get(k) for k in AIC_PARTS}
    missing = [k for k, o in parts.items() if o is None]
    if missing:
        exclude(M("d.liv.icp_missing", parts=missing), "missing")
        return None
    x = {k: o.value for k, o in parts.items()}
    negative = [k for k, v in x.items() if v < 0]
    if negative or hfce.value <= 0:
        exclude(M("d.liv.icp_negative", parts=negative or ["hfce"]), "check")
        return None
    na = get(NET_ABROAD)
    net_abroad = na.value if na else aic.value - sum(x.values())
    total = sum(x.values()) + net_abroad
    if abs(total / aic.value - 1) > ICP_TOL or abs((hfce.value + gov.value) / aic.value - 1) > ICP_TOL:
        exclude(M("d.liv.icp_identity", parts=total, hfce=hfce.value, gov=gov.value, aic=aic.value, tol=ICP_TOL), "identity")
        return None
    domestic = hfce.value - net_abroad
    shares = {g: x[k] / hfce.value for g, k in GROUPS.items()}
    other = domestic / hfce.value - sum(shares.values())
    if other < -ICP_TOL:
        exclude(M("d.liv.icp_other_negative", other=other), "check")
        return None
    other = max(other, 0.0)
    known = {k: x[k] / hfce.value for k in OTHER_PARTS}
    return {
        "shares": {**shares, "other": other},
        "other_parts": {**known, "rest": max(other - sum(known.values()), 0.0)} if sum(known.values()) <= other + ICP_TOL else None,
        "net_abroad": net_abroad / hfce.value,
        "net_abroad_published": na is not None,
        "government": gov.value / hfce.value,
        "icp_hfce": hfce.value,
        "snapshots": sorted({o.snapshot for o in (aic, hfce, gov, na, *parts.values()) if o}),
    }


def revision(store: Store, code: str, area: str, icp_hfce: float) -> tuple[float | None, float | None]:
    """(revision, unit change) between ICP's 2021 household consumption and WDI's current
    2021 figure.  The unit change is the ratio of the two published 2021 household PPPs
    (a redenomination or a new currency since ICP moves both); the revision is the rest.
    None where an input is missing."""
    wdi = store.get("hfce_lcu", area, ICP_YEAR)
    if not wdi or wdi.value <= 0:
        return None, None
    raw = icp_hfce * 1e9 / wdi.value  # ICP CN is in billions
    p_icp, p_wdi = store.get("icp21_ppp_hfce", code, ICP_YEAR), store.get("ppp_hfce", area, ICP_YEAR)
    unit = p_icp.value / p_wdi.value if p_icp and p_wdi and p_wdi.value > 0 else None
    return (raw / unit if unit else raw), unit
