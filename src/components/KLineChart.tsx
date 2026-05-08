import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { TrendingUp } from 'lucide-react';
import { useStockStore } from '../stores/stockStore';
import type { KlineData } from '../types';

function computeMA(data: KlineData[], period: number): (number | string)[] {
  return data.map((_, i) => {
    if (i < period - 1) return '-';
    const sum = data.slice(i - period + 1, i + 1).reduce((acc, d) => acc + d.close, 0);
    return parseFloat((sum / period).toFixed(2));
  });
}

export const KLineChart: React.FC = () => {
  const { klineData, klineIndicators } = useStockStore();

  const option = useMemo(() => {
    if (!klineData?.length) return {};

    const categoryData = klineData.map(item => item.date);
    // ECharts candlestick data format: [open, close, low, high]
    const values = klineData.map(item => [item.open, item.close, item.low, item.high]);
    
    const ma5 = computeMA(klineData, 5);
    const ma10 = computeMA(klineData, 10);
    const ma20 = computeMA(klineData, 20);

    const upColor = '#ef4444';
    const downColor = '#22c55e';

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: {
            color: '#999',
            type: 'dashed'
          }
        },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e5e7eb',
        textStyle: {
          color: '#374151',
          fontSize: 12
        },
        padding: [12, 16],
        formatter: function (params: any) {
          const dataIndex = params[0].dataIndex;
          const date = categoryData[dataIndex];
          const rawItem = klineData[dataIndex];
          
          const isUp = rawItem.close >= rawItem.open;
          const chg = rawItem.open !== 0 ? ((rawItem.close - rawItem.open) / rawItem.open * 100).toFixed(2) : '0.00';
          const chgColor = isUp ? upColor : downColor;
          const chgSign = isUp ? '+' : '';

          let html = `<div style="min-width: 140px;">
            <div style="font-weight: bold; color: #374151; margin-bottom: 8px; border-bottom: 1px solid #f3f4f6; padding-bottom: 4px;">${date}</div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #9ca3af;">开盘</span>
              <span style="font-weight: 500;">${rawItem.open.toFixed(2)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #9ca3af;">收盘</span>
              <span style="font-weight: bold; color: ${chgColor};">${rawItem.close.toFixed(2)} (${chgSign}${chg}%)</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #9ca3af;">最高</span>
              <span style="font-weight: 500; color: #f87171;">${rawItem.high.toFixed(2)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #9ca3af;">最低</span>
              <span style="font-weight: 500; color: #4ade80;">${rawItem.low.toFixed(2)}</span>
            </div>
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #f3f4f6;">`;

          params.forEach((param: any) => {
            if (param.seriesName.startsWith('MA') && param.value !== '-') {
              html += `<div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span style="color: ${param.color};">${param.seriesName}</span>
                <span style="color: #4b5563;">${parseFloat(param.value).toFixed(2)}</span>
              </div>`;
            }
          });

          html += `</div></div>`;
          return html;
        }
      },
      grid: {
        left: '2%',
        right: '4%',
        bottom: '12%',
        top: '4%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: categoryData,
        scale: true,
        boundaryGap: true,
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisLabel: {
          color: '#9ca3af',
          formatter: function (value: string) {
            // 只显示 MM-DD
            return value.substring(5);
          }
        },
        splitLine: { show: false },
        axisPointer: {
          label: {
            backgroundColor: '#6b7280'
          }
        }
      },
      yAxis: {
        scale: true,
        splitArea: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#9ca3af',
          formatter: '{value}'
        },
        splitLine: {
          lineStyle: {
            color: '#f3f4f6',
            type: 'dashed'
          }
        }
      },
      dataZoom: [
        {
          type: 'inside',
          start: klineData.length > 60 ? 50 : 0,
          end: 100
        },
        {
          show: true,
          type: 'slider',
          bottom: '2%',
          height: 24,
          start: klineData.length > 60 ? 50 : 0,
          end: 100,
          borderColor: 'transparent',
          backgroundColor: '#f9fafb',
          fillerColor: 'rgba(59, 130, 246, 0.1)',
          handleStyle: {
            color: '#fff',
            shadowBlur: 3,
            shadowColor: 'rgba(0, 0, 0, 0.2)',
            shadowOffsetX: 1,
            shadowOffsetY: 1
          },
          textStyle: {
            color: '#9ca3af'
          }
        }
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: values,
          itemStyle: {
            color: upColor,
            color0: '#fff', // 下跌为空心绿
            borderColor: upColor,
            borderColor0: downColor,
            borderWidth: 1.5
          },
          barMaxWidth: 20,
          barMinWidth: 2
        },
        {
          name: 'MA5',
          type: 'line',
          data: ma5,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: '#3b82f6', width: 1.5 },
          itemStyle: { color: '#3b82f6' }
        },
        {
          name: 'MA10',
          type: 'line',
          data: ma10,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: '#fb923c', width: 1.5 },
          itemStyle: { color: '#fb923c' }
        },
        {
          name: 'MA20',
          type: 'line',
          data: ma20,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: '#a855f7', width: 1.5 },
          itemStyle: { color: '#a855f7' }
        }
      ]
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
    <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100 h-full flex flex-col min-h-[450px]">
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">K线走势图</h3>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-0.5 bg-blue-500 rounded" />
            <span className="text-gray-500">MA5</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-0.5 bg-orange-400 rounded" />
            <span className="text-gray-500">MA10</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-0.5 bg-purple-500 rounded" />
            <span className="text-gray-500">MA20</span>
          </span>
          <span className="flex items-center gap-1.5 ml-1">
            <span className="inline-block w-3 h-4 bg-red-500 rounded-sm" />
            <span className="text-gray-500">涨</span>
            <span className="inline-block w-3 h-4 border border-green-500 rounded-sm bg-white" />
            <span className="text-gray-500">跌</span>
          </span>
        </div>
      </div>

      <div className="flex-1 min-h-0 w-full relative">
        <ReactECharts
          option={option}
          style={{ height: '100%', width: '100%' }}
          notMerge={true}
          lazyUpdate={true}
        />
      </div>

      {klineIndicators && (
        <div className="mt-4 flex-shrink-0 grid grid-cols-3 gap-3 border-t border-gray-100 pt-4">
          <div className="bg-gray-50 rounded-xl p-3 text-center transition-colors hover:bg-gray-100">
            <p className="text-xs text-gray-400 mb-1">最新收盘</p>
            <p className="text-lg font-bold text-gray-900">
              {klineIndicators.latest_close.toFixed(2)}
            </p>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 text-center transition-colors hover:bg-gray-100">
            <p className="text-xs text-gray-400 mb-1">区间涨跌</p>
            <p className={`text-lg font-bold ${klineIndicators.price_change >= 0 ? 'text-red-500' : 'text-green-600'}`}>
              {klineIndicators.price_change >= 0 ? '+' : ''}{klineIndicators.price_change.toFixed(2)}%
            </p>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 text-center transition-colors hover:bg-gray-100">
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
