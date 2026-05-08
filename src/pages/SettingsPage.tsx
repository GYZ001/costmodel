import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { getConfig, updateConfig, getModelList } from '../api/stockApi';
import { Save, Loader2, CheckCircle, Brain, ExternalLink } from 'lucide-react';
import type { AppConfig, AIConfig } from '../types';

const MODEL_LIST = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    models: ['deepseek-chat', 'deepseek-coder'],
    url: 'https://platform.deepseek.com/'
  },
  {
    id: 'qwen',
    name: '通义千问',
    models: ['qwen-plus', 'qwen-plus-latest', 'qwen-turbo', 'qwen-max', 'qwen-long'],
    url: 'https://dashscope.console.aliyun.com/'
  },
  {
    id: 'doubao',
    name: '豆包',
    models: ['doubao-pro-32k', 'doubao-pro-4k', 'doubao-lite-4k', 'doubao-lite-32k'],
    url: 'https://console.volcengine.com/ark/'
  },
  {
    id: 'glm',
    name: '智谱 GLM',
    models: ['glm-4', 'glm-4-plus', 'glm-4-flash', 'glm-3-turbo'],
    url: 'https://open.bigmodel.cn/'
  },
  {
    id: 'kimi',
    name: 'Kimi',
    models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
    url: 'https://platform.moonshot.cn/'
  },
];

const defaultConfig: AppConfig = {
  ai: {
    provider: 'deepseek',
    api_key: '',
    base_url: '',
    model: 'deepseek-chat',
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
    kline_provider: 'eastmoney',
  },
};

export const SettingsPage: React.FC = () => {
  const [config, setConfig] = useState<AppConfig>(defaultConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const data = await getConfig();
      if (data && data.ai) {
        setConfig(data);
      }
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
      await updateConfig(config);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to save config:', err);
      alert('保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  const handleProviderChange = (provider: string) => {
    const modelInfo = MODEL_LIST.find(m => m.id === provider);
    const defaultModel = modelInfo?.models[0] || '';

    setConfig({
      ...config,
      ai: {
        ...config.ai,
        provider,
        model: defaultModel,
        base_url: '',
      },
    });
  };

  const getCurrentModelInfo = () => {
    return MODEL_LIST.find(m => m.id === config.ai.provider);
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

  const currentModelInfo = getCurrentModelInfo();

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-8">系统设置</h1>

        <div className="space-y-6">
          <section className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
                <Brain className="w-5 h-5 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">AI 模型配置</h2>
                <p className="text-sm text-gray-500">选择 AI 模型并配置密钥</p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  AI 模型
                </label>
                <select
                  value={config.ai.provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                >
                  {MODEL_LIST.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  API Key
                  <span className="text-red-500 ml-1">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={config.ai.api_key}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        ai: { ...config.ai, api_key: e.target.value },
                      })
                    }
                    placeholder="输入您的 API Key"
                    className="w-full px-4 py-3 pr-12 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showKey ? '隐藏' : '显示'}
                  </button>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  请从 {currentModelInfo?.name} 官网获取 API Key
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  模型版本
                </label>
                <select
                  value={config.ai.model}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      ai: { ...config.ai, model: e.target.value },
                    })
                  }
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                >
                  {currentModelInfo?.models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </div>

              {config.ai.api_key && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center flex-shrink-0">
                      <CheckCircle className="w-4 h-4 text-white" />
                    </div>
                    <div>
                      <p className="font-medium text-emerald-800">AI 配置已就绪</p>
                      <p className="text-sm text-emerald-600 mt-1">
                        {currentModelInfo?.name} - {config.ai.model}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <a
                href={currentModelInfo?.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700"
              >
                <ExternalLink className="w-4 h-4" />
                前往 {currentModelInfo?.name} 获取 API Key
              </a>
            </div>
          </section>

          <section className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
            <h2 className="text-lg font-bold text-gray-900 mb-4">分析参数</h2>

            <div className="space-y-4">
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
                    分析天数
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
                    新闻天数
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
