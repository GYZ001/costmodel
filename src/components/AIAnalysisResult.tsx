import React, { useState } from 'react';
import { useStockStore } from '../stores/stockStore';
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Minus,
  MessageSquare,
  Shield,
  Download,
  Copy,
  Sparkles,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Target,
  Lightbulb,
  Activity,
  Wallet,
  TrendingUp as PnlUp,
} from 'lucide-react';

const RECOMMENDATION_CONFIG: Record<string, { bg: string; text: string; border: string }> = {
  强烈买入: { bg: 'bg-emerald-600', text: 'text-white', border: 'border-emerald-600' },
  买入:     { bg: 'bg-emerald-500', text: 'text-white', border: 'border-emerald-500' },
  持有:     { bg: 'bg-blue-500',    text: 'text-white', border: 'border-blue-500'    },
  观望:     { bg: 'bg-amber-500',   text: 'text-white', border: 'border-amber-500'   },
  减仓:     { bg: 'bg-orange-500',  text: 'text-white', border: 'border-orange-500'  },
  卖出:     { bg: 'bg-red-500',     text: 'text-white', border: 'border-red-500'     },
};

const RISK_CONFIG: Record<string, { bg: string; text: string; icon: string }> = {
  高: { bg: 'bg-red-50',     text: 'text-red-700',     icon: '🔴' },
  中: { bg: 'bg-amber-50',   text: 'text-amber-700',   icon: '🟡' },
  低: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: '🟢' },
};

const SENTIMENT_CONFIG: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  正面: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <TrendingUp className="w-4 h-4" /> },
  中性: { bg: 'bg-gray-50',    text: 'text-gray-700',    icon: <Minus className="w-4 h-4" /> },
  负面: { bg: 'bg-red-50',     text: 'text-red-700',     icon: <TrendingDown className="w-4 h-4" /> },
};

const TREND_CONFIG: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  上涨: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <TrendingUp className="w-4 h-4" /> },
  筑底: { bg: 'bg-blue-50',    text: 'text-blue-700',    icon: <Activity className="w-4 h-4" /> },
  震荡: { bg: 'bg-gray-50',    text: 'text-gray-700',    icon: <Minus className="w-4 h-4" /> },
  见顶: { bg: 'bg-orange-50',  text: 'text-orange-700',  icon: <TrendingDown className="w-4 h-4" /> },
  下跌: { bg: 'bg-red-50',     text: 'text-red-700',     icon: <TrendingDown className="w-4 h-4" /> },
};

function getTrendConfig(trend: string) {
  return TREND_CONFIG[trend] ?? { bg: 'bg-gray-50', text: 'text-gray-700', icon: <Minus className="w-4 h-4" /> };
}

function getSentimentConfig(sentiment: string) {
  if (sentiment?.includes('正面')) return SENTIMENT_CONFIG['正面'];
  if (sentiment?.includes('负面')) return SENTIMENT_CONFIG['负面'];
  return SENTIMENT_CONFIG['中性'];
}

function getRiskConfig(risk: string) {
  return RISK_CONFIG[risk] ?? { bg: 'bg-gray-50', text: 'text-gray-700', icon: '⚪' };
}

function getRecommendationConfig(rec: string) {
  return RECOMMENDATION_CONFIG[rec] ?? { bg: 'bg-gray-500', text: 'text-white', border: 'border-gray-500' };
}

const EMPTY = '—';

export const AIAnalysisResult: React.FC = () => {
  const { analysisResult, stockCode, stockName } = useStockStore();
  const [techExpanded, setTechExpanded] = useState(true);
  const [newsExpanded, setNewsExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const generateTextReport = () => {
    if (!analysisResult) return '';
    const r = analysisResult;
    return `股票 AI 分析报告
================
股票代码: ${r.stock_code}
股票名称: ${r.stock_name}
分析日期: ${r.analysis_date}
${r.is_local_analysis ? '（本地规则分析）' : '（AI 深度分析）'}

【投资建议】${r.recommendation}  风险等级：${r.risk_level}

【核心逻辑】
${r.investment_logic || EMPTY}

【操作策略】
${r.action_plan || EMPTY}

【技术面分析】
趋势：${r.technical_analysis?.trend || EMPTY}
支撑位：${r.technical_analysis?.support_level ?? EMPTY}
压力位：${r.technical_analysis?.resistance_level ?? EMPTY}
指标：${r.technical_analysis?.indicators_summary || EMPTY}
${r.technical_analysis?.detail ? '\n深度分析：\n' + r.technical_analysis.detail : ''}

【消息面分析】
情绪：${r.news_analysis?.sentiment || EMPTY}
关键事件：
${(r.news_analysis?.key_events || []).map((e: string) => '- ' + e).join('\n') || EMPTY}
市场反馈：${r.news_analysis?.market_feedback || EMPTY}
${r.news_analysis?.detail ? '\n深度分析：\n' + r.news_analysis.detail : ''}

【风险因素】
${(r.risk_factors || []).map((f: string) => '- ' + f).join('\n') || EMPTY}

【综合总结】
${r.summary || EMPTY}
`;
  };

  const handleExport = () => {
    if (!analysisResult) return;
    const report = generateTextReport();
    const blob = new Blob([report], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${stockCode}_${stockName || '股票'}_分析报告_${analysisResult.analysis_date}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    if (!analysisResult) return;
    navigator.clipboard.writeText(generateTextReport());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!analysisResult) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">AI 分析报告</h3>
        </div>
        <div className="h-48 flex items-center justify-center text-gray-400">
          暂无分析结果，请先搜索股票
        </div>
      </div>
    );
  }

  const r = analysisResult;
  const isLocal = r.is_local_analysis === true;
  const recConf = getRecommendationConfig(r.recommendation);
  const riskConf = getRiskConfig(r.risk_level);
  const trendConf = getTrendConfig(r.technical_analysis?.trend);
  const sentConf = getSentimentConfig(r.news_analysis?.sentiment);

  const techIndicators = r.technical_analysis?.indicators_summary;
  const techDetail = r.technical_analysis?.detail;
  const newsDetail = r.news_analysis?.detail;
  const keyEvents: string[] = r.news_analysis?.key_events || [];
  const marketFeedback = r.news_analysis?.market_feedback;
  const riskFactors: string[] = r.risk_factors || [];

  return (
    <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
      <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">AI 分析报告</h3>
            <p className="text-xs text-gray-400">
              {r.analysis_date} · {r.stock_name}（{r.stock_code}）
              {isLocal && (
                <span className="ml-1 inline-flex items-center gap-0.5 text-amber-500">
                  <Sparkles className="w-3 h-3" />本地规则
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-1"
          >
            <Copy className="w-3.5 h-3.5" />
            {copied ? '已复制' : '复制'}
          </button>
          <button
            onClick={handleExport}
            className="px-3 py-1.5 text-sm bg-violet-500 text-white rounded-lg hover:bg-violet-600 transition-colors flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5" />
            导出
          </button>
        </div>
      </div>

      <div className="p-6 space-y-5">

        <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl bg-gray-50 border border-gray-100">
          <span className={`px-5 py-2 rounded-xl font-bold text-lg shadow ${recConf.bg} ${recConf.text}`}>
            {r.recommendation || EMPTY}
          </span>
          <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-lg text-sm font-medium ${trendConf.bg} ${trendConf.text}`}>
            {trendConf.icon} {r.technical_analysis?.trend || EMPTY}
          </span>
          <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-lg text-sm font-medium ${sentConf.bg} ${sentConf.text}`}>
            {sentConf.icon} {r.news_analysis?.sentiment || EMPTY}
          </span>
          <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-lg text-sm font-medium ${riskConf.bg} ${riskConf.text}`}>
            {riskConf.icon} 风险{r.risk_level || EMPTY}
          </span>
        </div>

        <div className="flex gap-3 p-4 bg-violet-50 border border-violet-100 rounded-xl">
          <Lightbulb className="w-5 h-5 text-violet-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-violet-700 mb-1">核心投资逻辑</p>
            <p className="text-sm text-violet-800 leading-relaxed">
              {r.investment_logic || <span className="text-violet-400">{EMPTY}</span>}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="bg-emerald-50 rounded-xl p-3 text-center">
            <p className="text-xs text-emerald-600 mb-1">支撑位</p>
            <p className="text-lg font-bold text-emerald-700">
              {r.technical_analysis?.support_level != null
                ? r.technical_analysis.support_level.toFixed(2)
                : EMPTY}
            </p>
          </div>
          <div className="bg-red-50 rounded-xl p-3 text-center">
            <p className="text-xs text-red-500 mb-1">压力位</p>
            <p className="text-lg font-bold text-red-600">
              {r.technical_analysis?.resistance_level != null
                ? r.technical_analysis.resistance_level.toFixed(2)
                : EMPTY}
            </p>
          </div>
        </div>

        <div className="border border-gray-100 rounded-xl overflow-hidden">
          <button
            onClick={() => setTechExpanded(!techExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 bg-blue-50 hover:bg-blue-100 transition-colors"
          >
            <span className="flex items-center gap-2 text-sm font-semibold text-blue-800">
              <TrendingUp className="w-4 h-4" />
              技术面分析
            </span>
            {techExpanded
              ? <ChevronUp className="w-4 h-4 text-blue-500" />
              : <ChevronDown className="w-4 h-4 text-blue-500" />}
          </button>
          {techExpanded && (
            <div className="px-4 py-4 space-y-3">
              <div>
                <p className="text-xs font-semibold text-gray-400 mb-1">核心指标</p>
                <p className="text-xs text-gray-600 bg-gray-50 rounded-lg px-3 py-2 font-mono whitespace-pre-wrap">
                  {techIndicators || EMPTY}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-400 mb-1">深度分析</p>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {techDetail || <span className="text-gray-400">{EMPTY}</span>}
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="border border-gray-100 rounded-xl overflow-hidden">
          <button
            onClick={() => setNewsExpanded(!newsExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 bg-purple-50 hover:bg-purple-100 transition-colors"
          >
            <span className="flex items-center gap-2 text-sm font-semibold text-purple-800">
              <MessageSquare className="w-4 h-4" />
              消息面分析
            </span>
            {newsExpanded
              ? <ChevronUp className="w-4 h-4 text-purple-500" />
              : <ChevronDown className="w-4 h-4 text-purple-500" />}
          </button>
          {newsExpanded && (
            <div className="px-4 py-4 space-y-3">
              <div>
                <p className="text-xs font-semibold text-gray-400 mb-2">关键事件</p>
                {keyEvents.length > 0 ? (
                  <ul className="space-y-1.5">
                    {keyEvents.map((event: string, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                        <span className="w-1.5 h-1.5 rounded-full bg-purple-400 flex-shrink-0 mt-1.5" />
                        {event}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-400">{EMPTY}</p>
                )}
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-400 mb-1">市场反馈</p>
                <p className="text-xs text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
                  {marketFeedback || EMPTY}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-400 mb-1">深度分析</p>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {newsDetail || <span className="text-gray-400">{EMPTY}</span>}
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-3 p-4 bg-amber-50 border border-amber-100 rounded-xl">
          <Target className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-amber-700 mb-1">操作策略</p>
            <p className="text-sm text-amber-800 leading-relaxed">
              {r.action_plan || <span className="text-amber-400">{EMPTY}</span>}
            </p>
          </div>
        </div>

        {r.position_analysis && (r.position_analysis.current_pnl_pct != null || r.position_analysis.advice_for_holder) && (
          <div className="border border-blue-100 rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-blue-50 flex items-center gap-2">
              <Wallet className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-semibold text-blue-800">持仓诊断</span>
            </div>
            <div className="px-4 py-4 space-y-3">
              {r.position_analysis.current_pnl_pct != null && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">当前浮动盈亏</span>
                  <span className={`text-base font-bold ${
                    r.position_analysis.current_pnl_pct >= 0 ? 'text-red-500' : 'text-green-600'
                  }`}>
                    {r.position_analysis.current_pnl_pct >= 0 ? '+' : ''}{r.position_analysis.current_pnl_pct.toFixed(2)}%
                  </span>
                </div>
              )}
              {r.position_analysis.cost_vs_support && (
                <div>
                  <p className="text-xs font-semibold text-gray-400 mb-1">成本位与支撑位关系</p>
                  <p className="text-xs text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
                    {r.position_analysis.cost_vs_support}
                  </p>
                </div>
              )}
              {r.position_analysis.advice_for_holder && (
                <div>
                  <p className="text-xs font-semibold text-blue-600 mb-1">持仓操作建议</p>
                  <p className="text-sm text-blue-800 leading-relaxed whitespace-pre-wrap">
                    {r.position_analysis.advice_for_holder}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="p-4 bg-red-50 border border-red-100 rounded-xl">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-red-500" />
            <p className="text-xs font-semibold text-red-700">主要风险</p>
          </div>
          {riskFactors.length > 0 ? (
            <ul className="space-y-1">
              {riskFactors.map((f: string, i: number) => (
                <li key={i} className="flex items-start gap-2 text-sm text-red-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0 mt-1.5" />
                  {f}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-red-400">{EMPTY}</p>
          )}
        </div>

        <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-gray-500" />
            <p className="text-xs font-semibold text-gray-600">综合总结</p>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">
            {r.summary || <span className="text-gray-400">{EMPTY}</span>}
          </p>
        </div>

        <p className="text-center text-xs text-gray-400">本报告仅供参考，不构成投资建议，请自行承担投资风险</p>
      </div>
    </div>
  );
};
