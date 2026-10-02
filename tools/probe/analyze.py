"""Round-specific deep probes."""
import csv, io, re, urllib.request
from collections import defaultdict
UA = "costmodel-data-pipeline/0.1 (+https://github.com/GYZ001/costmodel)"
def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()
def section(t): print(f"\n######## {t}", flush=True)
def safe(fn):
    try: fn()
    except Exception as e: print("FAILED:", type(e).__name__, e, flush=True)

def flows():
    section("OECD.ELS.SAE dataflows")
    x = get("https://sdmx.oecd.org/public/rest/dataflow/OECD.ELS.SAE").decode()
    for m in re.finditer(r'<structure:Dataflow[^>]*id="([^"]+)"[^>]*>.*?<common:Name xml:lang="en">([^<]+)</common:Name>', x, re.S):
        print(m.group(1), "|", m.group(2))

def usual():
    for flow in ["DSD_HW@DF_AVG_USL_WK_WKD", "DSD_HW@DF_AVG_ANN_HRS_WKD"]:
        section(f"OECD {flow}")
        raw = get(f"https://sdmx.oecd.org/public/rest/data/OECD.ELS.SAE,{flow},1.0/all?startPeriod=2023&format=csvfilewithlabels").decode()
        rows = list(csv.DictReader(io.StringIO(raw)))
        print("rows", len(rows), "cols", list(rows[0].keys())[:40] if rows else None)
        combos = defaultdict(int)
        dims = [k for k in rows[0] if k.isupper() and k not in ("STRUCTURE", "STRUCTURE_ID", "ACTION", "REF_AREA", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS", "UNIT_MULT", "DECIMALS")] if rows else []
        for r in rows:
            combos[tuple((d, r[d]) for d in dims)] += 1
        for k, v in sorted(combos.items(), key=lambda x: -x[1])[:25]:
            print(v, k)
        for r in rows:
            if r["REF_AREA"] in ("USA", "JPN", "DEU", "KOR", "AUS") and r["TIME_PERIOD"] in ("2024", "2025"):
                print(" ", r["REF_AREA"], r["TIME_PERIOD"], {d: r[d] for d in dims}, r["OBS_VALUE"])

if __name__ == "__main__":
    safe(flows)
    safe(usual)
