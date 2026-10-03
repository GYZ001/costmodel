"""Run the pipeline:  python -m wagegold [--offline] [--today YYYY-MM-DD]

1. fetch (or, with --offline, reuse) raw snapshots from every publisher
2. parse them into observations
3. build the dataset the website renders
4. run cross-source checks; any failing check aborts before anything is written
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
import traceback
from datetime import date, datetime, timezone

from . import build, validate
from .config import GRAMS_PER_TROY_OUNCE, SITE_DATA_DIR
from .fetch import Fetcher, FetchError
from .model import Store
from .msg import M, canonical
from .sources import ilostat, imf, mhlw, nbs, oecd, pinksheet, worldbank
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
        ("oecd average wages", lambda: oecd.collect(f), False),
        # Survey publishers' own releases of series ILOSTAT republishes (build.UnitGraph._extend).
        ("nbs (china) urban private-unit wages", lambda: nbs.collect(f), False),
        ("mhlw (japan) basic survey on wage structure", lambda: mhlw.collect(f), False),
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
        report = [{"id": "sources", "status": "fail", "detail": M("c.list", items=problems)}]
        (DATA_DIR / "checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("\nRequired sources failed; website dataset not written.\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1

    try:
        return _build_and_write(store, f, meta, ilo_dic, today, save)
    except Exception as exc:  # noqa: BLE001 - a build error must still leave a report behind
        traceback.print_exc()
        save()
        from .config import DATA_DIR
        report = [{"id": "build", "status": "fail", "detail": M("c.list", items=[f"{type(exc).__name__}: {exc}"])}]
        (DATA_DIR / "checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return 3


def _build_and_write(store, f, meta, ilo_dic, today, save) -> int:
    years = [str(y) for y in range(2000, today.year + 1)]
    gold = build.gold_tables(store)
    pink = f.used.get("worldbank/CMO-Historical-Data-Monthly")
    gold["source_updated"] = pinksheet.updated_on(pink.read()) if pink else None
    units = build.UnitGraph(store, ilo_dic, years, meta)
    dataset = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "constants": {"grams_per_troy_ounce": GRAMS_PER_TROY_OUNCE, "weeks_per_month": build.WEEKS_PER_MONTH,
                      "max_factor": build.MAX_FACTOR,
                      "time_factor": build.TIME_FACTOR, "unit_gap": build.UNIT_GAP,
                      "hours_in_month": build.HOURS_IN_MONTH, "history_min_years": build.HISTORY_MIN_YEARS,
                      "extension_tol": build.EXTENSION_TOL,
                      # widest move of OECD's same-concept wages against nominal income per head, by
                      # yardstick and years apart (cumulative), used for the continuity check
                      "level_bounds": {k.split("_")[0]: {str(n): v for n, v in b.items()} for k, b in units.level_bounds.items()}},
        "gold": gold,
        "countries": build.country_years(store, gold, meta, ilo_dic, years, units),
        "icp2021_pli": build.icp_levels(store, meta),
        "icp2021_spending": build.icp_spending(store, meta, units),
        "wage_gold_history": build.wage_gold_history(store, gold, meta, ilo_dic, units),
    }
    dataset["oecd_vs_survey"] = build.oecd_vs_survey(dataset["countries"])
    # Names of every economy, including those whose inputs were all left out (named in
    # dataset.exclusions but absent from countries).
    dataset["economies"] = {a: {"name_en": i["name_en"], "iso2": i["iso2"]} for a, i in sorted(meta.items()) if i.get("is_economy")}
    dataset["exclusions"] = _dedupe(units.log)
    checks = validate.run_all(store, dataset, years, today.isoformat())
    for c in checks:
        print(f"[check:{c['status']}] {c['id']} — {canonical(c['detail'])}", flush=True)
    save()
    from .config import DATA_DIR
    (DATA_DIR / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    dataset["checks"] = checks
    # Only the snapshots this run read: the provenance of the numbers published.
    dataset["sources"] = describe({k: asdict(sn) for k, sn in f.used.items()})
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
        k = (r["area"], r["year"], r["scope"], canonical(r["detail"]))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return sorted(out, key=lambda r: (r["area"], r["year"], r["scope"], canonical(r["detail"])))


if __name__ == "__main__":
    sys.exit(main())
