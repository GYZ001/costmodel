import React from 'react';
import { useStockStore } from '../stores/stockStore';
import { useStockAnalysis } from '../hooks/useStockAnalysis';
import { Search, Loader2, Wallet } from 'lucide-react';
import type { Period } from '../types';

const PERIOD_CONFIG: Record<Period, { label: string; defaultCount: number; min: number; max: number; unit: string }> = {
  日线: { label: '分析天数', defaultCount: 30, min: 5,  max: 365, unit: '天' },
  周线: { label: '分析周数', defaultCount: 12, min: 4,  max: 52,  unit: '周' },
  月线: { label: '分析月数', defaultCount: 6,  min: 1,  max: 24,  unit: '个月' },
};

export const StockSearchForm: React.FC = () => {
  const {
    stockCode,
    market,
    period,
    days,
    hasPosition,
    costPrice,
    shares,
    setStockCode,
    setMarket,
    setPeriod,
    setDays,
    setHasPosition,
    setCostPrice,
    setShares,
  } = useStockStore();

  const { analyze, isAnalyzing, progress } = useStockAnalysis();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    analyze();
  };

  const handleCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setStockCode(e.target.value.toUpperCase());
  };

  const handlePeriodChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newPeriod = e.target.value as Period;
    setPeriod(newPeriod);
    setDays(PERIOD_CONFIG[newPeriod].defaultCount);
  };

  const periodConf = PERIOD_CONFIG[period];

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-6 md:p-8 border border-gray-100">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center">
          <Search className="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-gray-900">股票分析</h2>
          <p className="text-sm text-gray-500">输入股票代码开始智能分析</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div className="lg:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-2">股票代码</label>
          <input
            type="text"
            value={stockCode}
            onChange={handleCodeChange}
            placeholder="如: 600519"
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50 text-lg font-mono"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">市场</label>
          <select
            value={market}
            onChange={(e) => setMarket(e.target.value as any)}
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50 appearance-none cursor-pointer"
          >
            <option value="A股">A股</option>
            <option value="港股">港股</option>
            <option value="美股">美股</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">周期</label>
          <select
            value={period}
            onChange={handlePeriodChange}
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50 appearance-none cursor-pointer"
          >
            <option value="日线">日线</option>
            <option value="周线">周线</option>
            <option value="月线">月线</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {periodConf.label}
          </label>
          <div className="relative">
            <input
              type="number"
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value) || periodConf.defaultCount)}
              min={periodConf.min}
              max={periodConf.max}
              className="w-full px-4 py-3 pr-10 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 pointer-events-none">
              {periodConf.unit}
            </span>
          </div>
        </div>
      </div>

      <div className="border-t border-gray-100 pt-5 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <Wallet className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-600">持仓信息（可选）</span>
          <label className="flex items-center gap-2 ml-auto cursor-pointer select-none">
            <span className="text-sm text-gray-500">我已持仓</span>
            <div
              onClick={() => setHasPosition(!hasPosition)}
              className={`relative w-10 h-5 rounded-full transition-colors cursor-pointer ${
                hasPosition ? 'bg-emerald-500' : 'bg-gray-200'
              }`}
            >
              <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                hasPosition ? 'translate-x-5' : 'translate-x-0.5'
              }`} />
            </div>
          </label>
        </div>

        {hasPosition && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                持仓成本价 <span className="text-gray-400 font-normal">（元/股）</span>
              </label>
              <input
                type="number"
                value={costPrice}
                onChange={(e) => setCostPrice(e.target.value)}
                placeholder="如: 42.50"
                min={0}
                step={0.01}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                持仓数量 <span className="text-gray-400 font-normal">（股）</span>
              </label>
              <input
                type="number"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                placeholder="如: 1000"
                min={100}
                step={100}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all bg-gray-50/50"
              />
            </div>
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={isAnalyzing || !stockCode.trim()}
        className="w-full md:w-auto px-8 py-3.5 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold rounded-xl hover:from-emerald-600 hover:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 flex items-center justify-center gap-2"
      >
        {isAnalyzing ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>{progress || '分析中...'}</span>
          </>
        ) : (
          <>
            <Search className="w-5 h-5" />
            <span>开始分析</span>
          </>
        )}
      </button>
    </form>
  );
};
