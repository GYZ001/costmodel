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

export function primaryWage(row: CountryYear | undefined): Wage | undefined {
  return row?.wages.find((w) => w.role === "primary");
}

export function typicalWage(row: CountryYear | undefined): Wage | undefined {
  return row?.wages.find((w) => w.role === "typical");
}

/** Years (descending) where the economy has a primary hourly wage. */
export function wageYears(c: Country): string[] {
  return Object.keys(c.years)
    .filter((y) => primaryWage(c.years[y]))
    .sort()
    .reverse();
}

export type YearMode = "latest" | string;

/** Row used for an economy: an exact year, or its most recent year with a wage (not older than `floor`). */
export function rowFor(c: Country, mode: YearMode, floor = "2021"): { year: string; row: CountryYear } | null {
  if (mode !== "latest") {
    const row = c.years[mode];
    return row ? { year: mode, row } : null;
  }
  const y = wageYears(c).find((yy) => yy >= floor);
  return y ? { year: y, row: c.years[y] } : null;
}

export function countryName(c: Country): string {
  return c.name_zh || c.name_en;
}

export function latestCommonYear(ds: Dataset): string {
  // The most recent year for which at least 40 economies have a primary hourly wage.
  const counts: Record<string, number> = {};
  for (const c of Object.values(ds.countries)) for (const y of wageYears(c)) counts[y] = (counts[y] ?? 0) + 1;
  return Object.keys(counts).filter((y) => counts[y] >= 40).sort().reverse()[0] ?? Object.keys(counts).sort().reverse()[0];
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
