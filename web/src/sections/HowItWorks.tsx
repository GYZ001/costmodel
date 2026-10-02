import { useMemo, useState } from "react";
import type { Scope } from "../App";
import { useI18n } from "../i18n";
import { byName, minutes, money, primaryWage, wageCurrency, wageLabel } from "../lib";
import { useRows } from "./common";

type SortKey = "name" | "gold" | "days_per_g" | "days" | "minutes" | "ppp";

/** The three steps, stated once for every economy, and a table of all economies in scope. */
export function HowItWorks(scope: Scope) {
  const i = useI18n();
  const { year, view, picks, togglePick } = scope;
  const hourly = view === "hourly";
  const rows = useRows(scope);
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "name", desc: false });

  const table = useMemo(() => {
    const out = rows.flatMap((r) => {
      const w = primaryWage(r.row, view);
      const lcu = hourly ? w?.hourly_lcu : w?.monthly_lcu;
      if (!w || !lcu) return [];
      const cohd = r.row.cohd.total;
      return [{
        ...r, w, lcu, cur: wageCurrency(w, r.c),
        gold: hourly ? w.hourly_gold_g : w.monthly_gold_g,
        days_per_g: r.row.cohd_days_per_g,
        days: cohd ? lcu / cohd : null,
        minutes: w.minutes_per_cohd_day,
        ppp: hourly ? w.hourly_ppp : w.monthly_ppp,
      }];
    });
    const cmp = byName(i);
    const val = (x: (typeof out)[number]) => (sort.key === "name" ? null : x[sort.key]);
    return out.sort((a, b) => {
      if (sort.key === "name") return (sort.desc ? -1 : 1) * cmp(a.name, b.name);
      const va = val(a), vb = val(b);
      if (va == null) return vb == null ? cmp(a.name, b.name) : 1; // missing values last
      if (vb == null) return -1;
      return (sort.desc ? vb - va : va - vb) || cmp(a.name, b.name);
    });
  }, [rows, view, hourly, sort, i]);
  const missing = rows.filter((r) => !table.some((x) => x.iso === r.iso)).map((r) => r.name).sort(byName(i));

  const th = (key: SortKey, label: string, cls = "") => (
    <th className={cls} aria-sort={sort.key === key ? (sort.desc ? "descending" : "ascending") : "none"}>
      <button className="sort" onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== "name" && key !== "minutes" }))}>
        {label}<span aria-hidden="true">{sort.key === key ? (sort.desc ? " ↓" : " ↑") : " ↕"}</span>
      </button>
    </th>
  );
  const per = hourly ? "hour" : "month";

  return (
    <section className="block" id="how">
      <h2>{i.t("how.title")}</h2>
      <p className="sub">{i.t(`how.sub_${per}`)}</p>
      <div className="chain" aria-label={i.t("how.steps_label")}>
        <div className="step">
          <div className="k">{i.t("how.step1_k")}</div>
          <div className="v">{i.t(`how.step1_v_${per}`)}</div>
          <div className="f">{i.t(`how.step1_f_${per}`)}</div>
        </div>
        <div className="arrow" aria-hidden>→</div>
        <div className="step">
          <div className="k">{i.t("how.step2_k")}</div>
          <div className="v">{i.t("how.step2_v")}</div>
          <div className="f">{i.t("how.step2_f")}</div>
        </div>
        <div className="arrow" aria-hidden>→</div>
        <div className="step">
          <div className="k">{i.t("how.step3_k")}</div>
          <div className="v">{i.t(`how.step3_v_${per}`)}</div>
          <div className="f">{i.t(`how.step3_f_${per}`)}</div>
        </div>
      </div>
      <div className="callout">
        <strong>{i.t("how.ruler_title")}</strong>{i.t("_sep.sentence")}{i.t("how.ruler_body")}
      </div>
      <div className="card">
        <h3>{i.t(`how.table_title_${per}`, { year })}</h3>
        <p className="small ink2" style={{ margin: "0 0 8px" }}>{i.t("how.table_hint")}</p>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                {th("name", i.t("col.economy"), "l nw")}
                <th className="l">{i.t("col.measure")}</th>
                <th>{i.t(`col.wage_lcu_${per}`)}</th>
                <th>{i.t("col.gold_lcu_g")}</th>
                {th("gold", i.t(`col.gold_per_${per}`))}
                {th("days_per_g", i.t("col.days_per_g"))}
                {th("days", i.t(`col.days_per_${per}`))}
                {hourly && th("minutes", i.t("col.minutes"))}
                {th("ppp", i.t(`col.ppp_${per}`))}
              </tr>
            </thead>
            <tbody>
              {table.map((x) => (
                <tr key={x.iso} className={picks.includes(x.iso) ? "focus" : undefined}>
                  <td className="l nw">
                    <button className="linkish" onClick={() => togglePick(x.iso)} title={i.t(picks.includes(x.iso) ? "controls.remove" : "controls.add_focus")}>{x.name}</button>
                  </td>
                  <td className="l small ink2" title={i.r(x.w.caveat) || undefined}>{wageLabel(i, x.w, view)}</td>
                  <td>{money(i, x.lcu, x.cur)}</td>
                  <td>{money(i, x.row.gold_lcu_g, x.c.currency, 1)}</td>
                  <td>{i.n(x.gold, "sig3")}</td>
                  <td>{i.n(x.days_per_g, "sig3")}</td>
                  <td>{i.n(x.days, "sig3")}</td>
                  {hourly && <td>{minutes(i, x.minutes)}</td>}
                  <td>{i.n(x.ppp, hourly ? "d1" : "d0")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          {i.j([missing.length > 0 ? i.t(`how.missing_${per}`, { year, list: i.j(missing, "enum") }) : "", i.t("how.note")], "sentence")}
        </p>
      </div>
    </section>
  );
}
