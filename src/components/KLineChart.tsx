import React from 'react';
import { useStockStore } from '../stores/stockStore';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { TrendingUp } from 'lucide-react';

export const KLineChart: React.FC = () => {
  const { klineData, klineIndicators } = useStockStore();

  if (!klineData || klineData.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">K线走势图</h3>
        </div>
        <div className="h-64 flex items-center justify-center text-gray-400">
          暂无数据，请先搜索股票进行分析
        </div>
      </div>
    );
  }

  const chartData = klineData.map((item) => ({
    date: item.date.slice(5),
    close: item.close,
    open: item.open,
    high: item.high,
    low: item.low,
  }));

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center">
          <TrendingUp className="w-5 h-5 text-white" />
        </div>
        <h3 className="text-lg font-bold text-gray-900">K线走势图</h3>
      </div>

      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12, fill: '#6b7280' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
            />
            <YAxis
              tick={{ fontSize: 12, fill: '#6b7280' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                border: '1px solid #e5e7eb',
                borderRadius: '12px',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
              }}
              labelStyle={{ color: '#374151', fontWeight: 600 }}
            />
            <Legend
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ paddingTop: '20px' }}
            />
            <Line
              type="monotone"
              dataKey="close"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="收盘价"
            />
            <Line
              type="monotone"
              dataKey="open"
              stroke="#10b981"
              strokeWidth={1.5}
              dot={false}
              name="开盘价"
              strokeDasharray="5 5"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {klineIndicators && (
        <div className="mt-4 grid grid-cols-3 gap-3">
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">最新收盘</p>
            <p className="text-lg font-bold text-gray-900">
              {klineIndicators.latest_close.toFixed(2)}
            </p>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">区间涨跌</p>
            <p
              className={`text-lg font-bold ${
                klineIndicators.price_change >= 0 ? 'text-emerald-600' : 'text-red-600'
              }`}
            >
              {klineIndicators.price_change >= 0 ? '+' : ''}
              {klineIndicators.price_change.toFixed(2)}%
            </p>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">成交量变化</p>
            <p
              className={`text-lg font-bold ${
                klineIndicators.volume_change >= 0 ? 'text-emerald-600' : 'text-red-600'
              }`}
            >
              {klineIndicators.volume_change >= 0 ? '+' : ''}
              {klineIndicators.volume_change.toFixed(1)}%
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
