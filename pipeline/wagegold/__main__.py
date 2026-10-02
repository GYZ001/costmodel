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
from .sources import bls, ecb, fred, ilostat, imf, nbs, pinksheet, worldbank
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

    def run(name, fn, required=True):
        try:
            res = fn()
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

    meta = run("worldbank countries", lambda: worldbank.collect_countries(f)) or {}
    for name, fn, required in (
        ("worldbank pink sheet gold", lambda: pinksheet.collect(f), True),
        ("imf pcps gold", lambda: imf.collect(f), False),
        ("worldbank wdi", lambda: worldbank.collect_wdi(f), True),
        ("worldbank icp 2021", lambda: worldbank.collect_icp2021(f), True),
        ("worldbank food prices for nutrition", lambda: worldbank.collect_fpn(f), True),
        ("ecb exchange rates", lambda: ecb.collect(f), False),
        ("fred", lambda: fred.collect(f), False),
        ("bls", lambda: bls.collect(f, today), True),
        ("nbs", lambda: nbs.collect(f), True),
    ):
        obs = run(name, fn, required)
        if obs:
            store.extend(obs)
    ilo = run("ilostat", lambda: ilostat.collect(f))
    ilo_dic = {}
    if ilo:
        store.extend(ilo[0])
        ilo_dic = ilo[1]

    if problems:
        print("\nRequired sources failed; nothing written.\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1

    years = [str(y) for y in range(2000, today.year + 1)]
    gold = build.gold_tables(store)
    dataset = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "constants": {"grams_per_troy_ounce": GRAMS_PER_TROY_OUNCE, "weeks_per_month": build.WEEKS_PER_MONTH,
                      "statutory_hours_cn": build.STATUTORY_HOURS_CN},
        "gold": gold,
        "countries": build.country_years(store, gold, meta, ilo_dic, years),
        "icp2021_pli_us": build.icp_levels(store),
        "us_monthly": build.us_monthly(store, gold),
        "us_items": build.us_items(store, gold),
        "cn_hours_monthly": [[p, o.value] for p, o in sorted(store.series("cn_weekly_hours_enterprise", "CHN").items())],
    }
    checks = validate.run_all(store, dataset, years, today.isoformat())
    for c in checks:
        print(f"[check:{c['status']}] {c['title']} — {c['detail']}", flush=True)
    f.save_manifest()
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


def _merged_manifest(f: Fetcher) -> dict:
    from dataclasses import asdict

    merged = dict(f.manifest)
    for k, s in f.used.items():
        merged[k] = asdict(s)
    return merged


if __name__ == "__main__":
    sys.exit(main())
