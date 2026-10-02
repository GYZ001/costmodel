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
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def uk3():
    o = Out("UK3 price quotes Aug 2026 + MM23 recency + shopping tool viz data")
    u = "/economy/inflationandpriceindices/datasets/consumerpriceindicescpiandretailpricesindexrpiitemindicesandpricequotes/pricequotesaugust2026"
    st, ct, b, fu, dt = fetch("https://www.ons.gov.uk" + u + "/data")
    try:
        jj = json.loads(b)
        files = [x.get("file") for x in jj.get("downloads", [])]
        o("   pricequotesaugust2026 release", jj.get("description", {}).get("releaseDate"), "| files", files)
        fu_ = "https://www.ons.gov.uk/file?uri=" + u + "/" + files[0]
        st, ct, b, fu = o.show("pq file", fu_, n=0, timeout=150)
        if b[:2] == b"PK":
            z = zipfile.ZipFile(io.BytesIO(b))
            o("   zip:", z.namelist()[:5])
            b = z.read([n for n in z.namelist() if n.lower().endswith(".csv")][0])
        rows = list(csv.DictReader(io.StringIO(txt(b))))
        cols = list(rows[0].keys())
        o("   rows:", len(rows), "cols:", cols)
        o("   sample:", rows[0])
        low = {c.lower(): c for c in cols}
        cid, cdesc, cprice, cval = low.get("item_id"), low.get("item_desc"), low.get("price"), low.get("validity")
        o("   VALIDITY:", Counter(r.get(cval) for r in rows).most_common(10) if cval else None)
        for extra in ("shop_type", "region", "stratum_type", "indicator_box"):
            if low.get(extra):
                o(f"   {extra}:", Counter(r.get(low[extra]) for r in rows).most_common(8))
        items = defaultdict(list)
        desc = {}
        for r in rows:
            desc[r[cid]] = r[cdesc]
            try:
                pr = float(r[cprice])
            except (TypeError, ValueError):
                continue
            if pr > 0 and (not cval or r[cval] in ("3", "4")):
                items[r[cid]].append(pr)
        o("   distinct items:", len(desc))
        n = 0
        for iid, d in sorted(desc.items(), key=lambda x: x[1]):
            if any(k in d.lower() for k in KEYS) and items.get(iid):
                ps = items[iid]
                o(f"     {iid} | {d} | n={len(ps)} median={statistics.median(ps):.2f}")
                n += 1
                if n > 60:
                    break
    except Exception as e:  # noqa: BLE001
        o("   pq fail", type(e).__name__, e)
    st, ct, b, fu, dt = fetch("https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/consumerpriceindices/current/mm23.csv", timeout=120)
    try:
        rd = list(csv.reader(io.StringIO(txt(b))))
        titles, cdids = rd[0], rd[1]
        av = [i for i, t in enumerate(titles) if "ave price" in t.lower()]
        monthly = [r for r in rd if re.match(r"^\d{4} [A-Z]{3}$", (r[0] or "").strip())]
        o("   MM23 monthly rows:", len(monthly), "first", monthly[0][0], "last", monthly[-1][0])
        lastp = Counter()
        for i in av:
            last = None
            for r in monthly:
                if i < len(r) and r[i].strip():
                    last = (r[0], r[i])
            lastp[last[0] if last else None] += 1
            if any(k in titles[i].lower() for k in KEYS):
                o("     ", cdids[i], "|", titles[i][:75], "| last:", last)
        o("   last-period histogram of", len(av), "avg-price cols:", lastp.most_common(8))
    except Exception as e:  # noqa: BLE001
        o("   mm23 fail", type(e).__name__, e)
    st, ct, b, fu = o.show("viz index", "https://www.ons.gov.uk/visualisations/dvc2523/shopping-prices-comparison-tool/index.html", n=0)
    h = txt(b)
    o("   data-ish refs:", sorted(set(re.findall(r"""["']([^"']+\.(?:csv|json|js))["']""", h)))[:20])
    return o


def fao3():
    o = Out("FAO3 FPMA API")
    base = "https://fpma.fao.org/giews/v4/global/price_module/api/v1/"
    st, ct, b, fu = o.show("api root", base + "?format=json", n=1500)
    st, ct, b, fu = o.show("FpmaSerie sample", base + "FpmaSerie/?format=json&page_size=2", n=0, timeout=90)
    try:
        j = json.loads(b)
        if isinstance(j, dict):
            o("   keys:", list(j.keys()), "count:", j.get("count"))
            res = j.get("results", [])
        else:
            o("   list len:", len(j))
            res = j
        if res:
            o("   first record:", json.dumps(res[0], ensure_ascii=False)[:1500])
    except Exception as e:  # noqa: BLE001
        o("   fail", e, txt(b[:300]))
    for q in ("FpmaSerie/?format=json&iso3_country_code=IND&page_size=3", "FpmaSerie/?format=json&country__iso3=IND&page_size=3",
              "FpmaSerie/?format=json&iso3=IND&page_size=3", "Market/?format=json&page_size=2", "FpmaSerieDomestic/?format=json&page_size=2"):
        st, ct, b, fu = o.show("q", base + q, n=600, timeout=90)
    o.show("core Global", "https://fpma.fao.org/giews/v4/global/core/api/v1/Global/?format=json", n=600)
    return o


def japan3():
    o = Out("JAPAN3 e-Stat datalist drill")
    seen = set()
    frontier = ["https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00200571&tstat=000000680001&cycle=1&tclass1=000001035981&tclass2val=0",
                "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00200571&tstat=000000680001&cycle=1&tclass1val=0"]
    found = []
    depth = 0
    while frontier and depth < 4 and len(found) < 40:
        nxt = []
        for u in frontier[:8]:
            if u in seen:
                continue
            seen.add(u)
            st, ct, b, fu, dt = fetch(u, timeout=45)
            h = txt(b).replace("&amp;", "&")
            for m in re.finditer(r'statInfId=(\d{12})', h):
                sid = m.group(1)
                if sid not in [f[0] for f in found]:
                    seg = h[max(0, m.start() - 1500): m.start()]
                    tt = re.findall(r'class="stat-title-has-data[^"]*"[^>]*>([^<]+)<|<span[^>]*class="[^"]*stat-title[^"]*"[^>]*>([^<]+)<', seg)
                    title = strip(" / ".join([x[0] or x[1] for x in tt][-3:]))
                    found.append((sid, title[:160]))
            for m in re.finditer(r'href="(/stat-search/files\?[^"]*toukei=00200571[^"]*tclass\d=\d+[^"]*)"[^>]*>\s*([^<]{1,80})', h):
                link = "https://www.e-stat.go.jp" + m.group(1)
                if link not in seen:
                    nxt.append(link)
                    if depth < 2:
                        o(f"   d{depth} drill:", strip(m.group(2))[:60], "->", m.group(1)[-90:])
        frontier = nxt
        depth += 1
    o("   statInfIds found:", len(found))
    for sid, t in found[:30]:
        o("     ", sid, "|", t)
    pick = None
    for sid, t in found:
        if "主要品目" in t or "都市別" in t or "東京都区部" in t:
            pick = sid
            break
    pick = pick or (found[0][0] if found else None)
    if pick:
        st, ct, b, fu = o.show("file-download excel", f"https://www.e-stat.go.jp/stat-search/file-download?statInfId={pick}&fileKind=0", n=0, timeout=90)
        try:
            if b[:2] == b"PK":
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(b), read_only=True, data_only=True)
                ws = wb.worksheets[0]
                rows = list(ws.iter_rows(values_only=True))
            else:
                import xlrd
                wb = xlrd.open_workbook(file_contents=b)
                sh = wb.sheet_by_index(0)
                rows = [sh.row_values(i) for i in range(sh.nrows)]
            o("   rows", len(rows))
            for r in rows[:10]:
                o("     top:", " | ".join(str(c) for c in r if c not in (None, ""))[:300])
            hits = 0
            for r in rows:
                line = " | ".join(str(c) for c in r if c not in (None, ""))
                if any(k in line for k in ("食パン", "牛乳", "鶏卵", "うるち米", "砂糖", "バナナ")):
                    o("     hit:", line[:300])
                    hits += 1
                    if hits > 10:
                        break
        except Exception as e:  # noqa: BLE001
            o("   excel fail", type(e).__name__, e, txt(b[:200]))
        o.show("file-download csv", f"https://www.e-stat.go.jp/stat-search/file-download?statInfId={pick}&fileKind=1", n=300, timeout=90)
    return o


def korea3():
    o = Out("KOREA3 KAMIS coverage")
    st, ct, b, fu = o.show("KAMIS dailySalesList", "https://www.kamis.or.kr/service/price/xml.do?action=dailySalesList&p_cert_key=111&p_cert_id=222&p_returntype=json", n=0, timeout=90)
    try:
        j = json.loads(b)
        pr = j.get("price", [])
        o("   n items:", len(pr), "| cls:", Counter(p.get("product_cls_name") for p in pr), "| cats:", Counter(p.get("category_name") for p in pr))
        for p in pr:
            if p.get("product_cls_name") == "소매":
                o("     ", p.get("productno"), p.get("item_name"), p.get("unit"), p.get("lastest_day"), p.get("dpr1"))
    except Exception as e:  # noqa: BLE001
        o("   fail", e, txt(b[:300]))
    return o


def misc3():
    o = Out("MISC3 Germany list, DIEESE POST, SingStat keys, NZ csv, Mexico retries")
    st, ct, b, fu = o.show("GENESIS find", "https://genesis.destatis.de/genesisWS/rest/2020/find/find", n=0,
                           data=urllib.parse.urlencode({"term": "Durchschnittspreise", "category": "tables", "pagelength": "50", "language": "de"}).encode(),
                           headers={"username": "GAST", "password": "GAST", "Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
    try:
        for t in json.loads(b).get("Tables") or []:
            o("     ", t["Code"], "|", t["Content"].replace("\n", " ")[:120])
    except Exception as e:  # noqa: BLE001
        o("   fail", e)
    st, ct, b, fu = o.show("DIEESE page", "https://www.dieese.org.br/cesta/", n=0, timeout=40)
    h = txt(b)
    sels = re.findall(r'<select name="(\w+)"[^>]*>(.*?)</select>', h, flags=re.S)
    prods, cities = [], []
    for name, body in sels:
        opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', body)
        if name == "produtos" and not prods:
            prods = opts
        if name == "cidades" and not cities:
            cities = opts
    o("   produtos:", prods)
    o("   cidades n:", len(cities))
    if prods and cities:
        data = [("produtos", p[0]) for p in prods] + [("cidades", "9"), ("tipoDado", "5"), ("dataInicial", "012026"), ("dataFinal", "082026"), ("farinha", "true")]
        st, ct, b, fu = o.show("DIEESE POST cidade", "https://www.dieese.org.br/cesta/cidade", n=0, data=urllib.parse.urlencode(data).encode(),
                               headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": "https://www.dieese.org.br/cesta/"}, timeout=60)
        hh = txt(b)
        o("   title:", title_of(hh), "| tables:", hh.count("<table"), "| xls links:", re.findall(r'href="[^"]*(?:xls|csv|export)[^"]*"', hh)[:5])
        o("   text:", strip(re.sub(r"<script.*?</script>", " ", hh, flags=re.S))[:1500])
    st, ct, b, fu = o.show("SingStat monthly default", "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213761", n=0, timeout=60)
    try:
        dat = json.loads(b).get("Data", {})
        rows = dat.get("row", [])
        r0 = rows[0]
        keys = [c.get("key") for c in r0.get("columns", [])]
        o("   rows:", len(rows), "| row0:", r0.get("rowText"), "| n cols:", len(keys), "| first keys:", keys[:3], "| last keys:", keys[-3:])
        for r in rows:
            if any(k in (r.get("rowText") or "").lower() for k in ("egg", "milk", "rice", "sugar", "bread")):
                c = r.get("columns", [])
                o("     ", r.get("rowText"), "|", c[-1] if c else None)
    except Exception as e:  # noqa: BLE001
        o("   singstat fail", e, txt(b[:200]))
    st, ct, b, fu = o.show("StatsNZ SPI release", "https://www.stats.govt.nz/information-releases/selected-price-indexes-august-2026/", n=0)
    h = txt(b)
    o("   refs:", sorted(set(re.findall(r'(?:href|data-url|src)="([^"]*(?:Uploads|csv|xlsx|download)[^"]*)"', h)))[:15])
    for ua in ("python-urllib/3.12", "curl/8.5.0"):
        o.show(f"PROFECO csv UA={ua}", "https://repodatos.atdt.gob.mx/api_update/profeco/programa_quien_es_quien_precios_2026/b07_2026_q1.csv", n=300,
               headers={"User-Agent": ua, "Range": "bytes=0-4095"}, timeout=60)
    st, ct, b, fu = o.show("INEGI preciospromedio", "https://www.inegi.org.mx/app/preciospromedio/", n=0)
    h = txt(b)
    js = " ".join(re.findall(r"<script[^>]*>(.*?)</script>", h, flags=re.S))
    o("   inline-js endpoints:", sorted(set(re.findall(r"""["']([^"'\s]*(?:\.aspx/[A-Za-z]+|\.asmx[^"']*|\.ashx[^"']*|Exportacion[^"']*|/api/[^"']*))["']""", js)))[:20])
    for m in list(re.finditer(r"(ajax|\$\.post|\$\.get|fetch\(|url\s*:)", js))[:6]:
        o("     ctx:", js[max(0, m.start() - 100): m.end() + 200].replace("\n", " ")[:300])
    o.show("INEGI Exportacion no params", "https://www.inegi.org.mx/app/preciospromedio/Exportacion.aspx", n=300)
    return o


if __name__ == "__main__":
    fns = [uk3, fao3, japan3, korea3, misc3]
    with ThreadPoolExecutor(max_workers=len(fns)) as ex:
        futs = [ex.submit(f) for f in fns]
        for f, fu in zip(fns, futs):
            try:
                out = fu.result(timeout=900)
                print("\n".join(out.lines), flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"\n######## {f.__name__} CRASHED {type(e).__name__}: {e}", flush=True)
