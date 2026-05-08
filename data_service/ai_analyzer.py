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
        'base_url': 'https://api.deepseek.com',
        'models': ['deepseek-v4-flash', 'deepseek-v4-pro', 'deepseek-chat', 'deepseek-reasoner'],
    },
    'qwen': {
        'name': '通义千问',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'models': ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long', 'qwen3-235b-a22b'],
    },
    'doubao': {
        'name': '豆包',
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'models': ['doubao-1-5-pro-32k', 'doubao-1-5-lite-32k', 'doubao-pro-32k', 'doubao-lite-32k'],
    },
    'glm': {
        'name': '智谱 GLM',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'models': ['glm-4-plus', 'glm-4-air', 'glm-4-flash', 'glm-z1-flash'],
    },
    'kimi': {
        'name': 'Kimi',
        'base_url': 'https://api.moonshot.cn/v1',
        'models': ['kimi-latest', 'moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'],
    },
    'openai': {
        'name': 'OpenAI',
        'base_url': 'https://api.openai.com/v1',
        'models': ['gpt-4.1', 'gpt-4.1-mini', 'gpt-4o', 'gpt-4o-mini', 'o3', 'o3-mini'],
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
            "temperature": 0.5,
            "max_tokens": 4000,
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

    def test_connection(self) -> tuple:
        """测试 AI API 连通性，返回 (success: bool, message: str)"""
        if not self.api_key:
            return False, "未配置 API Key"
        if not self.base_url:
            return False, "未配置 Base URL"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi, please reply with exactly: OK"}],
            "temperature": 0,
            "max_tokens": 10,
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

        try:
            url = f"{self.base_url}/chat/completions"
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')

            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))

            if 'choices' in result and len(result['choices']) > 0:
                return True, f"连接成功，模型 {self.model} 响应正常"
            return False, "API 返回数据格式异常"

        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 401:
                return False, "API Key 无效或已过期"
            elif e.code == 403:
                return False, "API Key 权限不足"
            elif e.code == 404:
                return False, f"模型 {self.model} 不存在或 API 地址错误"
            elif e.code == 429:
                return False, "请求频率超限，请稍后重试"
            return False, f"HTTP {e.code}: {body[:200]}"
        except urllib.error.URLError as e:
            return False, f"网络错误: {str(e.reason)}"
        except Exception as e:
            return False, f"连接失败: {str(e)}"

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
            'technical_analysis': {
                'trend': '未知',
                'support_level': 0,
                'resistance_level': 0,
                'indicators_summary': '',
                'detail': ''
            },
            'news_analysis': {
                'sentiment': '未知',
                'key_events': [],
                'market_feedback': '',
                'detail': ''
            },
            'recommendation': '观望',
            'risk_level': '中',
            'summary': response[:500] if response else '解析失败',
            'investment_logic': '',
            'risk_factors': [],
            'action_plan': ''
        }

STOCK_ANALYSIS_PROMPT = """你是一位拥有20年实战经验的资深金融分析师，同时精通技术分析和基本面/消息面研判。请综合以下股票的技术面数据和消息面信息，从专业投资者的角度给出完整的分析报告。

## 标的信息
- 股票代码：{stock_code}
- 股票名称：{stock_name}

## 技术面数据
{kline_summary}

## 消息面/事件驱动
{news_summary}

{position_section}

## 分析要求

请从以下维度深入分析，结合市场环境给出**有逻辑深度**的专业报告：

1. **技术面分析**：分析趋势结构（多空力量对比）、量价关系、均线系统排列、关键支撑/压力位，以及可能的形态结构（如突破、回踩、背离等）。
2. **消息面分析**：解读近期新闻事件对股价的潜在催化或压制作用，评估市场情绪，注意政策面、行业面、公司层面的多维度信号。
3. **综合研判**：结合技术面和消息面给出投资逻辑和操作建议，明确风险收益比。{position_requirement}

请严格以如下 JSON 格式输出：

```json
{{
    "technical_analysis": {{
        "trend": "趋势方向（上涨/下跌/震荡/筑底/见顶）",
        "support_level": 支撑位（数字）,
        "resistance_level": 压力位（数字）,
        "indicators_summary": "核心指标简要（如MA排列、MACD状态、量能变化）",
        "detail": "技术面深度分析文字（200-400字，包含趋势结构、量价配合、形态研判等）"
    }},
    "news_analysis": {{
        "sentiment": "综合情绪（正面/中性/负面）",
        "key_events": ["关键事件1", "关键事件2", "关键事件3"],
        "market_feedback": "市场对事件的反馈描述",
        "detail": "消息面深度分析文字（200-400字，包含政策影响、行业趋势、事件催化等）"
    }},
    "recommendation": "投资建议（强烈买入/买入/持有/观望/减仓/卖出）",
    "risk_level": "风险等级（高/中/低）",
    "summary": "综合分析摘要（200-300字，整合技术面和消息面结论）",
    "investment_logic": "核心投资逻辑（100字以内，说明为什么给出该建议）",
    "risk_factors": ["风险因素1", "风险因素2", "风险因素3"],
    "action_plan": "操作策略建议（如建仓点位、止损位、目标位、仓位建议等）",
    "position_analysis": {{
        "current_pnl_pct": 当前盈亏百分比（数字，无持仓则null）,
        "cost_vs_support": "持仓成本与支撑位关系描述（无持仓则null）",
        "advice_for_holder": "针对当前持仓的具体操作建议（无持仓则null）"
    }}
}}
```
"""

POSITION_SECTION_TEMPLATE = """## 用户持仓信息
- 持仓状态：已持有该股票
- 持仓成本：{cost_price} 元/股
- 持仓数量：{shares} 股
- 持仓市值：约 {market_value:.0f} 元
- 当前浮动盈亏：{pnl_pct:+.2f}%（{pnl_amount:+.0f} 元）"""

POSITION_REQUIREMENT = """
4. **持仓诊断**：该用户已经持有此股票，必须结合用户的持仓成本分析当前盈亏状况，给出"是继续持有、加仓、减仓还是止损"的明确建议，并说明理由。操作建议需包含具体的价位（如止损线设在哪里，是否可以在某价位补仓或减仓等）。"""

def analyze_with_ai(
    stock_code: str,
    stock_name: str,
    kline_data: list,
    news_data: list,
    ai_config: dict,
    position: dict = None
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

    position_section = ''
    position_requirement = ''
    if position and position.get('has_position') and position.get('cost_price'):
        cost_price = float(position['cost_price'])
        shares = int(position.get('shares') or 0)
        current_price = kline_data[-1]['close'] if kline_data else cost_price
        pnl_pct = (current_price - cost_price) / cost_price * 100
        market_value = cost_price * shares if shares else cost_price
        current_value = current_price * shares if shares else current_price
        pnl_amount = current_value - market_value if shares else 0
        position_section = POSITION_SECTION_TEMPLATE.format(
            cost_price=cost_price,
            shares=shares if shares else '未填写',
            market_value=market_value,
            pnl_pct=pnl_pct,
            pnl_amount=pnl_amount,
        )
        position_requirement = POSITION_REQUIREMENT
    
    prompt = STOCK_ANALYSIS_PROMPT.format(
        stock_code=stock_code,
        stock_name=stock_name,
        kline_summary=kline_summary,
        news_summary=news_summary,
        position_section=position_section,
        position_requirement=position_requirement,
    )
    
    system_prompt = """你是一位拥有20年实战经验的资深基金经理，曾任职于顶级投资机构，精通A股、港股、美股市场。你擅长将技术分析与消息面驱动相结合，输出的分析报告专业、客观、有深度，可直接指导实盘操作。请严格按照用户要求的JSON格式输出，不要输出任何JSON之外的内容。"""
    
    response = analyzer.analyze(prompt, system_prompt)
    
    if response:
        return parse_ai_response(response)
    
    return None

def _summarize_kline(kline_data: list) -> str:
    if not kline_data:
        return "无数据"

    closes = [d['close'] for d in kline_data]
    volumes = [d.get('volume', 0) for d in kline_data]
    highs = [d['high'] for d in kline_data]
    lows = [d['low'] for d in kline_data]

    recent_10 = kline_data[-10:] if len(kline_data) >= 10 else kline_data
    lines = []
    for d in recent_10:
        chg = ((d['close'] - d['open']) / d['open'] * 100) if d['open'] != 0 else 0
        lines.append(
            f"{d['date']}: 开{d['open']:.2f} 高{d['high']:.2f} 低{d['low']:.2f} 收{d['close']:.2f} "
            f"量{d.get('volume', 0):.0f} 日涨跌{chg:+.2f}%"
        )

    summary = f"近10日K线明细：\n" + "\n".join(lines)

    ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else None
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else None
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None

    avg_vol = sum(volumes) / len(volumes) if volumes else 0
    recent5_vol = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else 0
    vol_ratio = recent5_vol / avg_vol if avg_vol > 0 else 1

    period_change = ((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] != 0 else 0
    week_change = ((closes[-1] - closes[-6]) / closes[-6] * 100) if len(closes) >= 6 and closes[-6] != 0 else 0

    period_high = max(highs)
    period_low = min(lows)
    current_price = closes[-1]
    range_pct = ((current_price - period_low) / (period_high - period_low) * 100) if period_high != period_low else 50

    up_days = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
    down_days = len(closes) - 1 - up_days

    summary += f"\n\n技术指标摘要："
    summary += f"\n- 当前价: {current_price:.2f}"
    if ma5:
        summary += f"\n- MA5: {ma5:.2f}（价{'>' if current_price > ma5 else '<'}均线，{'偏强' if current_price > ma5 else '偏弱'}）"
    if ma10:
        summary += f"\n- MA10: {ma10:.2f}"
    if ma20:
        summary += f"\n- MA20: {ma20:.2f}"
    summary += f"\n- 区间最高: {period_high:.2f}  区间最低: {period_low:.2f}"
    summary += f"\n- 当前价处于区间 {range_pct:.1f}% 位置（100%=历史高点，0%=历史低点）"
    summary += f"\n- 区间总涨跌幅: {period_change:+.2f}%"
    if len(closes) >= 6:
        summary += f"\n- 近5日涨跌幅: {week_change:+.2f}%"
    summary += f"\n- 近5日均量/全期均量: {vol_ratio:.2f}x（{'明显放量' if vol_ratio > 1.5 else '温和放量' if vol_ratio > 1.1 else '缩量' if vol_ratio < 0.8 else '平量'}）"
    summary += f"\n- 上涨天数/下跌天数: {up_days}/{down_days}"

    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            ma_pat = "多头排列（MA5>MA10>MA20），趋势强势"
        elif ma5 < ma10 < ma20:
            ma_pat = "空头排列（MA5<MA10<MA20），趋势偏弱"
        elif ma5 > ma10 and ma10 < ma20:
            ma_pat = "MA5上穿MA10，短期或形成金叉"
        elif ma5 < ma10 and ma10 > ma20:
            ma_pat = "MA5下穿MA10，短期或形成死叉"
        else:
            ma_pat = "均线交织，趋势不明朗，震荡整理"
        summary += f"\n- 均线形态: {ma_pat}"

    return summary

def _summarize_news(news_data: list) -> str:
    if not news_data:
        return "暂无相关新闻，请结合技术面独立判断。"

    summaries = []
    for i, news in enumerate(news_data[:15], 1):
        title = news.get('title', '')
        time_ = news.get('publish_time', '')
        source = news.get('source', '')
        summary = news.get('summary', '')
        line = f"{i}. [{time_}][{source}] {title}"
        if summary:
            line += f"\n   摘要：{summary[:100]}"
        summaries.append(line)

    return "\n".join(summaries)
