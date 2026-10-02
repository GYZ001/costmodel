import { useEffect, useState } from "react";
import type { Country, CountryYear, Dataset, Wage } from "./types";

// ---------------------------------------------------------------- formatting

export function fmt(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  return x.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Significant-figure formatting for values spanning many magnitudes (grams, minutes). */
export function sig(x: number | null | undefined, n = 3): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  if (x === 0) return "0";
  const d = Math.max(0, n - 1 - Math.floor(Math.log10(Math.abs(x))));
  return fmt(x, Math.min(d, 6));
}

export function money(x: number | null | undefined, cur: string | null, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  const unit = cur ?? "本币";
  const big = Math.abs(x) >= 1000;
  return `${fmt(x, big ? 0 : digits)} ${unit}`;
}

export function minutes(x: number | null | undefined): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  if (x < 60) return `${sig(x, 2)} 分钟`;
  const h = Math.floor(x / 60);
  const m = Math.round(x - h * 60);
  return m === 60 ? `${h + 1} 小时` : `${h} 小时 ${m} 分`;
}

export function pct(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  return `${fmt(x * 100, digits)}%`;
}

// ---------------------------------------------------------------- dataset helpers

/** The label to show for a wage in the given view. */
export function wageLabel(w: Wage, view: View): string {
  return view === "hourly" && w.label_hourly ? w.label_hourly : w.label;
}

/** Currency to print next to a wage: the one its publisher states, else the economy's. */
export function wageCurrency(w: Wage, c: Country): string | null {
  return w.currency ?? c.currency;
}

/** Tooltip / table lines describing where a wage figure comes from and what it measures. */
export function wageNotes(w: Wage, view: View, c: Country, max = 0): string[] {
  const value = view === "hourly" ? `${money(w.hourly_lcu, wageCurrency(w, c))}/小时` : `${money(w.monthly_lcu, wageCurrency(w, c))}/月`;
  const caveat = max && w.caveat.length > max ? `${w.caveat.slice(0, max)}…` : w.caveat;
  const sw = view === "hourly" ? w.role_switch : w.mrole_switch;
  return [
    `${wageLabel(w, view)}：${value}`,
    ...(view === "hourly" && w.hours_week ? [`工时：每周 ${w.hours_week.toFixed(1)} 小时（${w.method}）`] : []),
    w.source,
    ...(sw ? [`注意：${sw.year} 年用的是另一序列（${sw.label}，${sw.source}），与上一年比较的变化含口径变化`] : []),
    ...(caveat ? [`口径注释：${caveat}`] : []),
  ];
}

export type View = "hourly" | "monthly";

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

export function rowFor(c: Country, year: string): { year: string; row: CountryYear } | null {
  const row = c.years[year];
  return row ? { year, row } : null;
}

export function countryName(c: Country): string {
  return c.name_zh || c.name_en;
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

// ---------------------------------------------------------------- theme

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Re-render charts when the OS theme or the page's theme toggle changes. */
export function useThemeVersion(): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const bump = () => setV((x) => x + 1);
    mq.addEventListener("change", bump);
    const obs = new MutationObserver(bump);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
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
