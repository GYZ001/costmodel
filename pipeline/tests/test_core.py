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
