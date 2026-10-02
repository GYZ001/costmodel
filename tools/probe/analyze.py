"""Retail-price probe R1: official item-level average retail prices outside US/CN.

Each section runs in its own thread, buffers its output, and output is printed in order.
Stdlib only (+ openpyxl / pyarrow when available).
"""
import csv
import gzip
import io
import json
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36 costmodel-probe"
KEYS = ["bread", "rice", "flour", "egg", "milk", "beef", "chicken", "pork", "potato", "tomato", "apple", "banana", "sugar", "oil"]


def fetch(url, data=None, headers=None, timeout=30, method=None):
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en,fr;q=0.8"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return r.status, r.headers.get("Content-Type", ""), body, r.geturl(), time.time() - t
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:  # noqa: BLE001
            body = b""
        return e.code, (e.headers.get("Content-Type", "") if e.headers else ""), body, url, time.time() - t
    except Exception as e:  # noqa: BLE001
        return -1, "", f"{type(e).__name__}: {e}".encode(), url, time.time() - t


def txt(b):
    for enc in ("utf-8", "cp932", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


class Out:
    def __init__(self, title):
        self.lines = [f"\n######## {title}"]

    def __call__(self, *a):
        self.lines.append(" ".join(str(x) for x in a))

    def show(self, label, url, n=300, **kw):
        st, ct, b, fu, dt = fetch(url, **kw)
        self(f"[{label}] {st} {ct} {len(b)}B {dt:.1f}s final={fu}")
        if n:
            self("   HEAD:", txt(b[:n]).replace("\n", " ")[:n])
        return st, ct, b, fu

    def links(self, html, pat, n=25, label="links"):
        found = []
        for m in re.finditer(pat, html, flags=re.I):
            v = m.group(0)
            if v not in found:
                found.append(v)
        self(f"   {label} ({len(found)}):", found[:n])
        return found


def title_of(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.S | re.I)
    return strip(m.group(1))[:150] if m else None


csv.field_size_limit(10**9)


def uk4():
    o = Out("UK4 price quotes Aug 2026 staples by CS_DESC")
    u = "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/consumerpriceindicescpiandretailpricesindexrpiitemindicesandpricequotes/pricequotesaugust2026/upload-pricequotes202608.csv"
    st, ct, b, fu, dt = fetch(u, timeout=150)
    rows = list(csv.DictReader(io.StringIO(txt(b))))
    o("   rows", len(rows), "distinct CS:", len({r["CS_ID"] for r in rows}))
    items = defaultdict(list)
    desc = {}
    for r in rows:
        desc[r["CS_ID"]] = r["CS_DESC"]
        if r["VALIDITY"] == "True":
            try:
                p = float(r["PRICE"])
            except ValueError:
                continue
            if p > 0:
                items[r["CS_ID"]].append(p)
    n = 0
    kw = KEYS + ["loaf", "eggs", "spaghetti", "pasta", "cheese", "butter", "flour"]
    for cid, d in sorted(desc.items(), key=lambda x: x[1]):
        if any(k in d.lower() for k in kw) and items.get(cid):
            ps = items[cid]
            o(f"     {cid} | {d} | n={len(ps)} median={statistics.median(ps):.2f}")
            n += 1
            if n > 70:
                break
    st, ct, b, fu, dt = fetch("https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/consumerpriceindicescpiandretailpricesindexrpiitemindicesandpricequotes/data")
    j = json.loads(b)
    o("   landing markdown:", strip(json.dumps(j.get("section", {}), ensure_ascii=False))[:900])
    return o


def fao4():
    o = Out("FAO4 FPMA coverage by country + price fetch")
    base = "https://fpma.fao.org/giews/v4/global/price_module/api/v1/"
    sample = None
    for iso in ("IND", "MEX", "BRA", "CHN", "JPN", "KOR", "USA", "ZAF", "IDN", "PHL", "TUR", "EGY", "NGA", "RUS", "ARG", "THA", "VNM", "PAK", "BGD"):
        st, ct, b, fu, dt = fetch(base + f"FpmaSerie/?format=json&iso3_country_code={iso}", timeout=90)
        try:
            res = json.loads(b).get("results", [])
        except Exception as e:  # noqa: BLE001
            o("   ", iso, "fail", st, e)
            continue
        ret = [r for r in res if r.get("price_type") == "RETAIL"]
        ends = []
        for r in ret:
            for p in r.get("periodicity", []):
                if p.get("period") == "monthly":
                    ends.append(p.get("end_date"))
        coms = Counter(r.get("commodity_name") for r in ret)
        srcs = Counter(r.get("source_name") for r in ret)
        mkts = Counter(r.get("market_name") for r in ret)
        o(f"   {iso}: series {len(res)} retail {len(ret)} | latest monthly end {max(ends) if ends else None} | commodities {dict(coms.most_common(14))}")
        o(f"        sources {dict(srcs.most_common(3))} | markets {list(mkts)[:8]}")
        if iso == "IND" and ret and not sample:
            sample = ret[0]
    if sample:
        o("   sample series:", sample.get("uuid"), sample.get("commodity_name"), sample.get("market_name"), sample.get("currency"), sample.get("measure_unit_label"))
        for q in (f"FpmaSeriePrice/?format=json&uuid__in={sample['uuid']}&periodicity=monthly", f"FpmaSeriePrice/{sample['uuid']}/?format=json&periodicity=monthly"):
            st, ct, b, fu = o.show("prices", base + q, n=900, timeout=90)
    return o


def japan4():
    o = Out("JAPAN4 e-Stat top-level categories + main table")
    u = "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00200571&tstat=000000680001&cycle=1&tclass1val=0"
    st, ct, b, fu, dt = fetch(u, timeout=60)
    h = txt(b).replace("&amp;", "&")
    anchors = re.findall(r'<a[^>]+href="([^"]*tclass1=\d+[^"]*)"[^>]*>(.*?)</a>', h, flags=re.S)
    cats = {}
    for href, inner in anchors:
        t = strip(inner)
        m = re.search(r"tclass1=(\d+)", href)
        if t and m and m.group(1) not in cats:
            cats[m.group(1)] = t
    o("   tclass1 categories:", cats)
    spans = re.findall(r'<span[^>]*class="[^"]*stat-(?:title|cycle|text)[^"]*"[^>]*>([^<]{2,80})<', h)
    o("   span texts:", spans[:40])
    main = [k for k, v in cats.items() if "ガソリン" not in v]
    for k in main[:4]:
        u2 = f"https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00200571&tstat=000000680001&cycle=1&tclass1={k}&tclass2val=0"
        st, ct, b, fu, dt = fetch(u2, timeout=60)
        hh = txt(b).replace("&amp;", "&")
        ids = []
        for m in re.finditer(r"stat_infid=(\d{12})", hh):
            if m.group(1) not in ids:
                ids.append(m.group(1))
        sub = re.findall(r'<a[^>]+href="([^"]*tclass2=\d+[^"]*)"[^>]*>(.*?)</a>', hh, flags=re.S)
        o(f"   tclass1={k} ({cats[k]}): stat_infids {len(ids)} {ids[:5]} | tclass2:", [(re.search(r'tclass2=(\d+)', a).group(1), strip(t)) for a, t in sub if strip(t)][:12])
        titles = re.findall(r"「?[^<>]{0,40}小売価格[^<>]{0,60}", hh)
        o("      titles:", list(dict.fromkeys(strip(t) for t in titles))[:8])
        if ids:
            st, ct, b2, fu = o.show("xlsx", f"https://www.e-stat.go.jp/stat-search/file-download?statInfId={ids[0]}&fileKind=0", n=0, timeout=90)
            try:
                if b2[:2] == b"PK":
                    import openpyxl
                    wb = openpyxl.load_workbook(io.BytesIO(b2), read_only=True, data_only=True)
                    rows = list(wb.worksheets[0].iter_rows(values_only=True))
                else:
                    import xlrd
                    sh = xlrd.open_workbook(file_contents=b2).sheet_by_index(0)
                    rows = [sh.row_values(i) for i in range(sh.nrows)]
                for r in rows[:12]:
                    o("      top:", " | ".join(str(c) for c in r if c not in (None, ""))[:250])
                hits = 0
                for r in rows:
                    line = " | ".join(str(c) for c in r if c not in (None, ""))
                    if any(x in line for x in ("食パン", "牛乳", "鶏卵", "うるち米", "砂糖", "バナナ", "東京都区部")):
                        o("      hit:", line[:300])
                        hits += 1
                        if hits > 10:
                            break
            except Exception as e:  # noqa: BLE001
                o("      xl fail", type(e).__name__, e)
    return o


def misc4():
    o = Out("MISC4 DIEESE tipoDado meanings + StatsSA last column + NZ")
    for td in ("3", "4"):
        data = [("produtos", str(i)) for i in range(1, 15)] + [("cidades", "9"), ("tipoDado", td), ("dataInicial", "062026"), ("dataFinal", "082026"), ("farinha", "true")]
        st, ct, b, fu = o.show(f"DIEESE tipoDado={td}", "https://www.dieese.org.br/cesta/cidade", n=0, data=urllib.parse.urlencode(data).encode(),
                               headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": "https://www.dieese.org.br/cesta/"}, timeout=60)
        o("   text:", strip(re.sub(r"<script.*?</script>", " ", txt(b), flags=re.S))[150:1100])
    st, ct, b, fu = o.show("DIEESE page labels", "https://www.dieese.org.br/cesta/", n=0)
    h = txt(b)
    o("   radio labels:", [strip(x)[:80] for x in re.findall(r'name="tipoDado"[^>]*/>([^<]{0,80})', h)][:6])
    u = "https://www.statssa.gov.za/timeseriesdata/Excel/P0141%20-%20CPI%20Average%20Prices%20All%20urban%20(202608).zip"
    st, ct, b, fu, dt = fetch(u, timeout=90)
    try:
        import openpyxl
        z = zipfile.ZipFile(io.BytesIO(b))
        wb = openpyxl.load_workbook(io.BytesIO(z.read(z.namelist()[0])), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        hdr = rows[0]
        o("   StatsSA sheets:", wb.sheetnames, "| header tail:", hdr[-4:], "| n cols", len(hdr), "| n rows", len(rows))
        for r in rows[1:]:
            d = " ".join(str(c) for c in r[:10] if c)
            if any(k in d.lower() for k in ("egg", "milk", "sugar", "chicken", "potato", "banana", "apple", "tomato", "sunflower", "pork")):
                o("     ", d[:140], "| last:", r[-1])
    except Exception as e:  # noqa: BLE001
        o("   statssa fail", type(e).__name__, e)
    st, ct, b, fu = o.show("StatsNZ SPI release", "https://www.stats.govt.nz/information-releases/selected-price-indexes-august-2026/", n=0)
    h = txt(b)
    i = h.find("Download")
    o("   download ctx:", strip(h[i - 300: i + 900]) if i >= 0 else None)
    o("   any .csv:", re.findall(r"[^\"'\s]+\.csv", h)[:5])
    return o


if __name__ == "__main__":
    fns = [uk4, fao4, japan4, misc4]
    with ThreadPoolExecutor(max_workers=len(fns)) as ex:
        futs = [ex.submit(f) for f in fns]
        for f, fu in zip(fns, futs):
            try:
                out = fu.result(timeout=900)
                print("\n".join(out.lines), flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"\n######## {f.__name__} CRASHED {type(e).__name__}: {e}", flush=True)
