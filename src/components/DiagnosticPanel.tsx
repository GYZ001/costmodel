import React, { useEffect, useState } from 'react';
import { useStockStore } from '../stores/stockStore';
import { analyzeStock, getKlineData, getNews } from '../api/stockApi';
import { AlertTriangle, CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface DiagnosticStep {
  name: string;
  status: 'pending' | 'loading' | 'success' | 'error';
  message?: string;
  data?: any;
}

export const DiagnosticPanel: React.FC = () => {
  const [diagnostics, setDiagnostics] = useState<DiagnosticStep[]>([
    { name: '连接后端服务', status: 'pending' },
    { name: '获取股票分析', status: 'pending' },
    { name: '获取K线数据', status: 'pending' },
    { name: '获取新闻数据', status: 'pending' },
    { name: '更新Store状态', status: 'pending' },
  ]);

  const {
    setStockName,
    setKlineData,
    setNewsData,
    setAnalysisResult,
    setError,
    setLoading
  } = useStockStore();

  const runDiagnostics = async () => {
    setDiagnostics(prev => prev.map(s => ({ ...s, status: 'pending' })));

    // Step 1: Check backend connection
    setDiagnostics(prev => {
      const updated = [...prev];
      updated[0] = { name: '连接后端服务', status: 'loading' };
      return updated;
    });

    try {
      const response = await fetch('/api/health');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      setDiagnostics(prev => {
        const updated = [...prev];
        updated[0] = {
          name: '连接后端服务',
          status: 'success',
          message: `后端服务正常，AI配置: ${data.ai_configured ? '已配置' : '未配置'}`
        };
        return updated;
      });

      // Step 2: Analyze stock
      setDiagnostics(prev => {
        const updated = [...prev];
        updated[1] = { name: '获取股票分析', status: 'loading' };
        return updated;
      });

      const analyzeResult = await analyzeStock({
        stock_code: '600519',
        stock_name: '',
        market: 'A股',
        period: '日线',
        days: 30
      });

      setDiagnostics(prev => {
        const updated = [...prev];
        updated[1] = {
          name: '获取股票分析',
          status: 'success',
          message: `${analyzeResult.stock_name} - ${analyzeResult.recommendation}`,
          data: analyzeResult
        };
        return updated;
      });

      // Step 3: Get kline data
      setDiagnostics(prev => {
        const updated = [...prev];
        updated[2] = { name: '获取K线数据', status: 'loading' };
        return updated;
      });

      const klineResult = await getKlineData('600519', 'A股', '日线', 30);

      setDiagnostics(prev => {
        const updated = [...prev];
        updated[2] = {
          name: '获取K线数据',
          status: 'success',
          message: `${klineResult.data.length}条数据，最新收盘 ${klineResult.indicators.latest_close}`,
          data: klineResult
        };
        return updated;
      });

      // Step 4: Get news data
      setDiagnostics(prev => {
        const updated = [...prev];
        updated[3] = { name: '获取新闻数据', status: 'loading' };
        return updated;
      });

      const newsResult = await getNews('600519', analyzeResult.stock_name || '贵州茅台', 7);

      setDiagnostics(prev => {
        const updated = [...prev];
        updated[3] = {
          name: '获取新闻数据',
          status: 'success',
          message: `${newsResult.data.length}条新闻，情绪: ${newsResult.sentiment.sentiment}`,
          data: newsResult
        };
        return updated;
      });

      // Step 5: Update store
      setDiagnostics(prev => {
        const updated = [...prev];
        updated[4] = { name: '更新Store状态', status: 'loading' };
        return updated;
      });

      try {
        setStockName(analyzeResult.stock_name);
        setAnalysisResult(analyzeResult);
        setKlineData(klineResult.data, klineResult.indicators);
        setNewsData(newsResult.data, newsResult.sentiment);

        setDiagnostics(prev => {
          const updated = [...prev];
          updated[4] = {
            name: '更新Store状态',
            status: 'success',
            message: '所有数据已成功更新到Store'
          };
          return updated;
        });
      } catch (error) {
        setDiagnostics(prev => {
          const updated = [...prev];
          updated[4] = {
            name: '更新Store状态',
            status: 'error',
            message: `更新失败: ${error}`
          };
          return updated;
        });
      }

    } catch (error: any) {
      const failedIndex = diagnostics.findIndex(d => d.status === 'loading');
      setDiagnostics(prev => {
        const updated = [...prev];
        if (failedIndex >= 0) {
          updated[failedIndex] = {
            name: diagnostics[failedIndex].name,
            status: 'error',
            message: `失败: ${error.message}`
          };
        }
        return updated;
      });
      setError(`诊断失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runDiagnostics();
  }, []);

  const getIcon = (status: DiagnosticStep['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'loading':
        return <Loader2 className="w-5 h-5 text-yellow-500 animate-spin" />;
      default:
        return <div className="w-5 h-5 rounded-full border-2 border-gray-300" />;
    }
  };

  const completedCount = diagnostics.filter(d => d.status === 'success').length;
  const allSuccess = completedCount === diagnostics.length;

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-yellow-500" />
          诊断面板
        </h3>
        <div className="text-sm text-gray-600">
          {completedCount} / {diagnostics.length} 步骤完成
          {allSuccess && (
            <span className="ml-2 text-green-600 font-semibold">✓ 全部成功</span>
          )}
        </div>
      </div>

      <div className="space-y-3 mb-4">
        {diagnostics.map((step, index) => (
          <div
            key={index}
            className={`flex items-center gap-3 p-3 rounded-lg ${
              step.status === 'loading' ? 'bg-yellow-50' :
              step.status === 'success' ? 'bg-green-50' :
              step.status === 'error' ? 'bg-red-50' :
              'bg-gray-50'
            }`}
          >
            {getIcon(step.status)}
            <div className="flex-1">
              <div className="font-medium text-gray-900">{step.name}</div>
              {step.message && (
                <div className={`text-sm ${
                  step.status === 'success' ? 'text-green-700' :
                  step.status === 'error' ? 'text-red-700' :
                  'text-gray-600'
                }`}>
                  {step.message}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={runDiagnostics}
        className="w-full py-2 px-4 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors"
      >
        重新运行诊断
      </button>

      {allSuccess && (
        <div className="mt-4 p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
          <p className="text-emerald-800 font-medium">
            ✓ 所有诊断通过！数据应该已正常显示在页面上。
          </p>
          <p className="text-emerald-600 text-sm mt-1">
            请滚动页面查看 K线走势图、技术指标、新闻资讯和分析结果。
          </p>
        </div>
      )}
    </div>
  );
};
