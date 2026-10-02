import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { linesOption } from "../charts";
import { useI18n } from "../i18n";
import { countryName, levelBoundsText, useThemeVersion } from "../lib";
import { FocusPrompt } from "./Profiles";

export function GoldRuler(scope: Scope) {
  const { ds, picks, slotOf } = scope;
  const i = useI18n();
  const theme = useThemeVersion();

  // The benchmark price as the World Bank publishes it (US dollars per troy ounce).
  const goldOpt = useMemo(() => linesOption({
    series: [{ name: i.t("ruler.gold_series"), points: ds.gold.monthly.map(([p, v]) => [p, v]), colorIndex: 3 }],
    yName: i.t("ruler.gold_axis"), format: (v) => i.n(v, "int"), log: true,
  }), [ds, theme, i]);
  const years = Object.keys(ds.gold.annual).filter((y) => y >= "2000").sort();
  const y0 = years[0], y1 = years[years.length - 1];
  const a0 = ds.gold.annual[y0]?.usd_oz, a1 = ds.gold.annual[y1]?.usd_oz;

  // Gold in each focus economy's own currency, as an index from the first year all of them have.
  const local = useMemo(() => {
    const have = picks.filter((iso) => ds.countries[iso]);
    const yearsOf = (iso: string) => Object.keys(ds.countries[iso].years).filter((y) => ds.countries[iso].years[y].gold_lcu_g != null);
    const common = have.length ? yearsOf(have[0]).filter((y) => have.every((iso) => ds.countries[iso].years[y]?.gold_lcu_g != null)).sort() : [];
    const base = common[0];
    return {
      base,
      series: base ? have.map((iso) => {
        const c = ds.countries[iso];
        const b = c.years[base].gold_lcu_g!;
        return {
          name: countryName(i, c),
          points: yearsOf(iso).filter((y) => y >= base).sort().map((y) => [y, (c.years[y].gold_lcu_g! / b) * 100] as [string, number]),
          colorIndex: slotOf[iso],
        };
      }) : [],
    };
  }, [ds, picks, slotOf, i]);
  const localOpt = useMemo(() => linesOption({
    series: local.series, yName: i.t("ruler.local_axis", { year: local.base ?? "" }), format: (v) => i.n(v, "int"), log: true, xType: "category",
  }), [local, theme, i]);

  const hist = useMemo(() => picks
    .filter((iso) => ds.wage_gold_history[iso])
    .map((iso) => ({
      iso,
      name: countryName(i, ds.countries[iso]),
      // A null point before a series break stops the line from bridging two different concepts.
      points: ds.wage_gold_history[iso].points.flatMap(([y, , g, , brk]) =>
        brk ? [[`${Number(y) - 1}-07`, null], [`${y}`, g]] : [[`${y}`, g]]) as [string, number | null][],
      colorIndex: slotOf[iso],
    })), [ds, picks, slotOf, i]);
  const noHistory = picks.filter((iso) => !ds.wage_gold_history[iso]).map((iso) => countryName(i, ds.countries[iso]));
  const breaks = picks
    .filter((iso) => ds.wage_gold_history[iso])
    .flatMap((iso) => ds.wage_gold_history[iso].points.filter((p) => p[4])
      .map((p) => i.t("ruler.break_item", { name: countryName(i, ds.countries[iso]), year: p[0], why: i.r(p[5]) })));
  const histOpt = useMemo(() => linesOption({
    series: hist, yName: i.t("ruler.hist_axis"), format: (v) => i.n(v, "sig2"), log: true,
  }), [hist, theme, i]);

  return (
    <section className="block" id="ruler">
      <h2>{i.t("ruler.title")}</h2>
      <p className="sub">{i.t("ruler.sub")}</p>
      {a0 && a1 && (
        <div className="callout">
          {i.t(a1 >= a0 ? "ruler.callout_up" : "ruler.callout_down", { y0, y1, a0: i.n(a0, "int"), a1: i.n(a1, "int"), r: i.n(a1 / a0, "d1") })}
        </div>
      )}
      <div className="card">
        <h3>{i.t("ruler.gold_title")}</h3>
        <Chart option={goldOpt} height={300} ariaLabel={i.t("ruler.gold_title")} />
        <p className="note">{i.t("ruler.gold_note")}</p>
      </div>
      {picks.length === 0 ? (
        <FocusPrompt scope={scope} text={i.t("ruler.prompt")} />
      ) : (
        <div className="grid2">
          <div className="card">
            <h3>{i.t("ruler.local_title")}</h3>
            <Legend series={local.series.map((s) => ({ name: s.name, colorIndex: s.colorIndex }))} />
            {local.base ? <Chart option={localOpt} height={320} ariaLabel={i.t("ruler.local_title")} /> : <p className="muted">{i.t("ruler.local_none")}</p>}
            <p className="note">{i.t("ruler.local_note", { year: local.base ?? "—" })}</p>
          </div>
          <div className="card">
            <h3>{i.t("ruler.hist_title")}</h3>
            <Legend series={hist} />
            <Chart option={histOpt} height={320} ariaLabel={i.t("ruler.hist_title")} />
            <p className="note">
              {i.t("ruler.hist_note")}{" "}
              {i.t("ruler.hist_labels", {
                list: i.j(hist.map((s) => {
                  const h = ds.wage_gold_history[s.iso];
                  const notes = i.r(h.notes);
                  return i.t(notes ? "ruler.hist_label_notes" : "ruler.hist_label", { name: s.name, label: i.r(h.label), notes });
                })),
              })}{" "}
              {i.t("ruler.hist_rule")}{" "}
              {i.t("ruler.hist_breaks", { bounds: levelBoundsText(i, ds, "hfce") })}{" "}
              {i.t("ruler.isolated")}
              {breaks.length > 0 && <> {i.t("ruler.breaks", { list: i.j(breaks) })}</>}
              {noHistory.length > 0 && <> {i.t("ruler.no_history", { list: i.j(noHistory, "enum") })}</>}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

function Legend({ series }: { series: { name: string; colorIndex: number }[] }) {
  return (
    <div className="legend">
      {series.map((s) => (
        <span key={s.name}><span className="ln" style={{ background: `var(--s${s.colorIndex + 1})` }} />{s.name}</span>
      ))}
    </div>
  );
}
