import React from 'react';
import { Header } from '../components/Header';
import { StockSearchForm } from '../components/StockSearchForm';
import { KLineChart } from '../components/KLineChart';
import { TechnicalIndicators } from '../components/TechnicalIndicators';
import { NewsList } from '../components/NewsList';
import { AIAnalysisResult } from '../components/AIAnalysisResult';
import { DiagnosticPanel } from '../components/DiagnosticPanel';
import { useStockStore } from '../stores/stockStore';
import { AlertCircle } from 'lucide-react';

export const HomePage: React.FC = () => {
  const { error, isLoading } = useStockStore();

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <StockSearchForm />
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <DiagnosticPanel />

        {isLoading && (
          <div className="mb-6 p-8 bg-white rounded-2xl shadow-lg border border-gray-100 text-center">
            <div className="animate-spin w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            <p className="text-gray-600">正在分析股票数据...</p>
          </div>
        )}

        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <KLineChart />
            </div>
            <div>
              <TechnicalIndicators />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <NewsList />
            <AIAnalysisResult />
          </div>
        </div>
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
