"""Cross-source consistency checks.

Each check compares two independent publications of the same quantity, or
verifies an accounting identity.  A failing check stops the pipeline, so data
that disagrees with its cross-reference is never published.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .config import GRAMS_PER_TROY_OUNCE
from .model import Store, annual_mean


@dataclass
class Check:
    id: str
    title: str
    status: str  # pass | warn | fail
    detail: str


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


def gold_cross_source(store: Store) -> Check:
    wb = store.series("gold_usd_oz", "WLD")
    imf = store.series("gold_usd_oz_imf", "WLD")
    common = sorted(p for p in wb if p in imf and p >= "2000-01")
    if len(common) < 120:
        return Check("gold_wb_vs_imf", "金价：世界银行 vs IMF 月均价", "fail", f"重叠月份不足（{len(common)}）")
    worst = max(common, key=lambda p: _rel(wb[p].value, imf[p].value))
    d = _rel(wb[worst].value, imf[worst].value)
    status = "pass" if d < 0.02 else "fail"
    return Check("gold_wb_vs_imf", "金价：世界银行 Pink Sheet vs IMF PCPS 月均价", status,
                 f"{len(common)} 个重叠月份，最大偏差 {d:.2%}（{worst}：世行 {wb[worst].value:,.1f}，IMF {imf[worst].value:,.1f}）")


def gold_freshness(store: Store, today: str) -> Check:
    wb = store.series("gold_usd_oz", "WLD")
    last = max(wb)
    y, m = int(last[:4]), int(last[5:7])
    ty, tm = int(today[:4]), int(today[5:7])
    lag = (ty - y) * 12 + (tm - m)
    status = "pass" if lag <= 2 else "warn"
    return Check("gold_fresh", "金价数据新鲜度", status, f"最新月份 {last}，距今 {lag} 个月")


def fx_cross_source(store: Store) -> Check:
    worst = (0.0, "")
    n = 0
    areas = store.areas("fx_lcu_usd_h10")
    for area in areas:
        h10 = store.series("fx_lcu_usd_h10", area)
        ecb = store.series("fx_lcu_usd_ecb", area)
        for p in h10:
            if p in ecb and p >= "2015-01":
                n += 1
                d = _rel(ecb[p].value, h10[p].value)
                if d > worst[0]:
                    worst = (d, f"{area} {p}：ECB 交叉汇率 {ecb[p].value:.4f}，美联储 H.10 {h10[p].value:.4f}")
    if n == 0:
        return Check("fx_ecb_vs_h10", "汇率：ECB vs 美联储 H.10 月均", "warn", "无重叠数据（FRED 未取到）")
    status = "pass" if worst[0] < 0.015 else "fail"
    return Check("fx_ecb_vs_h10", "汇率：ECB 参考汇率（交叉）vs 美联储 H.10 月均", status,
                 f"{n} 个国家-月份对比，最大偏差 {worst[0]:.2%}（{worst[1]}）")


def fx_annual_vs_monthly(store: Store, years: list[str]) -> Check:
    worst = (0.0, "")
    n = 0
    for area in store.areas("fx_lcu_usd_ecb"):
        if area == "EUR":
            continue
        monthly = store.series("fx_lcu_usd_ecb", area)
        for y in years:
            wdi = store.get("fx_lcu_usd", area, y)
            m = annual_mean(monthly, y)
            if wdi and m:
                n += 1
                d = _rel(m[0], wdi.value)
                if d > worst[0]:
                    worst = (d, f"{area} {y}：WDI {wdi.value:.4f}，ECB 月均之均值 {m[0]:.4f}")
    status = "pass" if worst[0] < 0.03 else "fail"
    return Check("fx_wdi_vs_ecb", "汇率：世界银行 WDI 年均 vs ECB 月均的年度平均", status,
                 f"{n} 个国家-年份对比，最大偏差 {worst[0]:.2%}（{worst[1]}）")


def bls_vs_fred(store: Store) -> Check:
    pairs = [("us_ahe_all_sa", "us_ahe_all_sa_fred")]
    worst = (0.0, "")
    n = 0
    for a, b in pairs:
        sa, sb = store.series(a, "USA"), store.series(b, "USA")
        for p in sa:
            if p in sb:
                n += 1
                d = _rel(sa[p].value, sb[p].value)
                if d > worst[0]:
                    worst = (d, f"{p}：BLS {sa[p].value}，FRED {sb[p].value}")
    if n == 0:
        return Check("bls_vs_fred", "美国时薪：BLS API vs FRED", "warn", "无重叠数据（FRED 未取到）")
    status = "pass" if worst[0] < 0.005 else "warn"
    return Check("bls_vs_fred", "美国时薪：BLS API vs FRED 转载", status,
                 f"{n} 个月份对比，最大偏差 {worst[0]:.2%}{'（' + worst[1] + '）' if worst[1] else ''}（BLS 修订后 FRED 可能晚一天同步）")


def nbs_consistency(store: Store) -> Check:
    msgs, bad = [], False
    for series in ("cn_wage_nonprivate", "cn_wage_private", "cn_migrant_monthly"):
        implied = store.series(f"{series}__implied_prev", "CHN")
        direct = store.series(series, "CHN")
        for p, o in implied.items():
            if p in direct:
                same = abs(direct[p].value - o.value) < 0.5
                bad |= not same
                msgs.append(f"{series} {p}：本年发布 {direct[p].value:.0f}，次年发布反推 {o.value:.0f}{'' if same else ' ✗'}")
        for p, o in direct.items():
            if "growth_pct=" in o.note:
                prev = direct.get(str(int(p) - 1)) or implied.get(str(int(p) - 1))
                if prev:
                    g = float(o.note.split("growth_pct=")[1])
                    calc = (o.value / prev.value - 1) * 100
                    ok = abs(calc - g) < 0.06
                    bad |= not ok
                    msgs.append(f"{series} {p} 增速：公布 {g}%，计算 {calc:.2f}%{'' if ok else ' ✗'}")
    if not msgs:
        return Check("nbs_internal", "国家统计局工资：前后年份与增速自洽", "warn", "未取到可对比的发布")
    return Check("nbs_internal", "国家统计局工资：前后年份与增速自洽", "fail" if bad else "pass", "；".join(msgs))


def china_ilo_equals_nbs(store: Store) -> Check:
    """ILOSTAT's China monthly earnings should be NBS urban private-unit wages / 12."""
    from .build import pick_source

    s = pick_source(store, "ilo_monthly_mean", "CHN")
    nbs = {**store.series("cn_wage_private__implied_prev", "CHN"), **store.series("cn_wage_private", "CHN")}
    if not s or not nbs:
        return Check("cn_ilo_nbs", "中国：ILOSTAT 月薪 = 国家统计局私营单位年薪 ÷ 12", "warn", "缺少可对比年份")
    ilo = store.series(s, "CHN")
    common = sorted(set(ilo) & set(nbs))
    if not common:
        return Check("cn_ilo_nbs", "中国：ILOSTAT 月薪 = 国家统计局私营单位年薪 ÷ 12", "warn", "没有重叠年份")
    worst = max(common, key=lambda y: _rel(ilo[y].value * 12, nbs[y].value))
    d = _rel(ilo[worst].value * 12, nbs[worst].value)
    return Check("cn_ilo_nbs", "中国：ILOSTAT 月薪 = 国家统计局私营单位年薪 ÷ 12", "pass" if d < 0.002 else "fail",
                 f"重叠年份 {', '.join(common)}；最大偏差 {d:.3%}（{worst}：ILOSTAT×12 = {ilo[worst].value * 12:,.0f}，国家统计局 {nbs[worst].value:,.0f}）")


def cohd_ppp_identity(store: Store) -> Check:
    worst = (0.0, "")
    n = 0
    for (s, a, p), o in store.items.items():
        if s != "cohd_total":
            continue
        ppp_cost = store.get("cohd_total_ppp", a, p)
        ppp = store.get("ppp_hfce", a, p)
        if ppp_cost and ppp and ppp_cost.value > 0:
            n += 1
            d = _rel(o.value / ppp_cost.value, ppp.value)
            if d > worst[0]:
                worst = (d, f"{a} {p}")
    status = "pass" if worst[0] < 0.05 else "warn"
    return Check("cohd_ppp", "健康饮食成本：本币值 ÷ PPP 值 = WDI 居民消费 PPP", status,
                 f"{n} 个国家-年份，最大偏差 {worst[0]:.1%}（{worst[1]}）；偏差大说明世行两处 PPP 版本不同")


def us_ppp_is_one(store: Store, years: list[str]) -> Check:
    vals = [store.get("ppp_hfce", "USA", y) for y in years]
    vals = [v for v in vals if v]
    ok = all(abs(v.value - 1) < 1e-9 for v in vals)
    return Check("us_ppp_1", "美国 PPP 恒等于 1（国际元以美元为基准）", "pass" if ok else "fail",
                 f"检查 {len(vals)} 个年份")


def identities(dataset: dict) -> Check:
    """real hourly wage (PPP) == gold grams per hour × US-$-equivalent purchasing power of 1 g."""
    worst = 0.0
    n = 0
    for area, c in dataset["countries"].items():
        for y, row in c["years"].items():
            for w in row["wages"]:
                if w["hourly_ppp"] and w["hourly_gold_g"] and row["gold_usdeq_g"]:
                    n += 1
                    worst = max(worst, _rel(w["hourly_gold_g"] * row["gold_usdeq_g"], w["hourly_ppp"]))
    return Check("identity_chain", "恒等式：克金/小时 × 每克金购买力 = PPP 实际时薪", "pass" if worst < 1e-9 else "fail",
                 f"{n} 条记录，最大相对误差 {worst:.1e}")


def run_all(store: Store, dataset: dict, years: list[str], today: str) -> list[dict]:
    checks = [
        gold_cross_source(store), gold_freshness(store, today), fx_cross_source(store),
        fx_annual_vs_monthly(store, years), bls_vs_fred(store), nbs_consistency(store), china_ilo_equals_nbs(store),
        cohd_ppp_identity(store), us_ppp_is_one(store, years), identities(dataset),
    ]
    return [asdict(c) for c in checks]


__all__ = ["run_all", "GRAMS_PER_TROY_OUNCE"]
