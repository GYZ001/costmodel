import { useMemo, useState } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { rankingHeight, rankingOption, type RankItem } from "../charts";
import { useI18n } from "../i18n";
import { money, useThemeVersion } from "../lib";
import { Legend, useKV, usePickByName, useRows } from "./common";

type Measure = "diet" | "consumption";

export function GoldBuys(scope: Scope) {
  const i = useI18n();
  const kv = useKV();
  const theme = useThemeVersion();
  const rows = useRows(scope);
  const pick = usePickByName(rows, scope.togglePick);
  const [m, setM] = useState<Measure>("diet");
  const items: RankItem[] = useMemo(
    () =>
      rows.flatMap(({ iso, c, name, year, row }) => {
        const v = m === "diet" ? row.cohd_days_per_g : row.gold_usdeq_g;
        if (!v) return [];
        const tip = m === "diet"
          ? [i.t("buys.tip_gold", { price: money(i, row.gold_lcu_g, c.currency) }), i.t("buys.tip_diet", { cost: money(i, row.cohd.total, c.currency), year })]
          : [i.t("buys.tip_pli", { pli: i.n(row.pli_hfce, "d2"), year }), i.t("buys.tip_usd", { usd: i.n(row.gold_usd_g, "d1") })];
        return [{ id: iso, name, value: v, highlight: scope.picks.includes(iso), tip }];
      }),
    [rows, m, scope.picks, i],
  );
  const option = useMemo(
    () => rankingOption({
      items,
      valueName: i.t(m === "diet" ? "buys.value_diet" : "buys.value_consumption"),
      format: (v) => (m === "diet" ? i.t("u.days", { n: i.n(v, "sig2") }) : i.t("u.intl_dollars", { n: i.n(v, "int") })),
      kv,
    }),
    [items, m, theme, i],
  );
  return (
    <section className="block" id="buys">
      <h2>{i.t("buys.title", { year: scope.year })}</h2>
      <p className="sub">{i.t("buys.sub")}</p>
      <div className="card">
        <div className="controls">
          <span className="seg" role="group" aria-label={i.t("buys.measure")}>
            <button aria-pressed={m === "diet"} onClick={() => setM("diet")}>{i.t("buys.diet")}</button>
            <button aria-pressed={m === "consumption"} onClick={() => setM("consumption")}>{i.t("buys.consumption")}</button>
          </span>
        </div>
        <Legend anyFocus={items.some((x) => x.highlight)} focus={i.t("legend.focus")} others={i.t("legend.others")} all={i.t("legend.all")} />
        <Chart option={option} height={rankingHeight(items.length)} ariaLabel={i.t("buys.aria")} onPick={pick} />
        <p className="note">{i.t(m === "diet" ? "buys.note_diet" : "buys.note_consumption")}</p>
        <details>
          <summary>{i.t("table.show", { n: i.n(items.length, "int") })}</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>{i.t("col.economy")}</th><th>{i.t(m === "diet" ? "buys.col_diet" : "buys.col_consumption")}</th><th className="l">{i.t("col.basis")}</th></tr></thead>
              <tbody>
                {[...items].sort((a, b) => b.value - a.value).map((x) => (
                  <tr key={x.id}><td>{x.name}</td><td>{i.n(x.value, m === "diet" ? "sig3" : "d1")}</td><td className="l small ink2">{i.j(x.tip)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </section>
  );
}
