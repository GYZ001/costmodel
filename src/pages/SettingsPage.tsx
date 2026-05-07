import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { getConfig, updateConfig } from '../api/stockApi';
import { Save, Loader2, CheckCircle } from 'lucide-react';
import type { AppConfig } from '../types';

const defaultConfig: AppConfig = {
  ai: {
    provider: 'openai',
    api_key: '',
    base_url: '',
    model: 'gpt-4',
  },
  stock: {
    default_market: 'A股',
    default_period: '日线',
    default_days: 30,
  },
  news: {
    search_days: 7,
    max_results: 10,
    keywords_template: '{stock_code} {stock_name}',
  },
  data_source: {
    kline_provider: 'akshare',
  },
};

export const SettingsPage: React.FC = () => {
  const [config, setConfig] = useState<AppConfig>(defaultConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const data = await getConfig();
      setConfig(data);
    } catch (err) {
      console.error('Failed to load config:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);

    try {
      await updateConfig({
        stock: config.stock,
        news: config.news,
        data_source: config.data_source,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to save config:', err);
      alert('保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-8">系统设置</h1>

        <div className="space-y-6">
          <section className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
            <h2 className="text-lg font-bold text-gray-900 mb-4">AI 配置</h2>
            <p className="text-sm text-gray-500 mb-6">
              配置 AI 接口以启用智能分析功能
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  AI 提供商
                </label>
                <select
                  value={config.ai.provider}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      ai: { ...config.ai, provider: e.target.value },
                    })
                  }
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                >
                  <option value="openai">OpenAI (GPT-4)</option>
                  <option value="claude">Claude</option>
                  <option value="ollama">Ollama (本地模型)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  API Key
                </label>
                <input
                  type="password"
                  value={config.ai.api_key}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      ai: { ...config.ai, api_key: e.target.value },
                    })
                  }
                  placeholder="输入您的 API Key"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                />
              </div>

              {config.ai.provider === 'ollama' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Base URL
                  </label>
                  <input
                    type="text"
                    value={config.ai.base_url}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        ai: { ...config.ai, base_url: e.target.value },
                      })
                    }
                    placeholder="http://localhost:11434"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  模型
                </label>
                <input
                  type="text"
                  value={config.ai.model}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      ai: { ...config.ai, model: e.target.value },
                    })
                  }
                  placeholder="gpt-4"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                />
              </div>
            </div>
          </section>

          <section className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
            <h2 className="text-lg font-bold text-gray-900 mb-4">数据源配置</h2>
            <p className="text-sm text-gray-500 mb-6">
              配置股票数据来源和分析参数
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  K线数据源
                </label>
                <select
                  value={config.data_source.kline_provider}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      data_source: {
                        ...config.data_source,
                        kline_provider: e.target.value,
                      },
                    })
                  }
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                >
                  <option value="akshare">AkShare (推荐)</option>
                  <option value="yfinance">Yahoo Finance</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    默认市场
                  </label>
                  <select
                    value={config.stock.default_market}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        stock: { ...config.stock, default_market: e.target.value },
                      })
                    }
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                  >
                    <option value="A股">A股</option>
                    <option value="港股">港股</option>
                    <option value="美股">美股</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    默认周期
                  </label>
                  <select
                    value={config.stock.default_period}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        stock: { ...config.stock, default_period: e.target.value },
                      })
                    }
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                  >
                    <option value="日线">日线</option>
                    <option value="周线">周线</option>
                    <option value="月线">月线</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    默认分析天数
                  </label>
                  <input
                    type="number"
                    value={config.stock.default_days}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        stock: {
                          ...config.stock,
                          default_days: parseInt(e.target.value) || 30,
                        },
                      })
                    }
                    min={5}
                    max={365}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    新闻搜索天数
                  </label>
                  <input
                    type="number"
                    value={config.news.search_days}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        news: {
                          ...config.news,
                          search_days: parseInt(e.target.value) || 7,
                        },
                      })
                    }
                    min={1}
                    max={30}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                  />
                </div>
              </div>
            </div>
          </section>

          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full py-4 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold rounded-xl hover:from-emerald-600 hover:to-teal-700 disabled:opacity-50 transition-all shadow-lg shadow-emerald-500/25 flex items-center justify-center gap-2"
          >
            {saving ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                保存中...
              </>
            ) : saved ? (
              <>
                <CheckCircle className="w-5 h-5" />
                保存成功
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                保存设置
              </>
            )}
          </button>
        </div>
      </main>
    </div>
  );
};
