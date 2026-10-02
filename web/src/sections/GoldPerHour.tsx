import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { rankingHeight, rankingOption, type RankItem } from "../charts";
import { useI18n } from "../i18n";
import { fxNote, grams, money, otherWages, primaryWage, typicalWage, useThemeVersion, wageNotes } from "../lib";
import { Legend, useKV, usePickByName, useRows } from "./common";

export function GoldPerHour(scope: Scope) {
  const i = useI18n();
  const kv = useKV();
  const theme = useThemeVersion();
  const rows = useRows(scope);
  const hourly = scope.view === "hourly";
  const per = hourly ? "hour" : "month";
  const pick = usePickByName(rows, scope.togglePick);
  const items: RankItem[] = useMemo(
    () =>
      rows.flatMap(({ iso, c, name, year, row }) => {
        const w = primaryWage(row, scope.view);
        const v = hourly ? w?.hourly_gold_g : w?.monthly_gold_g;
        if (!w || !v) return [];
        const t = typicalWage(row, scope.view);
        const median = (x: string, k: number) => (k === 0 ? i.t("gold.median_line", { text: x }) : x);
        return [{
          id: iso,
          name,
          value: v,
          secondary: (hourly ? t?.hourly_gold_g : t?.monthly_gold_g) ?? null,
          highlight: scope.picks.includes(iso),
          tip: [
            ...wageNotes(i, w, scope.view, c, 160),
            ...(t ? wageNotes(i, t, scope.view, c, 120).map(median) : []),
            i.t("gold.local_price", { price: money(i, row.gold_lcu_g, c.currency), year }),
            ...fxNote(i, row, c),
          ],
          table: [
            ...wageNotes(i, w, scope.view, c),
            ...(t ? wageNotes(i, t, scope.view, c).map(median) : []),
            ...fxNote(i, row, c),
            ...otherWages(i, row, w, scope.view, c),
          ],
        }];
      }),
    [rows, scope.picks, scope.view, hourly, i],
  );
  // Largest gap between the official rate and the World Bank's GDP conversion factor, over the economies drawn.
  const fxGap = useMemo(() => {
    const ds = rows.filter(({ row }) => primaryWage(row, scope.view)).map(({ row }) => row.fx_vs_gdp_factor).filter((d): d is number => d != null);
    return ds.length ? Math.max(...ds.map((d) => Math.max(d, 1 / d))) - 1 : null;
  }, [rows, scope.view]);
  const option = useMemo(
    () => rankingOption({
      items,
      valueName: i.t(`gold.value_${per}`),
      secondaryName: i.t(`gold.secondary_${per}`),
      format: (v) => grams(i, v, 2),
      kv,
    }),
    [items, theme, per, i],
  );
  const ovs = scope.ds.oecd_vs_survey;

  return (
    <section className="block" id="gold">
      <h2>{i.t(`gold.title_${per}`, { year: scope.year })}</h2>
      <p className="sub">{i.t("gold.sub", { year: scope.year })}</p>
      <div className="card">
        <Legend anyFocus={items.some((x) => x.highlight)} focus={i.t(`legend.focus_${per}`)} others={i.t("legend.others")} all={i.t(`legend.all_${per}`)}
          extra={<span><span className="sw" style={{ background: "var(--s2)", borderRadius: "50%" }} />{i.t(`gold.legend_median_${per}`)}</span>} />
        <Chart option={option} height={rankingHeight(items.length)} ariaLabel={i.t(`gold.aria_${per}`)} onPick={pick} />
        <p className="note">
          {i.t("gold.note_order")}{" "}
          {ovs && <>{i.t("gold.note_concepts", { min: i.n(ovs.min, "d2"), max: i.n(ovs.max, "d2"), n: i.n(ovs.n, "int") })} </>}
          {i.t("gold.note_median")}{" "}
          {i.t("gold.note_sources")}{" "}
          {fxGap != null
            ? i.t("gold.note_fx_gap", { year: scope.year, pct: i.n(fxGap * 100, "sig2"), mf: i.n(scope.ds.constants.max_factor, "d1") })
            : i.t("gold.note_fx", { mf: i.n(scope.ds.constants.max_factor, "d1") })}
        </p>
        <DataTable items={items} per={per} />
      </div>
    </section>
  );
}

function DataTable({ items, per }: { items: RankItem[]; per: string }) {
  const i = useI18n();
  const sorted = [...items].sort((a, b) => b.value - a.value);
  return (
    <details>
      <summary>{i.t("table.show", { n: i.n(items.length, "int") })}</summary>
      <div className="table-scroll">
        <table className="data">
          <thead>
            <tr><th>{i.t("col.economy")}</th><th>{i.t(`gold.col_mean_${per}`)}</th><th>{i.t(`gold.col_median_${per}`)}</th><th className="l">{i.t("col.notes")}</th></tr>
          </thead>
          <tbody>
            {sorted.map((x) => (
              <tr key={x.id}>
                <td>{x.name}</td>
                <td>{i.n(x.value, "sig3")}</td>
                <td>{i.n(x.secondary ?? null, "sig3")}</td>
                <td className="l small ink2">{i.j(x.table ?? x.tip)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
