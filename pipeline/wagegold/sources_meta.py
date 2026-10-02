"""The publishers whose snapshots the dataset was built from, keyed by snapshot-key prefix.
Names, titles, licences and what each is used for are in the website's catalogs
(src.<id>.publisher / .title / .license / .use)."""

SOURCES = [
    {"prefix": "worldbank/CMO-Historical-Data-Monthly", "id": "pinksheet", "landing": "https://www.worldbank.org/en/research/commodity-markets"},
    {"prefix": "imf/", "id": "imf", "landing": "https://data.imf.org/en/datasets/IMF.RES:PCPS"},
    {"prefix": "worldbank/wdi_", "id": "wdi", "landing": "https://data.worldbank.org/"},
    {"prefix": "worldbank/fpn_", "id": "fpn", "landing": "https://api.worldbank.org/v2/sources/88"},
    {"prefix": "worldbank/icp2021_", "id": "icp", "landing": "https://api.worldbank.org/v2/sources/90"},
    {"prefix": "worldbank/countries", "id": "countries", "landing": "https://api.worldbank.org/v2/country"},
    {"prefix": "worldbank/commodity_markets_landing", "id": "cmo_landing", "landing": "https://www.worldbank.org/en/research/commodity-markets"},
    {"prefix": "ilostat/", "id": "ilostat", "landing": "https://ilostat.ilo.org/data/"},
    {"prefix": "oecd/", "id": "oecd", "landing": "https://data-explorer.oecd.org/"},
    {"prefix": "bls/", "id": "bls", "landing": "https://www.bls.gov/developers/"},
    {"prefix": "fred/", "id": "fred", "landing": "https://fred.stlouisfed.org/"},
    {"prefix": "nbs/", "id": "nbs", "landing": "https://www.stats.gov.cn/sj/zxfb/"},
]


def describe(manifest: dict) -> list[dict]:
    out = []
    for src in SOURCES:
        snaps = [dict(key=k, **{f: v[f] for f in ("url", "path", "retrieved_at", "sha256", "bytes", "status", "error")})
                 for k, v in sorted(manifest.items()) if k.startswith(src["prefix"])]
        if snaps:
            out.append({**src, "snapshots": snaps})
    return out
