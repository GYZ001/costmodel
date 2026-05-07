import { useCallback, useState } from 'react';
import { useStockStore } from '../stores/stockStore';
import { analyzeStock, getKlineData, getNews } from '../api/stockApi';

export const useStockAnalysis = () => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState('');

  const {
    stockCode,
    market,
    period,
    days,
    setStockName,
    setKlineData,
    setNewsData,
    setAnalysisResult,
    setLoading,
    setError,
  } = useStockStore();

  const analyze = useCallback(async () => {
    if (!stockCode || !stockCode.trim()) {
      setError('请输入股票代码');
      return;
    }

    setIsAnalyzing(true);
    setLoading(true);
    setError(null);

    try {
      setProgress('正在获取 K 线数据...');
      const klineResult = await getKlineData(stockCode, market, period, days);
      setKlineData(klineResult.data, klineResult.indicators);

      setProgress('正在获取新闻资讯...');
      const newsResult = await getNews(stockCode, '', 7);
      setNewsData(newsResult.data, newsResult.sentiment);

      setProgress('正在分析...');
      const analysisResult = await analyzeStock({
        stock_code: stockCode,
        stock_name: '',
        market,
        period,
        days,
      });

      if (analysisResult.stock_name) {
        setStockName(analysisResult.stock_name);
      }

      setAnalysisResult(analysisResult);

      setProgress('分析完成');
    } catch (err: any) {
      console.error('Analysis error:', err);
      const errorMessage = err.response?.data?.message || err.message || '分析失败，请稍后重试';
      setError(errorMessage);
    } finally {
      setIsAnalyzing(false);
      setLoading(false);
      setProgress('');
    }
  }, [stockCode, market, period, days, setStockName, setKlineData, setNewsData, setAnalysisResult, setLoading, setError]);

  return {
    analyze,
    isAnalyzing,
    progress,
  };
};
