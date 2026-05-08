import express from 'express';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors({
  origin: '*',
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));
app.use(express.json());

interface KlineData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Config {
  ai: {
    provider: string;
    api_key: string;
    base_url: string;
    model: string;
  };
  stock: {
    default_market: string;
    default_period: string;
    default_days: number;
  };
  news: {
    search_days: number;
    max_results: number;
  };
  data_source: {
    kline_provider: string;
  };
}

let config: Config = {
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
  },
  data_source: {
    kline_provider: 'mock',
  },
};

const stockNameMap: Record<string, string> = {
  '600519': '贵州茅台',
  '000858': '五粮液',
  '000001': '平安银行',
  '600036': '招商银行',
  '601318': '中国平安',
  '000333': '美的集团',
  '600887': '伊利股份',
  '002594': '比亚迪',
  '600276': '恒瑞医药',
  '300750': '宁德时代',
  '601888': '中国中免',
  '600030': '中信证券',
  '600900': '长江电力',
  '601012': '隆基绿能',
  '002415': '海康威视',
  '601398': '工商银行',
  '601939': '建设银行',
  '600016': '民生银行',
  '000002': '万科A',
  '600048': '保利发展',
  '00700': '腾讯控股',
  '09988': '阿里巴巴',
  'TSLA': '特斯拉',
  'AAPL': '苹果',
  'GOOGL': '谷歌',
  'MSFT': '微软',
  'AMZN': '亚马逊',
  'NVDA': '英伟达',
  'META': 'Meta',
};

function getStockName(code: string): string {
  const upperCode = code.toUpperCase();
  if (stockNameMap[upperCode]) {
    return stockNameMap[upperCode];
  }
  if (upperCode.startsWith('6')) {
    return '上证股票';
  }
  if (upperCode.startsWith('0') || upperCode.startsWith('3')) {
    return '深证股票';
  }
  if (upperCode.startsWith('HK') || /^\d{5}$/.test(upperCode)) {
    return '港股';
  }
  return `股票${code}`;
}

function generateMockKlineData(days: number): { data: KlineData[]; indicators: any } {
  const data: KlineData[] = [];
  let basePrice = 100;

  for (let i = 0; i < days; i++) {
    const date = new Date();
    date.setDate(date.getDate() - (days - i - 1));
    const change = (Math.random() - 0.5) * 6;
    basePrice = basePrice * (1 + change / 100);

    const open = basePrice * (1 + (Math.random() - 0.5) * 0.02);
    const close = basePrice;
    const high = Math.max(open, close) * (1 + Math.random() * 0.02);
    const low = Math.min(open, close) * (1 - Math.random() * 0.02);
    const volume = Math.floor(Math.random() * 9000000 + 1000000);

    data.push({
      date: date.toISOString().split('T')[0],
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume,
    });
  }

  const closes = data.map(d => d.close);
  const ma5 = closes.slice(-5).reduce((a, b) => a + b, 0) / 5;
  const ma10 = closes.slice(-10).reduce((a, b) => a + b, 0) / Math.min(10, closes.length);
  const ma20 = closes.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, closes.length);
  const priceChange = ((closes[closes.length - 1] - closes[0]) / closes[0]) * 100;
  const avgVolume = data.reduce((a, b) => a + b.volume, 0) / data.length;
  const volumeChange = ((data[data.length - 1].volume - avgVolume) / avgVolume) * 100;

  return {
    data,
    indicators: {
      ma5: Number(ma5.toFixed(2)),
      ma10: Number(ma10.toFixed(2)),
      ma20: Number(ma20.toFixed(2)),
      price_change: Number(priceChange.toFixed(2)),
      volume_change: Number(volumeChange.toFixed(2)),
      latest_close: closes[closes.length - 1],
      highest: Math.max(...data.map(d => d.high)),
      lowest: Math.min(...data.map(d => d.low)),
    },
  };
}

function generateMockNews(stockCode: string, stockName: string, days: number) {
  const newsTemplates = [
    `${stockName}发布年度业绩预告，净利润同比增长20%`,
    `分析师上调${stockName}目标价至新高`,
    `${stockName}获机构买入评级`,
    `${stockName}发布新产品线`,
    `${stockName}宣布战略合作计划`,
    `机构调研${stockName}，关注核心业务`,
    `${stockName}股价创近期新高`,
    `券商看好${stockName}，维持增持评级`,
    `${stockName}入选重要指数成分股`,
    `${stockName}发布季报，业绩超预期`,
  ];

  const sources = ['东方财富', '新浪财经', '证券时报', '第一财经', '财联社'];
  const data = [];

  for (let i = 0; i < Math.min(10, newsTemplates.length); i++) {
    const daysAgo = Math.floor(Math.random() * days);
    const date = new Date();
    date.setDate(date.getDate() - daysAgo);

    data.push({
      title: newsTemplates[i],
      url: `https://finance.example.com/news/${stockCode}_${i}`,
      publish_time: date.toISOString().replace('T', ' ').slice(0, 16),
      source: sources[Math.floor(Math.random() * sources.length)],
      summary: `${stockName}相关报道，更多详情请查看原文。`,
    });
  }

  const positiveCount = Math.floor(Math.random() * 5) + 3;
  const negativeCount = Math.floor(Math.random() * 2);
  const neutralCount = 10 - positiveCount - negativeCount;

  let sentiment = '中性';
  if (positiveCount > negativeCount + 2) sentiment = '偏正面';
  else if (negativeCount > positiveCount) sentiment = '偏负面';

  return {
    data,
    sentiment: {
      sentiment,
      positive_count: positiveCount,
      negative_count: negativeCount,
      neutral_count: neutralCount,
      positive_ratio: (positiveCount / 10) * 100,
      negative_ratio: (negativeCount / 10) * 100,
    },
  };
}

function generateLocalAnalysis(stockCode: string, stockName: string, klineResult: any, newsResult: any) {
  const { indicators } = klineResult;
  const { sentiment } = newsResult;

  let trend = '震荡';
  if (indicators.price_change > 3) trend = '上涨';
  else if (indicators.price_change < -3) trend = '下跌';

  let recommendation = '观望';
  if (trend === '上涨' && (sentiment.sentiment === '偏正面' || sentiment.sentiment === '正面')) {
    recommendation = '买入';
  } else if (trend === '震荡' && sentiment.sentiment === '中性') {
    recommendation = '持有';
  } else if (trend === '下跌' && (sentiment.sentiment === '偏负面' || sentiment.sentiment === '负面')) {
    recommendation = '卖出';
  }

  const supportLevel = indicators.lowest * 1.02;
  const resistanceLevel = indicators.highest * 0.98;

  const keyEvents = newsResult.data.slice(0, 5).map((n: any) => n.title);

  return {
    stock_code: stockCode,
    stock_name: stockName,
    analysis_date: new Date().toISOString().split('T')[0],
    technical_analysis: {
      trend,
      support_level: Number(supportLevel.toFixed(2)),
      resistance_level: Number(resistanceLevel.toFixed(2)),
      indicators_summary: `MA5:${indicators.ma5}, MA10:${indicators.ma10}, 涨跌:${indicators.price_change.toFixed(2)}%`,
    },
    news_analysis: {
      sentiment: sentiment.sentiment,
      key_events: keyEvents,
      market_feedback: `正${sentiment.positive_count}负${sentiment.negative_count}中${sentiment.neutral_count}`,
    },
    recommendation,
    risk_level: Math.abs(indicators.price_change) > 10 ? '高' : Math.abs(indicators.price_change) > 5 ? '中' : '低',
    summary: `${stockName}(${stockCode})近期${trend}，消息面${sentiment.sentiment}，建议${recommendation}`,
    is_local_analysis: true,
  };
}

app.post('/api/analyze', (req, res) => {
  try {
    const { stock_code, stock_name, market, period, days } = req.body;

    if (!stock_code) {
      return res.status(400).json({ message: '请输入股票代码' });
    }

    const actualStockName = stock_name || getStockName(stock_code);
    const klineResult = generateMockKlineData(days || 30);
    const newsResult = generateMockNews(stock_code, actualStockName, 7);

    const hasAIConfig = config.ai.api_key && config.ai.api_key.length > 0;

    if (hasAIConfig) {
      console.log(`[AI模式] 分析 ${actualStockName}(${stock_code})`);
    } else {
      console.log(`[本地模式] 分析 ${actualStockName}(${stock_code})`);
    }

    const analysisResult = generateLocalAnalysis(stock_code, actualStockName, klineResult, newsResult);

    res.json(analysisResult);
  } catch (error: any) {
    console.error('Analyze error:', error);
    res.status(500).json({
      message: '分析失败，请稍后重试',
      error: error.message
    });
  }
});

app.get('/api/kline', (req, res) => {
  try {
    const { code, market, period, days } = req.query;

    if (!code) {
      return res.status(400).json({ message: '请输入股票代码' });
    }

    const result = generateMockKlineData(Number(days) || 30);
    res.json(result);
  } catch (error: any) {
    console.error('Kline error:', error);
    res.status(500).json({
      message: '获取K线数据失败，请稍后重试',
      data: [],
      indicators: null
    });
  }
});

app.get('/api/news', (req, res) => {
  try {
    const { code, name, days } = req.query;

    if (!code) {
      return res.status(400).json({ message: '请输入股票代码' });
    }

    const stockName = name || getStockName(String(code));
    const result = generateMockNews(String(code), stockName, Number(days) || 7);
    res.json(result);
  } catch (error: any) {
    console.error('News error:', error);
    res.status(500).json({
      message: '获取新闻数据失败，请稍后重试',
      data: [],
      sentiment: null
    });
  }
});

app.get('/api/config', (req, res) => {
  const hasAIConfig = config.ai.api_key && config.ai.api_key.length > 0;
  res.json({
    ...config,
    has_ai_config: hasAIConfig,
    ai: {
      ...config.ai,
      api_key: hasAIConfig ? '***' + config.ai.api_key.slice(-4) : '',
    },
  });
});

app.post('/api/config', (req, res) => {
  try {
    const { stock, news, data_source, ai } = req.body;

    if (stock) config.stock = { ...config.stock, ...stock };
    if (news) config.news = { ...config.news, ...news };
    if (data_source) config.data_source = { ...config.data_source, ...data_source };
    if (ai) {
      if (ai.api_key && !ai.api_key.startsWith('***')) {
        config.ai.api_key = ai.api_key;
      }
      if (ai.model) config.ai.model = ai.model;
      if (ai.provider) config.ai.provider = ai.provider;
      if (ai.base_url !== undefined) config.ai.base_url = ai.base_url;
    }

    const hasAIConfig = config.ai.api_key && config.ai.api_key.length > 0;

    res.json({
      ...config,
      has_ai_config: hasAIConfig,
      ai: {
        ...config.ai,
        api_key: hasAIConfig ? '***' + config.ai.api_key.slice(-4) : '',
      },
    });
  } catch (error: any) {
    console.error('Config error:', error);
    res.status(500).json({ message: '保存配置失败，请稍后重试' });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Server error:', err);
  res.status(500).json({ message: '服务器错误，请稍后重试' });
});

app.listen(PORT, () => {
  console.log(`API server running on http://localhost:${PORT}`);
});

export default app;
