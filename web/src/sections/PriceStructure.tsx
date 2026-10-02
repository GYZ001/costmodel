import { useMemo, useState } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { heatmapOption } from "../charts";
import { useI18n } from "../i18n";
import { byName, countryName, quantile, useThemeVersion } from "../lib";

// ICP 2021 categories shown (catalog keys cat.<key>).
const CATS = ["hfce", "food_nonalc", "bread_cereals", "meat", "milk_cheese_eggs", "fruit", "vegetables",
  "clothing", "housing", "health", "transport", "communication", "education", "restaurants_hotels"];
// Goods traded across borders vs local services, for the spread across economies.
const FOOD = "food_nonalc";
const SERVICES = ["housing", "health", "education", "restaurants_hotels"];

export function PriceStructure(scope: Scope) {
  const i = useI18n();
  const theme = useThemeVersion();
  const { ds, group, picks } = scope;
  const pli = ds.icp2021_pli;
  // Base of comparison: the world average (ICP's own index base) or any economy.
  const [base, setBase] = useState<string>("WORLD");
  const baseOf = (cat: string): number | null => (base === "WORLD" ? 100 : pli[base]?.[cat] ?? null);

  const { rows, values, isos } = useMemo(() => {
    const isos = Object.keys(pli)
      .filter((iso) => ds.countries[iso] && (group === "all" || ds.countries[iso].g20 || picks.includes(iso)))
      .sort((a, b) => (pli[b].hfce ?? 0) - (pli[a].hfce ?? 0));
    const rows = isos.map((iso) => countryName(i, ds.countries[iso]));
    const values: [number, number, number | null][] = [];
    isos.forEach((iso, r) => CATS.forEach((cat, c) => {
      const v = pli[iso][cat], b = baseOf(cat);
      values.push([c, r, v != null && b ? v / b : null]);
    }));
    return { rows, values, isos };
  }, [ds, group, picks, i, base]);
  const hl = useMemo(() => new Set(picks.filter((p) => ds.countries[p]).map((p) => countryName(i, ds.countries[p]))), [ds, picks, i]);
  const baseName = base === "WORLD" ? i.t("ps.world") : countryName(i, ds.countries[base]);
  const option = useMemo(() => heatmapOption({
    rows, cols: CATS.map((c) => i.t(`catshort.${c}`)), values, highlightRows: hl,
    label: (r) => i.n(r * 100, "int"),
    tip: (r) => i.t("ps.tip", { v: i.n(r * 100, "int"), base: baseName }),
  }), [rows, values, hl, theme, i, baseName]);

  // How widely price levels differ across all economies ICP covers: the ratio of the
  // 75th to the 25th percentile (independent of the base of comparison).
  const spread = useMemo(() => {
    const all = Object.values(pli);
    const of = (cat: string) => {
      const v = all.map((r) => r[cat]).filter((x): x is number => x != null);
      const q1 = quantile(v, 0.25), q3 = quantile(v, 0.75);
      return { name: i.t(`cat.${cat}`), n: v.length, ratio: q1 && q3 ? q3 / q1 : null };
    };
    return { food: of(FOOD), services: SERVICES.map(of) };
  }, [pli, i]);
  const baseOptions = useMemo(() => {
    const cmp = byName(i);
    return Object.keys(pli).filter((iso) => ds.countries[iso]).map((iso) => [iso, countryName(i, ds.countries[iso])] as const)
      .sort((a, b) => cmp(a[1], b[1]));
  }, [pli, ds, i]);

  return (
    <section className="block" id="structure">
      <h2>{i.t("ps.title")}</h2>
      <p className="sub">
        {i.j([
          i.t("ps.sub"),
          i.t("ps.spread", {
            n: spread.food.n,
            food: spread.food.ratio,
            services: i.j(spread.services.map((s) => i.t("ps.spread_item", { name: s.name, r: s.ratio })), "enum"),
          }),
          spread.food.ratio != null && spread.services.every((s) => s.ratio != null && s.ratio > spread.food.ratio!) ? i.t("ps.spread_conclusion") : "",
        ], "sentence")}
      </p>
      <div className="card">
        <div className="controls">
          <label>
            {i.t("ps.base")}{" "}
            <select value={base} onChange={(e) => setBase(e.target.value)}>
              <option value="WORLD">{i.t("ps.world")}</option>
              {baseOptions.map(([iso, name]) => <option key={iso} value={iso}>{name}</option>)}
            </select>
          </label>
        </div>
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--div-neg)" }} />{i.t("ps.cheaper", { base: baseName })}</span>
          <span><span className="sw" style={{ background: "var(--div-mid)", border: "1px solid var(--axis)" }} />{i.t("ps.same", { base: baseName })}</span>
          <span><span className="sw" style={{ background: "var(--div-pos)" }} />{i.t("ps.dearer", { base: baseName })}</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <div style={{ minWidth: 980 }}>
            <Chart option={option} height={Math.max(220, isos.length * 26 + 60)} ariaLabel={i.t("ps.aria", { base: baseName })} />
          </div>
        </div>
        <p className="note">{i.j([i.t("ps.note_index", { base: baseName }), i.t("ps.note_cols"), i.t("ps.note_year")], "sentence")}</p>
      </div>
    </section>
  );
}
