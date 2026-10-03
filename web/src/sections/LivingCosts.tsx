import { useEffect, useMemo, useState } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { compositionOption, linesOption, rankingHeight, ratioRankingOption } from "../charts";
import { useI18n } from "../i18n";
import { countryName, LIVING_GROUPS, money, primaryWage, skippedYears, typicalWage, useThemeVersion, wageLabel, wageNotes, yearlyLine } from "../lib";
import { Legend, useKV, usePickByName, useRows } from "./common";
import { FocusPrompt } from "./Profiles";
import type { Msg } from "../i18n/render";

const NAMED = 6; // the groups before "other"

/** "2016–2020, 2022": consecutive years as ranges. */
function yearRanges(years: number[]): string[] {
  const out: string[] = [];
  for (let k = 0; k < years.length; k++) {
    let j = k;
    while (j + 1 < years.length && years[j + 1] === years[j] + 1) j++;
    out.push(j > k ? `${years[k]}–${years[j]}` : `${years[k]}`);
    k = j;
  }
  return out;
}

/** Whether a media query matches, following changes. */
function useMedia(q: string): boolean {
  const [on, setOn] = useState(() => typeof window !== "undefined" && !!window.matchMedia?.(q).matches);
  useEffect(() => {
    const m = window.matchMedia?.(q);
    if (!m) return;
    const f = () => setOn(m.matches);
    f();
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, [q]);
  return on;
}

/** ④ What households consume, compared with the wage: household consumption per resident per
 *  month (World Bank, every year) ÷ the average monthly wage of the same year; its 2021
 *  composition (ICP); and its course over time on one wage series. Always monthly wages. */
export function LivingCosts(scope: Scope) {
  const { ds, year, picks, slotOf } = scope;
  const i = useI18n();
  const kv = useKV();
  const theme = useThemeVersion();
  const narrow = useMedia("(max-width: 640px)"); // fewer axis ticks
  const sideless = useMedia("(max-width: 900px)"); // no side panel: its values stay in tooltips and the table
  const rows = useRows(scope);
  const pick = usePickByName(rows, scope.togglePick);
  const pct = (v: number) => i.n(v, "pct0");
  const [mode, setMode] = useState<"wage" | "cons">("wage");

  // ---- Card 1: the ratio in the reference year
  const ratio = useMemo(() => rows.flatMap(({ iso, c, name, row }) => {
    const w = primaryWage(row, "monthly");
    if (!w?.living_ratio) return [];
    const L = row.living;
    const others = row.wages
      .filter((x) => x !== w && x.concept === "mean" && x.living_ratio != null)
      .map((x) => ({ value: x.living_ratio as number, label: i.t("liv.other_wage", { label: wageLabel(i, x, "monthly"), source: i.r(x.source) }) }));
    const med = typicalWage(row, "monthly");
    const tip = [
      i.t("liv.tip_cons", { v: money(i, L.consumption_month, c.currency), year }),
      ...(c.na_fiscal ? [i.t("liv.tip_fiscal", { note: c.na_fiscal })] : []),
      ...wageNotes(i, w, "monthly", c, 160),
      ...(med?.living_ratio != null ? [i.t("liv.tip_median", { r: med.living_ratio })] : []),
      ...(L.employees_share != null ? [i.t("liv.tip_employees", { q: L.employees_share })] : []),
      ...(L.residents_per_employed != null ? [i.t("liv.tip_residents", { n: L.residents_per_employed })] : []),
    ];
    return [{ id: iso, name, value: w.living_ratio, highlight: picks.includes(iso), others, side: L.employees_share, tip,
      cons: L.consumption_month, wage: w, med: med?.living_ratio ?? null, residents: L.residents_per_employed, c }];
  }), [rows, picks, year, i]);

  // In scope with a primary monthly wage but no World Bank consumption for the year (with the latest year
  // that has it), or consumption not shown to be in the wages' currency unit.
  const noCons = useMemo(() => rows.filter(({ row }) => primaryWage(row, "monthly") && row.living.consumption_month == null
    && !row.living.consumption_unconfirmed)
    .map(({ c, name }) => {
      return c.consumption_latest ? i.t("liv.missing_item", { name, year: c.consumption_latest }) : name;
    }), [rows, i]);
  const unconfirmed = useMemo(() => rows.filter(({ row }) => primaryWage(row, "monthly") && row.living.consumption_unconfirmed)
    .map(({ name }) => name), [rows]);
  const noWage = useMemo(() => Object.entries(ds.countries)
    .filter(([iso, c]) => (scope.group === "all" ? picks.includes(iso) : c.g20 || picks.includes(iso)))
    .filter(([, c]) => !primaryWage(c.years[year], "monthly"))
    .map(([, c]) => countryName(i, c)), [ds, scope.group, picks, year, i]);
  const minority = ratio.filter((r) => r.side != null && r.side < 0.5).map((r) => r.name);
  const fiscal = ratio.filter((r) => r.c.na_fiscal).map((r) => r.name);
  // How much the government provides free on top, across all ICP economies (not in the consumption counted).
  const govRange = useMemo(() => {
    const g = Object.entries(ds.icp2021_spending).sort(([, a], [, b]) => a.government - b.government);
    if (!g.length) return null;
    const nameOf = (iso: string) => countryName(i, ds.countries[iso] ?? ds.economies[iso]);
    const [lo, hi] = [g[0], g[g.length - 1]];
    return { gmin: lo[1].government, emin: nameOf(lo[0]), gmax: hi[1].government, emax: nameOf(hi[0]) };
  }, [ds, i]);
  const switched = ratio.filter((r) => r.wage.mrole_switch?.kind === "source").map((r) => r.name);
  const ovs = ds.oecd_vs_survey;

  const rOpt = useMemo(() => ratioRankingOption({
    items: ratio, valueName: i.t("liv.ratio_value"), otherName: i.t("liv.other_name"),
    sideName: sideless ? undefined : i.t("liv.side"), sideWidth: 200, splitNumber: narrow ? 3 : undefined, ref: { value: 1, label: i.t("liv.ref") },
    format: pct, sideFormat: pct, kv,
  }), [ratio, narrow, sideless, theme, i]);

  // ---- Card 2: the ICP benchmark composition
  const revisionLine = (sp: (typeof ds.icp2021_spending)[string]) => {
    const [lo, hi] = sp.revision!;
    const k = sp.converted;
    if (!k) return i.t("liv.tip_revision", { year: sp.year, r: lo });
    if (k.fx != null && k.ppp != null) {
      return i.n(lo, "pct1") === i.n(hi, "pct1")
        ? i.t("liv.tip_revision_both", { year: sp.year, r: lo, kf: k.fx, kp: k.ppp })
        : i.t("liv.tip_revision_range", { year: sp.year, lo, hi, kf: k.fx, kp: k.ppp });
    }
    return i.t(k.fx != null ? "liv.tip_revision_fx" : "liv.tip_revision_ppp", { year: sp.year, r: lo, k: k.fx ?? k.ppp });
  };
  const spendYears = useMemo(() => [...new Set(Object.values(ds.icp2021_spending).map((s) => s.year))].sort(), [ds]);
  const inView = (iso: string) => (scope.group === "all" ? picks.includes(iso) : !!ds.countries[iso]?.g20 || picks.includes(iso));
  const comp = useMemo(() => Object.entries(ds.icp2021_spending)
    .filter(([iso]) => scope.group === "all" || ds.countries[iso]?.g20 || picks.includes(iso))
    .flatMap(([iso, sp]) => {
      const c = ds.countries[iso];
      const econ = c ?? ds.economies[iso];
      if (!econ) return [];
      const name = countryName(i, econ);
      const row = c?.years[sp.year];
      const w = primaryWage(row, "monthly");
      const scale = mode === "wage" ? (sp.consumption_month != null && w?.monthly_lcu ? sp.consumption_month / w.monthly_lcu : null) : 1;
      if (scale == null) return [];
      const amount = (s: number) => (sp.consumption_month != null ? i.t("liv.amount", { v: money(i, s * sp.consumption_month, sp.currency) }) : null);
      // Net spending abroad: stated only where ICP publishes it as non-zero and it does not round to zero as shown.
      const shown = (v: number) => i.n(Math.abs(v), "pct1") !== i.n(0, "pct1");
      const net = sp.net_abroad_status === "published" && shown(sp.net_abroad) ? sp.net_abroad : 0;
      const tip = [
        i.t("liv.tip_other", { rh: sp.other_parts.restaurants_hotels, at: sp.other_parts.alcohol_tobacco, rest: sp.other_parts.rest }),
        ...(net < 0 ? [i.t("liv.tip_abroad_neg", { v: -net })] : net > 0 ? [i.t("liv.tip_abroad_pos", { v: net })] : []),
        ...(sp.net_abroad_status !== "published" ? [i.t(`liv.tip_abroad_${sp.net_abroad_status}`)] : []),
        i.t("liv.tip_housing_actual", { v: sp.housing_actual }),
        i.t("liv.tip_gov_share", { p: sp.government }),
        ...(sp.revision != null ? [revisionLine(sp)] : []),
        ...(sp.na_fiscal ? [i.t("liv.tip_fiscal", { note: sp.na_fiscal })] : []),
        ...(mode === "wage" && w && c ? wageNotes(i, w, "monthly", c).slice(0, 1) : []), // the wage; its source and notes are in the ranking's tooltip
        ...(sp.consumption_month != null ? [i.t("liv.tip_basis", { year: sp.year })] : []),
      ];
      const parts = LIVING_GROUPS.map((g) => sp.shares[g] * scale);
      const extra = shown(net * scale) ? net * scale : 0;
      return [{
        iso, name, parts, partNotes: LIVING_GROUPS.map((g) => amount(sp.shares[g])), total: scale, extra,
        known: sp.net_abroad_status === "published", highlight: picks.includes(iso), tip,
      }];
    }), [ds, scope.group, picks, mode, i]);
  // Shares are shown for every economy with a composition; amounts and wage shares only where the
  // World Bank's total is the one ICP's shares divide, and where the year's wage is known.
  // Economies in view without amounts, by reason (the exclusion the pipeline logged; none: no World Bank total).
  const noAmounts = useMemo(() => {
    const reason: Record<string, string> = {
      "d.liv.revised": "liv.amounts_revised", "d.liv.unit_unknown": "liv.amounts_unit",
      "d.liv.no_currency": "liv.amounts_currency", "d.liv.cons_unconfirmed": "liv.amounts_unconfirmed",
    };
    const by: Record<string, string[]> = {};
    for (const [iso, sp] of Object.entries(ds.icp2021_spending)) {
      if (!inView(iso) || sp.consumption_month != null) continue;
      const e = ds.exclusions.find((x) => x.area === iso && x.scope === "living:split" && x.kind === "amounts");
      const k = (e && reason[(e.detail as Msg).k]) || "liv.amounts_missing";
      (by[k] ??= []).push(countryName(i, ds.countries[iso] ?? ds.economies[iso]));
    }
    return Object.entries(by).sort(([a], [b]) => a.localeCompare(b));
  }, [ds, scope.group, picks, i]);
  const compWageless = useMemo(() => Object.entries(ds.icp2021_spending)
    .filter(([iso, sp]) => inView(iso) && sp.consumption_month != null && !primaryWage(ds.countries[iso]?.years[sp.year], "monthly"))
    .map(([iso]) => countryName(i, ds.countries[iso] ?? ds.economies[iso])), [ds, scope.group, picks, i]);
  // Wage view of the composition: economies where employees are under half of the employed that year.
  const compMinority = useMemo(() => comp.filter((r) => (ds.countries[r.iso]?.years[spendYears[spendYears.length - 1] ?? ""]?.living.employees_share ?? 1) < 0.5)
    .map((r) => r.name), [comp, ds, spendYears]);
  // Wage view: economies in view with a composition but not drawn (no amounts or no wage that year).
  const notInView = useMemo(() => (mode !== "wage" ? [] : Object.keys(ds.icp2021_spending)
    .filter((iso) => inView(iso) && !comp.some((r) => r.iso === iso))
    .map((iso) => countryName(i, ds.countries[iso] ?? ds.economies[iso]))), [mode, comp, ds, scope.group, picks, i]);
  // In view but without an ICP composition (not published, or not passing the checks).
  const noComp = useMemo(() => Object.keys(ds.countries).filter((iso) => inView(iso) && !ds.icp2021_spending[iso])
    .map((iso) => countryName(i, ds.countries[iso])), [ds, scope.group, picks, i]);
  const spendYear = spendYears[spendYears.length - 1] ?? "";
  const groupNames = LIVING_GROUPS.map((g) => i.t(`liv.g.${g}`));
  const cOpt = useMemo(() => compositionOption({
    rows: comp, partNames: groupNames, extraName: i.t("liv.g.abroad"),
    totalName: i.t(mode === "wage" ? "liv.total_wage" : "liv.total_cons"),
    order: mode === "wage" ? (a, b) => b.total - a.total : (a, b) => b.parts[0] - a.parts[0],
    format: (v) => i.n(v, v > 0 && v < 0.1 ? "pct1" : "pct0"),
    ref: mode === "wage" ? { value: 1, label: i.t("liv.ref") } : undefined,
    endLabel: mode === "cons" ? (r) => i.t("liv.end_named", { v: r.parts.slice(0, NAMED).reduce((a, b) => a + b, 0) }) : undefined,
    splitNumber: narrow ? 2 : undefined,
    kv,
  }), [comp, mode, narrow, theme, i]);

  // ---- Card 3: over time, on each focus economy's one continuous wage series (breaks kept)
  const series = useMemo(() => picks.filter((iso) => ds.wage_gold_history[iso]).map((iso) => {
    const c = ds.countries[iso];
    const h = ds.wage_gold_history[iso];
    const gaps: number[] = []; // years of the series without World Bank consumption
    const unconfirmed: number[] = []; // ... with consumption that does not pass the currency-unit checks
    const points = yearlyLine(h.points.map(([y, wage, , , brk]) => {
      const L = c.years[y]?.living;
      const cons = L?.consumption_month;
      if (cons == null) (L?.consumption_unconfirmed ? unconfirmed : gaps).push(Number(y));
      return { y, v: cons != null && wage ? cons / wage : null, brk: !!brk };
    }));
    return { iso, name: countryName(i, c), points, colorIndex: slotOf[iso], gaps, unconfirmed,
      skipped: skippedYears(h.points.map((p) => p[0])), label: i.r(h.label) };
  }), [ds, picks, slotOf, i]);
  const trend = series.filter((s) => s.points.some(([, v]) => v != null));
  const trendNoCons = series.filter((s) => !s.points.some(([, v]) => v != null)).map((s) => s.name);
  const gapList = (key: "gaps" | "unconfirmed" | "skipped") => trend.filter((s) => s[key].length > 0)
    .map((s) => i.t("liv.trend_gap_item", { name: s.name, years: i.j(yearRanges(s[key]), "comma") }));
  const trendGaps = gapList("gaps"), trendUnconfirmed = gapList("unconfirmed"), trendSkipped = gapList("skipped");
  const noTrend = picks.filter((iso) => !ds.wage_gold_history[iso]).map((iso) => countryName(i, ds.countries[iso]));
  const tOpt = useMemo(() => linesOption({ series: trend, yName: i.t("liv.trend_axis"), format: pct }), [trend, theme, i]);

  return (
    <section className="block" id="living">
      <h2>{i.t("liv.title", { year })}</h2>
      <p className="sub">{i.j([i.t("liv.sub"), scope.view === "hourly" ? i.t("liv.hourly_note") : ""], "sentence")}</p>

      <div className="card">
        <h3>{i.t("liv.ratio_title", { year })}</h3>
        <Legend anyFocus={ratio.some((x) => x.highlight)} focus={i.t("legend.focus")} others={i.t("legend.others")} all={i.t("legend.all")}
          extra={<>
            <span><span className="sw" style={{ background: "var(--surface)", border: "1.5px solid var(--ink-2)", borderRadius: "50%" }} />{i.t("liv.other_name")}</span>
            {!sideless && <span><span className="sw" style={{ background: "var(--deemph)" }} />{i.t("liv.side")}</span>}
          </>} />
        {ratio.length > 0
          ? <Chart option={rOpt} height={rankingHeight(ratio.length) + 16} ariaLabel={i.t("liv.ratio_title", { year })} onPick={pick} />
          : <p className="muted">{i.t("liv.ratio_none", { year })}</p>}
        <p className="note">
          {i.j([
            i.t("liv.note_100"),
            i.t("liv.note_not"),
            govRange ? i.t("liv.note_gov", govRange) : "",
            ovs ? i.t("liv.note_sensitivity", { min: ovs.min, max: ovs.max, median: ovs.median, n: ovs.n, rlo: 1 / ovs.max, rhi: 1 / ovs.min }) : "",
            minority.length > 0 ? i.t("liv.note_minority", { list: i.j(minority, "enum") }) : "",
            switched.length > 0 ? i.t("liv.note_switch", { list: i.j(switched, "enum") }) : "",
            fiscal.length > 0 ? i.t("liv.note_fiscal", { list: i.j(fiscal, "enum") }) : "",
            noCons.length > 0 ? i.t("liv.missing_cons", { year, list: i.j(noCons, "enum") }) : "",
            unconfirmed.length > 0 ? i.t("liv.cons_unconfirmed", { year, list: i.j(unconfirmed, "enum") }) : "",
            noWage.length > 0 ? i.t("controls.missing_month", { year, list: i.j(noWage, "enum") }) : "",
          ], "sentence")}
        </p>
        <details>
          <summary>{i.t("table.show", { n: ratio.length })}</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr>
                <th>{i.t("col.economy")}</th><th>{i.t("liv.col_ratio")}</th><th>{i.t("liv.col_others")}</th><th>{i.t("liv.col_median")}</th>
                <th>{i.t("liv.col_cons")}</th><th className="l">{i.t("liv.col_wage")}</th><th>{i.t("liv.col_employees")}</th><th>{i.t("liv.col_residents")}</th>
              </tr></thead>
              <tbody>
                {[...ratio].sort((a, b) => b.value - a.value).map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}</td><td>{pct(r.value)}</td><td>{r.others.map((o) => pct(o.value)).join(" · ") || "—"}</td>
                    <td>{r.med != null ? pct(r.med) : "—"}</td><td>{money(i, r.cons, r.c.currency)}</td>
                    <td className="l">{money(i, r.wage.monthly_lcu, r.wage.currency ?? r.c.currency)}<div className="small muted">{wageLabel(i, r.wage, "monthly")}</div></td>
                    <td>{r.side != null ? pct(r.side) : "—"}</td><td>{r.residents != null ? i.n(r.residents, "d1") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <div className="card">
        <h3>{i.t("liv.where_title", { year: spendYear || "—" })}</h3>
        <p className="small ink2" style={{ margin: "0 0 8px" }}>{i.t("liv.where_sub", { years: i.j(spendYears, "enum") || "—" })}</p>
        <div className="seg" role="group" aria-label={i.t("liv.mode_label")}>
          <button aria-pressed={mode === "wage"} onClick={() => setMode("wage")}>{i.t("liv.mode_wage", { year: spendYear })}</button>
          <button aria-pressed={mode === "cons"} onClick={() => setMode("cons")}>{i.t("liv.mode_cons")}</button>
        </div>
        <div className="legend">
          {groupNames.map((g, k) => (
            <span key={g}><span className="sw" style={{ background: k === NAMED ? "var(--deemph)" : `var(--s${k + 1})` }} />{g}</span>
          ))}
          <span><span className="sw hatch" />{i.t("liv.g.abroad")}</span>
          <span><span className="sw tick" />{i.t("liv.tick")}</span>
        </div>
        {comp.length > 0
          ? <Chart option={cOpt} height={rankingHeight(comp.length) + 16} ariaLabel={i.t("liv.where_title", { year: spendYear })} onPick={pick} />
          : <p className="muted">{i.t("liv.where_none")}</p>}
        <p className="note">
          {i.j([
            i.t(mode === "wage" ? "liv.where_note_wage" : "liv.where_note_cons", { year: spendYear }),
            i.t("liv.where_note"),
            ...noAmounts.map(([k, list]) => i.t(k, { list: i.j(list, "enum"), year: spendYear, b: ds.constants.max_factor })),
            mode === "wage" && compMinority.length > 0 ? i.t("liv.note_minority", { list: i.j(compMinority, "enum") }) : "",
            mode === "wage" && compWageless.length > 0 ? i.t("liv.where_no_wage", { list: i.j(compWageless, "enum"), year: spendYear }) : "",
            notInView.length > 0 ? i.t("liv.where_not_in_view", { list: i.j(notInView, "enum"), mode: i.t("liv.mode_cons") }) : "",
            noComp.length > 0 ? i.t("liv.where_missing", { list: i.j(noComp, "enum") }) : "",
          ], "sentence")}
        </p>
        <details>
          <summary>{i.t("table.show", { n: comp.length })}</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>{i.t("col.economy")}</th><th>{i.t(mode === "wage" ? "liv.total_wage" : "liv.total_cons")}</th>{groupNames.map((g) => <th key={g}>{g}</th>)}<th>{i.t("liv.g.abroad")}</th></tr></thead>
              <tbody>
                {[...comp].sort((a, b) => b.total - a.total || b.parts[0] - a.parts[0]).map((r) => (
                  <tr key={r.iso}><td>{r.name}</td><td>{i.n(r.total, "pct0")}</td>{r.parts.map((v, k) => <td key={k}>{i.n(v, "pct1")}</td>)}<td>{r.known ? i.n(r.extra, "pct1") : "—"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      {picks.length === 0 ? (
        <FocusPrompt scope={scope} text={i.t("liv.trend_prompt")} />
      ) : (
        <div className="card">
          <h3>{i.t("liv.trend_title")}</h3>
          <div className="legend">
            {trend.map((s) => <span key={s.name}><span className="ln" style={{ background: `var(--s${s.colorIndex + 1})` }} />{s.name}</span>)}
          </div>
          {trend.length > 0 ? <Chart option={tOpt} height={300} ariaLabel={i.t("liv.trend_title")} /> : null}
          <p className="note">
            {i.j([
              i.t("liv.trend_note"),
              trend.length > 0 ? i.t("liv.trend_series", { list: i.j(trend.map((s) => i.t("liv.trend_series_item", { name: s.name, series: s.label })), "list") }) : "",
              trendSkipped.length > 0 ? i.t("liv.trend_skipped", { list: i.j(trendSkipped, "list") }) : "",
              trendGaps.length > 0 ? i.t("liv.trend_gaps", { list: i.j(trendGaps, "list") }) : "",
              trendUnconfirmed.length > 0 ? i.t("liv.trend_unconfirmed", { list: i.j(trendUnconfirmed, "list") }) : "",
              trendNoCons.length > 0 ? i.t("liv.trend_no_cons", { list: i.j(trendNoCons, "enum") }) : "",
              noTrend.length > 0 ? i.t("liv.trend_none", { list: i.j(noTrend, "enum") }) : "",
            ], "sentence")}
          </p>
        </div>
      )}
    </section>
  );
}
