import { create } from 'zustand';
import type {
  KlineData,
  KlineIndicators,
  NewsItem,
  SentimentResult,
  AnalysisResult,
  Market,
  Period
} from '../types';

interface StockState {
  stockCode: string;
  stockName: string;
  market: Market;
  period: Period;
  days: number;
  klineData: KlineData[];
  klineIndicators: KlineIndicators | null;
  newsData: NewsItem[];
  newsSentiment: SentimentResult | null;
  analysisResult: AnalysisResult | null;
  isLoading: boolean;
  error: string | null;

  setStockCode: (code: string) => void;
  setStockName: (name: string) => void;
  setMarket: (market: Market) => void;
  setPeriod: (period: Period) => void;
  setDays: (days: number) => void;
  setKlineData: (data: KlineData[], indicators: KlineIndicators) => void;
  setNewsData: (data: NewsItem[], sentiment: SentimentResult) => void;
  setAnalysisResult: (result: AnalysisResult) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  stockCode: '',
  stockName: '',
  market: 'A股' as Market,
  period: '日线' as Period,
  days: 30,
  klineData: [],
  klineIndicators: null,
  newsData: [],
  newsSentiment: null,
  analysisResult: null,
  isLoading: false,
  error: null,
};

export const useStockStore = create<StockState>((set) => ({
  ...initialState,

  setStockCode: (code) => set({ stockCode: code }),
  setStockName: (name) => set({ stockName: name }),
  setMarket: (market) => set({ market }),
  setPeriod: (period) => set({ period }),
  setDays: (days) => set({ days }),

  setKlineData: (data, indicators) =>
    set({ klineData: data, klineIndicators: indicators }),

  setNewsData: (data, sentiment) =>
    set({ newsData: data, newsSentiment: sentiment }),

  setAnalysisResult: (result) => set({ analysisResult: result }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  reset: () => set(initialState),
}));
