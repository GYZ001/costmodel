import React from 'react';
import { useStockStore } from '../stores/stockStore';
import { BarChart3 } from 'lucide-react';

export const TechnicalIndicators: React.FC = () => {
  const { klineIndicators } = useStockStore();

  if (!klineIndicators) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-amber-500 to-orange-600 rounded-xl flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">技术指标</h3>
        </div>
        <div className="h-32 flex items-center justify-center text-gray-400">
          暂无数据
        </div>
      </div>
    );
  }

  const indicators = [
    { label: 'MA5', value: klineIndicators.ma5, color: 'blue' },
    { label: 'MA10', value: klineIndicators.ma10, color: 'emerald' },
    { label: 'MA20', value: klineIndicators.ma20, color: 'purple' },
  ];

  const colorMap: Record<string, string> = {
    blue: 'bg-blue-500',
    emerald: 'bg-emerald-500',
    purple: 'bg-purple-500',
    orange: 'bg-orange-500',
    red: 'bg-red-500',
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-gradient-to-br from-amber-500 to-orange-600 rounded-xl flex items-center justify-center">
          <BarChart3 className="w-5 h-5 text-white" />
        </div>
        <h3 className="text-lg font-bold text-gray-900">技术指标</h3>
      </div>

      <div className="space-y-4">
        {indicators.map((item) => (
          <div key={item.label} className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${colorMap[item.color]}`} />
              <span className="text-sm font-medium text-gray-600">{item.label}</span>
            </div>
            <span className="text-lg font-bold text-gray-900">
              {item.value.toFixed(2)}
            </span>
          </div>
        ))}

        <div className="border-t border-gray-100 pt-4 mt-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-emerald-50 rounded-xl p-3">
              <p className="text-xs text-emerald-600 mb-1">最高价</p>
              <p className="text-sm font-bold text-emerald-700">
                {klineIndicators.highest.toFixed(2)}
              </p>
            </div>
            <div className="bg-red-50 rounded-xl p-3">
              <p className="text-xs text-red-600 mb-1">最低价</p>
              <p className="text-sm font-bold text-red-700">
                {klineIndicators.lowest.toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
