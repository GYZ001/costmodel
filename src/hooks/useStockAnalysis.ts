import { useCallback, useState } from 'react';
import { useStockStore } from '../stores/stockStore';
import { analyzeStock, getKlineData, getNews } from '../api/stockApi';

const PERIOD_TO_DAYS: Record<string, number> = {
  日线: 1,
  周线: 7,
  月线: 30,
};

function toDays(count: number, period: string): number {
  return count * (PERIOD_TO_DAYS[period] ?? 1);
}

export const useStockAnalysis = () => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState('');

  const {
    stockCode,
    market,
    period,
    days,
    getPositionInfo,
    setStockName,
    setKlineData,
    setNewsData,
    setAnalysisResult,
    setLoading,
    setError,
  } = useStockStore();

  const analyze = useCallback(async () => {
    console.log('[useStockAnalysis] 开始分析', { stockCode, market, period, days });

    if (!stockCode || !stockCode.trim()) {
      console.log('[useStockAnalysis] 股票代码为空');
      setError('请输入股票代码');
      return;
    }

    setIsAnalyzing(true);
    setLoading(true);
    setError(null);

    const actualDays = toDays(days, period);

    try {
      setProgress('正在分析...');

      console.log('[useStockAnalysis] 调用 analyzeStock API...');
      const positionInfo = getPositionInfo();
      const analysisResult = await analyzeStock({
        stock_code: stockCode.trim().toUpperCase(),
        stock_name: '',
        market,
        period,
        days: actualDays,
        position: positionInfo.has_position ? positionInfo : undefined,
      });

      console.log('[useStockAnalysis] 分析结果:', analysisResult);

      if (analysisResult) {
        if (analysisResult.stock_name) {
          console.log('[useStockAnalysis] 设置股票名称:', analysisResult.stock_name);
          setStockName(analysisResult.stock_name);
        }

        console.log('[useStockAnalysis] 设置分析结果到 store');
        setAnalysisResult(analysisResult);

        console.log('[useStockAnalysis] 获取 K 线数据...');
        console.log('[useStockAnalysis] 调用参数:', {
          code: stockCode.trim().toUpperCase(),
          market,
          period,
          days: actualDays,
        });

        try {
          const klineResult = await getKlineData(stockCode.trim().toUpperCase(), market, period, actualDays);
          console.log('[useStockAnalysis] K 线数据:', klineResult.data.length, '条');
          setKlineData(klineResult.data, klineResult.indicators);
        } catch (klineError) {
          console.error('[useStockAnalysis] K线数据获取失败:', klineError);
          throw klineError;
        }

        console.log('[useStockAnalysis] 获取新闻数据...');
        try {
          const newsResult = await getNews(stockCode.trim().toUpperCase(), analysisResult.stock_name || '', 7);
          console.log('[useStockAnalysis] 新闻数据:', newsResult.data.length, '条');
          setNewsData(newsResult.data, newsResult.sentiment);
        } catch (newsError) {
          console.error('[useStockAnalysis] 新闻数据获取失败:', newsError);
          throw newsError;
        }
      } else {
        console.log('[useStockAnalysis] 分析结果为空');
      }

      setProgress('分析完成');
      console.log('[useStockAnalysis] 分析完成');
    } catch (err: any) {
      console.error('[useStockAnalysis] 分析错误:', err);
      let errorMessage = '分析失败，请稍后重试';

      if (err.response) {
        errorMessage = err.response.data?.message || `服务器错误 (${err.response.status})`;
      } else if (err.request) {
        errorMessage = '无法连接到服务器，请确保后端服务已启动';
      } else {
        errorMessage = err.message || errorMessage;
      }

      console.error('[useStockAnalysis] 错误消息:', errorMessage);
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
