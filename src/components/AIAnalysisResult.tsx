import React from 'react';
import { useStockStore } from '../stores/stockStore';
import { Brain, TrendingUp, MessageSquare, Shield, Download, Copy } from 'lucide-react';

export const AIAnalysisResult: React.FC = () => {
  const { analysisResult, stockCode, stockName } = useStockStore();

  const handleExport = () => {
    if (!analysisResult) return;

    const report = generateTextReport();
    const blob = new Blob([report], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${stockCode}_${stockName}_分析报告_${analysisResult.analysis_date}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    if (!analysisResult) return;
    const report = generateTextReport();
    navigator.clipboard.writeText(report);
    alert('报告已复制到剪贴板');
  };

  const generateTextReport = () => {
    if (!analysisResult) return '';

    return `
股票 AI 分析报告
================

股票代码: ${analysisResult.stock_code}
股票名称: ${analysisResult.stock_name}
分析日期: ${analysisResult.analysis_date}

技术面分析
----------
趋势判断: ${analysisResult.technical_analysis.trend}
支撑位: ${analysisResult.technical_analysis.support_level}
压力位: ${analysisResult.technical_analysis.resistance_level}
指标总结: ${analysisResult.technical_analysis.indicators_summary}

消息面分析
----------
情绪判断: ${analysisResult.news_analysis.sentiment}
关键事件:
${analysisResult.news_analysis.key_events.map(e => `- ${e}`).join('\n')}
市场反馈: ${analysisResult.news_analysis.market_feedback}

综合建议
--------
投资建议: ${analysisResult.recommendation}
风险等级: ${analysisResult.risk_level}

分析总结
--------
${analysisResult.summary}
`;
  };

  if (!analysisResult) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-rose-500 to-red-600 rounded-xl flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">AI 分析结果</h3>
        </div>
        <div className="h-48 flex items-center justify-center text-gray-400">
          暂无分析结果，请先搜索股票
        </div>
      </div>
    );
  }

  const cards = [
    {
      icon: TrendingUp,
      label: '技术面',
      value: analysisResult.technical_analysis.trend,
      gradient: 'from-blue-500 to-indigo-600',
      bgColor: 'bg-blue-50',
      textColor: 'text-blue-700',
    },
    {
      icon: MessageSquare,
      label: '消息面',
      value: analysisResult.news_analysis.sentiment,
      gradient: 'from-purple-500 to-pink-600',
      bgColor: 'bg-purple-50',
      textColor: 'text-purple-700',
    },
    {
      icon: Shield,
      label: '风险等级',
      value: analysisResult.risk_level,
      gradient:
        analysisResult.risk_level === '高'
          ? 'from-red-500 to-orange-600'
          : analysisResult.risk_level === '低'
          ? 'from-emerald-500 to-teal-600'
          : 'from-amber-500 to-orange-600',
      bgColor:
        analysisResult.risk_level === '高'
          ? 'bg-red-50'
          : analysisResult.risk_level === '低'
          ? 'bg-emerald-50'
          : 'bg-amber-50',
      textColor:
        analysisResult.risk_level === '高'
          ? 'text-red-700'
          : analysisResult.risk_level === '低'
          ? 'text-emerald-700'
          : 'text-amber-700',
    },
  ];

  const recommendationColors: Record<string, string> = {
    买入: 'bg-emerald-500',
    持有: 'bg-blue-500',
    观望: 'bg-amber-500',
    卖出: 'bg-red-500',
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-rose-500 to-red-600 rounded-xl flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">AI 分析结果</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="复制报告"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium"
          >
            <Download className="w-4 h-4" />
            导出报告
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {cards.map((card, index) => (
          <div
            key={index}
            className={`${card.bgColor} rounded-xl p-4 text-center`}
          >
            <div
              className={`w-10 h-10 mx-auto mb-2 rounded-xl bg-gradient-to-br ${card.gradient} flex items-center justify-center`}
            >
              <card.icon className="w-5 h-5 text-white" />
            </div>
            <p className="text-xs text-gray-500 mb-1">{card.label}</p>
            <p className={`text-lg font-bold ${card.textColor}`}>{card.value}</p>
          </div>
        ))}
      </div>

      <div className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm font-medium text-gray-700">投资建议</span>
          <span
            className={`px-4 py-2 rounded-xl text-white font-bold text-lg shadow-lg ${
              recommendationColors[analysisResult.recommendation] || 'bg-gray-500'
            }`}
          >
            {analysisResult.recommendation}
          </span>
        </div>
      </div>

      <div className="bg-gray-50 rounded-xl p-4">
        <h4 className="text-sm font-semibold text-gray-900 mb-2">分析总结</h4>
        <p className="text-sm text-gray-600 leading-relaxed">
          {analysisResult.summary}
        </p>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-100">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">支撑位</span>
            <p className="font-semibold text-emerald-600">
              {analysisResult.technical_analysis.support_level.toFixed(2)}
            </p>
          </div>
          <div>
            <span className="text-gray-500">压力位</span>
            <p className="font-semibold text-red-600">
              {analysisResult.technical_analysis.resistance_level.toFixed(2)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
