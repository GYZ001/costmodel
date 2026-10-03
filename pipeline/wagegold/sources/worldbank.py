"""World Bank open data: WDI indicators and ICP 2021 category results.

WDI (source 2):
  PA.NUS.FCRF        Official exchange rate (LCU per US$, period average)
  PA.NUS.PRVT.PP     PPP conversion factor, household final consumption (LCU per international $)
  PA.NUS.PPP         PPP conversion factor, GDP (LCU per international $)
  SP.POP.TOTL        Population, total
  NY.GDP.MKTP.CN/.CD GDP in current LCU / current US$: their ratio is the conversion
                     factor the World Bank itself applies to that year's LCU figures
  NE.CON.PRVT.CN     Household final consumption in current LCU, and
  NE.CON.PRVT.PP.CD  in current international $: their ratio is the household PPP in
                     the unit of WDI's LCU series
  The last four only serve to check, year by year, that the exchange rate and the
  PPP are in the same currency unit as WDI's LCU series (see build.UnitGraph); household
  consumption ÷ population is also each year's consumption per resident (living.py).
  SP.POP.0014.TO     Population aged 0-14
  SL.EMP.TOTL.SP.ZS  Employment to population ratio, 15+ (ILO modelled estimate)
  SL.EMP.WORK.ZS     Wage and salaried workers, % of total employment (ILO modelled)

ICP 2021 (source 90): price level indices (World = 100) and PPPs (US$ = 1) for
expenditure categories, from the 2021 benchmark comparison, and expenditure (local
currency) on the parts of actual individual consumption.  Products priced in
the ICP follow common specifications across countries, so category price levels
are quality-matched, unlike comparing same-named supermarket items.
"""
from __future__ import annotations

import json

from ..fetch import Fetcher
from ..model import Obs
from .common import check_json

API = "https://api.worldbank.org/v2"

WDI_INDICATORS = {
    "PA.NUS.FCRF": "fx_lcu_usd",
    "PA.NUS.PRVT.PP": "ppp_hfce",
    "PA.NUS.PPP": "ppp_gdp",
    "SP.POP.TOTL": "population",
    "NY.GDP.MKTP.CN": "gdp_lcu",
    "NY.GDP.MKTP.CD": "gdp_usd",
    "NE.CON.PRVT.CN": "hfce_lcu",
    "NE.CON.PRVT.PP.CD": "hfce_intl",
    # Living costs (living.py): context beside the consumption-to-wage ratio, ILO modelled
    # estimates in WDI
    "SP.POP.0014.TO": "population_0_14",
    "SL.EMP.TOTL.SP.ZS": "emp_to_pop_15plus",
    "SL.EMP.WORK.ZS": "employees_pct_emp",
}

# ICP 2021 series id -> short category key used throughout the project
ICP_CATEGORIES = {
    "9100000": "hfce",  # households and NPISHs final consumption expenditure
    "1101000": "food_nonalc",
    "1101110": "bread_cereals",
    "1101120": "meat",
    "1101130": "fish",
    "1101140": "milk_cheese_eggs",
    "1101150": "oils_fats",
    "1101160": "fruit",
    "1101170": "vegetables",
    "1103000": "clothing",
    "1105000": "furnishings",
    "9060000": "housing",  # actual housing, water, electricity, gas and other fuels
    "9080000": "health",  # actual health
    "1107000": "transport",
    "1108000": "communication",
    "9110000": "recreation",  # actual recreation and culture
    "9120000": "education",  # actual education
    "1111000": "restaurants_hotels",
}
ICP_MEASURES = {"PX.WL": "icp21_pli_wl", "PPPGlob": "icp21_ppp"}

# ICP 2021 expenditure (classification CN: local currency units, billions) of the parts
# of actual individual consumption (AIC: what households consume, whether they pay for
# it or the government or NPISHs provide it).  The parts add up to AIC: household
# spending on food, alcohol & tobacco, clothing, furnishings, transport, communication,
# restaurants & hotels and net purchases abroad, and the "actual" (household + provided)
# housing, health, recreation, education and miscellaneous.  AIC = households' and
# NPISHs' consumption + government individual consumption, checked in build.
ICP_EXPENDITURE = {
    "9020000": "aic",
    "9100000": "hfce",
    "1300000": "gov_individual",
    "1101000": "food_nonalc",
    "1102000": "alcohol_tobacco",
    "1103000": "clothing",
    "9060000": "housing",
    "1105000": "furnishings",
    "9080000": "health",
    "1107000": "transport",
    "1108000": "communication",
    "9110000": "recreation",
    "9120000": "education",
    "1111000": "restaurants_hotels",
    "9140000": "misc",
    "1113000": "net_purchases_abroad",
}

# Food Prices for Nutrition (source 88): least-cost healthy diet per person per day,
# total and by food group, in local currency at each year's prices.
FPN_SERIES = {
    "CoHD_LCU": "cohd_total",
    "CoHD_ss_LCU": "cohd_staples",
    "CoHD_v_LCU": "cohd_vegetables",
    "CoHD_f_LCU": "cohd_fruits",
    "CoHD_asf_LCU": "cohd_animal",
    "CoHD_lns_LCU": "cohd_legumes",
    "CoHD_of_LCU": "cohd_oils",
    "CoHD_PPP": "cohd_total_ppp",
}


def _wdi_ok(data) -> bool:
    return isinstance(data, list) and len(data) == 2 and isinstance(data[1], list) and len(data[1]) > 0


def collect_countries(f: Fetcher) -> dict[str, dict]:
    """Economy metadata; aggregates (regions, income groups) have region id 'NA'."""
    snap = f.get(
        "worldbank/countries",
        f"{API}/country?format=json&per_page=400",
        ext="json",
        check=check_json(_wdi_ok, "WDI country list empty"),
    )
    rows = json.loads(snap.read())[1]
    return {
        r["id"]: {
            "iso2": r["iso2Code"],
            "name_en": r["name"],
            "is_economy": r["region"]["id"] != "NA",  # aggregates have no region
        }
        for r in rows
    }


def collect_wdi(f: Fetcher, first_year: int = 1990, last_year: int = 2030) -> list[Obs]:
    out: list[Obs] = []
    for code, series in WDI_INDICATORS.items():
        snap = f.get(
            f"worldbank/wdi_{code}",
            f"{API}/country/all/indicator/{code}?format=json&per_page=20000&date={first_year}:{last_year}",
            ext="json",
            check=check_json(_wdi_ok, f"WDI {code} empty"),
        )
        meta, rows = json.loads(snap.read())
        if meta.get("pages", 1) != 1:
            raise ValueError(f"WDI {code}: paging not handled ({meta})")
        for r in rows:
            if r["value"] is None:
                continue
            out.append(Obs(series, r["countryiso3code"] or r["country"]["id"], r["date"], float(r["value"]), snap.key))
    return out


def collect_icp2021(f: Fetcher) -> list[Obs]:
    out: list[Obs] = []
    reads = [(cls, prefix, ICP_CATEGORIES) for cls, prefix in ICP_MEASURES.items()] + [("CN", "icp21_cn", ICP_EXPENDITURE)]
    for cls, prefix, categories in reads:
        series = ";".join(categories)
        snap = f.get(
            f"worldbank/icp2021_{cls}",
            f"{API}/sources/90/country/all/series/{series}/classification/{cls}/time/YR2021?format=json&per_page=20000",
            ext="json",
            check=check_json(lambda d: d.get("source", {}).get("data"), "ICP 2021 payload empty"),
        )
        payload = json.loads(snap.read())
        if payload.get("pages", 1) != 1:
            raise ValueError(f"ICP {cls}: paging not handled")
        for row in payload["source"]["data"]:
            if row["value"] is None:
                continue
            var = {v["concept"]: v["id"] for v in row["variable"]}
            name = next(v.get("value", "") for v in row["variable"] if v["concept"] == "Country")
            cat = categories[var["Series"]]
            # ICP's own economy codes mostly equal ISO3 but not always; the name is kept so
            # build.icp_levels can match them to WDI economies (and drop ICP's aggregates).
            out.append(Obs(f"{prefix}_{cat}", var["Country"], "2021", float(row["value"]), snap.key, note=name))
    return out


def collect_fpn(f: Fetcher) -> list[Obs]:
    out: list[Obs] = []
    for code, series in FPN_SERIES.items():
        snap = f.get(
            f"worldbank/fpn_{code}",
            f"{API}/sources/88/country/all/series/{code}/time/all?format=json&per_page=20000",
            ext="json",
            check=check_json(lambda d: d.get("source", {}).get("data"), f"FPN {code} payload empty"),
        )
        payload = json.loads(snap.read())
        if payload.get("pages", 1) != 1:
            raise ValueError(f"FPN {code}: paging not handled")
        for row in payload["source"]["data"]:
            if row["value"] is None:
                continue
            var = {v["concept"]: v["id"] for v in row["variable"]}
            out.append(Obs(series, var["Country"], var["Time"].removeprefix("YR"), float(row["value"]), snap.key,
                           note=var.get("Classification", "")))
    return out
