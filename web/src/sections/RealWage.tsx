import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { dumbbellOption, rankingHeight, rankingOption, stackedOption, type RankItem } from "../charts";
import { useI18n } from "../i18n";
import { countryName, foodGroupYears, minutes, money, primaryWage, useThemeVersion, wageNotes } from "../lib";
import type { CohdKey } from "../types";
import { Legend, useKV, usePickByName, useRows } from "./common";

const GROUPS: CohdKey[] = ["staples", "vegetables", "fruits", "animal", "legumes", "oils"];

export function RealWage(scope: Scope) {
  const i = useI18n();
  const kv = useKV();
  const theme = useThemeVersion();
  const rows = useRows(scope);
  const pick = usePickByName(rows, scope.togglePick);
  const hourly = scope.view === "hourly";
  const per = hourly ? "hour" : "month";

  // Economies with a primary wage that cannot be drawn: no proven exchange rate or PPP that year.
  const undrawn = useMemo(
    () => rows.filter(({ row }) => {
      const w = primaryWage(row, scope.view);
      return w && !((hourly ? w.hourly_gold_g : w.monthly_gold_g) && (hourly ? w.hourly_ppp : w.monthly_ppp));
    }).map((r) => r.name),
    [rows, hourly, scope.view],
  );

  // The same wage in US dollars at the market exchange rate (= grams of gold × the dollar
  // price of a gram) and in international dollars at purchasing power parity.
  const dumb = useMemo(() => rows.flatMap(({ iso, c, name, row }) => {
    const w = primaryWage(row, scope.view);
    const g = hourly ? w?.hourly_gold_g : w?.monthly_gold_g;
    const p = hourly ? w?.hourly_ppp : w?.monthly_ppp;
    if (!w || !g || !p) return [];
    return [{ name, a: g * row.gold_usd_g, b: p, highlight: scope.picks.includes(iso), tip: wageNotes(i, w, scope.view, c, 160) }];
  }), [rows, hourly, scope.view, scope.picks, i]);

  const dietMinutes: RankItem[] = useMemo(
    () => rows.flatMap(({ iso, c, name, row }) => {
      const w = primaryWage(row, "hourly");
      if (!w?.minutes_per_cohd_day) return [];
      return [{
        id: iso, name, value: w.minutes_per_cohd_day, highlight: scope.picks.includes(iso),
        tip: [...wageNotes(i, w, "hourly", c, 160), i.t("real.tip_diet", { cost: money(i, row.cohd.total, c.currency) })],
      }];
    }),
    [rows, scope.picks, i],
  );

  // The food-group split exists only for some benchmark years (in the archive so far: 2021); the chart uses the latest.
  const groupYears = useMemo(() => foodGroupYears(scope.ds), [scope.ds]);
  const groupYear = groupYears[groupYears.length - 1] ?? "";
  const diet = useMemo(() => Object.entries(scope.ds.countries)
    .filter(([iso, c]) => scope.group === "all" || c.g20 || scope.picks.includes(iso))
    .flatMap(([iso, c]) => {
      const row = c.years[groupYear];
      const w = primaryWage(row, "hourly");
      if (!row || !w?.hourly_lcu || !row.cohd.total || GROUPS.some((g) => row.cohd[g] == null)) return [];
      const parts = GROUPS.map((g) => ((row.cohd[g] as number) / w.hourly_lcu!) * 60);
      return [{
        name: countryName(i, c), parts, total: parts.reduce((a, b) => a + b, 0),
        highlight: scope.picks.includes(iso), tip: wageNotes(i, w, "hourly", c, 160),
      }];
    }), [scope.ds, scope.group, scope.picks, groupYear, i]);

  const monthDays: RankItem[] = useMemo(
    () => rows.flatMap(({ iso, c, name, row }) => {
      const w = primaryWage(row, "monthly");
      if (!w?.cohd_days_per_month) return [];
      return [{
        id: iso, name, value: w.cohd_days_per_month, highlight: scope.picks.includes(iso),
        tip: [...wageNotes(i, w, "monthly", c, 160), i.t("real.tip_diet", { cost: money(i, row.cohd.total, c.currency) })],
      }];
    }),
    [rows, scope.picks, i],
  );

  const dollars = (v: number) => i.n(v, "sig3");
  const dOpt = useMemo(() => dumbbellOption({
    rows: dumb, aName: i.t(`real.a_${per}`), bName: i.t(`real.b_${per}`), format: dollars, kv,
  }), [dumb, theme, per, i]);
  const groupNames = GROUPS.map((g) => i.t(`food.${g}`));
  const sOpt = useMemo(() => stackedOption({
    rows: diet, partNames: groupNames, totalName: i.t("real.total"),
    format: (v) => i.t("u.min_short", { n: i.n(v, v > 0 && v < 10 ? "d1" : "d0") }), kv,
  }), [diet, theme, i]);
  const dmOpt = useMemo(() => rankingOption({
    items: dietMinutes, valueName: i.t("real.minutes_value"), format: (v) => i.t("u.min", { n: i.n(v, "sig2") }), kv,
  }), [dietMinutes, theme, i]);
  const mOpt = useMemo(() => rankingOption({
    items: monthDays, valueName: i.t("real.days_value"), format: (v) => i.t("u.days", { n: v }), kv,
  }), [monthDays, theme, i]);

  return (
    <section className="block" id="real">
      <h2>{i.t("real.title", { year: scope.year })}</h2>
      <p className="sub">{i.t(`real.sub_${per}`)}</p>
      <div className="card">
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--deemph)", borderRadius: "50%" }} />{i.t(`real.a_${per}`)}</span>
          <span><span className="sw" style={{ background: "var(--accent)", borderRadius: "50%" }} />{i.t(`real.b_${per}`)}</span>
        </div>
        <Chart option={dOpt} height={rankingHeight(dumb.length)} ariaLabel={i.t(`real.aria_${per}`)} onPick={pick} />
        <p className="note">
          {i.j([i.t("real.note"), undrawn.length > 0 ? i.t(`real.undrawn_${per}`, { list: i.j(undrawn, "enum") }) : ""], "sentence")}
        </p>
        <details>
          <summary>{i.t("table.show", { n: dumb.length })}</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>{i.t("col.economy")}</th><th>{i.t(`real.a_${per}`)}</th><th>{i.t(`real.b_${per}`)}</th><th>{i.t("real.col_ratio")}</th></tr></thead>
              <tbody>
                {[...dumb].sort((x, y) => y.b - x.b).map((r) => (
                  <tr key={r.name}><td>{r.name}</td><td>{dollars(r.a)}</td><td>{dollars(r.b)}</td><td>{i.n(r.b / r.a, "d2")}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      {hourly ? (
        <>
          <div className="card">
            <h3>{i.t("real.minutes_title", { year: scope.year })}</h3>
            <p className="small ink2" style={{ margin: "0 0 8px" }}>{i.t("real.minutes_sub")}</p>
            <Legend anyFocus={dietMinutes.some((x) => x.highlight)} focus={i.t("legend.focus")} others={i.t("legend.others")} all={i.t("legend.all")} />
            <Chart option={dmOpt} height={rankingHeight(dietMinutes.length)} ariaLabel={i.t("real.minutes_aria")} onPick={pick} />
          </div>
          <div className="card">
            <h3>{i.t("real.groups_title", { year: groupYear || "—" })}</h3>
            <p className="small ink2" style={{ margin: "0 0 8px" }}>
              {i.t("real.groups_sub", { years: i.j(groupYears, "enum") || "—", year: groupYear || "—" })}
            </p>
            <div className="legend">
              {groupNames.map((g, k) => (
                <span key={g}><span className="sw" style={{ background: `var(--s${k + 1})` }} />{g}</span>
              ))}
            </div>
            {diet.length ? (
              <Chart option={sOpt} height={rankingHeight(diet.length)} ariaLabel={i.t("real.groups_aria", { year: groupYear })} />
            ) : (
              <p className="muted">{i.t("real.groups_none", { year: groupYear || "—" })}</p>
            )}
            <details>
              <summary>{i.t("table.show", { n: diet.length })}</summary>
              <div className="table-scroll">
                <table className="data">
                  <thead><tr><th>{i.t("col.economy")}</th><th>{i.t("real.total")}</th>{groupNames.map((g) => <th key={g}>{i.t("real.col_group_min", { group: g })}</th>)}</tr></thead>
                  <tbody>
                    {[...diet].sort((a, b) => a.total - b.total).map((r) => (
                      <tr key={r.name}><td>{r.name}</td><td>{minutes(i, r.total)}</td>{r.parts.map((p, k) => <td key={k}>{i.n(p, "d1")}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        </>
      ) : (
        <div className="card">
          <h3>{i.t("real.days_title")}</h3>
          <Legend anyFocus={monthDays.some((x) => x.highlight)} focus={i.t("legend.focus")} others={i.t("legend.others")} all={i.t("legend.all")} />
          <Chart option={mOpt} height={rankingHeight(monthDays.length)} ariaLabel={i.t("real.days_aria")} onPick={pick} />
          <p className="note">{i.t("real.days_note")}</p>
        </div>
      )}
    </section>
  );
}
