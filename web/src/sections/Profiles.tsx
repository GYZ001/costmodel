import { useMemo } from "react";
import type { Scope } from "../App";
import { useI18n } from "../i18n";
import { byName, countryName, grams, minutes, money, wageCurrency, wageLabel } from "../lib";
import type { Country, Wage } from "../types";
import { scopeLabel } from "./Methods";

/** For each focus economy: the wage figures used for it that year, its rates and prices,
 *  and what was left out and why - the same layout for every economy. */
export function Profiles(scope: Scope) {
  const i = useI18n();
  const { ds, picks } = scope;
  return (
    <section className="block" id="profiles">
      <h2>{i.t("prof.title")}</h2>
      <p className="sub">{i.t("prof.sub")}</p>
      {picks.length === 0 ? (
        <FocusPrompt scope={scope} text={i.t("prof.prompt")} />
      ) : (
        picks.map((iso) => <Profile key={iso} scope={scope} iso={iso} c={ds.countries[iso]} />)
      )}
    </section>
  );
}

/** Shown where a section needs focus economies: a one-click list of the G20 member
 *  countries (any other economy can be added from the list at the top). */
export function FocusPrompt({ scope, text }: { scope: Scope; text: string }) {
  const i = useI18n();
  const members = useMemo(() => {
    const cmp = byName(i);
    return Object.entries(scope.ds.countries).filter(([, c]) => c.g20).map(([iso, c]) => [iso, countryName(i, c)] as const)
      .sort((a, b) => cmp(a[1], b[1]));
  }, [scope.ds, i]);
  return (
    <div className="card prompt">
      <p style={{ margin: "0 0 8px" }}>{i.j([text, i.t("focus.chips_g20")], "sentence")}</p>
      <div className="chips">
        {members.map(([iso, name]) => (
          <button key={iso} className="chip" aria-pressed="false" onClick={() => scope.togglePick(iso)}>{name}</button>
        ))}
      </div>
    </div>
  );
}

function roleText(i: ReturnType<typeof useI18n>, w: Wage): string[] {
  const out: string[] = [];
  if (w.role === "primary") out.push(i.t("prof.role_primary_hour"));
  if (w.mrole === "primary") out.push(i.t("prof.role_primary_month"));
  if (w.role === "typical" || w.mrole === "typical") out.push(i.t("prof.role_typical"));
  return out;
}

function Profile({ scope, iso, c }: { scope: Scope; iso: string; c: Country }) {
  const i = useI18n();
  const { ds } = scope;
  const years = Object.keys(c.years).sort();
  const year = c.years[scope.year] ? scope.year : years[years.length - 1];
  const row = c.years[year];
  const name = countryName(i, c);
  const pli = ds.icp2021_pli[iso]?.hfce;
  const excl = ds.exclusions.filter((e) => e.area === iso && (e.year === year || e.year === "*"));
  const wages = [...row.wages].sort((a, b) => Number(!(a.role || a.mrole)) - Number(!(b.role || b.mrole)));

  return (
    <div className="card profile">
      <h3>
        <span className="sw" style={{ background: `var(--s${scope.slotOf[iso] + 1})`, borderRadius: "50%" }} /> {name} · {year}
      </h3>
      {year !== scope.year && <p className="small muted" style={{ margin: "0 0 6px" }}>{i.t("prof.other_year", { year: scope.year, shown: year })}</p>}
      <dl className="facts">
        <div><dt>{i.t("prof.currency")}</dt><dd>{c.currency ?? "—"}</dd></div>
        <div><dt>{i.t("prof.fx")}</dt><dd>{row.fx != null ? i.t("prof.fx_value", { fx: i.n(row.fx, "d4"), cur: c.currency ?? i.t("u.lcu") }) : "—"}</dd></div>
        <div><dt>{i.t("prof.ppp")}</dt><dd>{row.ppp_hfce != null ? i.t("prof.ppp_value", { v: i.n(row.ppp_hfce, "d4"), cur: c.currency ?? i.t("u.lcu") }) : "—"}</dd></div>
        <div><dt>{i.t("prof.gold")}</dt><dd>{row.gold_lcu_g != null ? i.t("u.per_gram", { v: money(i, row.gold_lcu_g, c.currency) }) : "—"}</dd></div>
        <div><dt>{i.t("prof.diet")}</dt><dd>{row.cohd.total != null ? i.t("u.per_day", { v: money(i, row.cohd.total, c.currency) }) : "—"}</dd></div>
        <div><dt>{i.t("prof.pli")}</dt><dd>{pli != null ? i.n(pli, "int") : "—"}</dd></div>
      </dl>

      {wages.length > 0 && <div className="table-scroll">
        <table className="data">
          <thead>
            <tr>
              <th className="l">{i.t("col.measure")}</th>
              <th>{i.t("col.monthly")}</th>
              <th>{i.t("col.hourly")}</th>
              <th>{i.t("col.gold_per_month")}</th>
              <th>{i.t("col.gold_per_hour")}</th>
              <th>{i.t("col.ppp_hour")}</th>
              <th>{i.t("col.minutes")}</th>
            </tr>
          </thead>
          <tbody>
            {wages.map((w) => {
              const cur = wageCurrency(w, c);
              const roles = roleText(i, w);
              return (
                <tr key={w.key}>
                  <td className="l">
                    <div>{wageLabel(i, w, w.hourly_lcu != null ? "hourly" : "monthly")}</div>
                    <div className="small muted">{i.r(w.source)}{roles.length > 0 && <> · {i.j(roles, "enum")}</>}</div>
                  </td>
                  <td>{money(i, w.monthly_lcu, cur)}</td>
                  <td>{money(i, w.hourly_lcu, cur)}{w.hours_week ? <div className="small muted">{i.t("prof.hours", { h: i.n(w.hours_week, "d1") })}</div> : null}</td>
                  <td>{grams(i, w.monthly_gold_g)}</td>
                  <td>{grams(i, w.hourly_gold_g)}</td>
                  <td>{i.n(w.hourly_ppp, "d1")}</td>
                  <td>{minutes(i, w.minutes_per_cohd_day)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>}
      {wages.length === 0 && <p className="muted">{i.t("prof.no_wages", { year })}</p>}

      {wages.length > 0 && <details>
        <summary>{i.t("prof.notes_summary")}</summary>
        <dl className="small ink2 notes">
          {wages.map((w) => (
            <div key={w.key}>
              <dt>{wageLabel(i, w, "monthly")} — {i.r(w.source)}</dt>
              <dd>{i.t("prof.method", { text: i.r(w.method) })}</dd>
              {w.caveat.length > 0 && <dd>{i.t("prof.caveat", { text: i.r(w.caveat) })}</dd>}
            </div>
          ))}
        </dl>
      </details>}
      {excl.length > 0 && (
        <details>
          <summary>{i.t("prof.excl_summary", { n: excl.length })}</summary>
          <ul className="small ink2">
            {excl.map((e, k) => (
              <li key={k}>
                {i.t("prof.excl_item", { item: scopeLabel(i, e.scope), kind: i.t(`kind.${e.kind}`), detail: e.detail })}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
