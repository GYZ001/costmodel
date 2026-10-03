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
  /** Publisher and survey, e.g. "ILOSTAT BA:463", "OECD". */
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
  /** Household consumption per resident per month ÷ this monthly wage (the same year as the
   *  publishers date them, the same currency unit), as a share of the wage. */
  living_ratio: number | null;
}

export interface Switch {
  year: string;
  label: Msg;
  restricted: boolean;
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
  /** Household final consumption per resident per month (WDI, LCU), where it is shown to be in
   *  the wages' currency unit (consumption_unconfirmed: published but not shown to be), and
   *  context: residents per employed person (ILO employment ratio, World Bank population) and
   *  employees' share of the employed (ILO modelled estimate). */
  living: {
    consumption_month: number | null; consumption_unconfirmed: boolean;
    residents_per_employed: number | null; employees_share: number | null;
  };
  wages: Wage[];
  snapshots: string[];
}

/** Groups of household consumption (catalog keys liv.g.<key>), in display order. */
export type LivingGroup = "food" | "rent" | "furnishings" | "clothing" | "transport" | "communication" | "other";

/** The ICP benchmark composition of an economy's household consumption: shares of household
 *  consumption (households and NPISHs); rent = household consumption − ICP's consumption
 *  without housing; "other" is the rest of domestic consumption. */
export interface IcpSpending {
  year: string;
  shares: Record<LivingGroup, number>;
  /** published parts of "other" (restaurants & hotels, alcohol & tobacco) and the rest */
  other_parts: { restaurants_hotels: number; alcohol_tobacco: number; rest: number };
  /** residents' purchases abroad less visitors' purchases here (negative: visitors spend more);
   *  0 where ICP publishes none (net_abroad_published false) */
  net_abroad: number;
  net_abroad_published: boolean;
  /** ICP's actual housing (with water, energy, repairs and government housing), as a share of household consumption */
  housing_actual: number;
  /** government individual consumption (free or subsidised services) on top, as a share of household consumption */
  government: number;
  /** ICP's household consumption ÷ WDI's current figure for the year, in WDI's current currency
   *  unit (null: the units cannot be compared); the factor ICP's figure was divided by to get
   *  there, and from what ("fx": the two dollar exchange rates; "ppp": the two PPPs), if any */
  revision: number | null;
  converted: number | null;
  converted_by: "fx" | "ppp" | null;
  /** WDI consumption per resident per month in that year, and its currency, where ICP's shares
   *  divide it (else null; the reason is in dataset.exclusions) */
  consumption_month: number | null;
  currency: string | null;
  /** WDI's country note where it says the national accounts are kept by fiscal year (verbatim) */
  na_fiscal: string | null;
  snapshots: string[];
}

export interface Country {
  /** The World Bank's name (used when the browser has no name for iso2 in the reader's language). */
  name_en: string;
  iso2: string;
  /** Member country of the G20 (the EU and the African Union, also members, are not economies here). */
  g20: boolean;
  /** Currency of the World Bank's local-currency series, as proven by the records joined to it. */
  currency: string | null;
  /** WDI's country note where it says the national accounts are kept by fiscal year (verbatim) */
  na_fiscal: string | null;
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
  /** a survey publisher whose own release continues a series ILOSTAT republishes */
  extends?: boolean;
  snapshots: SnapshotInfo[];
}

export interface Dataset {
  generated_at: string;
  constants: {
    grams_per_troy_ounce: number; weeks_per_month: number;
    /** bound for currency units; for one figure in two time units; for figures of different concepts */
    max_factor: number; time_factor: number; unit_gap: number;
    /** hours in a month (31 × 24): the most a monthly ÷ hourly figure can be */
    hours_in_month: number;
    /** years a series needs to be drawn in the gold history */
    history_min_years: number;
    /** largest relative difference allowed between a publisher's release and ILOSTAT's
     *  republication for the release to continue the series */
    extension_tol: number;
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
  /** ICP 2021 composition of household consumption, by economy. */
  icp2021_spending: Record<string, IcpSpending>;
  /** [year, monthly wage in LCU, grams of gold, source line, series breaks before this point, why] */
  wage_gold_history: Record<string, {
    label: Msg; source_id: string; restricted: boolean;
    /** ILOSTAT's coverage notes and remarks on the drawn records (English, verbatim; with years when not all) */
    notes: Part[];
    points: [string, number, number, Msg | string, boolean, Part][];
  }>;
  /** ILOSTAT survey mean monthly earnings ÷ OECD's FTE wage, same economy and year: range over all such pairs. */
  /** ILOSTAT mean monthly wage ÷ OECD full-time-equivalent wage over every economy-year with both:
   *  range, median, and the share of pairs below 1. */
  oecd_vs_survey: { n: number; min: number; min_at: [string, string]; max: number; max_at: [string, string]; median: number; below: number } | null;
  /** Name and ISO2 code of every economy (also those absent from countries because all their inputs were left out). */
  economies: Record<string, { name_en: string; iso2: string }>;
  /** kind: unit / identity / missing / notes / check / area (see build.UnitGraph._exclude); year "*" = every year */
  exclusions: { area: string; year: string; scope: string; kind: string; detail: Part }[];
  checks: Check[];
  sources: SourceInfo[];
  stale: string[];
}
