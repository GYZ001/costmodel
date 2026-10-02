"""OECD Data Explorer: average annual wages and usual weekly hours.

* Average annual wages per full-time-equivalent dependent employee (national
  currency, current prices): OECD's harmonised wage level for its members.
* Average usual weekly hours on the main job of full-time dependent employees.

Hourly wage for OECD members = annual wage per FTE ÷ (usual weekly hours of
full-time employees × 52).  The annual wage is also an independent reference
for the LEVEL of ILOSTAT earnings: a gap of 3× or more reveals a currency-unit
error in one of the two.
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
        # national currency, current prices; skip the USD-PPP and constant-price variants
        if v is None or r["PRICE_BASE"] != "V" or r["UNIT_MEASURE"].startswith("USD_PPP"):
            continue
        out.append(Obs("oecd_avg_annual_wage", r["REF_AREA"], r["TIME_PERIOD"], v, snap.key, note=r["UNIT_MEASURE"]))
    # Average usual weekly hours on the main job, full-time dependent employees, both sexes, all ages.
    hs = f.get("oecd/avg_usual_weekly_hours", HOURS_URL, ext="csv",
               check=check_csv_header("REF_AREA", "WORKER_STATUS", "WORK_TIME_ARNGMNT", "OBS_VALUE"), timeout=120, retries=2)
    want = {"SEX": "_T", "AGE": "_T", "WORKER_STATUS": "ICSE93_1", "WORK_TIME_ARNGMNT": "FT",
            "HOURS_TYPE": "USUAL", "JOB_COVERAGE": "MAIN", "AGGREGATION_OPERATION": "MEAN"}
    for r in csv.DictReader(io.StringIO(hs.read().decode("utf-8-sig"))):
        v = to_float(r["OBS_VALUE"])
        # zero is not an observation of weekly hours; treat it as missing
        if v is None or v <= 0 or any(r.get(k) != val for k, val in want.items()):
            continue
        out.append(Obs("oecd_usual_weekly_hours_ft", r["REF_AREA"], r["TIME_PERIOD"], v, hs.key))
    return out
