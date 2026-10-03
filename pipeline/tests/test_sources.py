from wagegold.sources import mhlw, nbs


def _node(depth: int, ids: list[str], title: str, href: str | None = None) -> str:
    # The markup of one folder of e-Stat's file listing (trimmed from the real page).
    attrs = "".join(f' data-key{n}="tclass{n}" data-value{n}="{i}"' for n, i in enumerate(ids, 1))
    tag, end = ("a", "a") if href else ("div", "div")
    link = f' href="{href}"' if href else ""
    return (f'<{tag}{link} class="stat-search_result-item2-sub" data-key="tstat" data-matter="{depth}" data-value="000001011429"{attrs}>'
            f'<span class="stat-title-has-child" style="margin-left: 0em;"><span>\n {title}\n <span class="stat-pc">[1件]</span></span></span></{end}>')


def test_mhlw_finds_regular_employees_industry_folder_of_each_survey_year():
    q = "/stat-search/files?page=1&amp;toukei=00450091&amp;tstat=000001011429&amp;cycle=0"
    html = "".join([
        _node(1, ["1"], "■令和７年賃金構造基本統計調査"),
        _node(2, ["1", "11"], "一般労働者"),
        _node(3, ["1", "11", "111"], "産業大分類", f"{q}&amp;tclass1=1&amp;tclass2=11&amp;tclass3=111&amp;layout=datalist"),
        _node(2, ["1", "12"], "短時間労働者"),
        _node(3, ["1", "12", "121"], "産業大分類", f"{q}&amp;tclass1=1&amp;tclass2=12&amp;tclass3=121&amp;layout=datalist"),
        _node(1, ["2"], "■令和２年賃金構造基本統計調査"),
        _node(2, ["2", "21"], "一般労働者"),
        _node(3, ["2", "21", "211"], "産業大分類", f"{q}&amp;tclass1=2&amp;tclass2=21&amp;tclass3=211&amp;layout=datalist"),
        # Before the 2020 change of estimation method: not part of the series read.
        _node(1, ["3"], "■令和元年賃金構造基本統計調査"),
        _node(2, ["3", "31"], "一般労働者"),
        _node(3, ["3", "31", "311"], "産業大分類", f"{q}&amp;tclass1=3&amp;tclass2=31&amp;tclass3=311&amp;layout=datalist"),
    ])
    found = mhlw.industry_folders(html)
    assert sorted(found) == [2020, 2025]
    assert "tclass2=11&tclass3=111" in found[2025] and found[2025].startswith("https://www.e-stat.go.jp/")
    assert "tclass3=211" in found[2020]


def test_mhlw_table1_link_checks_the_survey_year():
    row = ('<article class="stat-dataset_list-item"><span class="stat-sp">表番号&nbsp;</span><span>{no}</span>'
           '<span class="stat-sp">調査年月&nbsp;&nbsp;</span> {year}年'
           '<a href="/stat-search/file-download?statInfId={id}&fileKind=4" class="stat-dl_icon" data-file_id="9" data-file_type="EXCEL_Report">')
    page = "<div>" + row.format(no=2, year=2025, id="000000000002") + row.format(no=1, year=2025, id="000000000001")
    assert mhlw.table1(page, 2025).endswith("statInfId=000000000001&fileKind=4")
    try:
        mhlw.table1(page, 2024)
    except ValueError as exc:
        assert "2025" in str(exc)
    else:
        raise AssertionError("a table of another survey year was accepted")


def test_nbs_release_gives_year_previous_year_and_coverage_change():
    # Synthetic figures in the releases' wording.
    html = ("<p>全国城镇非私营单位就业人员年平均工资为20000元。</p>"
            "<p>全国城镇私营单位就业人员年平均工资为 10500 元，比上年增加 500 元，名义增长5.0%，按可比口径计算增长4.0%。</p>")
    assert nbs.parse_release(html, "2031年城镇单位就业人员年平均工资情况", "s") == (2031, 10500, 10000, True)
    html = "<p>全国城镇私营单位就业人员年平均工资为9800元，比上年减少 200 元，名义下降2.0%。</p>"
    assert nbs.parse_release(html, "2030年城镇私营单位就业人员年平均工资9800元", "s") == (2030, 9800, 10000, False)


class _ListingDown:
    """A Fetcher online whose release listings cannot be read: it has only the archive."""
    offline = False

    def __init__(self):
        from wagegold.fetch import Fetcher
        self.archive = Fetcher(offline=True)

    def get_transient(self, url):
        from wagegold.fetch import FetchError
        raise FetchError(f"{url}: unreachable")

    def committed(self, prefix):
        return self.archive.committed(prefix)


def test_listing_failure_leaves_the_archive_in_use_as_offline():
    from wagegold.fetch import Fetcher
    for reader in (nbs, mhlw):
        online, offline = reader.collect(_ListingDown()), reader.collect(Fetcher(offline=True))
        assert online and sorted(map(repr, online)) == sorted(map(repr, offline))


def test_unreadable_release_is_rejected_at_download():
    # parse is the download check: a page or table that cannot be read is never archived.
    for bad in (b"<html><title>2031\xe5\xb9\xb4</title></html>", b"PK\x03\x04 not a workbook"):
        for check in (lambda b: nbs.parse_page(b.decode("utf-8", "replace"), "x"), lambda b: mhlw.parse(b, "x")):
            try:
                check(bad)
            except Exception:  # noqa: BLE001 - any error makes the Fetcher keep the previous snapshot
                continue
            raise AssertionError("an unreadable file passed the download check")
