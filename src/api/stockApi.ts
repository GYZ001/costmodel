import axios from 'axios';
import type {
  AnalyzeRequest,
  AnalysisResult,
  KlineData,
  KlineResponse,
  KlineIndicators,
  NewsItem,
  NewsResponse,
  SentimentResult,
  AppConfig
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const analyzeStock = async (request: AnalyzeRequest): Promise<AnalysisResult> => {
  const response = await api.post<AnalysisResult>('/analyze', request);
  return response.data;
};

export const getKlineData = async (
  code: string,
  market: string = 'A股',
  period: string = '日线',
  days: number = 30
): Promise<{ data: KlineData[]; indicators: KlineIndicators }> => {
  const response = await api.get<KlineResponse>('/kline', {
    params: { code, market, period, days },
  });
  return response.data;
};

export const getNews = async (
  code: string,
  name: string,
  days: number = 7
): Promise<{ data: NewsItem[]; sentiment: SentimentResult }> => {
  const response = await api.get<NewsResponse>('/news', {
    params: { code, name, days },
  });
  return response.data;
};

export const getConfig = async (): Promise<AppConfig> => {
  const response = await api.get<AppConfig>('/config');
  return response.data;
};

export const updateConfig = async (config: Partial<AppConfig>): Promise<AppConfig> => {
  const response = await api.post<AppConfig>('/config', config);
  return response.data;
};

export default api;
