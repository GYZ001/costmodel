"""Cross-source consistency checks.

Each check compares two independent publications of the same quantity, or
verifies an accounting identity.  A failing check stops the pipeline, so data
that disagrees with its cross-reference is never published.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .config import GRAMS_PER_TROY_OUNCE
from .model import Store
from .msg import M, Msg


@dataclass
class Check:
    id: str  # the website names each check by its id (catalog key check.<id>)
    status: str  # pass | warn | fail | info (an overview, not a check)
    detail: Msg


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


def gold_cross_source(store: Store) -> Check:
    wb = store.series("gold_usd_oz", "WLD")
    imf = store.series("gold_usd_oz_imf", "WLD")
    common = sorted(p for p in wb if p in imf)
    if len(common) < 120:
        return Check("gold_wb_vs_imf", "fail", M("c.gold.too_few", n=len(common)))
    worst = max(common, key=lambda p: _rel(wb[p].value, imf[p].value))
    d = _rel(wb[worst].value, imf[worst].value)
    status = "pass" if d < 0.02 else "fail"
    return Check("gold_wb_vs_imf", status, M("c.gold", n=len(common), d=d, month=worst, wb=wb[worst].value, imf=imf[worst].value))


def gold_freshness(store: Store, today: str) -> Check:
    wb = store.series("gold_usd_oz", "WLD")
    last = max(wb)
    y, m = int(last[:4]), int(last[5:7])
    ty, tm = int(today[:4]), int(today[5:7])
    lag = (ty - y) * 12 + (tm - m)
    status = "pass" if lag <= 2 else "warn"
    return Check("gold_fresh", status, M("c.gold_fresh", month=last, lag=lag))


def bls_vs_fred(store: Store) -> Check:
    pairs = [("us_ahe_all_sa", "us_ahe_all_sa_fred")]
    worst: tuple[float, Msg | None] = (0.0, None)
    n = 0
    for a, b in pairs:
        sa, sb = store.series(a, "USA"), store.series(b, "USA")
        for p in sa:
            if p in sb:
                n += 1
                d = _rel(sa[p].value, sb[p].value)
                if d > worst[0]:
                    worst = (d, M("c.bls_fred.worst", month=p, bls=sa[p].value, fred=sb[p].value))
    if n == 0:
        return Check("bls_vs_fred", "warn", M("c.bls_fred.none"))
    status = "pass" if worst[0] < 0.005 else "warn"
    return Check("bls_vs_fred", status, M("c.bls_fred.worse" if worst[1] else "c.bls_fred", n=n, d=worst[0], worst=worst[1] or ""))


def nbs_consistency(store: Store) -> Check:
    msgs, bad = [], False
    for series in ("cn_wage_nonprivate", "cn_wage_private", "cn_migrant_monthly"):
        implied = store.series(f"{series}__implied_prev", "CHN")
        direct = store.series(series, "CHN")
        for p, o in sorted(implied.items()):  # sorted: output must not depend on fetch order
            if p in direct:
                same = abs(direct[p].value - o.value) < 0.5
                bad |= not same
                msgs.append(M("c.nbs.level" if same else "c.nbs.level_bad", series=series, year=p, direct=direct[p].value, implied=o.value))
        for p, o in sorted(direct.items()):
            if "growth_pct=" in o.note:
                prev = direct.get(str(int(p) - 1)) or implied.get(str(int(p) - 1))
                if prev:
                    g = float(o.note.split("growth_pct=")[1])
                    calc = (o.value / prev.value - 1) * 100
                    ok = abs(calc - g) < 0.06
                    bad |= not ok
                    msgs.append(M("c.nbs.growth" if ok else "c.nbs.growth_bad", series=series, year=p, published=g, calc=calc))
    if not msgs:
        return Check("nbs_internal", "warn", M("c.nbs.none"))
    return Check("nbs_internal", "fail" if bad else "pass", M("c.list", items=msgs))


def china_ilo_equals_nbs(store: Store, dataset: dict) -> Check:
    """The ILOSTAT China series drawn in the gold history (dataset.wage_gold_history.CHN,
    labelled as the same series as NBS's) must be NBS urban private-unit wages ÷ 12."""
    src = (dataset.get("wage_gold_history", {}).get("CHN") or {}).get("source_id") or ""
    nbs = {**store.series("cn_wage_private__implied_prev", "CHN"), **store.series("cn_wage_private", "CHN")}
    if not src.startswith("ILOSTAT ") or not nbs:
        return Check("cn_ilo_nbs", "warn", M("c.cn_ilo.unused"))
    ilo = store.series(f"ilo_monthly_mean@{src.split(' ', 1)[1]}", "CHN")
    common = sorted(set(ilo) & set(nbs))
    if not common:
        return Check("cn_ilo_nbs", "warn", M("c.cn_ilo.no_overlap", source=src))
    worst = max(common, key=lambda y: _rel(ilo[y].value * 12, nbs[y].value))
    d = _rel(ilo[worst].value * 12, nbs[worst].value)
    return Check("cn_ilo_nbs", "pass" if d < 0.002 else "fail",
                 M("c.cn_ilo", source=src, years=", ".join(common), d=d, year=worst, ilo=ilo[worst].value * 12, nbs=nbs[worst].value))


def us_ppp_is_one(store: Store, years: list[str]) -> Check:
    vals = [store.get("ppp_hfce", "USA", y) for y in years]
    vals = [v for v in vals if v]
    ok = all(abs(v.value - 1) < 1e-9 for v in vals)
    return Check("us_ppp_1", "pass" if ok else "fail", M("c.years_checked", n=len(vals)))


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
    return Check("identity_chain", "pass" if worst < 1e-9 else "fail", M("c.identity", n=n, worst=worst))


def exclusions_summary(dataset: dict) -> Check:
    """What was left out and why, by kind of reason (an overview, not a pass/fail check)."""
    order = ["unit", "identity", "missing", "notes", "check", "area"]  # names: catalog keys kind.<kind>
    by_kind: dict[str, set] = {}
    for e in dataset.get("exclusions", []):
        by_kind.setdefault(e.get("kind", "unit"), set()).add(e["area"])
    groups = [M("c.gates.kind", kind=M(f"kind.{k}"), n=len(v), areas=", ".join(sorted(v)[:12]) + ("…" if len(v) > 12 else ""))
              for k, v in sorted(by_kind.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)]
    return Check("record_gates", "info", M("c.gates", groups=groups or [M("d.none")]))


def run_all(store: Store, dataset: dict, years: list[str], today: str) -> list[dict]:
    checks = [
        gold_cross_source(store), gold_freshness(store, today),
        bls_vs_fred(store), nbs_consistency(store), china_ilo_equals_nbs(store, dataset),
        us_ppp_is_one(store, years), exclusions_summary(dataset), identities(dataset),
    ]
    return [asdict(c) for c in checks]


__all__ = ["run_all", "GRAMS_PER_TROY_OUNCE"]
