import { useEffect, useMemo, useState } from "react";
import type { Dataset } from "./types";
import { useI18n } from "./i18n";
import { bestYear, byName, countryName, wageYears, type View } from "./lib";
import { HowItWorks } from "./sections/HowItWorks";
import { GoldPerHour } from "./sections/GoldPerHour";
import { GoldBuys } from "./sections/GoldBuys";
import { RealWage } from "./sections/RealWage";
import { PriceStructure } from "./sections/PriceStructure";
import { GoldRuler } from "./sections/GoldRuler";
import { Profiles } from "./sections/Profiles";
import { Methods } from "./sections/Methods";

export type Group = "g20" | "all";

export interface Scope {
  ds: Dataset;
  year: string;
  view: View;
  group: Group;
  /** Economies the reader chose to focus on (none by default). */
  picks: string[];
  /** Each picked economy keeps the categorical colour slot it was given when picked (0–7). */
  slotOf: Record<string, number>;
  togglePick: (iso3: string) => void;
}

const MAX_PICKS = 8; // one per categorical series colour

interface Pick { iso: string; slot: number }

function toggle(cur: Pick[], iso: string): Pick[] {
  if (cur.some((p) => p.iso === iso)) return cur.filter((p) => p.iso !== iso);
  const kept = cur.length >= MAX_PICKS ? cur.slice(1) : cur;
  const used = new Set(kept.map((p) => p.slot));
  const slot = [...Array(MAX_PICKS).keys()].find((i) => !used.has(i))!;
  return [...kept, { iso, slot }];
}

/** Focus economies from the address (?focus=ISO,ISO), so a view can be shared. */
function picksFromUrl(ds: Dataset): Pick[] {
  const raw = new URLSearchParams(location.search).get("focus") ?? "";
  return raw.split(",").filter((c) => ds.countries[c]).reduce(toggle, [] as Pick[]);
}

export default function App({ ds }: { ds: Dataset }) {
  const i = useI18n();
  const [view, setView] = useState<View>("hourly");
  const best = useMemo(() => bestYear(ds, view), [ds, view]);
  const [yearPick, setYearPick] = useState<string | null>(null);
  const year = yearPick ?? best;
  const [group, setGroup] = useState<Group>("g20");
  const [picked, setPicked] = useState<Pick[]>(() => picksFromUrl(ds));
  const togglePick = (iso3: string) => setPicked((cur) => toggle(cur, iso3));
  const picks = useMemo(() => picked.map((p) => p.iso), [picked]);
  const slotOf = useMemo(() => Object.fromEntries(picked.map((p) => [p.iso, p.slot])), [picked]);

  useEffect(() => {
    const url = new URL(location.href);
    if (picks.length) url.searchParams.set("focus", picks.join(","));
    else url.searchParams.delete("focus");
    history.replaceState(null, "", url);
  }, [picks]);

  const years = useMemo(() => {
    const ys = new Set<string>();
    for (const c of Object.values(ds.countries)) for (const y of wageYears(c, view)) if (y >= "2015") ys.add(y);
    return [...ys].sort().reverse();
  }, [ds, view]);

  const scope: Scope = { ds, year, view, group, picks, slotOf, togglePick };
  const missing = useMemo(
    () =>
      Object.entries(ds.countries)
        .filter(([iso, c]) => (group === "all" ? picks.includes(iso) : c.g20 || picks.includes(iso)))
        .filter(([, c]) => !wageYears(c, view).includes(year))
        .map(([, c]) => {
          const name = countryName(i, c);
          const ys = wageYears(c, view);
          if (view === "hourly" && wageYears(c, "monthly").includes(year)) return i.t("missing.monthly_only", { name });
          const medianNow = c.years[year]?.wages.some((w) => w.concept === "median" && (view === "hourly" ? w.hourly_gold_g : w.monthly_gold_g));
          const ms = view === "hourly" ? wageYears(c, "monthly") : [];
          if (ys.length) {
            const latest = i.t(view === "hourly" ? "missing.latest_hourly" : "missing.latest_monthly", { year: ys[0] });
            const later = ms.length && ms[0] > ys[0] ? i.t("missing.latest_monthly", { year: ms[0] }) : null;
            return i.t("missing.item", { name, detail: i.j([...(medianNow ? [i.t("missing.median_only_now")] : []), latest, ...(later ? [later] : [])]) });
          }
          if (ms.length) return i.t("missing.item", { name, detail: i.j([i.t("missing.no_hourly"), i.t("missing.latest_monthly", { year: ms[0] })]) });
          // Economies whose verified figures are all medians have no primary (average) figure.
          const med = Object.keys(c.years).filter((y) => c.years[y].wages.some((w) => w.concept === "median" && (w.hourly_gold_g || w.monthly_gold_g))).sort();
          return i.t("missing.item", { name, detail: med.length ? i.t("missing.median_only", { year: med[med.length - 1] }) : i.t("missing.none") });
        })
        .sort(byName(i)),
    [ds, group, picks, view, year, i],
  );
  const checks = ds.checks.filter((c) => c.status !== "info"); // "info" rows are overviews, not checks
  const passed = checks.filter((c) => c.status === "pass").length;
  const failed = checks.filter((c) => c.status === "fail").length;
  const g = ds.gold.latest;

  return (
    <>
      <header className="top wrap">
        <div className="langbar">
          <label>
            <span className="sr-only">{i.t("app.language")}</span>
            <select value={i.lang.code} onChange={(e) => i.setLang(e.target.value)} aria-label={i.t("app.language")}>
              {i.langs.map((l) => <option key={l.code} value={l.code} lang={l.code}>{l.name}</option>)}
            </select>
          </label>
        </div>
        <h1>{i.t("app.title")}</h1>
        <p className="lede">{i.t("app.lede")}</p>
        <div className="toolbar">
          <span className="badge">
            <span className="dot" style={{ background: "var(--gold)" }} />
            {i.t("app.gold_badge", { period: g.period, oz: g.usd_oz, g: g.usd_g })}
          </span>
          <span className="badge">
            <span className="dot" style={{ background: failed ? "var(--critical)" : "var(--good)" }} />
            {i.t("app.checks_badge", { passed, total: checks.length })}
          </span>
          <span className="badge">
            {i.t("app.generated", { time: new Date(ds.generated_at).toLocaleString(i.lang.locale, { dateStyle: "medium", timeStyle: "short" }) })}
          </span>
          {ds.stale.length > 0 && <span className="badge">⚠ {i.t("app.stale", { n: ds.stale.length })}</span>}
        </div>
      </header>

      <nav className="sections" aria-label={i.t("nav.label")}>
        <div className="wrap">
          <a href="#how">{i.t("nav.how")}</a>
          <a href="#gold">{i.t("nav.gold")}</a>
          <a href="#buys">{i.t("nav.buys")}</a>
          <a href="#real">{i.t("nav.real")}</a>
          <a href="#structure">{i.t("nav.structure")}</a>
          <a href="#ruler">{i.t("nav.ruler")}</a>
          <a href="#profiles">{i.t("nav.profiles")}</a>
          <a href="#method">{i.t("nav.method")}</a>
        </div>
      </nav>

      <main className="wrap">
        <section className="block" aria-label={i.t("controls.label")}>
          <div className="controls" style={{ marginBottom: 0 }}>
            <span className="seg" role="group" aria-label={i.t("controls.view")}>
              <button aria-pressed={view === "hourly"} onClick={() => setView("hourly")}>{i.t("controls.hourly")}</button>
              <button aria-pressed={view === "monthly"} onClick={() => setView("monthly")}>{i.t("controls.monthly")}</button>
            </span>
            <label>
              {i.t("controls.year")}{" "}
              <select value={year} onChange={(e) => setYearPick(e.target.value)} title={i.t("controls.year_default_title")}>
                {years.map((y) => (
                  <option key={y} value={y}>{i.t(y === best ? "controls.year_default" : "controls.year_option", { year: y })}</option>
                ))}
              </select>
            </label>
            <span className="seg" role="group" aria-label={i.t("controls.group")}>
              <button aria-pressed={group === "g20"} onClick={() => setGroup("g20")}>{i.t("controls.g20")}</button>
              <button aria-pressed={group === "all"} onClick={() => setGroup("all")}>{i.t("controls.all")}</button>
            </span>
          </div>
          <div className="controls" style={{ marginTop: 10 }}>
            <span>{i.t("controls.focus")}</span>
            <div className="chips">
              {picks.map((iso) => (
                <button key={iso} className="chip" aria-pressed="true" onClick={() => togglePick(iso)} title={i.t("controls.remove")}>
                  <span className="sw" style={{ background: `var(--s${slotOf[iso] + 1})`, borderRadius: "50%" }} />
                  {countryName(i, ds.countries[iso])} <span className="x" aria-hidden>×</span>
                </button>
              ))}
              <AddCountry ds={ds} picks={picks} onAdd={togglePick} />
            </div>
          </div>
          <p className="small muted" style={{ margin: "8px 0 0" }}>
            {i.j([
              i.t(picks.length === 0 ? "controls.focus_hint_empty" : "controls.focus_hint", { n: MAX_PICKS }),
              i.t(group === "g20" ? "controls.g20_shown" : "controls.all_shown", { g20: i.t("controls.g20"), all: i.t("controls.all") }),
              i.t("controls.same_year", { year: best }),
              missing.length > 0 ? i.t(view === "hourly" ? "controls.missing_hour" : "controls.missing_month", { year, list: i.j(missing, "enum") }) : "",
            ], "sentence")}
          </p>
        </section>

        <HowItWorks {...scope} />
        <GoldPerHour {...scope} />
        <GoldBuys {...scope} />
        <RealWage {...scope} />
        <PriceStructure {...scope} />
        <GoldRuler {...scope} />
        <Profiles {...scope} />
        <Methods ds={ds} />
      </main>
      <footer className="wrap">
        {i.t("app.footer_code")} <a href="https://github.com/GYZ001/costmodel">github.com/GYZ001/costmodel</a> · {i.t("app.footer")}
      </footer>
    </>
  );
}

function AddCountry({ ds, picks, onAdd }: { ds: Dataset; picks: string[]; onAdd: (iso: string) => void }) {
  const i = useI18n();
  const options = useMemo(() => {
    const cmp = byName(i);
    return Object.entries(ds.countries)
      .filter(([iso]) => !picks.includes(iso))
      .map(([iso, c]) => [iso, countryName(i, c)] as const)
      .sort((a, b) => cmp(a[1], b[1]));
  }, [ds, picks, i]);
  return (
    <select value="" aria-label={i.t("controls.add")} onChange={(e) => e.target.value && onAdd(e.target.value)}>
      <option value="">{i.t("controls.add_option")}</option>
      {options.map(([iso, name]) => <option key={iso} value={iso}>{name}</option>)}
    </select>
  );
}
