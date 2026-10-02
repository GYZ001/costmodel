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


def _yoy(text, topic=None):
    return [c for x in nbs.yoy_sentences(text, topic) for c in x["yoy"]]


def test_cpi_yoy_sentences_follow_stated_basis():
    # Wording and spacing as on the NBS page for August 2026.
    html = ('<div class="header">导航 价格 同比 1.0%。</div><div class="txt-content">'
            "<p>2026 年 8 月份，全国居民消费价格同比上涨 0.8% 。其中，城市上涨 0.8% ，农村上涨 0.7% ；食品价格下降 1.4% ，非食品价格上涨 1.2% 。"
            " 1\u00ad\u00ad — 8 月平均，全国居民消费价格比上年同期上涨 0.9% 。 8 月份，全国居民消费价格环比上涨 0.4% 。"
            "其中，城市上涨 0.4% ；食品价格上涨 0.4% ，非食品价格上涨 0.3% 。</p>"
            "<p>一、各类商品及服务价格同比变动情况 8 月份，食品烟酒及在外餐饮类价格同比下降 0.7% 。"
            "食品中，畜肉类价格下降 5.1% ，其中猪肉价格下降 11.8% ；粮食价格下降 0.6% 。</p>"
            "<p>二、各类商品及服务价格环比变动情况 8 月份，食品价格上涨 0.4% 。</p></div>"
            '<div class="mobile-content">2026 年 8 月份，全国居民消费价格同比上涨 0.8% 。</div>')
    assert _yoy(nbs.body_text(html)) == [
        "全国居民消费价格同比上涨0.8%", "城市上涨0.8%", "农村上涨0.7%",
        "食品价格下降1.4%", "非食品价格上涨1.2%",
        "食品烟酒及在外餐饮类价格同比下降0.7%",
        "畜肉类价格下降5.1%", "其中猪肉价格下降11.8%", "粮食价格下降0.6%",
    ]


def test_cumulative_period_is_inherited():
    # 2026-07 economy release: the CPI paragraph opens with January-July figures.
    text = ("七、市场价格温和上涨，7月份涨幅有所回落1—7月份，全国居民消费价格（CPI）同比上涨0.9%。"
            "分类别看，食品烟酒及在外餐饮价格同比下降0.2%，衣着价格上涨1.6%。"
            "在食品烟酒及在外餐饮价格中，猪肉价格下降13.4%，粮食价格下降0.3%。"
            "7月份，全国居民消费价格同比上涨0.5%，环比下降0.1%。其中，7月份核心CPI同比上涨0.9%。")
    assert _yoy(text, topic="居民消费价格") == ["全国居民消费价格同比上涨0.5%", "7月份核心CPI同比上涨0.9%"]
    # Only the clause that names February is February's.
    text = "1—2月份，全国居民消费价格同比持平。扣除食品和能源价格后的核心CPI同比上涨0.8%，其中2月份同比上涨1.2%。"
    assert _yoy(text, topic="居民消费价格") == ["其中2月份同比上涨1.2%"]


def test_economy_release_cpi_sentences_stay_in_cpi_paragraph():
    # Wording of the NBS release of 2026-09-15 ("8月份国民经济…").
    text = ("全国企业就业人员周平均工作时间为48.2小时。七、居民消费价格温和回升，工业生产者价格同比涨幅扩大8月份，"
            "全国居民消费价格（CPI）同比上涨0.8%，涨幅比上月扩大0.3个百分点；环比上涨0.4%。"
            "分类别看，食品烟酒及在外餐饮价格同比下降0.7%，衣着价格上涨1.3%。"
            "在食品烟酒及在外餐饮价格中，猪肉价格下降11.8%，鲜菜价格下降2.8%，粮食价格下降0.6%，鲜果价格下降0.5%。"
            "1—8月份，全国居民消费价格同比上涨0.9%。8月份，全国工业生产者出厂价格同比上涨3.8%。"
            "其中，生活资料价格上涨1.0%。八、房地产开发投资同比下降5.0%，新建商品房销售价格同比下降2.0%。")
    assert _yoy(text, topic="居民消费价格") == [
        "全国居民消费价格（CPI）同比上涨0.8%",
        "食品烟酒及在外餐饮价格同比下降0.7%", "衣着价格上涨1.3%",
        "猪肉价格下降11.8%", "鲜菜价格下降2.8%", "粮食价格下降0.6%", "鲜果价格下降0.5%",
    ]


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
            ("gdp_lcu", area, year, f * 1000, "s"), ("gdp_usd", area, year, 1000.0, "s"),
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
