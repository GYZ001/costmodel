import React from 'react';
import { useStockStore } from '../stores/stockStore';
import { useStockAnalysis } from '../hooks/useStockAnalysis';
import { Search, TrendingUp, Loader2 } from 'lucide-react';
import type { Market, Period } from '../types';

const markets: { value: Market; label: string }[] = [
  { value: 'A股', label: 'A股' },
  { value: '港股', label: '港股' },
  { value: '美股', label: '美股' },
];

const periods: { value: Period; label: string }[] = [
  { value: '日线', label: '日线' },
  { value: '周线', label: '周线' },
  { value: '月线', label: '月线' },
];

export const StockSearchForm: React.FC = () => {
  const {
    stockCode,
    stockName,
    market,
    period,
    days,
    setStockCode,
    setStockName,
    setMarket,
    setPeriod,
    setDays,
  } = useStockStore();

  const { analyze, isAnalyzing, progress } = useStockAnalysis();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    analyze();
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-6 md:p-8 border border-gray-100">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center">
          <Search className="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-gray-900">股票分析</h2>
          <p className="text-sm text-gray-500">输入股票信息开始智能分析</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div className="lg:col-span-1">
          <label className="block text-sm font-medium text-gray-700 mb-2">股票代码</label>
          <input
            type="text"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value)}
            placeholder="如: 600519"
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50"
          />
        </div>

        <div className="lg:col-span-1">
          <label className="block text-sm font-medium text-gray-700 mb-2">股票名称</label>
          <input
            type="text"
            value={stockName}
            onChange={(e) => setStockName(e.target.value)}
            placeholder="如: 贵州茅台"
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">市场</label>
          <select
            value={market}
            onChange={(e) => setMarket(e.target.value as Market)}
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50 appearance-none cursor-pointer"
          >
            {markets.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">周期</label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as Period)}
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50 appearance-none cursor-pointer"
          >
            {periods.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">分析天数</label>
          <input
            type="number"
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value) || 30)}
            min={5}
            max={365}
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={isAnalyzing}
        className="w-full md:w-auto px-8 py-3.5 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold rounded-xl hover:from-emerald-600 hover:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 flex items-center justify-center gap-2"
      >
        {isAnalyzing ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>{progress || '分析中...'}</span>
          </>
        ) : (
          <>
            <TrendingUp className="w-5 h-5" />
            <span>开始分析</span>
          </>
        )}
      </button>
    </form>
  );
};
