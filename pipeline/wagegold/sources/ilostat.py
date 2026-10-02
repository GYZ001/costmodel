"""ILOSTAT (International Labour Organization): earnings and hours of employees.

Indicators (annual, both sexes, local currency):
  EAR_EHRA_SEX_NB_A      average hourly earnings of employees
  EAR_EHRM_SEX_NB_A      median hourly earnings of employees
  EAR_EMTA_SEX_ECO_NB_A  average monthly earnings of employees, all economic activities
  EAR_EMTM_SEX_NB_A      median monthly earnings of employees
  HOW_XEES_SEX_NB_A      average weekly hours actually worked per employee

ILOSTAT compiles national sources (labour force surveys, establishment surveys,
administrative records), so concepts differ by country.  Every observation keeps
its ILOSTAT source id and note codes; their labels come from ILOSTAT's own
dictionaries and are shown next to each country on the site.
"""
from __future__ import annotations

import csv
import io

from ..fetch import Fetcher, FetchError
from ..model import Obs
from .common import check_csv_header, to_float

DATA = "https://rplumber.ilo.org/data/indicator/?id={id}&sex=SEX_T{extra}&timefrom={start}&format=.csv"
DIC = "https://rplumber.ilo.org/metadata/dic/?var={var}&lang=en&format=.csv"

# The same earnings converted by ILOSTAT itself into US dollars.  Used only to
# validate units: our "local value ÷ World Bank exchange rate" must match it.
CUR_INDICATORS = {
    "EAR_EHRA_SEX_CUR_NB_A": "ilo_hourly_mean",
    "EAR_EHRM_SEX_CUR_NB_A": "ilo_hourly_median",
    "EAR_EMTA_SEX_CUR_NB_A": "ilo_monthly_mean",
    "EAR_EMTM_SEX_CUR_NB_A": "ilo_monthly_median",
}

INDICATORS = {
    "EAR_EHRA_SEX_NB_A": ("ilo_hourly_mean", ""),
    "EAR_EHRM_SEX_NB_A": ("ilo_hourly_median", ""),
    "EAR_EMTA_SEX_ECO_NB_A": ("ilo_monthly_mean", "&classif1=ECO_SECTOR_TOTAL"),
    "EAR_EMTM_SEX_NB_A": ("ilo_monthly_median", ""),
    "HOW_XEES_SEX_NB_A": ("ilo_weekly_hours", ""),
}


def collect(f: Fetcher, start: int = 2000) -> tuple[list[Obs], dict[str, dict[str, str]]]:
    """Return observations (one per series/area/year/source) and code dictionaries."""
    out: list[Obs] = []
    for ind, (series, extra) in INDICATORS.items():
        snap = f.get(
            f"ilostat/{ind}",
            DATA.format(id=ind, extra=extra, start=start),
            ext="csv",
            check=check_csv_header("ref_area", "source", "time", "obs_value"),
        )
        for r in csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig"))):
            v = to_float(r["obs_value"])
            if v is None or r["sex"] != "SEX_T" or r.get("classif1", "ECO_SECTOR_TOTAL") != "ECO_SECTOR_TOTAL":
                continue
            notes = "|".join(x for x in (r.get("note_indicator"), r.get("note_source"), r.get("note_classif")) if x)
            # One series per ILOSTAT source, so a country with several sources keeps them apart.
            out.append(Obs(f"{series}@{r['source']}", r["ref_area"], r["time"], v, snap.key, note=notes))
    for ind, series in CUR_INDICATORS.items():
        try:  # validation-only data: without it the unit check reports "not verifiable"
            snap = f.get(
                f"ilostat/{ind}",
                DATA.format(id=ind, extra="", start=start),
                ext="csv",
                check=check_csv_header("ref_area", "source", "time", "obs_value"),
            )
        except FetchError as exc:
            print(f"[skip] ilostat {ind}: {exc}")
            continue
        for r in csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig"))):
            v = to_float(r["obs_value"])
            cur = next((r[k] for k in r if k.startswith("classif") and (r[k] or "").startswith("CUR_")), "")
            if v is None or r["sex"] != "SEX_T" or not cur.endswith("_USD"):
                continue
            out.append(Obs(f"{series}_usd@{r['source']}", r["ref_area"], r["time"], v, snap.key, note=cur))
    dictionaries = {}
    for var in ("source", "note_source", "note_indicator"):
        snap = f.get(f"ilostat/dic_{var}", DIC.format(var=var), ext="csv", check=check_csv_header(var, f"{var}.label"))
        rows = csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig")))
        dictionaries[var] = {r[var]: r[f"{var}.label"] for r in rows}
    return out, dictionaries
