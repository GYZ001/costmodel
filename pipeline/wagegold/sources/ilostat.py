"""ILOSTAT (International Labour Organization): earnings and hours of employees.

Earnings come from ILOSTAT's currency-harmonised indicators, in which every
observation is published three times - in local currency, in US dollars and in
PPP dollars - as ILOSTAT itself converted it (classif1 = CUR_TYPE_LCU / _USD / _PPP):

  EAR_EHRA_SEX_CUR_NB_A  average hourly earnings of employees
  EAR_EHRM_SEX_CUR_NB_A  median hourly earnings of employees
  EAR_EMTA_SEX_CUR_NB_A  average monthly earnings of employees
  EAR_EMTM_SEX_CUR_NB_A  median monthly earnings of employees
  HOW_XEES_SEX_NB_A      average weekly hours actually worked per employee

The USD and PPP versions let every local-currency value be checked against the
World Bank exchange rate and PPP it is later divided by (see build.UnitGraph).
Observations ILOSTAT publishes only in its unharmonised tables are ones it could
not convert itself; they are not used.

Each observation keeps its ILOSTAT source id and note codes (currency, central
tendency, nominal/real, coverage, breaks in series); build.py reads them and the
site shows their labels next to each figure.
"""
from __future__ import annotations

import csv
import io
import re

from ..fetch import Fetcher
from ..model import Obs
from .common import check_csv_header, to_float

DATA = "https://rplumber.ilo.org/data/indicator/?id={id}&sex=SEX_T{extra}&timefrom={start}&format=.csv"
DIC = "https://rplumber.ilo.org/metadata/dic/?var={var}&lang=en&format=.csv"

EARNINGS = {
    "EAR_EHRA_SEX_CUR_NB_A": ("ilo_hourly_mean", "hour"),
    "EAR_EHRM_SEX_CUR_NB_A": ("ilo_hourly_median", "hour"),
    "EAR_EMTA_SEX_CUR_NB_A": ("ilo_monthly_mean", "month"),
    "EAR_EMTM_SEX_CUR_NB_A": ("ilo_monthly_median", "month"),
}
HOURS = ("HOW_XEES_SEX_NB_A", "ilo_weekly_hours")
CUR_SUFFIX = {"CUR_TYPE_LCU": "", "CUR_TYPE_USD": "_usd", "CUR_TYPE_PPP": "_ppp"}


def collect(f: Fetcher, start: int = 2000) -> tuple[list[Obs], dict[str, dict[str, str]]]:
    """Observations (one series per ILOSTAT source; local-currency value under
    ``{base}@{source}``, ILOSTAT's own USD and PPP conversions under ``{base}_usd@…``
    and ``{base}_ppp@…``) and ILOSTAT's code dictionaries."""
    out: list[Obs] = []
    for ind, (base, _unit) in EARNINGS.items():
        snap = f.get(f"ilostat/{ind}", DATA.format(id=ind, extra="", start=start), ext="csv",
                     check=check_csv_header("ref_area", "source", "classif1", "time", "obs_value"))
        for r in csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig"))):
            v = to_float(r["obs_value"])
            suffix = CUR_SUFFIX.get(r["classif1"])
            # earnings are positive by definition; ILOSTAT uses 0 for a missing value
            if v is None or v <= 0 or r["sex"] != "SEX_T" or suffix is None:
                continue
            out.append(Obs(f"{base}{suffix}@{r['source']}", r["ref_area"], r["time"], v, snap.key, note=_notes(r)))
    ind, base = HOURS
    snap = f.get(f"ilostat/{ind}", DATA.format(id=ind, extra="", start=start), ext="csv",
                 check=check_csv_header("ref_area", "source", "time", "obs_value"))
    for r in csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig"))):
        v = to_float(r["obs_value"])
        if v is None or v <= 0 or r["sex"] != "SEX_T":
            continue
        out.append(Obs(f"{base}@{r['source']}", r["ref_area"], r["time"], v, snap.key, note=_notes(r)))
    dictionaries = {}
    for var in ("source", "note_source", "note_indicator"):
        snap = f.get(f"ilostat/dic_{var}", DIC.format(var=var), ext="csv", check=check_csv_header(var, f"{var}.label"))
        rows = csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig")))
        dictionaries[var] = {r[var]: r[f"{var}.label"] for r in rows}
    return out, dictionaries


def _notes(r: dict) -> str:
    """All note codes of an observation, e.g. 'T8:128_T9:131|S3:20' -> 'T8:128 T9:131 S3:20'."""
    parts = []
    for k in ("note_indicator", "note_source", "note_classif"):
        parts += [p for p in re.split(r"[_|]", r.get(k) or "") if p]
    return " ".join(dict.fromkeys(parts))


# --------------------------------------------------------------------------------------
# Reading the note codes (labels come from ILOSTAT's own dictionaries)
# --------------------------------------------------------------------------------------

def codes(o: Obs) -> list[str]:
    return [c for c in o.note.split() if c]


def note_of(o: Obs, prefix: str) -> list[str]:
    """Codes of one note type, e.g. note_of(o, 'T8') -> ['T8:128']."""
    return [c for c in codes(o) if c.split(":", 1)[0] == prefix]


def label(code: str, dic: dict) -> str:
    return dic.get("note_indicator", {}).get(code) or dic.get("note_source", {}).get(code) or code


CURRENCY_RE = re.compile(r"\(([A-Z]{3})\)\s*$")


def currency(o: Obs, dic: dict) -> str | None:
    """ISO 4217 code from the T30 'Currency: XXX - Name (CODE)' note, if present."""
    for c in note_of(o, "T30"):
        m = CURRENCY_RE.search(label(c, dic))
        if m:
            return m.group(1)
    return None
