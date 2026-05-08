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
      setProgress('正在分析...');
      
      const analysisResult = await analyzeStock({
        stock_code: stockCode.trim().toUpperCase(),
        stock_name: '',
        market,
        period,
        days,
      });

      if (analysisResult) {
        if (analysisResult.stock_name) {
          setStockName(analysisResult.stock_name);
        }
        
        setAnalysisResult(analysisResult);
        
        const klineResult = await getKlineData(stockCode.trim().toUpperCase(), market, period, days);
        setKlineData(klineResult.data, klineResult.indicators);

        const newsResult = await getNews(stockCode.trim().toUpperCase(), analysisResult.stock_name || '', 7);
        setNewsData(newsResult.data, newsResult.sentiment);
      }

      setProgress('分析完成');
    } catch (err: any) {
      console.error('Analysis error:', err);
      let errorMessage = '分析失败，请稍后重试';
      
      if (err.response) {
        errorMessage = err.response.data?.message || `服务器错误 (${err.response.status})`;
      } else if (err.request) {
        errorMessage = '无法连接到服务器，请确保后端服务已启动';
      } else {
        errorMessage = err.message || errorMessage;
      }
      
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
