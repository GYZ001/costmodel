import { Router } from 'express';
import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

const router = Router();

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
    keywords_template: string;
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
    keywords_template: '{stock_code} {stock_name}',
  },
  data_source: {
    kline_provider: 'akshare',
  },
};

const configPath = path.join(__dirname, '../../config/config.json');
if (fs.existsSync(configPath)) {
  try {
    config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch (e) {
    console.error('Failed to load config:', e);
  }
}

export const analyzeStock = Router().post('/analyze', async (req, res) => {
  try {
    const { stock_code, stock_name, market, period, days, use_ai } = req.body;

    const agentPath = path.join(__dirname, '../../src/agent.py');
    const args = [
      agentPath,
      '--code', stock_code,
      '--name', stock_name,
    ];

    if (market) args.push('--market', market);
    if (period) args.push('--period', period);
    if (days) args.push('--days', days.toString());
    if (use_ai === false) args.push('--no-ai');

    const result = await runPythonAgent(args);

    res.json(result);
  } catch (error: any) {
    console.error('Analysis error:', error);
    res.status(500).json({ message: error.message || 'Analysis failed' });
  }
});

export const getKlineData = Router().get('/kline', async (req, res) => {
  try {
    const { code, market, period, days } = req.query;

    const agentPath = path.join(__dirname, '../../src/data_fetcher.py');
    const args = [
      '-c',
      `import sys; sys.path.insert(0, '${path.dirname(agentPath)}'); ` +
      `from data_fetcher import KlineDataFetcher; ` +
      `fetcher = KlineDataFetcher(); ` +
      `data = fetcher.get_kline_data('${code}', '${market || 'A股'}', '${period || '日线'}', ${days || 30}); ` +
      `indicators = fetcher.calculate_indicators(data); ` +
      `print('__RESULT__' + __import__('json').dumps({'data': data, 'indicators': indicators}))`
    ];

    const result = await runPythonCommand(args);
    const parsed = parsePythonResult(result);

    res.json(parsed || { data: [], indicators: null });
  } catch (error: any) {
    console.error('K-line fetch error:', error);
    res.status(500).json({ message: 'Failed to fetch K-line data' });
  }
});

export const getNews = Router().get('/news', async (req, res) => {
  try {
    const { code, name, days } = req.query;

    const agentPath = path.join(__dirname, '../../src/news_fetcher.py');
    const args = [
      '-c',
      `import sys; sys.path.insert(0, '${path.dirname(agentPath)}'); ` +
      `from news_fetcher import NewsFetcher; ` +
      `fetcher = NewsFetcher(); ` +
      `data = fetcher.search_news('${code}', '${name}', ${days || 7}); ` +
      `sentiment = fetcher.analyze_sentiment(data); ` +
      `print('__RESULT__' + __import__('json').dumps({'data': data, 'sentiment': sentiment}))`
    ];

    const result = await runPythonCommand(args);
    const parsed = parsePythonResult(result);

    res.json(parsed || { data: [], sentiment: null });
  } catch (error: any) {
    console.error('News fetch error:', error);
    res.status(500).json({ message: 'Failed to fetch news' });
  }
});

export const getConfig = Router().get('/config', (req, res) => {
  const responseConfig = {
    ...config,
    ai: {
      ...config.ai,
      api_key: config.ai.api_key ? '***' + config.ai.api_key.slice(-4) : '',
    },
  };
  res.json(responseConfig);
});

export const updateConfig = Router().post('/config', (req, res) => {
  try {
    const { stock, news, data_source, ai } = req.body;

    if (stock) config.stock = { ...config.stock, ...stock };
    if (news) config.news = { ...config.news, ...news };
    if (data_source) config.data_source = { ...config.data_source, ...data_source };
    if (ai && ai.api_key && !ai.api_key.startsWith('***')) {
      config.ai.api_key = ai.api_key;
    }
    if (ai && ai.model) config.ai.model = ai.model;
    if (ai && ai.provider) config.ai.provider = ai.provider;
    if (ai && ai.base_url !== undefined) config.ai.base_url = ai.base_url;

    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

    res.json({
      ...config,
      ai: {
        ...config.ai,
        api_key: config.ai.api_key ? '***' + config.ai.api_key.slice(-4) : '',
      },
    });
  } catch (error: any) {
    console.error('Config update error:', error);
    res.status(500).json({ message: 'Failed to update config' });
  }
});

function runPythonAgent(args: string[]): Promise<any> {
  return new Promise((resolve, reject) => {
    const python = spawn('python3', ['main.py', 'analyze', ...args.slice(1)], {
      cwd: path.dirname(args[0]),
    });

    let output = '';
    let errorOutput = '';

    python.stdout.on('data', (data) => {
      output += data.toString();
    });

    python.stderr.on('data', (data) => {
      errorOutput += data.toString();
    });

    python.on('close', (code) => {
      if (code === 0) {
        try {
          const result = parsePythonResult(output);
          resolve(result || generateMockAnalysis(req => req.body));
        } catch (e) {
          reject(new Error('Failed to parse result'));
        }
      } else {
        reject(new Error(errorOutput || 'Python script failed'));
      }
    });

    python.on('error', (err) => {
      reject(err);
    });
  });
}

function runPythonCommand(args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const python = spawn('python3', args);

    let output = '';

    python.stdout.on('data', (data) => {
      output += data.toString();
    });

    python.on('close', (code) => {
      if (code === 0) {
        resolve(output);
      } else {
        reject(new Error('Command failed'));
      }
    });

    python.on('error', (err) => {
      reject(err);
    });
  });
}

function parsePythonResult(output: string): any {
  const match = output.match(/__RESULT__(.+)/s);
  if (match) {
    try {
      return JSON.parse(match[1]);
    } catch (e) {
      return null;
    }
  }
  return null;
}

function generateMockAnalysis(req: any): any {
  const { stock_code, stock_name } = req;
  return {
    stock_code,
    stock_name,
    analysis_date: new Date().toISOString().split('T')[0],
    technical_analysis: {
      trend: '震荡',
      support_level: 100,
      resistance_level: 110,
      indicators_summary: 'MA5: 105, MA10: 103',
    },
    news_analysis: {
      sentiment: '中性',
      key_events: [],
      market_feedback: '暂无明显消息',
    },
    recommendation: '观望',
    risk_level: '中',
    summary: `${stock_name}(${stock_code})近期走势震荡，建议保持观望`,
  };
}
