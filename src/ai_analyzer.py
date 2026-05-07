"""
AI Analyzer module for stock analysis
"""

import json
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AIAnalyzer:
    def __init__(
        self,
        provider: str = 'openai',
        api_key: str = '',
        base_url: str = '',
        model: str = 'gpt-4'
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = None

        self._init_client()

    def _init_client(self):
        if self.provider == 'openai' and OPENAI_AVAILABLE and self.api_key:
            if self.base_url:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            else:
                self.client = OpenAI(api_key=self.api_key)

        elif self.provider == 'claude' and ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)

        elif self.provider == 'ollama' and self.base_url:
            self.client = {'type': 'ollama', 'base_url': self.base_url}

    def analyze(
        self,
        stock_code: str,
        stock_name: str,
        kline_data: List[Dict],
        news_data: List[Dict],
        prompt_template: str = ''
    ) -> Dict[str, Any]:
        """
        Analyze stock using AI

        Args:
            stock_code: Stock code
            stock_name: Stock name
            kline_data: K-line data
            news_data: News data
            prompt_template: Custom prompt template

        Returns:
            Analysis result dictionary
        """
        if not self.client:
            return self._generate_mock_analysis(stock_code, stock_name, kline_data, news_data)

        try:
            prompt = self._build_prompt(stock_code, stock_name, kline_data, news_data, prompt_template)

            if self.provider == 'openai':
                return self._analyze_with_openai(prompt)
            elif self.provider == 'claude':
                return self._analyze_with_claude(prompt)
            elif self.provider == 'ollama':
                return self._analyze_with_ollama(prompt)
            else:
                return self._generate_mock_analysis(stock_code, stock_name, kline_data, news_data)

        except Exception as e:
            print(f"Error during AI analysis: {e}")
            return self._generate_mock_analysis(stock_code, stock_name, kline_data, news_data)

    def _build_prompt(
        self,
        stock_code: str,
        stock_name: str,
        kline_data: List[Dict],
        news_data: List[Dict],
        custom_template: str
    ) -> str:
        """Build prompt for AI analysis"""

        if custom_template:
            prompt = custom_template
        else:
            prompt = """你是一位专业的股票分析师。请根据以下信息对股票进行技术面和消息面分析。

股票信息：
- 代码：{stock_code}
- 名称：{stock_name}

技术面数据（近30日K线）：
{kline_summary}

消息面数据（近期新闻）：
{news_summary}

请以JSON格式返回分析结果，包含以下字段：
{{
    "technical_analysis": {{
        "trend": "趋势判断（上涨/下跌/震荡）",
        "support_level": 支撑位数字,
        "resistance_level": 压力位数字,
        "indicators_summary": "技术指标总结"
    }},
    "news_analysis": {{
        "sentiment": "情绪判断（正面/中性/负面）",
        "key_events": ["关键事件1", "关键事件2"],
        "market_feedback": "市场反馈描述"
    }},
    "recommendation": "投资建议（买入/持有/观望/卖出）",
    "risk_level": "风险等级（高/中/低）",
    "summary": "综合分析总结（100字以内）"
}}
"""

        kline_summary = self._summarize_kline(kline_data)
        news_summary = self._summarize_news(news_data)

        return prompt.format(
            stock_code=stock_code,
            stock_name=stock_name,
            kline_summary=kline_summary,
            news_summary=news_summary
        )

    def _summarize_kline(self, kline_data: List[Dict]) -> str:
        """Summarize K-line data for prompt"""
        if not kline_data:
            return "无数据"

        recent_5 = kline_data[-5:] if len(kline_data) >= 5 else kline_data
        recent_5_str = '\n'.join([
            f"{d['date']}: 开{d['open']:.2f} 高{d['high']:.2f} 低{d['low']:.2f} 收{d['close']:.2f} 量{d['volume']:,.0f}"
            for d in recent_5
        ])

        closes = [d['close'] for d in kline_data]
        if len(closes) >= 5:
            ma5 = sum(closes[-5:]) / 5
        else:
            ma5 = sum(closes) / len(closes)

        if len(closes) >= 10:
            ma10 = sum(closes[-10:]) / 10
        else:
            ma10 = ma5

        price_change = ((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] != 0 else 0

        summary = f"""最近5日数据：
{recent_5_str}

技术指标：
- MA5: {ma5:.2f}
- MA10: {ma10:.2f}
- 区间涨跌: {price_change:.2f}%
- 最高价: {max(d['high'] for d in kline_data):.2f}
- 最低价: {min(d['low'] for d in kline_data):.2f}"""

        return summary

    def _summarize_news(self, news_data: List[Dict]) -> str:
        """Summarize news data for prompt"""
        if not news_data:
            return "无相关新闻"

        summaries = []
        for i, news in enumerate(news_data[:10], 1):
            summary = f"{i}. [{news['publish_time']}] {news['title']} ({news['source']})"
            summaries.append(summary)

        return '\n'.join(summaries)

    def _analyze_with_openai(self, prompt: str) -> Dict[str, Any]:
        """Analyze using OpenAI API"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个专业的股票分析师。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        content = response.choices[0].message.content
        return self._parse_json_response(content)

    def _analyze_with_claude(self, prompt: str) -> Dict[str, Any]:
        """Analyze using Claude API"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = response.content[0].text
        return self._parse_json_response(content)

    def _analyze_with_ollama(self, prompt: str) -> Dict[str, Any]:
        """Analyze using Ollama (local LLM)"""
        import requests

        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        response = requests.post(url, json=data, timeout=60)
        response.raise_for_status()

        content = response.json().get('response', '')
        return self._parse_json_response(content)

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from AI response"""
        try:
            json_match = content.strip()
            if json_match.startswith('```'):
                lines = json_match.split('\n')
                json_match = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

            return json.loads(json_match)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            return {
                'technical_analysis': {'trend': '未知', 'support_level': 0, 'resistance_level': 0, 'indicators_summary': ''},
                'news_analysis': {'sentiment': '未知', 'key_events': [], 'market_feedback': ''},
                'recommendation': '无法确定',
                'risk_level': '未知',
                'summary': 'AI分析结果解析失败'
            }

    def _generate_mock_analysis(
        self,
        stock_code: str,
        stock_name: str,
        kline_data: List[Dict],
        news_data: List[Dict]
    ) -> Dict[str, Any]:
        """Generate mock analysis when AI is not available"""
        if not kline_data:
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'technical_analysis': {
                    'trend': '震荡',
                    'support_level': 0,
                    'resistance_level': 0,
                    'indicators_summary': '无数据'
                },
                'news_analysis': {
                    'sentiment': '中性',
                    'key_events': [],
                    'market_feedback': '无相关新闻'
                },
                'recommendation': '观望',
                'risk_level': '中',
                'summary': '数据不足，无法提供有效分析'
            }

        closes = [d['close'] for d in kline_data]
        latest_close = closes[-1]
        highest = max(d['high'] for d in kline_data)
        lowest = min(d['low'] for d in kline_data)

        price_change = ((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] != 0 else 0

        if price_change > 5:
            trend = '上涨'
        elif price_change < -5:
            trend = '下跌'
        else:
            trend = '震荡'

        support_level = lowest * 1.02
        resistance_level = highest * 0.98

        sentiment_map = {
            '正面': ['增长', '利好', '买入', '上调', '超预期'],
            '负面': ['下跌', '利空', '下调', '亏损', '风险']
        }

        positive_count = 0
        negative_count = 0
        key_events = []

        for news in news_data:
            title = news.get('title', '')
            for kw in sentiment_map['正面']:
                if kw in title:
                    positive_count += 1
                    key_events.append(title)
                    break
            for kw in sentiment_map['负面']:
                if kw in title:
                    negative_count -= 1
                    key_events.append(title)
                    break

        if positive_count > abs(negative_count):
            sentiment = '正面'
            recommendation = '买入'
        elif negative_count < 0 and abs(negative_count) > positive_count:
            sentiment = '负面'
            recommendation = '观望'
        else:
            sentiment = '中性'
            recommendation = '持有'

        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'analysis_date': kline_data[-1]['date'] if kline_data else '',
            'technical_analysis': {
                'trend': trend,
                'support_level': round(support_level, 2),
                'resistance_level': round(resistance_level, 2),
                'indicators_summary': f'MA5/MA10趋势{trend}，区间涨跌幅{price_change:.2f}%'
            },
            'news_analysis': {
                'sentiment': sentiment,
                'key_events': key_events[:5],
                'market_feedback': f'近期有{len(news_data)}条相关新闻，情感倾向{sentiment}'
            },
            'recommendation': recommendation,
            'risk_level': '中',
            'summary': f'{stock_name}({stock_code})近期{trend}，消息面{sentiment}，建议{recommendation}'
        }
