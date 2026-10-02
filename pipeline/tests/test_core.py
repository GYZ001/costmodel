from wagegold import build
from wagegold.config import GRAMS_PER_TROY_OUNCE
from wagegold.model import Obs, Store, annual_mean
from wagegold.sources import nbs


def test_annual_mean_requires_twelve_months():
    s = Store()
    for m in range(1, 12):
        s.add(Obs("x", "WLD", f"2025-{m:02d}", m, "t"))
    assert annual_mean(s.series("x", "WLD"), "2025") is None
    s.add(Obs("x", "WLD", "2025-12", 12, "t"))
    assert annual_mean(s.series("x", "WLD"), "2025") == (6.5, 12)


def test_store_rejects_conflicting_values():
    s = Store()
    s.add(Obs("x", "USA", "2025", 1.0, "a"))
    s.add(Obs("x", "USA", "2025", 1.0, "b"))  # same value from another snapshot is fine
    try:
        s.add(Obs("x", "USA", "2025", 2.0, "c"))
    except ValueError:
        return
    raise AssertionError("conflict not detected")


WAGE_HTML = """<html><title>2025年城镇单位就业人员年平均工资情况 - 国家统计局</title><body>
<p>2025 年，全国城镇非私营单位就业人员年平均工资 129441 元，比上年增加 5331 元，名义增长 <sup>[1]</sup> 4.3% ，扣除价格因素实际增长 4.2% 。</p>
<p>2025 年，全国城镇私营单位就业人员年平均工资 71590 元，比上年增加 2114 元，名义增长 3.0% ，扣除价格因素实际增长 2.9% 。</p>
<p>规模以上企业就业人员年平均工资为 106080 元，其中，中层及以上管理人员 210016 元，专业技术人员 155491 元，办事人员和有关人员 94936 元，社会生产服务和生活服务人员 79857 元，生产制造及有关人员 80739 元。</p>
</body></html>"""


def test_nbs_wage_release():
    obs = {(o.series, o.period): o for o in nbs.parse_release(WAGE_HTML, "2025年城镇单位就业人员年平均工资情况", "nbs/release/202605/t20260515_1")}
    assert obs[("cn_wage_nonprivate", "2025")].value == 129441
    assert obs[("cn_wage_nonprivate__implied_prev", "2024")].value == 124110
    assert obs[("cn_wage_private", "2025")].value == 71590
    assert obs[("cn_wage_large_ent_production", "2025")].value == 80739
    assert "growth_pct=4.3" in obs[("cn_wage_nonprivate", "2025")].note


def test_nbs_hours_month_and_year():
    html = '<meta name="PubDate" content="2026/01/19 10:00"><p>12 月份，全国城镇调查失业率为 5.1% 。全国企业就业人员周平均工作时间为 48.6 小时。</p>'
    obs = nbs.parse_release(html, "2025年国民经济稳中有进", "nbs/release/202601/t20260119_1")
    assert [(o.period, o.value) for o in obs] == [("2025-12", 48.6)]
    html = "<p>2026/09/15 10:00 来源：国家统计局</p><p>8 月份，全国城镇调查失业率为 5.3% ，比上月上升 0.1 个百分点。全国企业就业人员周平均工作时间为 48.2 小时。</p>"
    obs = nbs.parse_release(html, "8月份国民经济运行平稳", "nbs/release/202609/t20260915_1")
    assert [(o.period, o.value) for o in obs] == [("2026-08", 48.2)]


def test_nbs_reposted_release_uses_page_date():
    # Re-posted in Feb 2023 during the site migration; the page keeps its original date.
    html = "<p>2022/03/15 10:00</p><p>2 月份，全国城镇调查失业率为 5.5% 。全国企业就业人员周平均工作时间为 46.7 小时。</p>"
    obs = nbs.parse_release(html, "1-2月份国民经济恢复好于预期", "nbs/release/202302/t20230203_1901402")
    assert [(o.period, o.value) for o in obs] == [("2022-02", 46.7)]


def test_chain_identity():
    gold_usd_g = 3441.5 / GRAMS_PER_TROY_OUNCE
    fx, ppp = 7.19, 3.46
    v = build.WageVariant("k", "l", "mean", "s", None, 60.0, None, "m", [])
    w = build.wage_metrics(v, gold_usd_g * fx, fx, ppp, 12.6)
    pli = ppp / fx
    assert abs(w["hourly_gold_g"] * (gold_usd_g / pli) - w["hourly_ppp"]) < 1e-12
    assert abs(w["minutes_per_cohd_day"] - 12.6 / 60 * 60) < 1e-12


def test_nbs_wage_release_older_wording():
    html = ("<p>2023年，全国城镇非私营单位就业人员年平均工资为120698元，比上年增加6669元，名义增长5.8%，扣除价格因素实际增长5.5%。</p>"
            "<p>2023年，全国城镇私营单位就业人员年平均工资为68340元，比上年增加3103元，名义增长4.8%，扣除价格因素实际增长4.5%。</p>")
    obs = {(o.series, o.period): o.value for o in nbs.parse_release(html, "2023年城镇单位就业人员年平均工资情况", "nbs/release/202405/t20240520_1")}
    assert obs[("cn_wage_nonprivate", "2023")] == 120698
    assert obs[("cn_wage_nonprivate__implied_prev", "2022")] == 114029
    assert obs[("cn_wage_private", "2023")] == 68340


def test_nbs_q3_release_month_from_publication_date():
    html = "<p>2025/10/20 10:00</p><p>9 月份，全国城镇调查失业率为 5.2% 。全国企业就业人员周平均工作时间为 48.5 小时。</p>"
    obs = nbs.parse_release(html, "前三季度经济运行稳中有进", "nbs/release/202510/t20251020_1")
    assert [(o.period, o.value) for o in obs] == [("2025-09", 48.5)]


def test_nbs_half_year_recap_does_not_move_the_month():
    # 2022 H1 release (re-posted in Feb 2023): April is recapped right before the hours sentence, which is June's.
    html = ("<p>2022/07/15 10:00</p><p>上半年，全国城镇调查失业率平均为 5.7% 。4 月份，全国城镇调查失业率为 6.1% ； 5 、 6 月份连续回落，"
            "分别为 5.9% 、 5.5% 。 6 月份，本地户籍人口调查失业率为 5.3% 。全国企业就业人员周平均工作时间为 47.7 小时。</p>")
    obs = nbs.parse_release(html, "有力应对超预期因素影响 国民经济企稳回升", "nbs/release/202302/t20230203_1901513")
    assert [(o.period, o.value) for o in obs] == [("2022-06", 47.7)]


def _raises(html: str, title: str) -> bool:
    try:
        nbs.parse_release(html, title, "nbs/release/x")
    except ValueError:
        return True
    return False


def test_nbs_rejects_inconsistent_month():
    hours = "全国企业就业人员周平均工作时间为 48.5 小时。"
    # Title names a month the publication date does not imply.
    assert _raises(f"<p>2025/10/20 10:00</p><p>8 月份，全国城镇调查失业率为 5.2% 。{hours}</p>", "8月份国民经济运行")
    # Text never mentions the month the publication date implies.
    assert _raises(f"<p>2025/10/20 10:00</p><p>8 月份，全国城镇调查失业率为 5.2% 。{hours}</p>", "前三季度经济运行")


def _yoy(text, month, topic=None):
    return [c for x in nbs.yoy_sentences(text, month, topic) for c in x["yoy"]]


def test_cpi_yoy_sentences_follow_stated_basis():
    # Paragraphs of the archived NBS page for August 2026 (data/raw/nbs/release/202609/
    # t20260909_1965263.html), spacing and soft hyphens as on other NBS pages.
    html = ('<div class="header">导航 价格 同比 1.0%。</div><div class="txt-content">'
            "<p>\u3000\u30002026 年 8 月份，全国居民消费价格同比上涨 0.8% 。其中，城市上涨 0.8% ，农村上涨 0.7% ；"
            "食品价格下降 1.4% ，非食品价格上涨 1.2% ；消费品价格上涨0.8%，服务价格上涨0.8%。"
            "1\u00ad\u00ad—8月平均，全国居民消费价格比上年同期上涨0.9%。</p><p>\u2002</p>"
            "<p>\u3000\u30008月份，全国居民消费价格环比上涨0.4%。其中，城市上涨0.4%，农村上涨0.4%。</p>"
            "<p>\u3000\u3000一、各类商品及服务价格同比变动情况</p>"
            "<p>8月份，食品烟酒及在外餐饮类价格同比下降0.7%，影响CPI（居民消费价格指数）下降约0.21个百分点。"
            "食品中，畜肉类价格下降5.1%，影响CPI下降约0.21个百分点，其中猪肉价格下降11.8%；鲜菜价格下降2.8%，"
            "影响CPI下降约0.05个百分点。</p>"
            "<p>其他七大类价格同比六涨一降。其中，教育文化娱乐、衣着、生活用品及服务价格分别上涨1.4%、1.3%和0.7%；居住价格下降0.3%。</p>"
            "<p>二、各类商品及服务价格环比变动情况</p>"
            "<p>8月份，食品烟酒及在外餐饮类价格环比上涨0.3%。其中，居住、教育文化娱乐、医疗保健价格均持平。</p></div>"
            '<div class="mobile-content">2026 年 8 月份，全国居民消费价格同比上涨 0.8% 。</div>')
    got = nbs.yoy_sentences(nbs.body_text(html), 8)
    assert [c for x in got for c in x["yoy"]] == [
        "全国居民消费价格同比上涨0.8%", "城市上涨0.8%", "农村上涨0.7%",
        "食品价格下降1.4%", "非食品价格上涨1.2%", "消费品价格上涨0.8%", "服务价格上涨0.8%",
        "食品烟酒及在外餐饮类价格同比下降0.7%",
        "畜肉类价格下降5.1%", "其中猪肉价格下降11.8%", "鲜菜价格下降2.8%",
        "教育文化娱乐、衣着、生活用品及服务价格分别上涨1.4%、1.3%和0.7%", "居住价格下降0.3%",
    ]
    # the heading paragraph is not glued to the sentence after it
    assert next(x["text"] for x in got if "食品烟酒" in x["text"]).startswith("8月份，食品烟酒")


def test_cumulative_period_is_inherited():
    # 2026-07 economy release: the CPI paragraph opens with January-July figures.
    text = ("七、市场价格温和上涨，7月份涨幅有所回落1—7月份，全国居民消费价格（CPI）同比上涨0.9%。"
            "分类别看，食品烟酒及在外餐饮价格同比下降0.2%，衣着价格上涨1.6%。"
            "在食品烟酒及在外餐饮价格中，猪肉价格下降13.4%，粮食价格下降0.3%。"
            "7月份，全国居民消费价格同比上涨0.5%，环比下降0.1%。其中，7月份核心CPI同比上涨0.9%。")
    assert _yoy(text, 7, topic="居民消费价格") == ["全国居民消费价格同比上涨0.5%", "7月份核心CPI同比上涨0.9%"]
    # Only the clause that names February is February's.
    text = "1—2月份，全国居民消费价格同比持平。扣除食品和能源价格后的核心CPI同比上涨0.8%，其中2月份同比上涨1.2%。"
    assert _yoy(text, 2, topic="居民消费价格") == ["其中2月份同比上涨1.2%"]


def test_cpi_other_months_and_unchanged():
    # 2023-02 economy release: January's value is recapped before February's.
    text = "分月看，1月份全国居民消费价格同比上涨2.1%，2月份同比上涨1.0%。"
    assert _yoy(text, 2, topic="居民消费价格") == ["2月份同比上涨1.0%"]
    # 2022-06: a two-month recap is not the reference month; "上月为…" is an aside.
    text = "4、5月份居民消费价格同比均上涨2.1%。6月份，全国居民消费价格同比上涨2.5%，上月为上涨2.1%，城市上涨2.5%。"
    assert _yoy(text, 6, topic="居民消费价格") == ["全国居民消费价格同比上涨2.5%", "城市上涨2.5%"]
    # 2023-06 CPI release: unchanged is a year-on-year change of 0.
    text = "2023年6月份，全国居民消费价格同比持平。其中，城市持平，农村下降0.2%。"
    assert _yoy(text, 6) == ["全国居民消费价格同比持平", "城市持平", "农村下降0.2%"]


def test_cpi_headings_tables_and_rate_comparisons_are_not_changes():
    # 2025-07 economy release: a bold heading, then the paragraph; "涨幅与上月持平" compares rates.
    text = ("全国城镇调查失业率为5.2%。\n七、居民消费价格同比持平，核心CPI连续回升\n"
            "7月份，全国居民消费价格（CPI）同比持平，涨幅与上月持平；环比上涨0.4%。")
    assert _yoy(text, 7, topic="居民消费价格") == ["全国居民消费价格（CPI）同比持平"]
    # Table cells of the CPI release ("同比涨跌幅（%）") are not prose.
    html = ('<div class="txt-content"><p>2026年8月份，全国居民消费价格同比上涨0.8%。</p>'
            "<table><tr><td>2026年8月份居民消费价格主要数据</td><td>同比涨跌幅</td><td>（%）</td></tr></table></div>")
    assert _yoy(nbs.body_text(html, tables=False), 8) == ["全国居民消费价格同比上涨0.8%"]


def test_nbs_decline_wording():
    html = "<p>2027年，全国城镇私营单位就业人员年平均工资为71000元，比上年减少590元，名义下降0.8%。</p>"
    title = "2027年城镇私营单位就业人员年平均工资71000元"
    obs = {(o.series, o.period): (o.value, o.note) for o in nbs.parse_release(html, title, "nbs/x")}
    assert obs[("cn_wage_private", "2027")] == (71000, "growth_pct=-0.8")
    assert obs[("cn_wage_private__implied_prev", "2026")] == (71590, "")


def test_economy_release_cpi_sentences_stay_in_cpi_paragraph():
    # Wording of the NBS release of 2026-09-15 ("8月份国民经济…"); the heading is its own paragraph.
    text = ("全国企业就业人员周平均工作时间为48.2小时。\n七、居民消费价格温和回升，工业生产者价格同比涨幅扩大\n8月份，"
            "全国居民消费价格（CPI）同比上涨0.8%，涨幅比上月扩大0.3个百分点；环比上涨0.4%。"
            "分类别看，食品烟酒及在外餐饮价格同比下降0.7%，衣着价格上涨1.3%。"
            "在食品烟酒及在外餐饮价格中，猪肉价格下降11.8%，鲜菜价格下降2.8%，粮食价格下降0.6%，鲜果价格下降0.5%。"
            "1—8月份，全国居民消费价格同比上涨0.9%。8月份，全国工业生产者出厂价格同比上涨3.8%。"
            "其中，生活资料价格上涨1.0%。\n八、房地产开发投资同比下降5.0%，新建商品房销售价格同比下降2.0%。")
    got = nbs.yoy_sentences(text, 8, topic="居民消费价格")
    assert [c for x in got for c in x["yoy"]] == [
        "全国居民消费价格（CPI）同比上涨0.8%",
        "食品烟酒及在外餐饮价格同比下降0.7%", "衣着价格上涨1.3%",
        "猪肉价格下降11.8%", "鲜菜价格下降2.8%", "粮食价格下降0.6%", "鲜果价格下降0.5%",
    ]
    assert got[0]["text"].startswith("8月份，全国居民消费价格")


# ---- currency units proven by identities (build.UnitGraph)

DIC = {"note_indicator": {
    "T8:127": "Central tendency measure: Mean", "T8:128": "Central tendency measure: Median",
    "T9:133": "Value type: Nominal values", "T9:131": "Value type: Real values",
    "T30:1": "Currency: XXX - Euro (EUR)", "T30:2": "Currency: XXX - Old unit (OLD)",
    "S4:31": "Geographical coverage: Urban areas only",
}, "note_source": {}, "source": {}}
META = {a: {"is_economy": True, "name_en": a} for a in ("AAA", "BBB")}


def _store(*obs):
    s = Store()
    s.extend(Obs(*o) if isinstance(o, tuple) else o for o in obs)
    return s


def _wdi(area, year, fx, ppp, lcu_unit_fx=None):
    """WDI rows for one economy-year; lcu_unit_fx = the conversion factor in WDI's LCU unit."""
    f = lcu_unit_fx if lcu_unit_fx is not None else fx
    return [("fx_lcu_usd", area, year, fx, "s"), ("ppp_hfce", area, year, ppp, "s"),
            ("gdp_lcu", area, year, f * 1e12, "s"), ("gdp_usd", area, year, 1e12, "s"),
            ("hfce_lcu", area, year, ppp * 500, "s"), ("hfce_intl", area, year, 500.0, "s")]


def test_units_official_rate_in_other_unit_is_not_used():
    # Pre-euro year: the official rate is in the legacy unit (×200), WDI's LCU series in euro.
    s = _store(*_wdi("AAA", "2005", 200.0, 0.6, lcu_unit_fx=1.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2005", 1500.0, "s", "T8:127 T9:133 T30:1"),
               Obs("ilo_monthly_mean_ppp@X:1", "AAA", "2005", 2500.0, "s"))
    u = build.UnitGraph(s, DIC, ["2005"], META)
    g = u.year("AAA", "2005")
    assert not g.linked("F") and g.linked("P") and g.linked("ilo:ilo_monthly_mean@X:1")
    assert u.currency("AAA") == "EUR"
    u.explain("AAA", "2005", True)
    assert any(e["scope"] == "fx" for e in u.log)


def test_units_wage_in_old_currency_is_left_out():
    s = _store(*_wdi("AAA", "2018", 8.0, 3.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2018", 2_000_000.0, "s", "T30:2"),  # 1000× the unit of FX/PPP
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2018", 250.0, "s"))  # ILOSTAT's own (correct) USD figure
    u = build.UnitGraph(s, DIC, ["2018"], META)
    assert not u.year("AAA", "2018").linked("ilo:ilo_monthly_mean@X:1")
    assert build.ilo_variants(s, u, "AAA", "2018", DIC) == []
    u.explain("AAA", "2018", True)
    assert any(e["scope"] == "wage:ilo_monthly_mean" for e in u.log)


def test_units_ilostat_notes_set_concept_and_exclude_real_values():
    s = _store(*_wdi("AAA", "2019", 10.0, 5.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2019", 3800.0, "s", "T8:128 T9:133 S4:31"),
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2019", 380.0, "s"),
               Obs("ilo_hourly_mean@X:2", "AAA", "2019", 20.0, "s", "T8:127 T9:131"),
               Obs("ilo_hourly_mean_usd@X:2", "AAA", "2019", 2.0, "s"))
    u = build.UnitGraph(s, DIC, ["2019"], META)
    vs = build.ilo_variants(s, u, "AAA", "2019", DIC)
    assert [(v.key, v.restricted) for v in vs] == [("ilo_median_monthly", True)]  # median per its note; real-value record dropped
    assert "Urban areas only" in vs[0].caveat


def test_units_oecd_wage_joined_by_its_ppp_identity():
    s = _store(*_wdi("AAA", "2025", 0.9, 0.7),
               Obs("oecd_avg_annual_wage", "AAA", "2025", 50000.0, "s", "EUR"),
               Obs("oecd_avg_annual_wage_q", "AAA", "2025", 50000.0, "s", "EUR 2025"),
               Obs("oecd_avg_annual_wage_q_usdppp", "AAA", "2025", 50000.0 / 0.7, "s", "USD_PPP 2025"),
               # a second economy whose OECD series is in another unit than WDI's LCU series
               *[Obs(*o) for o in _wdi("BBB", "2025", 1.8, 0.39, lcu_unit_fx=0.92)],
               Obs("oecd_avg_annual_wage", "BBB", "2025", 28000.0, "s", "BGN"))
    u = build.UnitGraph(s, DIC, ["2025"], META)
    assert build.oecd_variant(s, u, "AAA", "2025") is not None
    assert build.oecd_variant(s, u, "BBB", "2025") is None


def test_units_physically_impossible_hours_drop_both_records():
    # ILOSTAT ZAF 2017 (same source): median monthly 3500, median hourly 0.102 -> 34,000 hours a month.
    s = _store(*_wdi("AAA", "2017", 13.3, 6.0),
               Obs("ilo_monthly_mean@BA:1", "AAA", "2017", 3500.0, "s", "T8:128 T9:133"),
               Obs("ilo_monthly_mean_usd@BA:1", "AAA", "2017", 263.0, "s"),
               Obs("ilo_hourly_mean@BA:1", "AAA", "2017", 0.102, "s", "T8:128 T9:133"),
               Obs("ilo_hourly_mean_usd@BA:1", "AAA", "2017", 0.0077, "s"))
    u = build.UnitGraph(s, DIC, ["2017"], META)
    assert build.ilo_variants(s, u, "AAA", "2017", DIC) == []


def test_units_wage_matching_both_factors_does_not_join_them():
    # Dollarisation year: WDI's LCU series is in US$, the official rate still in colones (×8.75);
    # ILOSTAT converted its wage with both, so it "agrees" with each - that proves nothing.
    s = _store(*_wdi("AAA", "2000", 8.75, 0.5, lcu_unit_fx=1.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2000", 3000.0, "s", "T8:127 T9:133"),
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2000", 3000.0 / 8.75, "s"),
               Obs("ilo_monthly_mean_ppp@X:1", "AAA", "2000", 3000.0 / 0.5, "s"))
    u = build.UnitGraph(s, DIC, ["2000"], META)
    g = u.year("AAA", "2000")
    assert g.linked("P") and not g.linked("F") and not g.linked("ilo:ilo_monthly_mean@X:1")
    u.explain("AAA", "2000", True)
    assert any("无法确定" in e["detail"] for e in u.log)


def test_units_ppp_proven_by_icp_price_level_and_carried_both_ways():
    # No household-consumption totals in WDI: the PPP is checked in 2021 against ICP's price
    # level (US = 1) × the official rate, and carried to adjacent years that moved < ×1.4.
    rows = []
    for y, fx, ppp in (("2020", 150.0, 140.0), ("2021", 155.0, 155.7), ("2022", 160.0, 171.4), ("2023", 400.0, 205.2)):
        rows += [("fx_lcu_usd", "AAA", y, fx, "s"), ("ppp_hfce", "AAA", y, ppp, "s"),
                 ("gdp_lcu", "AAA", y, fx * 1000, "s"), ("gdp_usd", "AAA", y, 1000.0, "s")]
    s = _store(*rows, ("icp21_pli_wl_hfce", "AAA", "2021", 50.0, "s", "A"),
               ("icp21_pli_wl_hfce", "USA", "2021", 49.8, "s", "United States"))
    u = build.UnitGraph(s, DIC, ["2020", "2021", "2022", "2023"], META)
    assert [u.year("AAA", y).linked("P") for y in ("2020", "2021", "2022", "2023")] == [True, True, True, True]
    s = _store(*rows, ("icp21_pli_wl_hfce", "AAA", "2021", 5.0, "s", "A"),  # PPP 10× the ICP price level
               ("icp21_pli_wl_hfce", "USA", "2021", 49.8, "s", "United States"))
    u = build.UnitGraph(s, DIC, ["2020", "2021", "2022", "2023"], META)
    assert not any(u.year("AAA", y).linked("P") for y in ("2020", "2021", "2022", "2023"))


def test_units_time_check_only_among_same_currency_figures():
    # A monthly figure published in another currency (×100) is left out for its currency,
    # and must not knock out the hourly figure it would contradict.
    s = _store(*_wdi("AAA", "2018", 100.0, 80.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2018", 3000.0, "s", "T8:127 T9:133"),  # in another currency
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2018", 3500.0, "s"),
               Obs("ilo_hourly_mean@X:2", "AAA", "2018", 1800.0, "s", "T8:127 T9:133"),
               Obs("ilo_hourly_mean_usd@X:2", "AAA", "2018", 18.0, "s"),
               Obs("ilo_weekly_hours@X:2", "AAA", "2018", 38.0, "s"))
    u = build.UnitGraph(s, DIC, ["2018"], META)
    assert [v.key for v in build.ilo_variants(s, u, "AAA", "2018", DIC)] == ["ilo_mean_hourly"]
    # Same currency, but the hourly figure is 100× too small against OECD's wage and hours.
    s = _store(*_wdi("AAA", "2018", 100.0, 80.0),
               Obs("ilo_hourly_mean@X:2", "AAA", "2018", 18.0, "s", "T8:127 T9:133"),
               Obs("ilo_hourly_mean_usd@X:2", "AAA", "2018", 0.18, "s"),
               Obs("oecd_avg_annual_wage", "AAA", "2018", 3_600_000.0, "s", "AAD"),
               Obs("oecd_avg_annual_wage_q", "AAA", "2018", 3_600_000.0, "s", "AAD 2018"),
               Obs("oecd_avg_annual_wage_q_usdppp", "AAA", "2018", 45000.0, "s", "USD_PPP 2018"),
               Obs("oecd_usual_weekly_hours_ft", "AAA", "2018", 40.0, "s"))
    u = build.UnitGraph(s, DIC, ["2018"], META)
    assert build.ilo_variants(s, u, "AAA", "2018", DIC) == []
    assert build.oecd_variant(s, u, "AAA", "2018") is not None


def _per_head(area, years, ppp, per_head):
    """Population giving the stated household consumption per head with _wdi's totals."""
    return [("population", area, y, ppp * 500 / v, "s") for y, v in zip(years, per_head)]


def test_units_scale_error_singled_out_by_its_own_series():
    # PRY BX:14043 2020: the hourly figure is 1/192 of its neighbours, the monthly one is in line.
    years = ["2019", "2020", "2021"]
    rows = [r for y in years for r in _wdi("AAA", y, 6000.0, 2500.0)] + _per_head("AAA", years, 2500.0, [100.0, 103.0, 113.0])
    obs = []
    for y, m, h in (("2019", 2_489_188.0, 15079.0), ("2020", 2_505_151.0, 78.482), ("2021", 2_584_029.0, 16570.0)):
        obs += [Obs("ilo_monthly_mean@X:1", "AAA", y, m, "s", "T8:127 T9:133"), Obs("ilo_monthly_mean_usd@X:1", "AAA", y, m / 6000, "s"),
                Obs("ilo_hourly_mean@X:1", "AAA", y, h, "s", "T8:127 T9:133"), Obs("ilo_hourly_mean_usd@X:1", "AAA", y, h / 6000, "s")]
    s = _store(*rows, *obs)
    u = build.UnitGraph(s, DIC, years, META)
    assert [v.key for v in build.ilo_variants(s, u, "AAA", "2020", DIC)] == ["ilo_mean_monthly"]
    assert [v.key for v in build.ilo_variants(s, u, "AAA", "2021", DIC)] == ["ilo_mean_hourly", "ilo_mean_monthly"]


def test_history_breaks_at_level_shift_and_primary_switch_is_marked():
    years = ["2021", "2022", "2023", "2024"]
    rows = [r for y in years for r in _wdi("AAA", y, 1.0, 0.8)] + _per_head("AAA", years, 0.8, [100.0, 105.0, 110.0, 116.0])
    obs = []
    for y, m in zip(years, (1000.0, 1050.0, 1100.0, 1900.0)):  # 2023->2024: ×1.73 against ×1.05
        obs += [Obs("ilo_monthly_mean@X:1", "AAA", y, m, "s", "T8:127 T9:133"), Obs("ilo_monthly_mean_usd@X:1", "AAA", y, m, "s")]
    s = _store(*rows, *obs, Obs("gold_usd_oz", "WLD", "2021-01", 1800.0, "s"))
    u = build.UnitGraph(s, DIC, years, META)
    gold = {"annual": {y: {"usd_g": 60.0} for y in years}}
    meta = {"AAA": {"is_economy": True, "name_en": "A"}}
    pts = build.wage_gold_history(s, gold, meta, DIC, u)["AAA"]["points"]
    assert [p[4] for p in pts] == [False, False, False, True] and "×/÷1.4" in pts[3][5]
    assert "相邻年份的变化超出" in build.ilo_variants(s, u, "AAA", "2024", DIC)[0].caveat
    w = lambda sid, key, notes, label: {"role": None, "mrole": "primary", "series_id": sid, "series_key": key,  # noqa: E731
                                        "notes_sig": notes, "label": label, "source": "x"}
    recs = {"2022": {"wages": [w("A", "A", [], "a")]}, "2023": {"wages": [w("A n1", "A", ["n1"], "a")]},
            "2024": {"wages": [w("B", "B", [], "b")]}}
    build.mark_switches(recs)
    assert recs["2023"]["wages"][0]["mrole_switch"] == {"year": "2022", "label": "a", "source": "x", "kind": "notes",
                                                        "only_before": [], "only_now": ["n1"]}
    assert recs["2024"]["wages"][0]["mrole_switch"]["kind"] == "source"


def test_units_concept_gap_is_not_a_time_unit_error():
    # MEX 2001: an LFS mean monthly wage is 0.44 of OECD's full-time-equivalent wage and
    # no other figure exists that year - a difference of concept, not of time unit.
    s = _store(*_wdi("AAA", "2001", 9.34, 6.0),
               Obs("ilo_monthly_mean@X:1", "AAA", "2001", 3320.05, "s", "T8:127 T9:133"),
               Obs("ilo_monthly_mean_usd@X:1", "AAA", "2001", 355.4, "s"),
               Obs("oecd_avg_annual_wage", "AAA", "2001", 91411.8, "s", "AAD"),
               Obs("oecd_avg_annual_wage_q", "AAA", "2001", 91411.8, "s", "AAD 2001"),
               Obs("oecd_avg_annual_wage_q_usdppp", "AAA", "2001", 91411.8 / 6.0, "s", "USD_PPP 2001"),
               Obs("oecd_usual_weekly_hours_ft", "AAA", "2001", 47.5, "s"))
    u = build.UnitGraph(s, DIC, ["2001"], META)
    assert [v.key for v in build.ilo_variants(s, u, "AAA", "2001", DIC)] == ["ilo_mean_monthly"]


def test_units_hours_with_scale_error_are_not_used():
    # BLR BA:13362: 39 hours a week for years, then 3.89 - not used to derive an hourly wage.
    years = ["2023", "2024", "2025"]
    rows = [r for y in years for r in _wdi("AAA", y, 3.0, 1.2)]
    obs = [Obs("ilo_weekly_hours@X:1", "AAA", y, h, "s") for y, h in zip(years, (39.2, 39.3, 3.89))]
    obs += [Obs("ilo_monthly_mean@X:1", "AAA", "2025", 2000.0, "s", "T8:127 T9:133"),
            Obs("ilo_monthly_mean_usd@X:1", "AAA", "2025", 2000.0 / 3.0, "s")]
    s = _store(*rows, *obs)
    u = build.UnitGraph(s, DIC, years, META)
    v = build.ilo_variants(s, u, "AAA", "2025", DIC)[0]
    assert v.hourly_lcu is None and any(e["scope"] == "hours" and e["year"] == "2025" for e in u.log)


def test_restricts_reads_coverage_labels():
    assert not build.restricts("T12", "Working time arrangement coverage: Full-time equivalents")
    assert not build.restricts("T12", "Working time arrangement coverage: Full-time and part time workers")
    assert build.restricts("T12", "Working time arrangement coverage: Full-time workers")
    assert not build.restricts("S9", "Reference group coverage: Total employment")
    assert build.restricts("S9", "Reference group coverage: Insured persons")
    assert not build.restricts("S5", "Population coverage: Excluding both institutional population and armed forces and/or conscripts")
    assert build.restricts("S5", "Population coverage: Nationals only")


def test_median_shown_only_from_the_primary_source():
    wages = [{"key": "oecd_fte", "restricted": False, "hourly_lcu": 10.0, "monthly_lcu": 1700.0, "source_id": "OECD",
              "role": None, "mrole": None},
             {"key": "ilo_median_monthly", "restricted": False, "hourly_lcu": None, "monthly_lcu": 1500.0,
              "source_id": "ILOSTAT X:1", "role": None, "mrole": None},
             {"key": "ilo_mean_monthly", "restricted": False, "hourly_lcu": None, "monthly_lcu": 1800.0,
              "source_id": "ILOSTAT X:1", "role": None, "mrole": None}]
    build.mark_roles(wages)
    assert [w["mrole"] for w in wages] == ["primary", None, None]


def test_prove_identity_failure_next_to_a_proven_year_is_unknown():
    # GUY 2005: the PPP identity fails (×2.5) although the PPP moved ×1.03 from a proven year.
    years = ["2005", "2006"]
    s = _store(("ppp_hfce", "AAA", "2005", 95.94, "s"), ("hfce_lcu", "AAA", "2005", 38.4 * 500, "s"),
               ("hfce_intl", "AAA", "2005", 500.0, "s"), ("ppp_hfce", "AAA", "2006", 99.15, "s"),
               ("hfce_lcu", "AAA", "2006", 99.15 * 500, "s"), ("hfce_intl", "AAA", "2006", 500.0, "s"))
    u = build.UnitGraph(s, DIC, years, META)
    _f, p = u._factors("AAA")
    assert p["2006"][0] is True and p["2005"][0] is None and "原因不明" in p["2005"][1]


def test_nbs_split_wage_releases():
    # 2021 and 2022 were published as one release per measure.
    html = "<p>2022年，全国城镇非私营单位就业人员年平均工资为114029元，比上年增加7192元，名义增长6.7%，扣除价格因素实际增长4.6%。</p>"
    obs = {(o.series, o.period): o.value for o in nbs.parse_release(html, "2022年城镇非私营单位就业人员年平均工资114029元", "nbs/x")}
    assert obs == {("cn_wage_nonprivate", "2022"): 114029, ("cn_wage_nonprivate__implied_prev", "2021"): 106837}
    html = "<p>2022年全国规模以上企业就业人员年平均工资为92492元，比上年名义增长5.0%。</p>"
    obs = {(o.series, o.period): o.value for o in nbs.parse_release(html, "2022年规模以上企业就业人员年平均工资情况", "nbs/z")}
    assert obs == {("cn_wage_large_ent", "2022"): 92492}
    try:  # a large-enterprise release without its sentence is an error, not silently empty
        nbs.parse_release("<p>无关内容</p>", "2022年规模以上企业就业人员年平均工资情况", "nbs/y")
    except ValueError:
        return
    raise AssertionError("missing large-enterprise sentence not detected")
