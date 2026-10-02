// Shape of public/data/dataset.json, produced by pipeline/wagegold/__main__.py.
// Text about the data is published as language-neutral messages (Msg, rendered with the
// reader's catalog); plain strings are codes or text quoted verbatim from a publisher.
import type { Msg, Param } from "./i18n/render";

export type Part = Param;

export interface Wage {
  role: "primary" | "typical" | null; // hourly view
  mrole: "primary" | "typical" | null; // monthly view
  key: string;
  label: Msg;
  /** Label for the hourly view when the hourly figure is derived from a monthly one. */
  label_hourly: Msg | null;
  concept: "mean" | "median";
  /** A message, or the publisher's own name for its survey (verbatim). */
  source: Msg | string;
  method: Msg;
  /** Notes that qualify the figure: this project's notes (messages) and ILOSTAT's own note
   *  labels (English, verbatim). */
  caveat: Part[];
  /** The publisher's own definitions, quoted verbatim in its language (NBS releases: Chinese); empty otherwise. */
  quote: string;
  /** Language of the quote (BCP 47), e.g. "zh". */
  quote_lang: string | null;
  /** Publisher and survey, e.g. "ILOSTAT BA:463", "OECD", "NBS", "BLS". */
  source_id: string;
  /** Coverage limited, as the publisher states (e.g. urban units, private sector, full-time workers only). */
  restricted: boolean;
  /** Currency the publisher states for the figure. */
  currency: string | null;
  /** Set on a primary figure whose series differs from the economy's previous year's primary one. */
  role_switch: Switch | null;
  mrole_switch: Switch | null;
  snapshots: string[];
  monthly_lcu: number | null;
  hourly_lcu: number | null;
  hours_week: number | null;
  monthly_gold_g: number | null;
  hourly_gold_g: number | null;
  hourly_usd_mkt: number | null;
  hourly_ppp: number | null;
  minutes_per_cohd_day: number | null;
  monthly_ppp: number | null;
  cohd_days_per_month: number | null;
}

export interface Switch {
  year: string;
  label: Msg;
  source: Msg | string;
  /** source: another publisher series; notes: the same series with different notes on what it measures */
  kind: "source" | "notes";
  only_before: string[];
  only_now: string[];
}

export type CohdKey = "total" | "staples" | "vegetables" | "fruits" | "animal" | "legumes" | "oils";

// A field is null when its inputs could not be proven to be in the same currency unit
// as the World Bank's local-currency series (see dataset.exclusions for the reason).
export interface CountryYear {
  fx: number | null;
  /** The factor the World Bank applied to the year's GDP (GDP in LCU ÷ in US$), and fx ÷ that factor. */
  fx_gdp_factor: number | null;
  fx_vs_gdp_factor: number | null;
  ppp_hfce: number | null;
  pli_hfce: number | null;
  population: number | null;
  gold_lcu_g: number | null;
  gold_usd_g: number;
  gold_usdeq_g: number | null;
  cohd: Record<CohdKey, number | null>;
  cohd_days_per_g: number | null;
  wages: Wage[];
  snapshots: string[];
}

export interface Country {
  name_en: string;
  /** The World Bank's Chinese name (fallback for zh when the browser has no name for iso2). */
  name_zh: string;
  iso2: string;
  region: string;
  income: string;
  g20: boolean;
  /** Currency of the World Bank's local-currency series, as proven by the records joined to it. */
  currency: string | null;
  years: Record<string, CountryYear>;
}

export interface Check {
  /** named by the catalog key check.<id> */
  id: string;
  /** info: an overview, not a pass/fail check */
  status: "pass" | "warn" | "fail" | "info";
  detail: Msg;
}

export interface SnapshotInfo {
  key: string;
  url: string;
  path: string;
  retrieved_at: string;
  sha256: string;
  bytes: number;
  status: "fresh" | "stale";
  error: string | null;
}

export interface SourceInfo {
  prefix: string;
  /** catalog keys src.<id>.publisher / .title / .license / .use */
  id: string;
  landing: string;
  snapshots: SnapshotInfo[];
}

export interface Dataset {
  generated_at: string;
  constants: {
    grams_per_troy_ounce: number; weeks_per_month: number;
    /** bound for currency units; for one figure in two time units; for figures of different concepts */
    max_factor: number; time_factor: number; unit_gap: number;
    /** By yardstick (hfce = household consumption per head, gdp = GDP per head) and years
     *  apart: the widest move OECD's same-concept average wage made against it over that
     *  many years or fewer (the continuity check's bound). */
    level_bounds: Record<string, Record<string, number>>;
  };
  gold: {
    monthly: [string, number][];
    annual: Record<string, { usd_oz: number; usd_g: number }>;
    latest: { period: string; usd_oz: number; usd_g: number };
    /** The workbook's own "Updated on …" line. */
    source_updated: string | null;
  };
  countries: Record<string, Country>;
  /** ICP 2021 category price level indices as ICP publishes them (world = 100). */
  icp2021_pli: Record<string, Record<string, number>>;
  /** [year, monthly wage in LCU, grams of gold, source line, series breaks before this point, why] */
  wage_gold_history: Record<string, {
    label: Msg; source_id: string; restricted: boolean;
    /** ILOSTAT's coverage notes and remarks on the drawn records (English, verbatim; with years when not all) */
    notes: Part[];
    points: [string, number, number, Msg | string, boolean, Part][];
  }>;
  /** ILOSTAT survey mean monthly earnings ÷ OECD's FTE wage, same economy and year: range over all such pairs. */
  oecd_vs_survey: { n: number; min: number; min_at: [string, string]; max: number; max_at: [string, string] } | null;
  /** kind: unit / identity / missing / notes / check / area (see build.UnitGraph._exclude); year "*" = every year */
  exclusions: { area: string; year: string; scope: string; kind: string; detail: Part }[];
  checks: Check[];
  sources: SourceInfo[];
  stale: string[];
}
