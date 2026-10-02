"""Round-specific deep probes: download, parse and print compact summaries."""
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict

UA = "costmodel-data-pipeline/0.1 (+https://github.com/GYZ001/costmodel)"


def get(url, data=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def section(title):
    print(f"\n######## {title}", flush=True)


def safe(fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED: {type(e).__name__}: {e}", flush=True)


def ilo_toc():
    section("ILO toc: EAR_* and HOW_* annual ids")
    rows = list(csv.DictReader(io.StringIO(get("https://rplumber.ilo.org/metadata/toc/indicator/?lang=en&format=.csv").decode("utf-8-sig"))))
    for r in rows:
        if r["freq"] == "A" and (r["id"].startswith("EAR_") or r["id"].startswith("HOW_XEES") or r["id"].startswith("HOW_TEMP_SEX_ECO")):
            print(r["id"], "|", r["indicator.label"], "|", r["data.start"], "-", r["data.end"], "| n_area", r["n.ref_area"])


def ilo_cov(ind, extra=""):
    def run():
        section(f"ILO coverage {ind} {extra}")
        raw = get(f"https://rplumber.ilo.org/data/indicator/?id={ind}&timefrom=2018{extra}&format=.csv").decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(raw)))
        print("rows", len(rows), "cols", list(rows[0].keys()) if rows else None)
        if rows:
            keys = [k for k in rows[0].keys() if k.startswith("classif")]
            combos = defaultdict(int)
            for r in rows:
                combos[tuple(r[k] for k in keys) + (r.get("sex"),)] += 1
            print("top classif combos:", sorted(combos.items(), key=lambda x: -x[1])[:8])
            latest = {}
            for r in rows:
                if r.get("sex") not in (None, "SEX_T"):
                    continue
                if any(r[k] not in ("ECO_AGGREGATE_TOTAL", "ECO_SECTOR_TOTAL", "OCU_SKILL_TOTAL", "OCU_ISCO08_TOTAL", "CUR_TYPE_LCU", "") and not r[k].startswith("CUR_TYPE_LCU") for k in keys):
                    continue
                a = r["ref_area"]
                if a not in latest or r["time"] > latest[a][0]:
                    latest[a] = (r["time"], r["obs_value"], r["source"], [r[k] for k in keys])
            focus = "USA CHN JPN DEU GBR FRA ITA ESP KOR IND BRA MEX RUS TUR IDN ZAF AUS CAN SAU ARG VNM THA PHL EGY NGA POL NLD CHE SWE MYS PAK BGD".split()
            for a in focus:
                print(a, latest.get(a))
            print("n areas with total:", len(latest), "by latest year:", sorted(defaultdict(int, {}).items()))
            yc = defaultdict(int)
            for v in latest.values():
                yc[v[0]] += 1
            print("latest-year histogram:", sorted(yc.items()))
    safe(run)


def nbs_lists():
    section("NBS release list pages: titles matching wages/hours/migrant/CPI")
    pat = re.compile(r'href="\./(\d{6}/t\d+_\d+\.html)"[^>]*title=\'([^\']+)\'')
    seen = set()
    for p in range(0, 12):
        url = "https://www.stats.gov.cn/sj/zxfb/" + ("" if p == 0 else f"index_{p}.html")
        try:
            html = get(url, timeout=60).decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(url, "FAILED", e)
            continue
        for href, title in pat.findall(html):
            if href in seen:
                continue
            seen.add(href)
            if re.search(r"平均工资|农民工|工作时间|居民收入|居民消费价格|城镇调查失业率|国民经济", title):
                print(p, "https://www.stats.gov.cn/sj/zxfb/" + href, title)


def nbs_page(url, needles):
    def run():
        section(f"NBS page {url}")
        html = get(url, timeout=60).decode("utf-8", "replace")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"\s+", " ", text)
        for n in needles:
            for m in list(re.finditer(n, text))[:3]:
                print(f"[{n}] ...{text[max(0, m.start() - 150): m.start() + 350]}...")
    safe(run)


def pinksheet():
    section("Pink Sheet monthly xlsx: sheets and gold column")
    import openpyxl
    html = get("https://www.worldbank.org/en/research/commodity-markets").decode("utf-8", "replace")
    url = re.search(r'https://thedocs\.worldbank\.org/[^"]+CMO-Historical-Data-Monthly\.xlsx', html).group(0)
    print("url", url)
    wb = openpyxl.load_workbook(io.BytesIO(get(url)), read_only=True, data_only=True)
    print("sheets", wb.sheetnames)
    ws = wb["Monthly Prices"]
    rows = list(ws.iter_rows(values_only=True))
    for i, r in enumerate(rows[:8]):
        print(i, [c for c in r[:6]], "...", [c for c in r if isinstance(c, str) and "old" in c.lower()][:3])
    hdr_idx = next(i for i, r in enumerate(rows) if r and any(isinstance(c, str) and c.strip().lower() == "gold" for c in r))
    hdr = rows[hdr_idx]
    col = next(j for j, c in enumerate(hdr) if isinstance(c, str) and c.strip().lower() == "gold")
    print("header row", hdr_idx, "gold col", col, "unit row:", rows[hdr_idx + 1][col], "code row:", rows[hdr_idx + 2][col] if len(rows) > hdr_idx + 2 else None)
    for r in rows[-24:]:
        print(r[0], r[col])
    ws2 = wb[wb.sheetnames[0]]
    for r in list(ws2.iter_rows(values_only=True))[:12]:
        print("README", [c for c in r[:3] if c])


def icp():
    section("ICP 2021 data (WB source 90)")
    for q in [
        "https://api.worldbank.org/v2/sources/90/country/CHN;USA;IND/series/1101000;9100000/classification/PX.WL;PPPGlob/time/YR2021?format=json&per_page=100",
        "https://api.worldbank.org/v2/sources/90/country/CHN;USA/series/1101000/classification/PX.WL/time/YR2021?format=json",
        "https://api.worldbank.org/v2/sources/90/country/all/series/1101000/classification/PX.WL/time/YR2021?format=json&per_page=500",
    ]:
        try:
            raw = get(q).decode()
            print(q, "\n", raw[:1500], "\n... bytes", len(raw))
        except Exception as e:  # noqa: BLE001
            print(q, "FAILED", e)


def oecd_wage_units():
    section("OECD AV_AN_WAGE unit/price-base combos")
    raw = get("https://sdmx.oecd.org/public/rest/data/OECD.ELS.SAE,DSD_EARNINGS@AV_AN_WAGE,1.0/all?startPeriod=2025&format=csvfilewithlabels").decode()
    rows = list(csv.DictReader(io.StringIO(raw)))
    combos = defaultdict(set)
    for r in rows:
        combos[(r["UNIT_MEASURE"], r["PRICE_BASE"])].add(r["REF_AREA"])
    for k, v in combos.items():
        print(k, len(v), sorted(v)[:50])
    for r in rows:
        if r["REF_AREA"] in ("USA", "JPN", "KOR", "MEX") and r["PRICE_BASE"] == "V":
            print(r["REF_AREA"], r["UNIT_MEASURE"], r["TIME_PERIOD"], r["OBS_VALUE"])


def statcan():
    section("StatCan 18-10-0245 products (latest month, Canada)")
    z = zipfile.ZipFile(io.BytesIO(get("https://www150.statcan.gc.ca/n1/tbl/csv/18100245-eng.zip")))
    name = [n for n in z.namelist() if not n.endswith("MetaData.csv")][0]
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig")))
    print("cols", list(rows[0].keys()))
    last = max(r["REF_DATE"] for r in rows)
    for r in rows:
        if r["REF_DATE"] == last and r["GEO"] == "Canada":
            print(last, r["Products"], r["VALUE"], r["UOM"])


def sge():
    section("SGE pages")
    for url in ["https://www.sge.com.cn/sjzx/jzj", "https://www.sge.com.cn/sjzx/mrhq"]:
        try:
            html = get(url, timeout=60).decode("utf-8", "replace")
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text)
            for n in ["上海金", "Au99.99", "基准价", "2026"]:
                for m in list(re.finditer(n, text))[:2]:
                    print(f"[{url} {n}] ...{text[max(0, m.start() - 100): m.start() + 300]}...")
            links = re.findall(r'href="([^"]*(?:jzj|mrhq)[^"]*)"', html)[:15]
            print("links", links)
        except Exception as e:  # noqa: BLE001
            print(url, "FAILED", e)


if __name__ == "__main__":
    safe(ilo_toc)
    safe(nbs_lists)
    nbs_page("https://www.stats.gov.cn/sj/zxfb/202609/t20260909_1965263.html", ["食品", "粮食", "猪肉", "鲜菜"])
    safe(pinksheet)
    safe(icp)
    safe(oecd_wage_units)
    safe(statcan)
    safe(sge)
    for ind in ["HOW_XEES_SEX_NB_A", "HOW_TEMP_SEX_ECO_NB_A"]:
        ilo_cov(ind)
