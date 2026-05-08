import React, { useMemo } from 'react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Customized,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import { useStockStore } from '../stores/stockStore';
import type { KlineData } from '../types';

function computeMA(data: KlineData[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < period - 1) return null;
    const sum = data.slice(i - period + 1, i + 1).reduce((acc, d) => acc + d.close, 0);
    return parseFloat((sum / period).toFixed(2));
  });
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;

  const isUp = d.close >= d.open;
  const chg = d.open !== 0 ? ((d.close - d.open) / d.open * 100).toFixed(2) : '0.00';

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-xl p-3 text-xs min-w-[140px]">
      <p className="font-bold text-gray-700 mb-2 border-b border-gray-100 pb-1">{d.fullDate}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-gray-400">开盘</span>
          <span className="font-medium text-gray-800">{d.open?.toFixed(2)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-400">收盘</span>
          <span className={`font-bold ${isUp ? 'text-red-500' : 'text-green-600'}`}>
            {d.close?.toFixed(2)} ({isUp ? '+' : ''}{chg}%)
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-400">最高</span>
          <span className="text-red-400 font-medium">{d.high?.toFixed(2)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-400">最低</span>
          <span className="text-green-500 font-medium">{d.low?.toFixed(2)}</span>
        </div>
      </div>
      {(d.ma5 || d.ma10 || d.ma20) && (
        <div className="mt-2 pt-2 border-t border-gray-100 space-y-1">
          {d.ma5 != null && (
            <div className="flex justify-between gap-4">
              <span className="text-blue-400">MA5</span>
              <span className="text-gray-700">{d.ma5.toFixed(2)}</span>
            </div>
          )}
          {d.ma10 != null && (
            <div className="flex justify-between gap-4">
              <span className="text-orange-400">MA10</span>
              <span className="text-gray-700">{d.ma10.toFixed(2)}</span>
            </div>
          )}
          {d.ma20 != null && (
            <div className="flex justify-between gap-4">
              <span className="text-purple-400">MA20</span>
              <span className="text-gray-700">{d.ma20.toFixed(2)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const CandlestickRenderer = ({ xAxisMap, yAxisMap, data }: any) => {
  if (!xAxisMap || !yAxisMap || !data?.length) return null;

  const xAxis = Object.values(xAxisMap)[0] as any;
  const yAxis = Object.values(yAxisMap)[0] as any;

  if (!xAxis?.scale || !yAxis?.scale) return null;

  return (
    <g>
      {data.map((d: any, i: number) => {
        const xVal = xAxis.scale(d.date);
        if (xVal === undefined || xVal === null) return null;

        const bw = typeof xAxis.scale.bandwidth === 'function' ? xAxis.scale.bandwidth() : 8;
        const bodyW = Math.max(bw * 0.65, 2);
        const bodyX = xVal + (bw - bodyW) / 2;
        const cx = xVal + bw / 2;

        const yHigh = yAxis.scale(d.high);
        const yLow = yAxis.scale(d.low);
        const yOpen = yAxis.scale(d.open);
        const yClose = yAxis.scale(d.close);

        const isUp = d.close >= d.open;
        const color = isUp ? '#ef4444' : '#22c55e';

        const bodyTop = Math.min(yOpen, yClose);
        const bodyBottom = Math.max(yOpen, yClose);
        const bodyH = Math.max(bodyBottom - bodyTop, 1.5);

        return (
          <g key={`candle-${i}`}>
            <line x1={cx} y1={yHigh} x2={cx} y2={bodyTop} stroke={color} strokeWidth={1} />
            <line x1={cx} y1={bodyBottom} x2={cx} y2={yLow} stroke={color} strokeWidth={1} />
            <rect
              x={bodyX}
              y={bodyTop}
              width={bodyW}
              height={bodyH}
              fill={isUp ? color : 'none'}
              stroke={color}
              strokeWidth={1}
            />
          </g>
        );
      })}
    </g>
  );
};

export const KLineChart: React.FC = () => {
  const { klineData, klineIndicators } = useStockStore();

  const { chartData, domain, xInterval } = useMemo(() => {
    if (!klineData?.length) return { chartData: [], domain: [0, 100] as [number, number], xInterval: 0 };

    const ma5 = computeMA(klineData, 5);
    const ma10 = computeMA(klineData, 10);
    const ma20 = computeMA(klineData, 20);

    const data = klineData.map((item, i) => ({
      date: item.date.slice(5),
      fullDate: item.date,
      open: item.open,
      close: item.close,
      high: item.high,
      low: item.low,
      ma5: ma5[i],
      ma10: ma10[i],
      ma20: ma20[i],
    }));

    const minP = Math.min(...klineData.map(d => d.low));
    const maxP = Math.max(...klineData.map(d => d.high));
    const pad = (maxP - minP) * 0.06;

    return {
      chartData: data,
      domain: [parseFloat((minP - pad).toFixed(2)), parseFloat((maxP + pad).toFixed(2))] as [number, number],
      xInterval: Math.max(Math.ceil(data.length / 7) - 1, 0),
    };
  }, [klineData]);

  if (!klineData?.length) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100 h-full flex flex-col">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">K线走势图</h3>
        </div>
        <div className="flex-1 flex items-center justify-center text-gray-400">
          暂无数据，请先搜索股票进行分析
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">K线走势图</h3>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-blue-500 inline-block rounded" />
            <span className="text-gray-500">MA5</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-orange-400 inline-block rounded" />
            <span className="text-gray-500">MA10</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-purple-500 inline-block rounded" />
            <span className="text-gray-500">MA20</span>
          </span>
          <span className="flex items-center gap-2 ml-2">
            <span className="inline-block w-3 h-3 bg-red-500 rounded-sm" />
            <span className="text-gray-500">涨</span>
            <span className="inline-block w-3 h-3 border border-green-500 rounded-sm" />
            <span className="text-gray-500">跌</span>
          </span>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
            <XAxis
              dataKey="date"
              type="category"
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              interval={xInterval}
            />
            <YAxis
              domain={domain}
              tickFormatter={(v: number) => v.toFixed(2)}
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
              width={58}
              tickCount={6}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ stroke: '#d1d5db', strokeWidth: 1, strokeDasharray: '4 2' }}
            />
            <Customized component={CandlestickRenderer} />
            <Line
              dataKey="close"
              dot={false}
              stroke="transparent"
              strokeWidth={0}
              legendType="none"
              isAnimationActive={false}
            />
            <Line
              dataKey="ma5"
              dot={false}
              stroke="#3b82f6"
              strokeWidth={1.5}
              connectNulls={false}
              legendType="none"
              isAnimationActive={false}
            />
            <Line
              dataKey="ma10"
              dot={false}
              stroke="#fb923c"
              strokeWidth={1.5}
              connectNulls={false}
              legendType="none"
              isAnimationActive={false}
            />
            <Line
              dataKey="ma20"
              dot={false}
              stroke="#a855f7"
              strokeWidth={1.5}
              connectNulls={false}
              legendType="none"
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {klineIndicators && (
        <div className="mt-4 flex-shrink-0 grid grid-cols-3 gap-3 border-t border-gray-100 pt-4">
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <p className="text-xs text-gray-400 mb-1">最新收盘</p>
            <p className="text-lg font-bold text-gray-900">
              {klineIndicators.latest_close.toFixed(2)}
            </p>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <p className="text-xs text-gray-400 mb-1">区间涨跌</p>
            <p className={`text-lg font-bold ${klineIndicators.price_change >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {klineIndicators.price_change >= 0 ? '+' : ''}{klineIndicators.price_change.toFixed(2)}%
            </p>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 text-center">
            <p className="text-xs text-gray-400 mb-1">成交量变化</p>
            <p className={`text-lg font-bold ${klineIndicators.volume_change >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {klineIndicators.volume_change >= 0 ? '+' : ''}{klineIndicators.volume_change.toFixed(1)}%
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
