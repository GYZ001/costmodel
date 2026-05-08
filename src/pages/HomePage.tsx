import React, { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { StockSearchForm } from '../components/StockSearchForm';
import { KLineChart } from '../components/KLineChart';
import { TechnicalIndicators } from '../components/TechnicalIndicators';
import { NewsList } from '../components/NewsList';
import { AIAnalysisResult } from '../components/AIAnalysisResult';
import { useStockStore } from '../stores/stockStore';
import { getConfig } from '../api/stockApi';
import { AlertCircle, TrendingUp, KeyRound, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';

export const HomePage: React.FC = () => {
  const { error, isLoading, stockCode, klineData } = useStockStore();
  const hasData = stockCode && klineData.length > 0;
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    getConfig()
      .then((cfg) => setAiConfigured(!!cfg.has_ai_config))
      .catch(() => setAiConfigured(false));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {aiConfigured === false && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <KeyRound className="w-5 h-5 text-amber-500 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-amber-800">AI 分析功能未启用</p>
                <p className="text-xs text-amber-600 mt-0.5">
                  请先在设置中配置 AI API Key，才能使用 AI 深度分析报告功能
                </p>
              </div>
            </div>
            <Link
              to="/settings"
              className="px-4 py-2 bg-amber-500 text-white text-sm font-medium rounded-lg hover:bg-amber-600 transition-colors flex items-center gap-1.5 flex-shrink-0"
            >
              <Settings className="w-4 h-4" />
              前往设置
            </Link>
          </div>
        )}

        <div className="mb-8">
          <StockSearchForm />
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {isLoading && (
          <div className="mb-6 p-8 bg-white rounded-2xl shadow-lg border border-gray-100 text-center">
            <div className="animate-spin w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            <p className="text-gray-600">正在分析股票数据...</p>
          </div>
        )}

        {!hasData && !isLoading && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-20 h-20 bg-gradient-to-br from-emerald-400 to-teal-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
              <TrendingUp className="w-10 h-10 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-gray-800 mb-2">输入股票代码开始分析</h2>
            <p className="text-gray-400 max-w-sm">
              搜索 A 股、港股或美股代码，获取 K 线图表、新闻资讯与 AI 深度分析报告
            </p>
          </div>
        )}

        {hasData && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:h-[620px]">
              <div className="lg:col-span-2 h-full">
                <KLineChart />
              </div>
              <div className="flex flex-col gap-4 h-full min-h-0">
                <TechnicalIndicators />
                <NewsList />
              </div>
            </div>

            {aiConfigured && <AIAnalysisResult />}

            {!aiConfigured && (
              <div className="bg-white rounded-2xl shadow-lg p-8 border border-gray-100 text-center">
                <KeyRound className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-bold text-gray-700 mb-2">AI 分析报告不可用</h3>
                <p className="text-sm text-gray-400 mb-4">请先配置 AI API Key 以启用深度分析功能</p>
                <Link
                  to="/settings"
                  className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-violet-500 text-white font-medium rounded-xl hover:bg-violet-600 transition-colors"
                >
                  <Settings className="w-4 h-4" />
                  前往设置
                </Link>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="mt-12 py-6 border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-gray-500">
          <p>股票 AI 分析 Agent © 2024</p>
          <p className="mt-1">本工具仅供参考，不构成投资建议</p>
        </div>
      </footer>
    </div>
  );
};
