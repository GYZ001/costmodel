"""Ministry of Health, Labour and Welfare of Japan (厚生労働省): its own release of the
series ILOSTAT republishes for Japan as DA:260 - the Basic Survey on Wage Structure
(賃金構造基本統計調査, June each year): scheduled cash earnings (所定内給与額) of
general employees (一般労働者: all but short-time workers), both sexes, all industries,
private establishments of enterprises with 10 or more employees.

ILOSTAT republishes it with a delay; MHLW's yearly tables (released each March on
e-Stat) continue it (build.UnitGraph._extend, which first checks that the two agree on
the years both have).  The tables are discovered on e-Stat's file listing of the
survey: each survey year's folder "■令和N年賃金構造基本統計調査" → "一般労働者" →
"産業大分類" holds table 1 (学歴、年齢階級別きまって支給する現金給与額、所定内給与額
及び年間賞与その他特別給与額, 産業計・産業別) as an Excel file.  A table is archived
only if it can be read (parse is the download check), so an online run and the offline
rebuild read the same tables.

MHLW changed the survey's estimation method with the 2020 survey: the yearly tables of
earlier surveys use the old method (MHLW re-estimated 2006-2019 with the new one in
separate reference tables).  The series read here is that of the current method's
yearly tables, from the 2020 survey on (FIRST_YEAR).
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin

from ..fetch import Fetcher, FetchError
from ..model import Obs
from .common import excel_format, excel_rows, warn

PUBLISHER = "mhlw"  # catalog keys src.mhlw.*
SERIES = "ext_ilo_monthly_mean@DA:260"  # continues ILOSTAT's ilo_monthly_mean@DA:260 for JPN
BASE = "https://www.e-stat.go.jp"
LIST_URL = BASE + "/stat-search/files?page=1&toukei=00450091&tstat=000001011429"
PREFIX = "mhlw/bsws/"
FIRST_YEAR = 2020  # the survey's current estimation method (see above)
YEAR_TITLE = re.compile(r"^■令和(\d+|元)年賃金構造基本統計調査$")
# A node of the listing's folder tree: its attributes (data-matter = depth,
# data-valueN = the tclassN ids of its path) and the title that follows.
NODE_RE = re.compile(r"<(?:div|a)\b([^>]*\bdata-matter=\"(\d)\"[^>]*)>")
NODE_TITLE_RE = re.compile(r"class=\"stat-title[^\"]*\"[^>]*>\s*<span[^>]*>\s*([^<]+?)\s*<span class=\"stat-pc\">")
ROW_SPLIT = '<article class="stat-dataset_list-item">'
TABLE_NO_RE = re.compile(r"表番号&nbsp;</span>\s*<span>\s*(\d+)\s*</span>")
SURVEY_YEAR_RE = re.compile(r"調査年月&nbsp;&nbsp;</span>\s*(\d{4})年")
EXCEL_RE = re.compile(r"href=\"(/stat-search/file-download\?statInfId=(\d+)&(?:amp;)?fileKind=\d+)\"[^>]*data-file_type=\"EXCEL")


def _text(s: str) -> str:
    return unicodedata.normalize("NFKC", re.sub(r"\s+", " ", s)).strip()


def survey_year(folder_title: str) -> int | None:
    m = YEAR_TITLE.match(_text(folder_title))
    if not m:
        return None
    return 2018 + (1 if m.group(1) == "元" else int(m.group(1)))


def folders(html: str) -> list[tuple[list[str], str, str | None]]:
    """The listing's folder tree: (tclass ids of the path, title, href or None)."""
    out = []
    for m in NODE_RE.finditer(html):
        attrs, depth = m.group(1), int(m.group(2))
        ids = [re.search(rf"data-value{n}=\"(\d+)\"", attrs) for n in range(1, depth + 1)]
        title = NODE_TITLE_RE.search(html, m.end())
        if not all(ids) or not title:
            continue
        href = re.search(r"\bhref=\"([^\"]+)\"", attrs)
        out.append(([i.group(1) for i in ids], _text(title.group(1)), href.group(1).replace("&amp;", "&") if href else None))
    return out


def industry_folders(html: str) -> dict[int, str]:
    """Survey year -> URL of its 一般労働者 / 産業大分類 folder."""
    tree = folders(html)
    title = {tuple(path): t for path, t, _h in tree}
    out: dict[int, str] = {}
    for path, t, href in tree:
        if len(path) != 3 or t != "産業大分類" or not href:
            continue
        year = survey_year(title.get(tuple(path[:1]), ""))
        if year is not None and year >= FIRST_YEAR and title.get(tuple(path[:2])) == "一般労働者":
            out[year] = urljoin(BASE, href)
    return out


def table1(html: str, year: int) -> str:
    """URL of table 1's Excel file on a 産業大分類 folder page."""
    for row in html.split(ROW_SPLIT)[1:]:
        no, yr, xl = TABLE_NO_RE.search(row), SURVEY_YEAR_RE.search(row), EXCEL_RE.search(row)
        if no and no.group(1) == "1" and xl:
            if not yr or int(yr.group(1)) != year:
                raise ValueError(f"table 1 of the {year} folder is for {yr.group(1) if yr else 'no'} survey year")
            return urljoin(BASE, xl.group(1))
    raise ValueError(f"no table 1 Excel file in the {year} folder")


def collect(f: Fetcher) -> list[Obs]:
    if not f.offline:
        fetch_new(f)
    return [Obs(SERIES, "JPN", s.key.rsplit("/", 1)[1][:4], parse(s.read(), s.key), s.key, PUBLISHER)
            for s in f.committed(PREFIX)]


def fetch_new(f: Fetcher) -> None:
    """Fetch every survey year's table listed on e-Stat.  A listing that cannot be read,
    or a year whose table cannot be found, fetched or read, leaves the archived tables in
    use and is reported."""
    try:
        folders = industry_folders(f.get_transient(LIST_URL).decode("utf-8", "replace"))
        if not folders:
            raise ValueError("no survey year folder found on the e-Stat listing")
    except (FetchError, ValueError) as exc:
        warn(f"mhlw: e-Stat listing not read, archived tables used: {exc}")
        return
    for year, folder in sorted(folders.items()):
        key = f"{PREFIX}{year}_ippan_sangyo_t1"
        try:
            url = table1(f.get_transient(folder).decode("utf-8", "replace"), year)
            f.get(key, url, ext=excel_format, check=lambda body, k=key: parse(body, k))
        except (FetchError, ValueError) as exc:
            warn(f"mhlw {year}: {exc}")


def _cell(c: object) -> str:
    return "" if c is None else re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(c)))


HEADER_ROWS = 15  # the table's headings are within its first rows
# The file has a sheet per industry for private establishments (民営事業所) and a few for
# private and public ones together (民営+公営).  ILOSTAT's DA:260 figures are those of
# private establishments: they equal that sheet's 産業計 exactly (2020: 307.7, 2021: 307.4
# thousand yen; private and public together: 308.1 and 308.0).
ESTABLISHMENTS = "民営事業所"


def parse(body: bytes, snapshot: str) -> float:
    """所定内給与額 (yen a month, June) of 産業計 (all industries), private establishments,
    企業規模計(10人以上), 男女計 (both sexes), 学歴計 (all levels of education and ages)."""
    sheets = excel_rows(body)
    found = [hit for name, rows in sheets.items() if (hit := _parse_sheet(name, rows)) is not None]
    if len(found) != 1:
        raise ValueError(f"{snapshot}: {len(found)} sheets for 産業計 (expected 1); sheets {list(sheets)[:8]}")
    return found[0]


def _parse_sheet(name: str, raw: list[list[object]]) -> float | None:
    """Table 1's layout: headings "産業" → its industry and "民公区分" → its establishments;
    a header row with the column labels (所定内給与額 on the row below the others) under
    the enterprise-size blocks, the leftmost being 企業規模計(10人以上); a row of units;
    then rows labelled e.g. "男女計 学歴計", "~19歳", …"""
    cells = [[_cell(c) for c in r] for r in raw]
    head = cells[:HEADER_ROWS]
    if _heading(head, "産業") != "産業計" or _heading(head, "民公区分") != ESTABLISHMENTS:
        return None

    def first_col(label: str) -> tuple[int, int]:
        hits = sorted((j, i) for i, r in enumerate(head) for j, c in enumerate(r) if c == label)
        if not hits:
            raise ValueError(f"sheet {name!r}: no column {label!r}")
        return hits[0]

    size_col, size_row = first_col("企業規模計(10人以上)")
    wage, _ = first_col("所定内給与額")
    nxt = next((j for j, c in enumerate(head[size_row]) if c and j > size_col), len(head[size_row]))
    if not size_col <= wage < nxt:
        raise ValueError(f"sheet {name!r}: 所定内給与額 is not under 企業規模計(10人以上)")
    if not any(len(r) > wage and r[wage] == "千円" for r in head):
        raise ValueError(f"sheet {name!r}: 所定内給与額 is not stated in 千円")
    for i, r in enumerate(cells):
        if "".join(r[:size_col]) == "男女計学歴計":
            w = raw[i][wage]
            if not isinstance(w, (int, float)) or isinstance(w, bool):
                raise ValueError(f"sheet {name!r}, row {i + 1}: non-numeric 所定内給与額 {w!r}")
            return float(w) * 1000
    raise ValueError(f"sheet {name!r}: no 男女計 学歴計 row")


def _heading(head: list[list[str]], label: str) -> str | None:
    """The value next to a heading label (e.g. "産業" → "産業計")."""
    for r in head:
        if label in r:
            return next((c for c in r[r.index(label) + 1:] if c), None)
    return None
