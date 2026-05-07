export interface KlineData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface NewsItem {
  title: string;
  url: string;
  publish_time: string;
  source: string;
  summary: string;
}

export interface TechnicalAnalysis {
  trend: string;
  support_level: number;
  resistance_level: number;
  indicators_summary: string;
}

export interface NewsAnalysis {
  sentiment: string;
  key_events: string[];
  market_feedback: string;
}

export interface AnalysisResult {
  stock_code: string;
  stock_name: string;
  analysis_date: string;
  technical_analysis: TechnicalAnalysis;
  news_analysis: NewsAnalysis;
  recommendation: string;
  risk_level: string;
  summary: string;
}

export interface KlineIndicators {
  ma5: number;
  ma10: number;
  ma20: number;
  price_change: number;
  volume_change: number;
  latest_close: number;
  highest: number;
  lowest: number;
}

export interface KlineResponse {
  data: KlineData[];
  indicators: KlineIndicators;
}

export interface SentimentResult {
  sentiment: string;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  positive_ratio: number;
  negative_ratio: number;
}

export interface NewsResponse {
  data: NewsItem[];
  sentiment: SentimentResult;
}

export interface AIConfig {
  provider: string;
  api_key: string;
  base_url: string;
  model: string;
}

export interface StockConfig {
  default_market: string;
  default_period: string;
  default_days: number;
}

export interface NewsConfig {
  search_days: number;
  max_results: number;
  keywords_template: string;
}

export interface DataSourceConfig {
  kline_provider: string;
}

export interface AppConfig {
  ai: AIConfig;
  stock: StockConfig;
  news: NewsConfig;
  data_source: DataSourceConfig;
}

export interface AnalyzeRequest {
  stock_code: string;
  stock_name: string;
  market?: string;
  period?: string;
  days?: number;
  use_ai?: boolean;
}

export type Market = 'A股' | '港股' | '美股';
export type Period = '日线' | '周线' | '月线';
