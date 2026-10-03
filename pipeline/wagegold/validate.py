"""Cross-source consistency checks.

Each check compares two independent publications of the same quantity, checks a
convention a publisher states, or tests this project's own arithmetic.  A failing check stops the pipeline, so data
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
    return Check("gold_fresh", status, M("c.gold_fresh", month=last, n=lag))


def us_ppp_is_one(store: Store, years: list[str]) -> Check:
    vals = [store.get("ppp_hfce", "USA", y) for y in years]
    vals = [v for v in vals if v]
    ok = all(abs(v.value - 1) < 1e-9 for v in vals)
    return Check("us_ppp_1", "pass" if ok else "fail", M("c.years_checked", n=len(vals)))


def identities(dataset: dict) -> Check:
    """Arithmetic self-test: real hourly wage (PPP) == gold grams per hour × US-$-equivalent
    purchasing power of 1 g.  All three come from the same inputs, so this catches errors
    in this project's arithmetic, not in the data."""
    worst = 0.0
    n = 0
    for area, c in dataset["countries"].items():
        for y, row in c["years"].items():
            for w in row["wages"]:
                if w["hourly_ppp"] and w["hourly_gold_g"] and row["gold_usdeq_g"]:
                    n += 1
                    worst = max(worst, _rel(w["hourly_gold_g"] * row["gold_usdeq_g"], w["hourly_ppp"]))
    return Check("identity_chain", "pass" if worst < 1e-9 else "fail", M("c.identity", n=n, worst=worst))


def living_arithmetic(dataset: dict) -> Check:
    """Arithmetic self-test of the living-cost figures: each wage's ratio × the wage =
    consumption per resident; each ICP composition's shares + net purchases abroad = 1, and
    the parts of "other" add up to it.  All come from the same inputs (published without
    any rounding moved between parts), so this tests this site's arithmetic, not the data."""
    worst, n = 0.0, 0
    for c in dataset["countries"].values():
        for row in c["years"].values():
            cons = row["living"]["consumption_month"]
            for w in row["wages"]:
                if w["living_ratio"] is not None:
                    n += 1
                    worst = max(worst, _rel(w["living_ratio"] * w["monthly_lcu"], cons))
    for sp in dataset.get("icp2021_spending", {}).values():
        n += 1
        worst = max(worst, abs(sum(sp["shares"].values()) + sp["net_abroad"] - 1),
                    abs(sum(sp["other_parts"].values()) - sp["shares"]["other"]))
    return Check("living_arith", "pass" if worst < 1e-9 else "fail", M("c.identity", n=n, worst=worst))


def exclusions_summary(dataset: dict) -> Check:
    """What was left out and why, by kind of reason (an overview, not a pass/fail check)."""
    order = ["unit", "identity", "missing", "notes", "check", "icp", "amounts", "range", "area", "chosen"]  # names: catalog keys kind.<kind>
    by_kind: dict[str, set] = {}
    for e in dataset.get("exclusions", []):
        by_kind.setdefault(e.get("kind", "unit"), set()).add(e["area"])
    groups = [M("c.gates.kind", kind=M(f"kind.{k}"), n=len(v))
              for k, v in sorted(by_kind.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)]
    return Check("record_gates", "info", M("c.gates", groups=groups or [M("d.none")]))


def run_all(store: Store, dataset: dict, years: list[str], today: str) -> list[dict]:
    checks = [
        gold_cross_source(store), gold_freshness(store, today),
        us_ppp_is_one(store, years), exclusions_summary(dataset), identities(dataset), living_arithmetic(dataset),
    ]
    return [asdict(c) for c in checks]


__all__ = ["run_all", "GRAMS_PER_TROY_OUNCE"]
