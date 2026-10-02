import { useEffect, useState } from "react";
import type { I18n } from "./i18n";
import type { Msg } from "./i18n/render";
import type { Country, CountryYear, Dataset, Wage } from "./types";

export type View = "hourly" | "monthly";

// ---------------------------------------------------------------- formatting

/** An amount in a currency: "1,234 CNY"; whole units at 1,000 and above. */
export function money(i: I18n, x: number | null | undefined, cur: string | null, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  return i.t("u.money", { v: i.n(x, Math.abs(x) >= 1000 ? "d0" : `d${digits}`), cur: cur ?? i.t("u.lcu") });
}

export function minutes(i: I18n, x: number | null | undefined): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  if (x < 60) return i.t("u.min", { n: i.n(x, "sig2") });
  const h = Math.floor(x / 60);
  const m = Math.round(x - h * 60);
  return m === 60 ? i.t("u.h", { h: i.n(h + 1, "int") }) : i.t("u.h_min", { h: i.n(h, "int"), m: i.n(m, "int") });
}

export function grams(i: I18n, x: number | null | undefined, n = 3): string {
  return x === null || x === undefined ? "—" : i.t("u.g", { n: i.n(x, `sig${n}`) });
}

// ---------------------------------------------------------------- names

const regionNames = new Map<string, Intl.DisplayNames | null>();

/** The economy's name in the reader's language (the browser's own list of region names),
 *  else the World Bank's (English) name - the same rule in every language. */
export function countryName(i: I18n, c: Country): string {
  const loc = i.lang.locale;
  if (!regionNames.has(loc)) {
    let dn: Intl.DisplayNames | null = null;
    try {
      dn = new Intl.DisplayNames([loc], { type: "region", fallback: "none" });
    } catch {
      dn = null;
    }
    regionNames.set(loc, dn);
  }
  let name: string | undefined;
  try {
    name = regionNames.get(loc)?.of(c.iso2);
  } catch {
    name = undefined;
  }
  return name && name !== c.iso2 ? name : c.name_en;
}

export function byName(i: I18n): (a: string, b: string) => number {
  const coll = new Intl.Collator(i.lang.locale);
  return (a, b) => coll.compare(a, b);
}

// ---------------------------------------------------------------- dataset helpers

/** A wage's label, marked where its publisher's notes limit its coverage - for every
 *  source alike. */
export function markedLabel(i: I18n, label: Msg, restricted: boolean): string {
  return restricted ? i.t("w.restricted", { label }) : i.r(label);
}

/** The label to show for a wage in the given view. */
export function wageLabel(i: I18n, w: Wage, view: View): string {
  return markedLabel(i, view === "hourly" && w.label_hourly ? w.label_hourly : w.label, w.restricted);
}

/** Currency to print next to a wage: the one its publisher states, else the economy's. */
export function wageCurrency(w: Wage, c: Country): string | null {
  return w.currency ?? c.currency;
}

function cut(s: string, max: number): string {
  return max && s.length > max ? `${s.slice(0, max)}…` : s;
}

/** Tooltip / table lines describing where a wage figure comes from and what it measures. */
export function wageNotes(i: I18n, w: Wage, view: View, c: Country, max = 0): string[] {
  const cur = wageCurrency(w, c);
  const value = view === "hourly" ? i.t("u.per_hour", { v: money(i, w.hourly_lcu, cur) }) : i.t("u.per_month", { v: money(i, w.monthly_lcu, cur) });
  const sw = view === "hourly" ? w.role_switch : w.mrole_switch;
  const notesKey = (b: boolean, n: boolean) => (b && n ? "wn.switch_notes_both" : b ? "wn.switch_notes_before" : n ? "wn.switch_notes_now" : "wn.switch_notes");
  const switchNote = !sw ? [] : sw.kind === "source"
    ? [i.t("wn.switch_source", { year: sw.year, label: markedLabel(i, sw.label, sw.restricted), source: i.r(sw.source) })]
    : [i.t(notesKey(sw.only_before.length > 0, sw.only_now.length > 0), { year: sw.year, before: sw.only_before, now: sw.only_now })];
  const caveat = i.r(w.caveat);
  return [
    i.t("wn.value", { label: wageLabel(i, w, view), value }),
    ...(view === "hourly" && w.hours_week ? [i.t("wn.hours", { h: i.n(w.hours_week, "d1"), method: i.r(w.method) })] : []),
    i.r(w.source),
    ...switchNote.map((t) => cut(t, max)),
    ...(caveat ? [i.t("wn.caveat", { text: cut(caveat, max) })] : []),
  ];
}

/** The continuity bound against one yardstick, for a few spans. */
export function levelBoundsText(i: I18n, ds: Dataset, yardstick: "hfce" | "gdp"): string {
  const b = ds.constants.level_bounds[yardstick] ?? {};
  const spans = Object.keys(b).map(Number).sort((x, y) => x - y);
  if (!spans.length) return i.t("lb.none");
  const shown = spans.filter((k) => [1, 2, 3, 5, 10].includes(k));
  const longest = spans[spans.length - 1];
  const items = shown.map((k) => i.t("lb.span", { n: k, b: b[String(k)] }));
  if (!shown.includes(longest)) items.push(i.t("lb.longest", { n: longest, b: b[String(longest)] }));
  return i.j(items, "enum");
}

/** The exchange-rate line for a row: the official rate, and where the World Bank converted
 *  that year's GDP at another factor (fiscal-year or other rates), that factor too. */
export function fxNote(i: I18n, row: CountryYear, c: Country): string[] {
  if (row.fx == null) return [];
  const d = row.fx_vs_gdp_factor;
  const cur = c.currency ?? i.t("u.lcu");
  return [row.fx_gdp_factor != null && d != null && Math.abs(d - 1) >= FX_NOTE_GAP
    ? i.t("fx.rate_gdp", { fx: row.fx, cur, f: row.fx_gdp_factor, ratio: d })
    : i.t("fx.rate", { fx: row.fx, cur })];
}

/** Gap between the official rate and the World Bank's GDP conversion factor from which it is mentioned. */
export const FX_NOTE_GAP = 0.005;

/** Years in which the archived World Bank data have all six food-group costs for some economy. */
export function foodGroupYears(ds: Dataset): string[] {
  const ys = new Set<string>();
  const keys = ["staples", "vegetables", "fruits", "animal", "legumes", "oils"] as const;
  for (const c of Object.values(ds.countries))
    for (const [y, row] of Object.entries(c.years)) if (keys.every((k) => row.cohd[k] != null)) ys.add(y);
  return [...ys].sort();
}

export function primaryWage(row: CountryYear | undefined, view: View = "hourly"): Wage | undefined {
  return row?.wages.find((w) => (view === "hourly" ? w.role : w.mrole) === "primary");
}

export function typicalWage(row: CountryYear | undefined, view: View = "hourly"): Wage | undefined {
  return row?.wages.find((w) => (view === "hourly" ? w.role : w.mrole) === "typical");
}

/** Years (descending) where the economy has a primary wage for the view. */
export function wageYears(c: Country, view: View = "hourly"): string[] {
  return Object.keys(c.years)
    .filter((y) => primaryWage(c.years[y], view))
    .sort()
    .reverse();
}

/** Default reference year: the most recent year in which at least two thirds of the
 *  G20 member countries have a wage figure for the view. */
export function bestYear(ds: Dataset, view: View): string {
  const counts: Record<string, number> = {};
  const members = Object.values(ds.countries).filter((c) => c.g20);
  for (const c of members) for (const y of wageYears(c, view)) counts[y] = (counts[y] ?? 0) + 1;
  const need = Math.ceil((members.length * 2) / 3);
  const years = Object.keys(counts).sort().reverse();
  return years.find((y) => counts[y] >= need) ?? years[0];
}

/** Median of a list of numbers. */
export function median(xs: number[]): number | null {
  const s = [...xs].sort((a, b) => a - b);
  if (!s.length) return null;
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** p-th quantile (0…1), linear interpolation. */
export function quantile(xs: number[], q: number): number | null {
  const s = [...xs].sort((a, b) => a - b);
  if (!s.length) return null;
  const i = (s.length - 1) * q;
  const lo = Math.floor(i);
  return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (i - lo);
}

// ---------------------------------------------------------------- theme

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Re-render charts when the OS theme, the page's theme toggle or the page's language changes. */
export function useThemeVersion(): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const bump = () => setV((x) => x + 1);
    mq.addEventListener("change", bump);
    const obs = new MutationObserver(bump);
    // lang too: the font stack depends on the page's language (styles.css)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "lang"] });
    return () => {
      mq.removeEventListener("change", bump);
      obs.disconnect();
    };
  }, []);
  return v;
}

export function palette() {
  return {
    surface: cssVar("--surface"),
    ink: cssVar("--ink"),
    ink2: cssVar("--ink-2"),
    muted: cssVar("--muted"),
    grid: cssVar("--grid"),
    axis: cssVar("--axis"),
    accent: cssVar("--accent"),
    gold: cssVar("--gold"),
    deemph: cssVar("--deemph"),
    series: ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7", "--s8"].map(cssVar),
    divNeg: cssVar("--div-neg"),
    divMid: cssVar("--div-mid"),
    divPos: cssVar("--div-pos"),
  };
}

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]!);
}
