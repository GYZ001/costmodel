"""ECB reference exchange rates (monthly averages), converted to LCU per US$.

The ECB publishes every rate against the euro.  LCU per US$ is the cross rate
(LCU per EUR) / (USD per EUR) for the same month, which is how the ECB itself
describes deriving cross rates from its reference rates.
"""
from __future__ import annotations

import csv
import io

from ..fetch import Fetcher
from ..model import Obs
from .common import check_csv_header, to_float

URL = "https://data-api.ecb.europa.eu/service/data/EXR/M..EUR.SP00.A?format=csvdata&startPeriod=1999-01"

# ECB currency code -> ISO3 economy using it as legal tender (euro handled separately)
CURRENCY_AREA = {
    "AUD": "AUS", "BGN": "BGR", "BRL": "BRA", "CAD": "CAN", "CHF": "CHE", "CNY": "CHN", "CZK": "CZE",
    "DKK": "DNK", "GBP": "GBR", "HKD": "HKG", "HUF": "HUN", "IDR": "IDN", "ILS": "ISR", "INR": "IND",
    "ISK": "ISL", "JPY": "JPN", "KRW": "KOR", "MXN": "MEX", "MYR": "MYS", "NOK": "NOR", "NZD": "NZL",
    "PHP": "PHL", "PLN": "POL", "RON": "ROU", "RUB": "RUS", "SEK": "SWE", "SGD": "SGP", "THB": "THA",
    "TRY": "TUR", "ZAR": "ZAF", "USD": "USA",
}


def collect(f: Fetcher) -> list[Obs]:
    snap = f.get("ecb/exr_monthly", URL, ext="csv", check=check_csv_header("CURRENCY", "TIME_PERIOD", "OBS_VALUE"))
    rows = list(csv.DictReader(io.StringIO(snap.read().decode("utf-8-sig"))))
    per_eur: dict[tuple[str, str], float] = {}
    for r in rows:
        v = to_float(r["OBS_VALUE"])
        if v is not None:
            per_eur[(r["CURRENCY"], r["TIME_PERIOD"])] = v
    out = []
    for (cur, period), lcu_per_eur in per_eur.items():
        usd_per_eur = per_eur.get(("USD", period))
        if usd_per_eur is None:
            continue
        rate = lcu_per_eur / usd_per_eur
        area = CURRENCY_AREA.get(cur)
        if area and area != "USA":
            out.append(Obs("fx_lcu_usd_ecb", area, period, rate, snap.key, note=cur))
        # Euro: EUR per USD applies to every euro-area member; stored under the currency code.
        if cur == "USD":
            out.append(Obs("fx_lcu_usd_ecb", "EUR", period, 1 / usd_per_eur, snap.key, note="EUR"))
    return out
