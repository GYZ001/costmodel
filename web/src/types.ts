// Shape of public/data/dataset.json, produced by pipeline/wagegold/__main__.py.

export interface Wage {
  role: "primary" | "typical" | null;
  key: string;
  label: string;
  concept: "mean" | "median";
  source: string;
  method: string;
  caveat: string;
  snapshots: string[];
  monthly_lcu: number | null;
  hourly_lcu: number | null;
  hours_week: number | null;
  monthly_gold_g: number | null;
  hourly_gold_g: number | null;
  hourly_usd_mkt: number | null;
  hourly_ppp: number | null;
  minutes_per_cohd_day: number | null;
}

export type CohdKey = "total" | "staples" | "vegetables" | "fruits" | "animal" | "legumes" | "oils";

export interface CountryYear {
  fx: number;
  ppp_hfce: number | null;
  pli_hfce: number | null;
  population: number | null;
  gold_lcu_g: number;
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
  status: "pass" | "warn" | "fail";
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
  constants: { grams_per_troy_ounce: number; weeks_per_month: number; statutory_hours_cn: number };
  gold: {
    monthly: [string, number][];
    annual: Record<string, { usd_oz: number; usd_g: number }>;
    latest: { period: string; usd_oz: number; usd_g: number };
  };
  countries: Record<string, Country>;
  icp2021_pli_us: Record<string, Record<string, number>>;
  us_monthly: Record<"us_ahe_pns_sa" | "us_ahe_all_sa", [string, number, number][]>;
  us_items: Record<string, UsItem>;
  cn_hours_monthly: [string, number][];
  checks: Check[];
  sources: SourceInfo[];
  stale: string[];
}
