"""
AI 模型调用模块 - 支持多种大模型
"""

import json
import urllib.request
import urllib.error
import sys
from typing import Optional, Dict, Any

AI_MODEL_CONFIGS = {
    'deepseek': {
        'name': 'DeepSeek',
        'base_url': 'https://api.deepseek.com/v1',
        'models': ['deepseek-chat', 'deepseek-coder'],
    },
    'qwen': {
        'name': '通义千问',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'models': ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-long'],
    },
    'doubao': {
        'name': '豆包',
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'models': ['doubao-pro-32k', 'doubao-pro-4k', 'doubao-lite-4k', 'doubao-lite-32k'],
    },
    'glm': {
        'name': '智谱 GLM',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'models': ['glm-4', 'glm-4-plus', 'glm-4-flash', 'glm-3-turbo'],
    },
    'kimi': {
        'name': 'Kimi',
        'base_url': 'https://api.moonshot.cn/v1',
        'models': ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
    },
    'openai': {
        'name': 'OpenAI',
        'base_url': 'https://api.openai.com/v1',
        'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
    },
}

class AIAnalyzer:
    def __init__(self, provider: str, api_key: str, model: str, base_url: str = ''):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        
        if base_url:
            self.base_url = base_url
        else:
            config = AI_MODEL_CONFIGS.get(provider)
            self.base_url = config['base_url'] if config else ''
        
        self.client = None

    def analyze(self, prompt: str, system_prompt: str = '') -> Optional[str]:
        """调用 AI 模型进行分析"""
        if not self.api_key or not self.base_url:
            return None

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

        try:
            url = f"{self.base_url}/chat/completions"
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            return None
            
        except urllib.error.HTTPError as e:
            print(f"AI API HTTP错误: {e.code} - {e.read().decode()}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"AI API 调用失败: {e}", file=sys.stderr)
            return None

def parse_ai_response(response: str) -> Dict[str, Any]:
    """解析 AI 返回的分析结果"""
    try:
        json_match = response.strip()
        if json_match.startswith('```json'):
            lines = json_match.split('\n')
            json_match = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
        elif json_match.startswith('```'):
            lines = json_match.split('\n')
            json_match = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
        
        return json.loads(json_match)
    except json.JSONDecodeError:
        return {
            'technical_analysis': {'trend': '未知', 'support_level': 0, 'resistance_level': 0, 'indicators_summary': ''},
            'news_analysis': {'sentiment': '未知', 'key_events': [], 'market_feedback': ''},
            'recommendation': '观望',
            'risk_level': '中',
            'summary': response[:200] if response else '解析失败'
        }

STOCK_ANALYSIS_PROMPT = """你是一位专业的股票分析师。请根据以下信息对股票进行技术面和消息面分析。

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

def analyze_with_ai(
    stock_code: str,
    stock_name: str,
    kline_data: list,
    news_data: list,
    ai_config: dict
) -> Optional[Dict[str, Any]]:
    """使用 AI 分析股票"""
    if not ai_config.get('api_key'):
        return None
    
    provider = ai_config.get('provider', 'deepseek')
    api_key = ai_config.get('api_key', '')
    model = ai_config.get('model', 'deepseek-chat')
    base_url = ai_config.get('base_url', '')

    analyzer = AIAnalyzer(provider, api_key, model, base_url)
    
    kline_summary = _summarize_kline(kline_data)
    news_summary = _summarize_news(news_data)
    
    prompt = STOCK_ANALYSIS_PROMPT.format(
        stock_code=stock_code,
        stock_name=stock_name,
        kline_summary=kline_summary,
        news_summary=news_summary
    )
    
    system_prompt = """你是一位专业的股票分析师，擅长技术分析和基本面分析。
请根据提供的数据进行分析，回答时使用JSON格式。"""
    
    response = analyzer.analyze(prompt, system_prompt)
    
    if response:
        return parse_ai_response(response)
    
    return None

def _summarize_kline(kline_data: list) -> str:
    """总结K线数据"""
    if not kline_data:
        return "无数据"
    
    recent_5 = kline_data[-5:] if len(kline_data) >= 5 else kline_data
    lines = []
    for d in recent_5:
        lines.append(f"{d['date']}: 开{d['open']:.2f} 高{d['high']:.2f} 低{d['low']:.2f} 收{d['close']:.2f}")
    
    summary = "最近5日数据：\n" + "\n".join(lines)
    
    closes = [d['close'] for d in kline_data]
    if len(closes) >= 5:
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else sum(closes) / len(closes)
        price_change = ((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] != 0 else 0
        
        summary += f"\n\n技术指标："
        summary += f"\n- MA5: {ma5:.2f}"
        summary += f"\n- MA10: {ma10:.2f}"
        summary += f"\n- 区间涨跌: {price_change:.2f}%"
        summary += f"\n- 最高价: {max(d['high'] for d in kline_data):.2f}"
        summary += f"\n- 最低价: {min(d['low'] for d in kline_data):.2f}"
    
    return summary

def _summarize_news(news_data: list) -> str:
    """总结新闻数据"""
    if not news_data:
        return "无相关新闻"
    
    summaries = []
    for i, news in enumerate(news_data[:10], 1):
        summaries.append(f"{i}. [{news['publish_time']}] {news['title']} ({news['source']})")
    
    return "\n".join(summaries)
