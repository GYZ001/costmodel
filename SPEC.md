# 股票 AI 分析 Agent (Stock AI Analyst)

## 1. 项目概述

**项目名称：** stock-analyst-agent
**项目类型：** Python CLI 工具
**核心功能：** 通过 AI 接口分析股票的技术面（K线数据）和消息面（新闻资讯），为投资决策提供参考。
**目标用户：** 股票投资者、量化交易者、金融分析师

## 2. 功能需求

### 2.1 核心功能

#### 2.1.1 K线数据获取
- 支持获取股票的历史K线数据（OHLCV）
- 支持不同时间周期：日线、周线、月线
- 支持主要股票市场：
  - A股（上交所、深交所）
  - 港股
  - 美股
- 数据字段：日期、开盘价、最高价、最低价、收盘价、成交量

#### 2.1.2 新闻资讯获取
- 自动搜索股票相关新闻
- 支持关键词配置
- 解析新闻内容：标题、时间、来源、摘要
- 支持新闻时间范围过滤

#### 2.1.3 AI 分析接口
- 配置化 AI 接口支持（OpenAI、Claude、本地模型等）
- 支持自定义 Prompt 模板
- 返回结构化的分析结果

#### 2.1.4 主程序 Agent
- 命令行交互界面
- 支持分析单只或多只股票
- 生成综合分析报告
- 支持报告导出（文本格式）

### 2.2 技术架构

```
stock-analyst-agent/
├── config/
│   └── config.yaml          # 主配置文件
├── src/
│   ├── __init__.py
│   ├── config_loader.py     # 配置加载器
│   ├── data_fetcher.py      # K线数据获取
│   ├── news_fetcher.py      # 新闻获取
│   ├── ai_analyzer.py       # AI 分析接口
│   ├── agent.py             # 主 Agent 逻辑
│   └── reporter.py          # 报告生成
├── prompts/
│   └── analysis_prompt.j2    # 分析 Prompt 模板
├── main.py                  # 程序入口
├── requirements.txt         # 依赖
└── SPEC.md
```

### 2.3 配置项

```yaml
# config.yaml
ai:
  provider: "openai"  # openai, claude, ollama, custom
  api_key: ""          # API密钥
  base_url: ""         # 自定义接口地址
  model: "gpt-4"      # 模型名称

stock:
  default_market: "A股"  # A股, 港股, 美股
  default_period: "日线"  # 日线, 周线, 月线
  default_days: 30       # 默认分析天数

news:
  search_days: 7         # 搜索最近N天新闻
  max_results: 10        # 最大新闻数量
  keywords_template: "{stock_code} {stock_name}"  # 搜索关键词模板

data_source:
  kline_provider: "akshare"  # 数据源：akshare, tushare, yfinance
```

## 3. 数据接口

### 3.1 K线数据接口

```python
# src/data_fetcher.py
class KlineDataFetcher:
    def get_kline_data(
        stock_code: str,
        market: str,  # A股, 港股, 美股
        period: str,  # 日线, 周线, 月线
        days: int
    ) -> List[Dict]:
        """
        获取K线数据
        返回: [{date, open, high, low, close, volume}]
        """
```

### 3.2 新闻获取接口

```python
# src/news_fetcher.py
class NewsFetcher:
    def search_news(
        stock_code: str,
        stock_name: str,
        days: int,
        max_results: int
    ) -> List[Dict]:
        """
        搜索股票相关新闻
        返回: [{title, url, publish_time, source, summary}]
        """
```

### 3.3 AI 分析接口

```python
# src/ai_analyzer.py
class AIAnalyzer:
    def analyze(
        stock_code: str,
        stock_name: str,
        kline_data: List[Dict],
        news_data: List[Dict],
        prompt_template: str
    ) -> Dict:
        """
        调用 AI 分析股票
        返回: {technical_analysis, news_analysis, recommendation, risk_level}
        """
```

## 4. AI 分析报告结构

```json
{
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "analysis_date": "2024-01-15",
  "technical_analysis": {
    "trend": "上涨趋势",
    "support_level": 1650.0,
    "resistance_level": 1800.0,
    "indicators": {
      "ma5": 1720.5,
      "ma10": 1705.3,
      "ma20": 1680.0,
      "volume_change": "+15%"
    }
  },
  "news_analysis": {
    "sentiment": "偏正面",
    "key_events": [
      "公司发布年度业绩预告",
      "行业政策利好"
    ],
    "market_feedback": "投资者关注度高"
  },
  "recommendation": "持有",
  "risk_level": "中等",
  "summary": "综合分析总结..."
}
```

## 5. 技术选型

- **编程语言：** Python 3.10+
- **HTTP 客户端：** httpx（异步支持）
- **数据处理：** pandas
- **K线数据：** akshare（免费开源）
- **新闻搜索：** requests + BeautifulSoup
- **AI 接口：** OpenAI SDK / Anthropic SDK
- **配置管理：** PyYAML
- **CLI：** click 或 argparse

## 6. 使用方式

### 命令行使用

```bash
# 分析单只股票
python main.py analyze --code 600519 --name "贵州茅台"

# 分析多只股票
python main.py batch --file stocks.txt

# 交互模式
python main.py interactive

# 导出配置模板
python main.py init-config
```

## 7. 验收标准

- [ ] 成功获取A股股票K线数据
- [ ] 成功获取股票相关新闻
- [ ] 成功调用 AI 接口进行分析
- [ ] 生成结构化分析报告
- [ ] 支持配置文件管理
- [ ] CLI 界面可正常运行
