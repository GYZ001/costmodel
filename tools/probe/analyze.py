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


# ---------------------------------------------------------------- Canada
def canada():
    o = Out("CANADA StatCan 18-10-0245-01")
    o.show("WDS getFullTableDownloadCSV", "https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/18100245/en", n=250)
    st, ct, b, fu = o.show("WDS getCubeMetadata POST", "https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata",
                           n=0, data=json.dumps([{"productId": 18100245}]).encode(), headers={"Content-Type": "application/json"})
    try:
        m = json.loads(b)[0]["object"]
        o("   meta:", {k: m.get(k) for k in ("cubeTitleEn", "cubeStartDate", "cubeEndDate", "releaseTime", "frequencyCode", "nbSeriesCube")})
        for d in m.get("dimension", []):
            mem = d.get("member", [])
            o(f"   dim {d.get('dimensionNameEn')}: {len(mem)} members; first:", [x.get("memberNameEn") for x in mem[:16]])
        fn = m.get("footnote", [])
        o("   footnotes:", len(fn))
        for f in fn[:6]:
            o("     -", strip(f.get("footnotesEn", ""))[:300])
    except Exception as e:  # noqa: BLE001
        o("   meta parse failed", e)
    st, ct, b, fu = o.show("full zip", "https://www150.statcan.gc.ca/n1/tbl/csv/18100245-eng.zip", n=0, timeout=90)
    try:
        z = zipfile.ZipFile(io.BytesIO(b))
        o("   zip members:", z.namelist())
        rows = list(csv.DictReader(io.StringIO(z.read("18100245.csv").decode("utf-8-sig"))))
        geos = Counter(r["GEO"] for r in rows)
        o("   GEO values:", dict(geos))
        lat = max(r["REF_DATE"] for r in rows)
        o("   latest REF_DATE:", lat, "| min:", min(r["REF_DATE"] for r in rows))
        o("   UOM values:", Counter(r["UOM"] for r in rows).most_common(6))
        o("   STATUS values:", Counter(r["STATUS"] for r in rows).most_common(6), "SYMBOL:", Counter(r["SYMBOL"] for r in rows).most_common(4))
        latest_by_geo = defaultdict(int)
        for r in rows:
            if r["REF_DATE"] == lat and r["VALUE"]:
                latest_by_geo[r["GEO"]] += 1
        o("   #products with value in latest month by GEO:", dict(latest_by_geo))
        can = [r for r in rows if r["GEO"] == "Canada" and r["REF_DATE"] == lat]
        o("   n products Canada latest:", len(can))
        vecs = {}
        for r in can:
            pl = r["Products"].lower()
            if any(k in pl for k in KEYS):
                o(f"     {r['VECTOR']} | {r['Products']} | {r['VALUE']} {r['UOM']}")
                vecs[r["Products"]] = r["VECTOR"]
        meta = z.read("18100245_MetaData.csv").decode("utf-8-sig", "replace")
        idx = meta.find("Footnote")
        o("   metadata footnote block:", strip(meta[idx: idx + 1500]) if idx >= 0 else meta[:600])
        pick = [v for p, v in vecs.items() if p.startswith("Eggs") or p.startswith("White bread")][:2]
        if pick:
            body = json.dumps([{"vectorId": int(v[1:]), "latestN": 3} for v in pick]).encode()
            st, ct, b2, fu = o.show("WDS getDataFromVectorsAndLatestNPeriods", "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods",
                                    n=0, data=body, headers={"Content-Type": "application/json"})
            try:
                for obj in json.loads(b2):
                    ob = obj["object"]
                    o("     vec", ob["vectorId"], [(p["refPer"], p["value"], p.get("releaseTime")) for p in ob["vectorDataPoint"]])
            except Exception as e:  # noqa: BLE001
                o("     parse fail", e, txt(b2[:300]))
    except Exception as e:  # noqa: BLE001
        o("   zip parse failed", type(e).__name__, e)
    return o


# ---------------------------------------------------------------- France
def france():
    o = Out("FRANCE INSEE BDM IPC-PM-2015 (prix moyens)")
    st, ct, b, fu = o.show("BDM lastNObservations=1", "https://bdm.insee.fr/series/sdmx/data/IPC-PM-2015?lastNObservations=1", n=0, timeout=90)
    try:
        root = ET.fromstring(b)
        ser = [el for el in root.iter() if el.tag.split("}")[-1] == "Series"]
        o("   total series:", len(ser))
        o("   by (FREQ, SERIE_ARRETEE, REF_AREA):", Counter((s.get("FREQ"), s.get("SERIE_ARRETEE"), s.get("REF_AREA")) for s in ser).most_common(12))
        o("   attribute keys:", sorted(ser[0].attrib.keys()) if ser else None)
        act = [s for s in ser if s.get("SERIE_ARRETEE") == "FALSE" and s.get("FREQ") == "M"]
        o("   active monthly series:", len(act), "areas:", Counter(s.get("REF_AREA") for s in act))
        lastp = Counter()
        egg = None
        for s in act:
            obs = [x for x in s if x.tag.split("}")[-1] == "Obs"]
            p = obs[-1].get("TIME_PERIOD") if obs else None
            v = obs[-1].get("OBS_VALUE") if obs else None
            lastp[p] += 1
            if s.get("REF_AREA") == "FM":
                o(f"     {s.get('IDBANK')} | {s.get('PRIX_CONSO')} | {(s.get('TITLE_EN') or '')[:120]} | {p} {v} {s.get('UNIT_MEASURE')} | upd {s.get('LAST_UPDATE')}")
            if egg is None and "egg" in (s.get("TITLE_EN") or "").lower():
                egg = s.get("IDBANK")
        o("   last-period histogram (active monthly):", lastp.most_common(6))
        if egg:
            st, ct, b2, fu = o.show("BDM SERIES_BDM single idbank", f"https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/{egg}?startPeriod=2024-01", n=0)
            obs = re.findall(r'TIME_PERIOD="([^"]+)" OBS_VALUE="([^"]+)"', txt(b2))
            o("     obs:", obs[:3], "...", obs[-3:])
    except Exception as e:  # noqa: BLE001
        o("   parse failed", type(e).__name__, e, txt(b[:300]))
    o.show("api.insee.fr BDM V1", "https://api.insee.fr/series/BDM/V1/data/IPC-PM-2015?lastNObservations=1", n=250)
    o.show("api.insee.fr BDM (no V1)", "https://api.insee.fr/series/BDM/data/IPC-PM-2015?lastNObservations=1", n=250)
    o.show("BDM datastructure", "https://bdm.insee.fr/series/sdmx/datastructure/FR1/IPC-PM-2015", n=200)
    return o


# ---------------------------------------------------------------- UK
def uk():
    o = Out("UK ONS price quotes / item indices / MM23 avg prices / shopping prices tool")
    base = "https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/consumerpriceindicescpiandretailpricesindexrpiitemindicesandpricequotes"
    st, ct, b, fu = o.show("landing", base, n=0)
    h = txt(b)
    o("   title:", title_of(h))
    o.links(h, r'/file\?uri=[^"\s]+', n=12)
    st, ct, b, fu = o.show("landing /data json", base + "/data", n=0)
    pq_url = None
    try:
        j = json.loads(b)
        o("   keys:", list(j.keys()))
        dss = j.get("datasets", [])
        o("   datasets:", len(dss), [d.get("uri") for d in dss[:6]])
        for d in dss[:4]:
            st2, ct2, b2, fu2 = fetch("https://www.ons.gov.uk" + d["uri"] + "/data")
            try:
                jj = json.loads(b2)
                files = [x.get("file") for x in jj.get("downloads", [])]
                o("     ", d["uri"], "| release", jj.get("description", {}).get("releaseDate"), "| files", files)
                for f in files:
                    if f and "pricequote" in f.lower() and f.lower().endswith((".csv", ".zip")) and not pq_url:
                        pq_url = "https://www.ons.gov.uk/file?uri=" + d["uri"] + "/" + f
            except Exception as e:  # noqa: BLE001
                o("      sub fail", st2, e, txt(b2[:150]))
    except Exception as e:  # noqa: BLE001
        o("   json fail", e, txt(b[:200]))
    if pq_url:
        st, ct, b, fu = o.show("price quotes file", pq_url, n=0, timeout=120)
        try:
            if b[:2] == b"PK":
                z = zipfile.ZipFile(io.BytesIO(b))
                o("   zip:", z.namelist())
                b = z.read(z.namelist()[0])
            rows = list(csv.DictReader(io.StringIO(txt(b))))
            o("   rows:", len(rows), "cols:", list(rows[0].keys()))
            o("   sample row:", rows[0])
            items = defaultdict(list)
            desc = {}
            for r in rows:
                iid = r.get("ITEM_ID") or r.get("item_id")
                d = r.get("ITEM_DESC") or r.get("item_desc") or ""
                desc[iid] = d
                try:
                    pr = float(r.get("PRICE") or r.get("price"))
                    if pr > 0 and (r.get("VALIDITY") in (None, "3", "4")):
                        items[iid].append(pr)
                except (TypeError, ValueError):
                    pass
            o("   distinct items:", len(desc), "| VALIDITY:", Counter(r.get("VALIDITY") for r in rows).most_common(6))
            n = 0
            for iid, d in sorted(desc.items(), key=lambda x: x[1]):
                if any(k in d.lower() for k in KEYS) and items.get(iid):
                    ps = items[iid]
                    o(f"     {iid} | {d} | n={len(ps)} median={statistics.median(ps):.2f} mean={statistics.mean(ps):.2f}")
                    n += 1
                    if n > 70:
                        break
        except Exception as e:  # noqa: BLE001
            o("   pq parse failed", type(e).__name__, e)
    st, ct, b, fu = o.show("MM23 csv", "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/consumerpriceindices/current/mm23.csv", n=0, timeout=120)
    try:
        rd = list(csv.reader(io.StringIO(txt(b))))
        titles, cdids = rd[0], rd[1]
        av = [(c, t) for c, t in zip(cdids, titles) if "ave price" in t.lower() or "average price" in t.lower()]
        o("   MM23 columns:", len(titles), "| avg-price columns:", len(av))
        for c, t in av[:40]:
            o("     ", c, "|", t)
        o("   last rows first col:", [r[0] for r in rd[-3:]])
    except Exception as e:  # noqa: BLE001
        o("   mm23 parse failed", e)
    for q in ("shopping prices comparison tool", "average prices"):
        st, ct, b, fu = o.show(f"ONS search/data '{q}'", "https://www.ons.gov.uk/search/data?q=" + urllib.parse.quote(q), n=0)
        try:
            j = json.loads(b)
            res = j.get("result", {}).get("results", []) or j.get("results", [])
            for r in res[:10]:
                desc = r.get("description", {})
                o("     ", r.get("type"), "|", desc.get("title"), "|", r.get("uri"), "|", desc.get("releaseDate"))
        except Exception as e:  # noqa: BLE001
            o("   not json", e, txt(b[:200]))
    st, ct, b, fu = o.show("dp search api", "https://api.beta.ons.gov.uk/v1/search?q=shopping%20prices%20comparison%20tool&limit=10", n=0)
    try:
        j = json.loads(b)
        for it in j.get("items", [])[:10]:
            o("     ", it.get("type"), "|", it.get("title"), "|", it.get("uri"), "|", it.get("release_date"))
    except Exception as e:  # noqa: BLE001
        o("   dp search fail", e, txt(b[:200]))
    return o


# ---------------------------------------------------------------- Japan
def japan():
    o = Out("JAPAN Retail Price Survey (小売物価統計調査)")
    for u in ("https://www.stat.go.jp/data/kouri/doukou/index.html", "https://www.stat.go.jp/data/kouri/doukou/3.html",
              "https://www.stat.go.jp/data/kouri/index.html"):
        st, ct, b, fu = o.show("stat.go.jp", u, n=0)
        h = txt(b)
        o("   title:", title_of(h))
        o.links(h, r'href="[^"]+\.(?:xlsx?|csv|zip)"', n=15, label="file links")
        o.links(h, r'href="[^"]*e-stat[^"]*"', n=10, label="e-stat links")
    st, ct, b, fu = o.show("e-Stat file list", "https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200571", n=0, timeout=45)
    h = txt(b)
    o("   title:", title_of(h))
    ids = []
    for m in re.finditer(r"statInfId=(\d{12})", h):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    o("   statInfIds:", len(ids), ids[:15])
    for m in list(re.finditer(r'stat-search/files\?[^"]*tclass\d?=[^"]*', h))[:12]:
        o("     drill:", m.group(0)[:200])
    st, ct, b, fu = o.show("e-Stat API no appId", "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList?statsCode=00200571&limit=3", n=400)
    st, ct, b, fu = o.show("e-Stat database list", "https://www.e-stat.go.jp/stat-search/database?page=1&toukei=00200571", n=0, timeout=45)
    h = txt(b)
    o.links(h, r"statdisp_id=\d+", n=10, label="statdisp ids")
    o.links(h, r'<span class="stat-title-name[^"]*">[^<]+', n=10, label="titles")
    return o


# ---------------------------------------------------------------- Germany
def germany():
    o = Out("GERMANY Destatis GENESIS average prices?")
    o.show("GENESIS find GET GAST", "https://www-genesis.destatis.de/genesisWS/rest/2020/find/find?username=GAST&password=GAST&term=Durchschnittspreise&category=tables&pagelength=20&language=de", n=900)
    o.show("GENESIS find POST GAST", "https://www-genesis.destatis.de/genesisWS/rest/2020/find/find",
           n=900, data=urllib.parse.urlencode({"term": "Durchschnittspreise", "category": "tables", "pagelength": "20", "language": "de"}).encode(),
           headers={"username": "GAST", "password": "GAST", "Content-Type": "application/x-www-form-urlencoded"})
    return o


# ---------------------------------------------------------------- Mexico
def mexico():
    o = Out("MEXICO INEGI precios promedio / PROFECO QQP")
    for u in ("https://www.inegi.org.mx/app/preciospromedio/", "https://www.inegi.org.mx/programas/inpc/2018/",
              "https://datos.profeco.gob.mx/datos_abiertos/qqp.php", "https://www.profeco.gob.mx/precios/canasta/default.aspx"):
        st, ct, b, fu = o.show("page", u, n=0, timeout=40)
        h = txt(b)
        o("   title:", title_of(h))
        o.links(h, r'(?:href|src)="[^"]*(?:\.zip|\.csv|\.xlsx?|precio[^"]*|api[^"]*|datosabiertos[^"]*)"', n=25)
    st, ct, b, fu = o.show("datos.gob.mx CKAN search", "https://www.datos.gob.mx/api/3/action/package_search?q=quien%20es%20quien%20precios&rows=5", n=0)
    try:
        j = json.loads(b)
        for p in j["result"]["results"]:
            o("     pkg", p.get("name"), "|", p.get("title"), "|", p.get("metadata_modified"))
            for r in p.get("resources", [])[:6]:
                o("        res", r.get("format"), r.get("url"))
    except Exception as e:  # noqa: BLE001
        o("   ckan fail", e, txt(b[:200]))
    o.show("INEGI BIE API no token", "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR/628194/es/0700/false/BIE/2.0/notoken?type=json", n=300)
    return o


# ---------------------------------------------------------------- India
def india():
    o = Out("INDIA DoCA Price Monitoring Cell")
    for u in ("https://fcainfoweb.nic.in/reports/report_menu_web.aspx", "https://fcainfoweb.nic.in/pmsver2/reports/report_menu_web.aspx",
              "https://consumeraffairs.nic.in/price-monitoring-cell/price-monitoring-cell", "https://doca.gov.in/price/"):
        st, ct, b, fu = o.show("page", u, n=0, timeout=40)
        h = txt(b)
        o("   title:", title_of(h), "| __VIEWSTATE:", "__VIEWSTATE" in h)
        opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', h)
        o("   options:", opts[:40])
        o("   inputs:", re.findall(r'<input[^>]*name="([^"]+)"', h)[:25])
        o.links(h, r'href="[^"]*(?:report|price|\.pdf|\.xls)[^"]*"', n=20)
    o.show("data.gov.in sample-key mandi", "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070?api-key=579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b&format=json&limit=2", n=700)
    return o


# ---------------------------------------------------------------- Korea
def korea():
    o = Out("KOREA KAMIS / KOSIS / price.go.kr")
    o.show("KAMIS dailySalesList test key", "https://www.kamis.or.kr/service/price/xml.do?action=dailySalesList&p_cert_key=111&p_cert_id=222&p_returntype=json", n=700)
    o.show("KAMIS dailyPriceByCategoryList retail", "https://www.kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList&p_product_cls_code=01&p_country_code=1101&p_regday=2026-09-30&p_convert_kg_yn=N&p_item_category_code=100&p_cert_key=111&p_cert_id=222&p_returntype=json", n=700)
    st, ct, b, fu = o.show("KAMIS openapi list", "https://www.kamis.or.kr/customer/reference/openapi_list.do", n=0)
    h = txt(b)
    o("   title:", title_of(h))
    o.links(h, r"action=[A-Za-z]+", n=30)
    o.show("KOSIS no key", "https://kosis.kr/openapi/statisticsList.do?method=getList&vwCd=MT_ZTITLE&parentListId=&format=json&jsonVD=Y", n=300)
    o.show("price.go.kr", "https://www.price.go.kr/tprice/portal/main/main.do", n=150)
    return o


# ---------------------------------------------------------------- Brazil
def brazil():
    o = Out("BRAZIL DIEESE cesta basica / IBGE")
    for u in ("https://www.dieese.org.br/cesta/", "https://www.dieese.org.br/cesta/produto"):
        st, ct, b, fu = o.show("DIEESE", u, n=0, timeout=40)
        h = txt(b)
        o("   title:", title_of(h))
        o.links(h, r'(?:href|action|src)="[^"]*(?:cesta|xls|csv|export|json)[^"]*"', n=30)
        o("   options:", re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', h)[:40])
    o.show("SIDRA IPCA 7060 food", "https://apisidra.ibge.gov.br/values/t/7060/n1/all/v/63/p/last%201/c315/7170", n=500)
    return o


# ---------------------------------------------------------------- FAO FPMA
def fao():
    o = Out("FAO GIEWS FPMA tool")
    base = "https://fpma.fao.org/giews/fpmat4/global/"
    st, ct, b, fu = o.show("FPMA html", base, n=0)
    h = txt(b)
    scripts = re.findall(r'src="([^"]+\.js)"', h)
    o("   scripts:", scripts)
    urls = Counter()
    ctx = []
    for s in scripts:
        st2, ct2, js, fu2 = fetch(urllib.parse.urljoin(base, s), timeout=45)
        js = txt(js)
        for m in re.finditer(r"""["'`]((?:https?://|/)[^"'`\s]{3,200})["'`]""", js):
            v = m.group(1)
            if any(k in v.lower() for k in ("api", "fpma", "giews", "price", "serie")):
                urls[v] += 1
        for m in re.finditer(r"api/v\d", js):
            ctx.append(js[max(0, m.start() - 120): m.end() + 160].replace("\n", " "))
    o("   url-like strings:", list(urls)[:80])
    for c in ctx[:25]:
        o("     ctx:", c)
    for u in ("https://fpma.fao.org/giews/v4/price_module/api/v1/",
              "https://fpma.fao.org/giews/v4/price_module/api/v1/FpmaSerieDomestic/?country_iso3=IND&page_size=3",
              "https://fpma.fao.org/giews/v4/price_module/api/v1/FpmaSeriesDomestic/?iso3_country_code=IND",
              "https://fpma.fao.org/giews/fpmat4/api/v1/"):
        o.show("guess", u, n=400)
    for iso in ("india", "mexico", "brazil", "china"):
        st, ct, b, fu = o.show(f"HDX WFP {iso}", f"https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-{iso}", n=0)
        try:
            r = json.loads(b)["result"]
            o("     ", r.get("title"), "| modified", r.get("metadata_modified"), "|", [x.get("url") for x in r.get("resources", [])][:3])
        except Exception as e:  # noqa: BLE001
            o("     fail", e, txt(b[:150]))
    return o


# ---------------------------------------------------------------- Australia
def australia():
    o = Out("AUSTRALIA ABS")
    st, ct, b, fu = o.show("ABS dataflows", "https://data.api.abs.gov.au/rest/dataflow/ABS?detail=allstubs", n=0, timeout=60)
    h = txt(b)
    flows = re.findall(r'<structure:Dataflow[^>]*id="([^"]+)"[^>]*>.*?<common:Name xml:lang="en">([^<]+)</common:Name>', h, flags=re.S)
    if not flows:
        flows = re.findall(r'id="([^"]+)"[^>]*>\s*<com(?:mon)?:Name[^>]*>([^<]+)<', h)
    o("   n flows:", len(flows))
    for i, nm in flows:
        if re.search(r"price|retail", nm, flags=re.I):
            o("     ", i, "|", nm)
    return o


# ---------------------------------------------------------------- extras
def extras():
    o = Out("EXTRA candidates: NZ, Ireland, Singapore, Malaysia, South Africa, Russia")
    st, ct, b, fu = o.show("StatsNZ csv list", "https://www.stats.govt.nz/large-datasets/csv-files-for-download/", n=0)
    h = txt(b)
    sp = o.links(h, r'href="[^"]*selected-price-index[^"]*\.csv"', n=5)
    if sp:
        u = urllib.parse.urljoin("https://www.stats.govt.nz/", sp[0][6:-1])
        st, ct, b, fu = o.show("StatsNZ SPI csv", u, n=0, timeout=120)
        try:
            rows = list(csv.DictReader(io.StringIO(txt(b))))
            o("   rows", len(rows), "cols", list(rows[0].keys()))
            ap = [r for r in rows if (r.get("Series_reference") or "").startswith("CPIM.SAP")]
            lat = max(r["Period"] for r in ap) if ap else None
            o("   CPIM.SAP rows", len(ap), "latest", lat, "distinct", len({r["Series_reference"] for r in ap}))
            for r in ap:
                if r["Period"] == lat and any(k in (r.get("Series_title_1") or "").lower() for k in KEYS):
                    o("     ", r["Series_reference"], "|", r.get("Series_title_1"), "|", r.get("Data_value"), r.get("UNITS"))
        except Exception as e:  # noqa: BLE001
            o("   nz parse fail", e)
    st, ct, b, fu = o.show("CSO Ireland CPM12", "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/CPM12/JSON-stat/2.0/en", n=0, timeout=60)
    try:
        j = json.loads(b)
        o("   label:", j.get("label"), "| updated:", j.get("updated"), "| ids:", j.get("id"), "| size:", j.get("size"))
        for d in j.get("id", []):
            lab = j["dimension"][d]["category"].get("label", {})
            o(f"   dim {d} ({j['dimension'][d].get('label')}):", list(lab.values())[:60] if len(lab) < 400 else (list(lab.values())[:5], "...", list(lab.values())[-5:]))
    except Exception as e:  # noqa: BLE001
        o("   cso fail", e, txt(b[:200]))
    st, ct, b, fu = o.show("SingStat search", "https://tablebuilder.singstat.gov.sg/api/table/resourceid?keyword=average%20retail%20prices&searchOption=all", n=0)
    try:
        j = json.loads(b)
        recs = j.get("Data", {}).get("records", [])
        for r in recs[:10]:
            o("     ", r.get("id"), "|", r.get("title"), "|", r.get("frequency"))
        if recs:
            st2, ct2, b2, fu2 = o.show("SingStat tabledata", f"https://tablebuilder.singstat.gov.sg/api/table/tabledata/{recs[0]['id']}?limit=200", n=0)
            jj = json.loads(b2)
            dat = jj.get("Data", {})
            o("     title:", dat.get("title"), "| dataLastUpdated:", dat.get("dataLastUpdated"))
            for row in dat.get("row", [])[:60]:
                cols = row.get("columns", [])
                o("       ", row.get("rowText"), "|", row.get("uoM"), "|", cols[-1] if cols else None)
    except Exception as e:  # noqa: BLE001
        o("   singstat fail", e, txt(b[:200]))
    for u in ("https://storage.data.gov.my/pricecatcher/lookup_item.parquet", "https://storage.data.gov.my/pricecatcher/lookup_item.csv",
              "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-09.parquet", "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-08.parquet"):
        st, ct, b, fu = o.show("Malaysia PriceCatcher", u, n=0, timeout=90)
        if st == 200 and u.endswith("lookup_item.csv"):
            lines = txt(b).splitlines()
            o("   header:", lines[0], "| n:", len(lines))
            for ln in lines[1:]:
                if any(k in ln.lower() for k in ("beras", "telur", "susu", "roti", "ayam", "daging", "gula", "minyak", "kentang", "tomato", "pisang", "epal", "tepung")):
                    o("     ", ln[:160])
        if st == 200 and u.endswith(".parquet") and "lookup" not in u:
            try:
                import pyarrow.parquet as pq
                t = pq.read_table(io.BytesIO(b))
                o("   parquet rows", t.num_rows, "schema", t.schema.names, "date range", min(t.column("date").to_pylist()), max(t.column("date").to_pylist()))
            except Exception as e:  # noqa: BLE001
                o("   parquet read fail", e)
    st, ct, b, fu = o.show("StatsSA P0141", "https://www.statssa.gov.za/?page_id=1854&PPN=P0141", n=0, timeout=45)
    h = txt(b)
    o.links(h, r'href="[^"]*(?:[Aa]verage|xlsx?)[^"]*"', n=15)
    o.show("Rosstat price page", "https://rosstat.gov.ru/statistics/price", n=150)
    o.show("fedstat 31448", "https://fedstat.ru/indicator/31448", n=150)
    return o


if __name__ == "__main__":
    fns = [canada, france, uk, japan, germany, mexico, india, korea, brazil, fao, australia, extras]
    with ThreadPoolExecutor(max_workers=len(fns)) as ex:
        futs = [ex.submit(f) for f in fns]
        for f, fu in zip(fns, futs):
            try:
                out = fu.result(timeout=900)
                print("\n".join(out.lines), flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"\n######## {f.__name__} CRASHED {type(e).__name__}: {e}", flush=True)
