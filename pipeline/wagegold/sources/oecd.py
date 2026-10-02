"""OECD Data Explorer: average annual wages and usual weekly hours.

* Average annual wages per full-time-equivalent dependent employee, national
  currency at current prices (PRICE_BASE V): OECD's harmonised wage level.
* The same wages at constant prices of the base year (PRICE_BASE Q), in national
  currency and converted to US dollars with that base year's PPPs.  Their ratio is
  the PPP OECD used, in the unit of OECD's national-currency series - which lets
  build.UnitGraph check that unit against the World Bank's PPP.
* Average usual weekly hours on the main job of full-time dependent employees.

Hourly wage = annual wage per FTE ÷ (usual weekly hours of full-time employees × 52).
"""
from __future__ import annotations

import csv
import io

from ..fetch import Fetcher
from ..model import Obs
from .common import check_csv_header, to_float

URL = ("https://sdmx.oecd.org/public/rest/data/OECD.ELS.SAE,DSD_EARNINGS@AV_AN_WAGE,1.0/all"
       "?startPeriod=2000&format=csvfilewithlabels")
# Key order: REF_AREA.MEASURE.UNIT_MEASURE.SEX.AGE.LABOUR_FORCE_STATUS.WORK_PERIOD.HOURS_TYPE.
#            WORKER_STATUS.WORK_TIME_ARNGMNT.AGGREGATION_OPERATION.HOUR_BANDS.JOB_COVERAGE
HOURS_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.ELS.SAE,DSD_HW@DF_AVG_USL_WK_WKD,1.0/"
             ".HW.H_WK_PS._T._T.EMP.W.USUAL.ICSE93_1.FT.MEAN._Z.MAIN?startPeriod=2000&format=csvfilewithlabels")


def collect(f: Fetcher) -> list[Obs]:
    snap = f.get("oecd/av_an_wage", URL, ext="csv", check=check_csv_header("REF_AREA", "UNIT_MEASURE", "PRICE_BASE", "OBS_VALUE"),
                 timeout=90, retries=2)
    out = []
    for r in csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig"))):
        v = to_float(r["OBS_VALUE"])
        if v is None or v <= 0:
            continue
        ppp = r["UNIT_MEASURE"].startswith("USD_PPP")
        if r["PRICE_BASE"] == "V" and not ppp:  # national currency, current prices
            out.append(Obs("oecd_avg_annual_wage", r["REF_AREA"], r["TIME_PERIOD"], v, snap.key, note=r["UNIT_MEASURE"]))
        elif r["PRICE_BASE"] == "Q":  # constant prices of BASE_PER; note = "unit base-year"
            series = "oecd_avg_annual_wage_q_usdppp" if ppp else "oecd_avg_annual_wage_q"
            out.append(Obs(series, r["REF_AREA"], r["TIME_PERIOD"], v, snap.key, note=f"{r['UNIT_MEASURE']} {r['BASE_PER']}"))
    # Average usual weekly hours on the main job, full-time dependent employees, both sexes, all ages.
    hs = f.get("oecd/avg_usual_weekly_hours", HOURS_URL, ext="csv",
               check=check_csv_header("REF_AREA", "WORKER_STATUS", "WORK_TIME_ARNGMNT", "OBS_VALUE"), timeout=120, retries=2)
    want = {"SEX": "_T", "AGE": "_T", "WORKER_STATUS": "ICSE93_1", "WORK_TIME_ARNGMNT": "FT",
            "HOURS_TYPE": "USUAL", "JOB_COVERAGE": "MAIN", "AGGREGATION_OPERATION": "MEAN"}
    for r in csv.DictReader(io.StringIO(hs.read().decode("utf-8-sig"))):
        v = to_float(r["OBS_VALUE"])
        if v is None or any(r.get(k) != val for k, val in want.items()):
            continue
        # A published 0 is not an observation of weekly hours: kept apart so the site
        # can say that OECD's value is 0, rather than that OECD published nothing.
        out.append(Obs("oecd_usual_weekly_hours_ft" if v > 0 else "oecd_usual_weekly_hours_ft__zero",
                       r["REF_AREA"], r["TIME_PERIOD"], v, hs.key))
    return out
