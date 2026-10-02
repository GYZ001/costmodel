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
    status: str  # pass | warn | fail | info (an overview, not a check)
    detail: str


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


def gold_cross_source(store: Store) -> Check:
    wb = store.series("gold_usd_oz", "WLD")
    imf = store.series("gold_usd_oz_imf", "WLD")
    common = sorted(p for p in wb if p in imf)
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
            if p in ecb:
                n += 1
                d = _rel(ecb[p].value, h10[p].value)
                if d > worst[0]:
                    worst = (d, f"{area} {p}：ECB 交叉汇率 {ecb[p].value:.4f}，美联储 H.10 {h10[p].value:.4f}")
    if n == 0:
        return Check("fx_ecb_vs_h10", "汇率：ECB vs 美联储 H.10 月均", "warn", "无重叠数据（FRED 未取到）")
    # Two fixings of the same market rate (ECB 14:15 CET, Fed noon New York): their monthly
    # averages differ only by intraday moves.  A wrong currency mapping or an inverted
    # quote shows up as a gap of tens of percent; 3 % separates the two.
    status = "pass" if worst[0] < 0.03 else "fail"
    return Check("fx_ecb_vs_h10", "汇率：ECB 参考汇率（交叉）vs 美联储 H.10 月均", status,
                 f"{n} 个国家-月份对比，最大偏差 {worst[0]:.2%}（{worst[1]}）；阈值 3%（两者是同一市场汇率在不同时点的定价）")


def bls_vs_fred(store: Store) -> Check:
    pairs = [("us_ahe_all_sa", "us_ahe_all_sa_fred"), ("us_ahe_pns_sa", "us_ahe_pns_sa_fred")]
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
        for p, o in sorted(implied.items()):  # sorted: output must not depend on fetch order
            if p in direct:
                same = abs(direct[p].value - o.value) < 0.5
                bad |= not same
                msgs.append(f"{series} {p}：本年发布 {direct[p].value:.0f}，次年发布反推 {o.value:.0f}{'' if same else ' ✗'}")
        for p, o in sorted(direct.items()):
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


def china_ilo_equals_nbs(store: Store, dataset: dict) -> Check:
    """The ILOSTAT China series drawn in the gold history (dataset.wage_gold_history.CHN,
    labelled as the same series as NBS's) must be NBS urban private-unit wages ÷ 12."""
    title = "中国：历年图中的 ILOSTAT 月薪 = 国家统计局私营单位年薪 ÷ 12"
    src = (dataset.get("wage_gold_history", {}).get("CHN") or {}).get("source_id") or ""
    nbs = {**store.series("cn_wage_private__implied_prev", "CHN"), **store.series("cn_wage_private", "CHN")}
    if not src.startswith("ILOSTAT ") or not nbs:
        return Check("cn_ilo_nbs", title, "warn", "历年图没有用 ILOSTAT 的中国序列，或缺少国家统计局私营单位工资")
    ilo = store.series(f"ilo_monthly_mean@{src.split(' ', 1)[1]}", "CHN")
    common = sorted(set(ilo) & set(nbs))
    if not common:
        return Check("cn_ilo_nbs", title, "warn", f"{src} 与国家统计局私营单位工资没有重叠年份，无法核对是同一序列")
    worst = max(common, key=lambda y: _rel(ilo[y].value * 12, nbs[y].value))
    d = _rel(ilo[worst].value * 12, nbs[worst].value)
    return Check("cn_ilo_nbs", title, "pass" if d < 0.002 else "fail",
                 f"{src}；重叠年份 {', '.join(common)}；最大偏差 {d:.3%}（{worst}：ILOSTAT×12 = {ilo[worst].value * 12:,.0f}，国家统计局 {nbs[worst].value:,.0f}）")


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


def exclusions_summary(dataset: dict) -> Check:
    """What was left out and why, by kind of reason (an overview, not a pass/fail check)."""
    names = {"unit": "无法证明同一货币单位", "missing": "发布方未发布该年数值", "notes": "发布方的注释或观测状态表明不能使用",
             "check": "数量级、时间单位或工时核对不通过", "area": "地区代码无法对应"}
    by_kind: dict[str, set] = {}
    for e in dataset.get("exclusions", []):
        by_kind.setdefault(e.get("kind", "unit"), set()).add(e["area"])
    detail = "；".join(f"{names.get(k, k)}：{len(v)} 个经济体（{', '.join(sorted(v)[:12])}{'…' if len(v) > 12 else ''}）"
                     for k, v in sorted(by_kind.items(), key=lambda kv: list(names).index(kv[0]) if kv[0] in names else 99)) or "无"
    return Check("record_gates", "不参与计算的输入（按原因）", "info", f"原因和数字逐条列在剔除记录中。{detail}")


def run_all(store: Store, dataset: dict, years: list[str], today: str) -> list[dict]:
    checks = [
        gold_cross_source(store), gold_freshness(store, today), fx_cross_source(store),
        bls_vs_fred(store), nbs_consistency(store), china_ilo_equals_nbs(store, dataset),
        us_ppp_is_one(store, years), exclusions_summary(dataset), identities(dataset),
    ]
    return [asdict(c) for c in checks]


__all__ = ["run_all", "GRAMS_PER_TROY_OUNCE"]
