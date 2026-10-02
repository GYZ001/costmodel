// Shape of public/data/dataset.json, produced by pipeline/wagegold/__main__.py.

export interface Wage {
  role: "primary" | "typical" | null; // hourly view
  mrole: "primary" | "typical" | null; // monthly view
  key: string;
  label: string;
  /** Label for the hourly view when the hourly figure is derived from a monthly one. */
  label_hourly: string | null;
  concept: "mean" | "median";
  source: string;
  method: string;
  /** Notes that qualify the figure: ILOSTAT's own note labels (English, verbatim), and this
   *  project's notes (e.g. a level shift against adjacent years, how hours were applied). */
  caveat: string;
  /** The publisher's own definitions, quoted verbatim (NBS releases); empty otherwise. */
  quote: string;
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
  label: string;
  source: string;
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
  name_zh: string;
  iso2: string;
  region: string;
  income: string;
  g20: boolean;
  /** Currency of the World Bank's local-currency series, as proven by the records joined to it. */
  currency: string | null;
  years: Record<string, CountryYear>;
}

export interface UsItemRow {
  period: string;
  price_bls_unit: number;
  price: number;
  minutes: number | null;
  gold_mg: number | null;
  preliminary: boolean;
  /** The same month's average hourly earnings is still marked preliminary by BLS. */
  wage_preliminary: boolean;
}

export interface UsItem {
  label: string;
  bls_unit: string;
  unit: string;
  series_id: string;
  rows: UsItemRow[];
}

export interface Check {
  id: string;
  title: string;
  /** info: an overview, not a pass/fail check */
  status: "pass" | "warn" | "fail" | "info";
  detail: string;
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
  publisher: string;
  title: string;
  landing: string;
  license: string;
  use: string;
  snapshots: SnapshotInfo[];
}

export interface Dataset {
  generated_at: string;
  constants: {
    grams_per_troy_ounce: number; weeks_per_month: number; assumed_hours_cn: number;
    /** bound for currency units; for one figure in two time units; for figures of different concepts */
    max_factor: number; time_factor: number; unit_gap: number;
    /** how far a same-concept series can move against nominal consumption per head in a year, and why */
    level_bound: number; level_basis: string;
  };
  gold: {
    monthly: [string, number][];
    annual: Record<string, { usd_oz: number; usd_g: number }>;
    latest: { period: string; usd_oz: number; usd_g: number };
    /** The workbook's own "Updated on …" line. */
    source_updated: string | null;
  };
  countries: Record<string, Country>;
  icp2021_pli_us: Record<string, Record<string, number>>;
  /** [month, US$ per hour, grams of gold per hour, BLS marks the value preliminary] */
  us_monthly: Record<"us_ahe_pns_sa" | "us_ahe_all_sa", [string, number, number, boolean][]>;
  us_items: Record<string, UsItem>;
  cn_hours_monthly: [string, number][];
  /** [year, monthly wage in LCU, grams of gold, source line, series breaks before this point, why] */
  wage_gold_history: Record<string, {
    label: string; source_id: string; restricted: boolean;
    /** ILOSTAT's coverage notes and remarks on the drawn records (English, verbatim) */
    notes: string[];
    points: [string, number, number, string, boolean, string][];
  }>;
  /** ILOSTAT survey mean monthly earnings ÷ OECD's FTE wage, same economy and year: range over all such pairs. */
  oecd_vs_survey: { n: number; min: number; min_at: [string, string]; max: number; max_at: [string, string] } | null;
  latest: {
    period: string;
    gold_usd_oz: number;
    gold_usd_g: number;
    cny_per_usd: number;
    gold_cny_g: number;
    us_ahe: number;
    us_ahe_preliminary: boolean;
    us_gold_g_per_hour: number;
    cn: { series: string; label: string; wage_year: string; annual: number; basis: "assumed" | "actual"; hours_year: number; hours_months: string[] | null; hourly: number; gold_g_per_hour: number }[];
  };
  fx_recent_ecb: Record<string, [string, number][]>;
  nbs_price_releases: {
    built_at: string;
    listing: string;
    from: string | null;
    to: string | null;
    groups: { kind: string; count: number; first: string; last: string; example: string }[];
  } | null;
  /** This month's year-on-year CPI sentences, quoted verbatim from archived NBS releases
   *  (the monthly CPI release, and the CPI paragraph of the monthly economy release). */
  cn_cpi_yoy: {
    period: string; kind: "cpi" | "economy"; title: string; url: string; snapshot: string; sha256: string;
    /** text = the sentence verbatim; yoy = its clauses that report this month's year-on-year change */
    sentences: { text: string; yoy: string[] }[];
  }[];
  /** Months BLS lists without a value, with BLS's own footnote. */
  bls_unavailable: { period: string; note: string; series: string[] }[];
  /** kind: unit / missing / notes / check / area (see build.UnitGraph._exclude) */
  exclusions: { area: string; year: string; scope: string; kind: string; detail: string }[];
  checks: Check[];
  sources: SourceInfo[];
  stale: string[];
}
