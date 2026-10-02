"""Run the pipeline:  python -m wagegold [--offline] [--today YYYY-MM-DD]

1. fetch (or, with --offline, reuse) raw snapshots from every publisher
2. parse them into observations
3. build the dataset the website renders
4. run cross-source checks; any failing check aborts before anything is written
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date, datetime, timezone

from . import build, validate
from .config import GRAMS_PER_TROY_OUNCE, SITE_DATA_DIR
from .fetch import Fetcher, FetchError
from .model import Store
from .sources import bls, ecb, fred, ilostat, imf, nbs, oecd, pinksheet, worldbank
from .sources_meta import describe


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="wagegold")
    ap.add_argument("--offline", action="store_true", help="use committed snapshots only")
    ap.add_argument("--today", default=date.today().isoformat())
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.today)

    f = Fetcher(offline=args.offline)
    store = Store()
    problems: list[str] = []

    def run(name, fn, required=True, into_store=True):
        try:
            res = fn()
            if into_store and res:
                store.extend(res)
            print(f"[ok] {name}", flush=True)
            return res
        except Exception as exc:  # noqa: BLE001 - report every failure, then decide by `required`
            msg = f"{name}: {type(exc).__name__}: {exc}"
            print(f"[{'FAIL' if required else 'skip'}] {msg}", flush=True)
            if required and not isinstance(exc, FetchError):
                traceback.print_exc()
            if required:
                problems.append(msg)
            return None

    meta = run("worldbank countries", lambda: worldbank.collect_countries(f), into_store=False) or {}
    for name, fn, required in (
        ("worldbank pink sheet gold", lambda: pinksheet.collect(f), True),
        ("imf pcps gold", lambda: imf.collect(f), False),
        ("worldbank wdi", lambda: worldbank.collect_wdi(f), True),
        ("worldbank icp 2021", lambda: worldbank.collect_icp2021(f), True),
        ("worldbank food prices for nutrition", lambda: worldbank.collect_fpn(f), True),
        ("ecb exchange rates", lambda: ecb.collect(f), False),
        ("fred", lambda: fred.collect(f), False),
        ("oecd average wages", lambda: oecd.collect(f), False),
        ("bls", lambda: bls.collect(f, today), True),
        ("nbs", lambda: nbs.collect(f), True),
    ):
        run(name, fn, required)
    ilo = run("ilostat", lambda: ilostat.collect(f), into_store=False)
    ilo_dic = {}
    if ilo:
        run("ilostat (store)", lambda: ilo[0])
        ilo_dic = ilo[1]

    def save():
        f.save_manifest()
        if not f.offline:
            for path in f.prune_orphans():
                print(f"[prune] {path}")

    if problems:
        # Keep what was fetched (each snapshot passed its own content check) so the
        # failure can be investigated offline; the website dataset is not touched.
        save()
        from .config import DATA_DIR
        report = [{"id": "sources", "title": "必需数据源", "status": "fail", "detail": "；".join(problems)}]
        (DATA_DIR / "checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("\nRequired sources failed; website dataset not written.\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1

    try:
        return _build_and_write(store, f, meta, ilo_dic, today, save)
    except Exception as exc:  # noqa: BLE001 - a build error must still leave a report behind
        traceback.print_exc()
        save()
        from .config import DATA_DIR
        report = [{"id": "build", "title": "数据集构建", "status": "fail", "detail": f"{type(exc).__name__}: {exc}"}]
        (DATA_DIR / "checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return 3


def _build_and_write(store, f, meta, ilo_dic, today, save) -> int:
    years = [str(y) for y in range(2000, today.year + 1)]
    gold = build.gold_tables(store)
    gates = build.Gates(store)
    dataset = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "constants": {"grams_per_troy_ounce": GRAMS_PER_TROY_OUNCE, "weeks_per_month": build.WEEKS_PER_MONTH,
                      "statutory_hours_cn": build.STATUTORY_HOURS_CN},
        "gold": gold,
        "countries": build.country_years(store, gold, meta, ilo_dic, years, gates),
        "icp2021_pli_us": build.icp_levels(store),
        "us_monthly": build.us_monthly(store, gold),
        "us_items": build.us_items(store, gold),
        "wage_gold_history": build.wage_gold_history(store, gold, meta, ilo_dic, gates),
        "latest": build.latest_block(store, gold),
        "fx_recent_ecb": build.fx_recent(store),
        "nbs_price_releases": nbs.price_release_summary(),
        "cn_hours_monthly": [[p, o.value] for p, o in sorted(store.series("cn_weekly_hours_enterprise", "CHN").items())],
    }
    dataset["exclusions"] = _dedupe(gates.log)
    checks = validate.run_all(store, dataset, years, today.isoformat())
    for c in checks:
        print(f"[check:{c['status']}] {c['title']} — {c['detail']}", flush=True)
    save()
    from .config import DATA_DIR
    (DATA_DIR / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    dataset["checks"] = checks
    dataset["sources"] = describe(_merged_manifest(f))
    dataset["stale"] = [k for k, s in f.used.items() if s.status == "stale"]

    if any(c["status"] == "fail" for c in checks):
        print("\nA cross-source check failed; dataset NOT written.", file=sys.stderr)
        return 2
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = SITE_DATA_DIR / "dataset.json"
    out.write_text(json.dumps(dataset, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


def _dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        k = (r["area"], r["year"], r["scope"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return sorted(out, key=lambda r: (r["area"], r["year"], r["scope"]))


def _merged_manifest(f: Fetcher) -> dict:
    from dataclasses import asdict

    merged = dict(f.manifest)
    for k, s in f.used.items():
        merged[k] = asdict(s)
    return merged


if __name__ == "__main__":
    sys.exit(main())
