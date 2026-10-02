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


JP_KEYS = ["食パン", "米", "うるち米", "鶏卵", "牛乳", "牛肉", "豚肉", "鶏肉", "じゃがいも", "トマト", "りんご", "バナナ", "砂糖", "食用油", "小麦粉", "ばれいしょ"]


def xl_rows(b, name, limit_sheets=3, max_rows=4000):
    """Yield (sheet, row_values) from xlsx or xls bytes."""
    out = []
    if b[:2] == b"PK":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(b), read_only=True, data_only=True)
        for ws in wb.worksheets[:limit_sheets]:
            for i, r in enumerate(ws.iter_rows(values_only=True)):
                if i > max_rows:
                    break
                out.append((ws.title, [c for c in r]))
    else:
        import xlrd
        wb = xlrd.open_workbook(file_contents=b)
        for sh in wb.sheets()[:limit_sheets]:
            for i in range(min(sh.nrows, max_rows)):
                out.append((sh.name, sh.row_values(i)))
    return out


def compact(row, n=14):
    vals = [str(c).strip() for c in row if c not in (None, "") and str(c).strip()]
    return " | ".join(vals[:n])[:400]


# ---------------------------------------------------------------- UK round 2
def uk2():
    o = Out("UK2 price quotes download + MM23 recency + shopping tool adhoc")
    base = "https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/consumerpriceindicescpiandretailpricesindexrpiitemindicesandpricequotes"
    st, ct, b, fu, dt = fetch(base + "/data")
    j = json.loads(b)
    dss = [d["uri"] for d in j.get("datasets", [])]
    pq = [u for u in dss if "pricequote" in u.lower()]
    o("   dataset uris containing 'pricequote':", len(pq), pq[:6])
    o("   other recent dataset uris:", [u.rsplit("/", 1)[-1] for u in dss[:14]])
    pq_url = None
    for u in pq[:3]:
        st2, ct2, b2, fu2, dt2 = fetch("https://www.ons.gov.uk" + u + "/data")
        try:
            jj = json.loads(b2)
            files = [x.get("file") for x in jj.get("downloads", [])]
            o("     ", u.rsplit("/", 1)[-1], "| release", jj.get("description", {}).get("releaseDate"), "| title", jj.get("description", {}).get("title"), "| files", files)
            if not pq_url and files:
                pq_url = "https://www.ons.gov.uk/file?uri=" + u + "/" + files[0]
        except Exception as e:  # noqa: BLE001
            o("      sub fail", st2, e)
    if pq_url:
        st, ct, b, fu = o.show("price quotes file", pq_url, n=0, timeout=120)
        try:
            if b[:2] == b"PK":
                z = zipfile.ZipFile(io.BytesIO(b))
                o("   zip:", z.namelist())
                b = z.read(z.namelist()[0])
            rows = list(csv.DictReader(io.StringIO(txt(b))))
            cols = list(rows[0].keys())
            o("   rows:", len(rows), "cols:", cols)
            o("   sample row:", rows[0])
            low = {c.lower(): c for c in cols}
            cid, cdesc, cprice, cval = low.get("item_id"), low.get("item_desc"), low.get("price"), low.get("validity")
            o("   VALIDITY:", Counter(r.get(cval) for r in rows).most_common(8) if cval else None, "| SHOP_TYPE:", Counter(r.get(low.get("shop_type")) for r in rows).most_common(4) if low.get("shop_type") else None)
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
            o("   pq parse failed", type(e).__name__, e)
    st, ct, b, fu, dt = fetch("https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/consumerpriceindices/current/mm23.csv", timeout=120)
    try:
        rd = list(csv.reader(io.StringIO(txt(b))))
        titles, cdids = rd[0], rd[1]
        av = [i for i, t in enumerate(titles) if "ave price" in t.lower()]
        monthly = [r for r in rd if re.match(r"^\d{4} [A-Z]{3}$", r[0] or "")]
        o("   MM23 monthly rows:", len(monthly), "first", monthly[0][0], "last", monthly[-1][0])
        lastp = Counter()
        for i in av:
            last = None
            for r in monthly:
                if i < len(r) and r[i].strip():
                    last = (r[0], r[i])
            lastp[last[0] if last else None] += 1
            if any(k in titles[i].lower() for k in KEYS):
                o("     ", cdids[i], "|", titles[i][:70], "| last:", last)
        o("   last-period histogram of the", len(av), "avg-price cols:", lastp.most_common(8))
    except Exception as e:  # noqa: BLE001
        o("   mm23 fail", type(e).__name__, e)
    st, ct, b, fu = o.show("shopping tool adhoc", "https://www.ons.gov.uk/economy/inflationandpriceindices/adhocs/2724shoppingpricescomparisontooldatadownloadbeforethe2025update", n=0)
    h = txt(b)
    o("   title:", title_of(h))
    o.links(h, r'/file\?uri=[^"\s]+', n=6)
    for m in re.finditer(r"(discontinu|no longer|2025 update|replaced)[^<]{0,250}", h, flags=re.I):
        o("     ctx:", strip(m.group(0))[:250])
        break
    st, ct, b, fu = o.show("shopping tool article", "https://www.ons.gov.uk/economy/inflationandpriceindices/articles/shoppingpricescomparisontool/2023-05-03", n=0)
    h = txt(b)
    o("   title:", title_of(h))
    o.links(h, r'href="[^"]*(?:dataset|file\?uri|visualisations)[^"]*"', n=10)
    return o


# ---------------------------------------------------------------- France round 2
def france2():
    o = Out("FRANCE2 stopped prix-moyens series for staple items")
    st, ct, b, fu, dt = fetch("https://bdm.insee.fr/series/sdmx/data/IPC-PM-2015?lastNObservations=1", timeout=90)
    root = ET.fromstring(b)
    ser = [el for el in root.iter() if el.tag.split("}")[-1] == "Series"]
    fr = ["oeuf", "œuf", "lait", "sucre", "riz", "farine", "poulet", "huile", "pain", "beurre", "pomme", "banane", "tomate", "porc", "boeuf", "bœuf"]
    for s in ser:
        if s.get("FREQ") != "M" or s.get("SERIE_ARRETEE") != "TRUE":
            continue
        t = (s.get("TITLE_FR") or "").lower()
        if any(k in t for k in fr):
            obs = [x for x in s if x.tag.split("}")[-1] == "Obs"]
            o(f"     {s.get('IDBANK')} | {s.get('TITLE_FR')[:110]} | last {obs[-1].get('TIME_PERIOD') if obs else None}")
    o.show("datastructure via api.insee.fr", "https://api.insee.fr/series/BDM/V1/datastructure/FR1/IPC-PM-2015", n=200, timeout=40)
    return o


# ---------------------------------------------------------------- Japan round 2
def japan2():
    o = Out("JAPAN2 stat.go.jp zuhyou xlsx + e-Stat datalist")
    st, ct, b, fu, dt = fetch("https://www.stat.go.jp/data/kouri/doukou/3.html")
    h = txt(b)
    for fn in ("202609.xlsx", "202608.xlsx", "kubu_chouki.xls", "shinkyu.xlsx"):
        i = h.find(fn)
        if i >= 0:
            o(f"   context {fn}:", strip(h[max(0, i - 700): i + 60])[-500:])
    allx = re.findall(r'href="(/data/kouri/doukou/zuhyou/[^"]+)"', h)
    o("   all zuhyou files:", len(allx), sorted(set(allx))[-30:])
    for fn in ("202609.xlsx", "202608.xlsx", "kubu_chouki.xls"):
        st, ct, b, fu = o.show("zuhyou", "https://www.stat.go.jp/data/kouri/doukou/zuhyou/" + fn, n=0, timeout=90)
        if st != 200:
            continue
        try:
            rows = xl_rows(b, fn, limit_sheets=2, max_rows=1500)
            sheets = Counter(s for s, _ in rows)
            o("   sheets/rows:", dict(sheets))
            for s, r in rows[:12]:
                o("     top:", s, "|", compact(r))
            shown = 0
            for s, r in rows:
                line = compact(r, 18)
                if any(k in line for k in JP_KEYS):
                    o("     hit:", s, "|", line)
                    shown += 1
                    if shown > 30:
                        break
        except Exception as e:  # noqa: BLE001
            o("   xl parse fail", type(e).__name__, e)
    st, ct, b, fu = o.show("e-Stat datalist", "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00200571&tstat=000000680001&cycle=1&tclass1val=0", n=0, timeout=60)
    h = txt(b)
    ids = []
    for m in re.finditer(r"statInfId=(\d{12})", h):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    o("   statInfIds:", len(ids), ids[:10])
    for m in list(re.finditer(r'tclass\d=\d+[^"]*"[^>]*>([^<]{2,80})<', h))[:20]:
        o("     drill:", m.group(0)[:160])
    return o


# ---------------------------------------------------------------- FAO round 2
def fao2():
    o = Out("FAO2 FPMA tool JS discovery")
    base = "https://fpma.fao.org/giews/fpmat4/global/"
    st, ct, b, fu = o.show("FPMA html", base, n=0)
    h = txt(b)
    scripts = re.findall(r'src="([^"]+\.js)"', h)
    o("   scripts:", scripts)
    urls = Counter()
    ctx = []
    for s in scripts:
        st2, ct2, js, fu2, dt2 = fetch(urllib.parse.urljoin(base, s), timeout=45)
        js = txt(js)
        o("   js", s, st2, len(js))
        for m in re.finditer(r"""["'`]((?:https?://|/)[^"'`\s]{3,200})["'`]""", js):
            v = m.group(1)
            if any(k in v.lower() for k in ("api", "fpma", "giews", "price", "serie", "v4", "v1")):
                urls[v] += 1
        for m in re.finditer(r"(api/v\d|price_module|apiUrl|baseUrl|environment)", js):
            ctx.append(js[max(0, m.start() - 150): m.end() + 200].replace("\n", " "))
    o("   url-like strings:", list(urls)[:100])
    for c in ctx[:30]:
        o("     ctx:", c)
    return o


# ---------------------------------------------------------------- Mexico round 2
def mexico2():
    o = Out("MEXICO2 PROFECO QQP file layout + INEGI preciospromedio form")
    st, ct, b, fu = o.show("CKAN package_show 2026", "https://www.datos.gob.mx/api/3/action/package_show?id=programa_quien_es_quien_precios_2026", n=0)
    try:
        p = json.loads(b)["result"]
        o("   org:", (p.get("organization") or {}).get("title"), "| license:", p.get("license_title"), "| modified:", p.get("metadata_modified"))
        o("   notes:", strip(p.get("notes") or "")[:600])
        res = p.get("resources", [])
        o("   n resources:", len(res))
        for r in res[:40]:
            o("     ", r.get("name"), "|", r.get("format"), "|", r.get("url"), "|", (r.get("description") or "")[:80])
        url = res[0]["url"] if res else None
    except Exception as e:  # noqa: BLE001
        o("   fail", e)
        url = None
    if url:
        st, ct, b, fu = o.show("QQP csv first 64KB", url, n=0, headers={"Range": "bytes=0-65535"}, timeout=60)
        t = txt(b)
        lines = t.splitlines()
        o("   first lines:")
        for ln in lines[:8]:
            o("     ", ln[:300])
        hits = [ln for ln in lines if re.search(r"HUEVO|LECHE|TORTILLA|ARROZ|FRIJOL|POLLO|AZUCAR|ACEITE|PAN ", ln, flags=re.I)]
        o("   staple hits:", len(hits))
        for ln in hits[:12]:
            o("     ", ln[:300])
    st, ct, b, fu = o.show("INEGI preciospromedio", "https://www.inegi.org.mx/app/preciospromedio/", n=0)
    h = txt(b)
    o("   forms:", re.findall(r"<form[^>]*>", h)[:3])
    o("   selects:", re.findall(r'<select[^>]*(?:id|name)="([^"]+)"', h)[:20])
    o("   options:", re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', h)[:60])
    o("   inputs:", re.findall(r'<input[^>]*name="([^"]+)"', h)[:30])
    o("   text:", strip(re.sub(r"<script.*?</script>", " ", h, flags=re.S))[:1500])
    return o


# ---------------------------------------------------------------- misc round 2
def misc2():
    o = Out("MISC2 Germany GENESIS new host, India captcha, Korea retry, Brazil DIEESE form, ABS")
    o.show("GENESIS new host find", "https://genesis.destatis.de/genesisWS/rest/2020/find/find",
           n=1200, data=urllib.parse.urlencode({"term": "Durchschnittspreise", "category": "tables", "pagelength": "20", "language": "de"}).encode(),
           headers={"username": "GAST", "password": "GAST", "Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
    st, ct, b, fu = o.show("fcainfoweb", "https://fcainfoweb.nic.in/reports/report_menu_web.aspx", n=0)
    h = txt(b)
    i = h.lower().find("captcha")
    o("   captcha ctx:", strip(h[max(0, i - 400): i + 400]) if i >= 0 else None)
    o.show("data.gov.in home", "https://www.data.gov.in/", n=120)
    o.show("KAMIS http retry", "http://www.kamis.or.kr/service/price/xml.do?action=dailySalesList&p_cert_key=111&p_cert_id=222&p_returntype=json", n=500, timeout=60)
    o.show("KAMIS home", "https://www.kamis.or.kr/customer/main/main.do", n=120, timeout=60)
    st, ct, b, fu = o.show("DIEESE cesta", "https://www.dieese.org.br/cesta/", n=0, timeout=40)
    h = txt(b)
    o("   forms:", re.findall(r"<form[^>]*>", h)[:4])
    o("   inputs:", re.findall(r'<input[^>]*>', h)[:20])
    o("   selects:", re.findall(r'<select[^>]*>', h)[:8])
    o("   scripts:", re.findall(r'<script[^>]*src="([^"]+)"', h)[:10])
    o("   inline js:", [strip(x)[:300] for x in re.findall(r"<script[^>]*>(.*?)</script>", h, flags=re.S) if x.strip()][:4])
    for u in ("https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/average-retail-prices-selected-items-eight-capital-cities",
              "https://www.abs.gov.au/ausstats/abs@.nsf/mf/6403.0.55.001"):
        st, ct, b, fu = o.show("ABS avg retail prices", u, n=0, timeout=40)
        h = txt(b)
        o("   title:", title_of(h))
        for m in re.finditer(r"(ceased|discontinu|final issue|last issue|no longer)[^<]{0,200}", h, flags=re.I):
            o("     ctx:", strip(m.group(0))[:220])
            break
    return o


# ---------------------------------------------------------------- extras round 2
def extras2():
    o = Out("EXTRAS2 NZ release page, CSO latest, SingStat monthly, StatsSA zip, Malaysia premise")
    st, ct, b, fu = o.show("StatsNZ SPI release", "https://www.stats.govt.nz/information-releases/selected-price-indexes-august-2026/", n=0)
    h = txt(b)
    o("   title:", title_of(h))
    csvs = o.links(h, r'href="[^"]+\.(?:csv|xlsx|zip)"', n=10)
    for c in csvs[:3]:
        if "csv" in c.lower():
            u = urllib.parse.urljoin("https://www.stats.govt.nz/", c[6:-1])
            st, ct, b, fu = o.show("NZ csv", u, n=0, timeout=120)
            try:
                rows = list(csv.DictReader(io.StringIO(txt(b))))
                o("   rows", len(rows), "cols", list(rows[0].keys()))
                refs = Counter((r.get("Series_reference") or "")[:8] for r in rows)
                o("   series prefixes:", refs.most_common(10))
                ap = [r for r in rows if (r.get("Series_reference") or "").startswith("CPIM.SAP")]
                if ap:
                    lat = max(r["Period"] for r in ap)
                    o("   CPIM.SAP latest", lat, "n series", len({r["Series_reference"] for r in ap}))
                    for r in ap:
                        if r["Period"] == lat and any(k in (r.get("Series_title_1") or "").lower() for k in KEYS):
                            o("     ", r["Series_reference"], "|", r.get("Series_title_1"), "|", r.get("Data_value"), r.get("UNITS"))
            except Exception as e:  # noqa: BLE001
                o("   nz csv fail", e)
            break
    st, ct, b, fu = o.show("CSO CPM12", "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/CPM12/JSON-stat/2.0/en", n=0, timeout=60)
    try:
        j = json.loads(b)
        tdim = j["dimension"]["TLIST(M1)"]["category"]
        tl = list(tdim["label"].values())
        idim = j["dimension"]["C02363V03422"]["category"]
        il = list(idim["label"].values())
        vals = j["value"]
        nt, ni = len(tl), len(il)
        o("   months", nt, "last", tl[-1], "| items", ni, "| source note:", strip(str(j.get("note", ""))[:400]))
        for k in range(ni):
            v = vals[(nt - 1) * ni + k] if isinstance(vals, list) else vals.get(str((nt - 1) * ni + k))
            if any(x in il[k].lower() for x in KEYS):
                o("     ", il[k], "|", tl[-1], v)
    except Exception as e:  # noqa: BLE001
        o("   cso fail", type(e).__name__, e)
    st, ct, b, fu = o.show("SingStat monthly", "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213761?limit=300&sortBy=key%20desc", n=0, timeout=60)
    try:
        dat = json.loads(b).get("Data", {})
        o("   title:", dat.get("title"), "| lastUpdated:", dat.get("dataLastUpdated"), "| source:", dat.get("datasource"), "| footnote:", strip(str(dat.get("footnote")))[:300])
        for row in dat.get("row", [])[:70]:
            cols = row.get("columns", [])
            keys_sorted = sorted(cols, key=lambda c: c.get("key"))
            o("     ", row.get("rowText"), "|", keys_sorted[-1] if keys_sorted else None, "| n", len(cols))
    except Exception as e:  # noqa: BLE001
        o("   singstat fail", e)
    u = "https://www.statssa.gov.za/timeseriesdata/Excel/P0141%20-%20CPI%20Average%20Prices%20All%20urban%20(202608).zip"
    st, ct, b, fu = o.show("StatsSA zip", u, n=0, timeout=90)
    try:
        z = zipfile.ZipFile(io.BytesIO(b))
        o("   zip members:", z.namelist())
        nm = z.namelist()[0]
        rows = xl_rows(z.read(nm), nm, limit_sheets=1, max_rows=600)
        for s, r in rows[:6]:
            o("     top:", compact(r, 20))
        o("   n rows", len(rows))
        sh = 0
        for s, r in rows:
            line = compact(r, 8)
            if any(k in line.lower() for k in KEYS):
                vals = [c for c in r if c not in (None, "")]
                o("     hit:", line[:160], "| last vals:", vals[-3:])
                sh += 1
                if sh > 40:
                    break
    except Exception as e:  # noqa: BLE001
        o("   statssa fail", type(e).__name__, e)
    for f in ("lookup_premise.csv",):
        st, ct, b, fu = o.show("Malaysia " + f, "https://storage.data.gov.my/pricecatcher/" + f, n=0)
        lines = txt(b).splitlines()
        o("   header:", lines[:1], "n", len(lines))
        try:
            rd = list(csv.DictReader(io.StringIO(txt(b))))
            o("   premise_type:", Counter(r.get("premise_type") for r in rd).most_common(12))
        except Exception as e:  # noqa: BLE001
            o("   fail", e)
    try:
        import pyarrow.parquet as pq
        st, ct, b, fu, dt = fetch("https://storage.data.gov.my/pricecatcher/pricecatcher_2026-08.parquet", timeout=90)
        t = pq.read_table(io.BytesIO(b)).to_pydict()
        st2, ct2, b2, fu2, dt2 = fetch("https://storage.data.gov.my/pricecatcher/lookup_item.csv")
        lk = {r["item_code"]: r for r in csv.DictReader(io.StringIO(txt(b2)))}
        by = defaultdict(list)
        for ic, pr in zip(t["item_code"], t["price"]):
            by[str(ic)].append(pr)
        for code in ("1", "2", "118", "1109", "224", "272", "904", "992", "917", "918", "114", "160", "18", "1370", "1381"):
            ps = by.get(code)
            if ps:
                o("     MY", code, lk.get(code, {}).get("item"), lk.get(code, {}).get("unit"), "| n", len(ps), "| median", round(statistics.median(ps), 2))
        sug = [c for c, r in lk.items() if "GULA" in r["item"].upper()][:6]
        for c in sug:
            ps = by.get(c)
            o("     MY sugar", c, lk[c]["item"], lk[c]["unit"], "| n", len(ps) if ps else 0, "| median", round(statistics.median(ps), 2) if ps else None)
    except Exception as e:  # noqa: BLE001
        o("   MY parquet fail", type(e).__name__, e)
    o.show("data.gov.my catalogue pricecatcher", "https://api.data.gov.my/data-catalogue?id=pricecatcher&limit=2", n=300)
    return o


if __name__ == "__main__":
    fns = [uk2, france2, japan2, fao2, mexico2, misc2, extras2]
    with ThreadPoolExecutor(max_workers=len(fns)) as ex:
        futs = [ex.submit(f) for f in fns]
        for f, fu in zip(fns, futs):
            try:
                out = fu.result(timeout=900)
                print("\n".join(out.lines), flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"\n######## {f.__name__} CRASHED {type(e).__name__}: {e}", flush=True)
