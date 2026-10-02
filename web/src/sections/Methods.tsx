import { useMemo } from "react";
import type { Dataset } from "../types";
import { useI18n } from "../i18n";
import { byName, countryName, levelBoundsText } from "../lib";

/** Catalog key naming each kind of excluded input (dataset.exclusions[].scope). */
export const SCOPE_KEYS: Record<string, string> = {
  fx: "scope.fx",
  ppp: "scope.ppp",
  cohd: "scope.cohd",
  currency: "scope.currency",
  hours: "scope.hours",
  area: "scope.area",
  "wage:cn": "scope.wage_cn",
  "wage:bls": "scope.wage_bls",
  "wage:oecd": "scope.wage_oecd",
  "wage:ilo_monthly_mean": "scope.ilo_monthly_mean",
  "wage:ilo_monthly_median": "scope.ilo_monthly_median",
  "wage:ilo_hourly_mean": "scope.ilo_hourly_mean",
  "wage:ilo_hourly_median": "scope.ilo_hourly_median",
};

// The branch the site and its dataset were built from (set by the Pages build, .github/workflows/pages.yml).
const BRANCH: string = import.meta.env.VITE_DATA_BRANCH || "main";

export function Methods({ ds }: { ds: Dataset }) {
  const i = useI18n();
  const repo = `https://github.com/GYZ001/costmodel/blob/${BRANCH}/`;
  const k = ds.constants;
  const name = (iso: string) => (ds.countries[iso] ? countryName(i, ds.countries[iso]) : iso);
  /** One row per economy, data item and kind of reason: the excluded years and the first reason given. */
  const groups = useMemo(() => {
    const m = new Map<string, { area: string; scope: string; kind: string; years: string[]; detail: string }>();
    for (const e of ds.exclusions) {
      const key = `${e.area}|${e.scope}|${e.kind}`;
      const g = m.get(key) ?? { area: e.area, scope: e.scope, kind: e.kind, years: [], detail: i.r(e.detail) };
      g.years.push(e.year);
      m.set(key, g);
    }
    const cmp = byName(i);
    return [...m.values()].sort((a, b) => cmp(name(a.area), name(b.area)) || a.scope.localeCompare(b.scope) || a.kind.localeCompare(b.kind));
  }, [ds, i]);
  const span = (ys: string[]) => {
    if (ys.includes("*")) return i.t("excl.all_years");
    const s = [...ys].sort();
    return s.length === 1 ? s[0] : i.t("excl.span", { first: s[0], last: s[s.length - 1], n: i.n(s.length, "int") });
  };
  const li = (key: string, params?: Record<string, string>) => <li>{i.t(key, params)}</li>;

  return (
    <section className="block" id="method">
      <h2>{i.t("m.title")}</h2>
      <p className="sub">{i.t("m.sub")}</p>

      <div className="grid2">
        <div className="card">
          <h3>{i.t("m.formulas")}</h3>
          <ul className="small list">
            {li("m.f_gold")}
            {li("m.f_step1")}
            {li("m.f_step2_diet")}
            {li("m.f_step2_intl")}
            {li("m.f_step3")}
            {li("m.f_oecd")}
            {li("m.f_ilo")}
            {li("m.f_nso")}
          </ul>
        </div>
        <div className="card">
          <h3>{i.t("m.concepts")}</h3>
          <ul className="small list">
            {li("m.c_median")}
            {li("m.c_ilostat")}
            {li("m.c_nso")}
            {li("m.c_excluded_notes")}
            {li("m.c_time_units", { tf: i.n(k.time_factor, "d2"), ug: i.n(k.unit_gap, "d2") })}
            {li("m.c_continuity", { tf: i.n(k.time_factor, "d2"), hfce: levelBoundsText(i, ds, "hfce"), gdp: levelBoundsText(i, ds, "gdp") })}
            {li("m.c_diet")}
            {li("m.c_intl_dollar")}
            {li("m.c_same_year")}
            {li("m.c_monthly_view")}
            {li("m.c_translation")}
          </ul>
        </div>
      </div>

      <div className="card">
        <h3>{i.t("m.checks")}</h3>
        <div className="table-scroll" style={{ maxHeight: "none" }}>
          <table className="data">
            <thead><tr><th className="l">{i.t("m.check")}</th><th className="l nw">{i.t("m.result")}</th><th className="l">{i.t("m.detail")}</th></tr></thead>
            <tbody>
              {ds.checks.map((c) => (
                <tr key={c.id}>
                  <td className="l" style={{ minWidth: 200 }}>{i.t(`check.${c.id}`)}</td>
                  <td className={`l nw status-${c.status}`}>{i.t(`status.${c.status}`)}</td>
                  <td className="l small ink2" style={{ minWidth: 360 }}>{i.r(c.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>{i.t("m.excl_title", { n: i.n(ds.exclusions.length, "int") })}</h3>
        <p className="small ink2" style={{ margin: "0 0 8px" }}>
          {i.t("m.excl_units", { mf: i.n(k.max_factor, "d1") })}{" "}
          {i.t("m.excl_rates", { mf: i.n(k.max_factor, "d1") })}{" "}
          {i.t("m.excl_joins")}{" "}
          {i.t("m.excl_rule")}
        </p>
        <details>
          <summary>{i.t("m.excl_by_economy")}</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th className="l">{i.t("col.economy")}</th><th className="l">{i.t("m.excl_item")}</th><th className="l">{i.t("m.excl_kind")}</th><th className="l">{i.t("m.excl_years")}</th><th className="l">{i.t("m.excl_reason")}</th></tr></thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={`${g.area}|${g.scope}|${g.kind}`}>
                    <td className="l">{name(g.area)}</td>
                    <td className="l small">{i.t(SCOPE_KEYS[g.scope] ?? "scope.other", { scope: g.scope })}</td>
                    <td className="l small">{i.t(`kind.${g.kind}`)}</td>
                    <td className="l small">{span(g.years)}</td>
                    <td className="l small ink2" style={{ minWidth: 320 }}>{g.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <div className="card">
        <h3>{i.t("m.sources")}</h3>
        <div className="table-scroll" style={{ maxHeight: "none" }}>
          <table className="data">
            <thead><tr><th className="l">{i.t("m.src_publisher")}</th><th className="l">{i.t("m.src_use")}</th><th className="l">{i.t("m.src_license")}</th><th>{i.t("m.src_snapshots")}</th></tr></thead>
            <tbody>
              {ds.sources.map((s) => (
                <tr key={s.prefix}>
                  <td className="l">
                    <div>{i.t(`src.${s.id}.publisher`)}</div>
                    <div className="small"><a href={s.landing}>{i.t(`src.${s.id}.title`)}</a></div>
                  </td>
                  <td className="l small ink2">{i.t(`src.${s.id}.use`)}</td>
                  <td className="l small">{i.t(`src.${s.id}.license`)}</td>
                  <td className="small">
                    <details>
                      <summary>{i.t("m.src_files", { n: i.n(s.snapshots.length, "int"), date: latest(s.snapshots.map((x) => x.retrieved_at)) })}</summary>
                      <table className="data" style={{ marginTop: 6 }}>
                        <tbody>
                          {s.snapshots.map((x) => (
                            <tr key={x.key}>
                              <td className="l"><a href={repo + x.path}>{x.path.replace("data/raw/", "")}</a>{x.status === "stale" ? ` ⚠ ${i.t("m.src_stale")}` : ""}</td>
                              <td className="l"><a href={x.url}>{i.t("m.src_original")}</a></td>
                              <td className="l mono" title={x.sha256}>{x.sha256.slice(0, 12)}…</td>
                              <td dir="ltr">{x.retrieved_at.replace("T", " ").replace("+00:00", " UTC")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">{i.t("m.src_note", { branch: BRANCH })}</p>
      </div>
    </section>
  );
}

function latest(xs: string[]): string {
  const m = xs.sort().pop();
  return m ? m.slice(0, 10) : "—";
}
