import React from 'react';
import { useStockStore } from '../stores/stockStore';
import { Newspaper, ExternalLink } from 'lucide-react';

export const NewsList: React.FC = () => {
  const { newsData, newsSentiment } = useStockStore();

  if (!newsData || newsData.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
            <Newspaper className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">新闻资讯</h3>
        </div>
        <div className="h-48 flex items-center justify-center text-gray-400">
          暂无新闻数据
        </div>
      </div>
    );
  }

  const sentimentColors: Record<string, { bg: string; text: string; label: string }> = {
    '偏正面': { bg: 'bg-emerald-100', text: 'text-emerald-700', label: '偏正面' },
    '正面': { bg: 'bg-emerald-100', text: 'text-emerald-700', label: '正面' },
    '中性': { bg: 'bg-gray-100', text: 'text-gray-700', label: '中性' },
    '偏负面': { bg: 'bg-red-100', text: 'text-red-700', label: '偏负面' },
    '负面': { bg: 'bg-red-100', text: 'text-red-700', label: '负面' },
  };

  const sentimentStyle = sentimentSentiment => {
    const style = sentimentColors[sentimentSentiment] || sentimentColors['中性'];
    return style;
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
            <Newspaper className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">新闻资讯</h3>
        </div>
        {newsSentiment && (
          <span
            className={`px-3 py-1 rounded-full text-xs font-semibold ${
              sentimentStyle(newsSentiment.sentiment).bg
            } ${sentimentStyle(newsSentiment.sentiment).text}`}
          >
            {sentimentStyle(newsSentiment.sentiment).label}
          </span>
        )}
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {newsData.map((news, index) => (
          <a
            key={index}
            href={news.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors group"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <h4 className="text-sm font-medium text-gray-900 group-hover:text-emerald-600 transition-colors line-clamp-2 mb-2">
                  {news.title}
                </h4>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">
                    {news.source}
                  </span>
                  <span>{news.publish_time}</span>
                </div>
              </div>
              <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-emerald-500 transition-colors flex-shrink-0 mt-1" />
            </div>
          </a>
        ))}
      </div>

      {newsSentiment && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">情感分析</span>
            <div className="flex items-center gap-4">
              <span className="text-emerald-600 font-medium">
                正面 {newsSentiment.positive_count}
              </span>
              <span className="text-gray-400">|</span>
              <span className="text-gray-600 font-medium">
                中性 {newsSentiment.neutral_count}
              </span>
              <span className="text-gray-400">|</span>
              <span className="text-red-600 font-medium">
                负面 {newsSentiment.negative_count}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
