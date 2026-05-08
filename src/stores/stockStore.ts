import { create } from 'zustand';
import type {
  KlineData,
  KlineIndicators,
  NewsItem,
  SentimentResult,
  AnalysisResult,
  Market,
  Period,
  PositionInfo,
} from '../types';

interface StockState {
  stockCode: string;
  stockName: string;
  market: Market;
  period: Period;
  days: number;
  hasPosition: boolean;
  costPrice: string;
  shares: string;
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
  setHasPosition: (v: boolean) => void;
  setCostPrice: (v: string) => void;
  setShares: (v: string) => void;
  getPositionInfo: () => PositionInfo;
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
  hasPosition: false,
  costPrice: '',
  shares: '',
  klineData: [],
  klineIndicators: null,
  newsData: [],
  newsSentiment: null,
  analysisResult: null,
  isLoading: false,
  error: null,
};

export const useStockStore = create<StockState>((set, get) => ({
  ...initialState,

  setStockCode: (code) => set({ stockCode: code }),
  setStockName: (name) => set({ stockName: name }),
  setMarket: (market) => set({ market }),
  setPeriod: (period) => set({ period }),
  setDays: (days) => set({ days }),
  setHasPosition: (v) => set({ hasPosition: v }),
  setCostPrice: (v) => set({ costPrice: v }),
  setShares: (v) => set({ shares: v }),

  getPositionInfo: () => {
    const { hasPosition, costPrice, shares } = get();
    return {
      has_position: hasPosition,
      cost_price: costPrice ? parseFloat(costPrice) : null,
      shares: shares ? parseInt(shares) : null,
    };
  },

  setKlineData: (data, indicators) =>
    set({ klineData: data, klineIndicators: indicators }),

  setNewsData: (data, sentiment) =>
    set({ newsData: data, newsSentiment: sentiment }),

  setAnalysisResult: (result) => set({ analysisResult: result }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  reset: () => set(initialState),
}));
