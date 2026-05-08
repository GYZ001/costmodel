#!/usr/bin/env python3
"""
股票数据服务 - 支持真实数据 + AI 分析
"""

import json
import sys
import re
import os
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse

from ai_models import AI_MODELS
from ai_analyzer import analyze_with_ai

config = {
    'ai': {
        'provider': 'deepseek',
        'api_key': '',
        'base_url': '',
        'model': 'deepseek-v4-flash',
    },
    'stock': {
        'default_market': 'A股',
        'default_period': '日线',
        'default_days': 30,
    },
    'news': {
        'search_days': 7,
        'max_results': 10,
    },
}

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    """加载配置"""
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                if saved.get('ai'):
                    config['ai'] = saved['ai']
                if saved.get('stock'):
                    config['stock'] = saved['stock']
        except Exception as e:
            print(f"加载配置失败: {e}", file=sys.stderr)

def save_config():
    """保存配置"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置失败: {e}", file=sys.stderr)

def get_kline_data_eastmoney(code: str, days: int = 30):
    """使用东方财富 API 获取真实K线数据"""
    try:
        if code.startswith('6'):
            secid = f"1.{code}"
        else:
            secid = f"0.{code}"

        url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&end=20500101&lmt={days}"

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        data_obj = data.get('data', {})
        klines = data_obj.get('klines', [])
        stock_name = data_obj.get('name', '')

        if not klines:
            return None

        result = []
        for kline in klines[-days:]:
            parts = kline.split(',')
            if len(parts) >= 6:
                result.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5])
                })

        return {
            'name': stock_name,
            'data': result
        }
    except Exception as e:
        print(f"东方财富数据获取失败: {e}", file=sys.stderr)
        return None

def get_kline_data_mock(code: str, days: int = 30):
    """生成模拟数据"""
    import random
    data = []
    base_price = 100.0

    for i in range(days):
        date = datetime.now() - timedelta(days=days - i - 1)
        change = random.uniform(-0.03, 0.03)
        base_price = base_price * (1 + change)

        open_price = base_price * (1 + random.uniform(-0.01, 0.01))
        close_price = base_price
        high_price = max(base_price, open_price) * (1 + random.uniform(0, 0.02))
        low_price = min(base_price, open_price) * (1 - random.uniform(0, 0.02))
        volume = random.randint(1000000, 10000000)

        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume
        })

    return {
        'name': f'股票{code}',
        'data': data
    }

def calculate_indicators(kline_data):
    """计算技术指标"""
    if not kline_data:
        return None

    closes = [d['close'] for d in kline_data]

    ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else sum(closes) / len(closes)
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else sum(closes) / len(closes)
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else sum(closes) / len(closes)

    latest_close = closes[-1]
    first_close = closes[0]
    price_change = ((latest_close - first_close) / first_close) * 100 if first_close != 0 else 0

    avg_volume = sum(d['volume'] for d in kline_data) / len(kline_data)
    latest_volume = kline_data[-1]['volume']
    volume_change = ((latest_volume - avg_volume) / avg_volume) * 100 if avg_volume != 0 else 0

    return {
        'ma5': round(ma5, 2),
        'ma10': round(ma10, 2),
        'ma20': round(ma20, 2),
        'price_change': round(price_change, 2),
        'volume_change': round(volume_change, 2),
        'latest_close': latest_close,
        'highest': max(d['high'] for d in kline_data),
        'lowest': min(d['low'] for d in kline_data)
    }

def _classify_sentiment(title: str, summary: str):
    positive_kw = ['增长', '新高', '突破', '上涨', '买入', '增持', '利好', '超预期', '盈利', '创新', '扭亏', '连涨', '大涨']
    negative_kw = ['下跌', '亏损', '减持', '利空', '风险', '违规', '处罚', '下调', '暴跌', '退市', '亏损', '连跌', '大跌', '警示']
    text = title + summary
    has_pos = any(k in text for k in positive_kw)
    has_neg = any(k in text for k in negative_kw)
    if has_pos and not has_neg:
        return 'positive'
    elif has_neg and not has_pos:
        return 'negative'
    return 'neutral'

def _build_sentiment(news_list: list):
    pos = sum(1 for n in news_list if n.get('_sent') == 'positive')
    neg = sum(1 for n in news_list if n.get('_sent') == 'negative')
    neu = len(news_list) - pos - neg
    total = len(news_list) or 1
    sentiment = '中性'
    if pos > neg + 2:
        sentiment = '偏正面'
    elif neg > pos + 1:
        sentiment = '偏负面'
    for n in news_list:
        n.pop('_sent', None)
    return {
        'sentiment': sentiment,
        'positive_count': pos,
        'negative_count': neg,
        'neutral_count': neu,
        'positive_ratio': round(pos / total, 2),
        'negative_ratio': round(neg / total, 2),
    }

def _get_news_eastmoney(name: str):
    """东方财富搜索 API，返回真实文章链接"""
    keyword = urllib.parse.quote(name)
    param = urllib.parse.quote(json.dumps({
        "uid": "",
        "keyword": name,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "time",
                "pageIndex": 1,
                "pageSize": 20,
                "preTag": "",
                "postTag": "",
            }
        }
    }, ensure_ascii=False))
    url = f"https://search-api-web.eastmoney.com/search/jsonp?cb=&param={param}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://so.eastmoney.com/',
        'Accept': '*/*',
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read().decode('utf-8').strip()

    raw = raw.lstrip('(').rstrip(';').rstrip(')')
    data = json.loads(raw)
    articles = data.get('result', {}).get('cmsArticleWebOld', [])
    if isinstance(articles, dict):
        articles = articles.get('list', [])

    news_list = []
    for a in articles[:15]:
        title = re.sub(r'<[^>]+>', '', a.get('title', ''))
        art_url = a.get('url', '')
        if not art_url or not art_url.startswith('http'):
            continue
        summary = re.sub(r'<[^>]+>', '', a.get('content', '') or a.get('summary', ''))[:120]
        item = {
            'title': title,
            'url': art_url,
            'publish_time': a.get('date', ''),
            'source': a.get('mediaName', '东方财富'),
            'summary': summary,
            '_sent': _classify_sentiment(title, summary),
        }
        news_list.append(item)
    return news_list

def _get_news_sina(name: str):
    """新浪财经 feed API，返回真实文章链接"""
    keyword = urllib.parse.quote(name)
    url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k={keyword}&num=20&page=1&r=0.1"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://finance.sina.com.cn/',
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode('utf-8'))

    articles = data.get('result', {}).get('data', [])
    news_list = []
    for a in articles[:15]:
        title = re.sub(r'<[^>]+>', '', a.get('title', ''))
        art_url = a.get('url', '')
        if not art_url or not art_url.startswith('http'):
            continue
        ctime = a.get('ctime', '')
        try:
            publish_time = datetime.fromtimestamp(int(ctime)).strftime('%Y-%m-%d %H:%M') if ctime else ''
        except Exception:
            publish_time = ctime
        summary = re.sub(r'<[^>]+>', '', a.get('intro', '') or a.get('summary', ''))[:120]
        item = {
            'title': title,
            'url': art_url,
            'publish_time': publish_time,
            'source': a.get('media_name', '新浪财经'),
            'summary': summary,
            '_sent': _classify_sentiment(title, summary),
        }
        news_list.append(item)
    return news_list

def get_news_real(code: str, name: str, days: int = 7):
    """多源获取真实新闻，所有来源失败时返回空列表"""
    news_list = []

    try:
        news_list = _get_news_eastmoney(name)
        print(f"[新闻] 东方财富获取 {len(news_list)} 条", file=sys.stderr)
    except Exception as e:
        print(f"[新闻] 东方财富失败: {e}", file=sys.stderr)

    if not news_list:
        try:
            news_list = _get_news_sina(name)
            print(f"[新闻] 新浪财经获取 {len(news_list)} 条", file=sys.stderr)
        except Exception as e:
            print(f"[新闻] 新浪财经失败: {e}", file=sys.stderr)

    sentiment = _build_sentiment(news_list)

    return {
        'data': news_list,
        'sentiment': sentiment,
    }


def generate_local_analysis(stock_code: str, stock_name: str, kline_data: list, news_data: list):
    """生成本地分析结果"""
    indicators = calculate_indicators(kline_data)
    closes = [d['close'] for d in kline_data]
    price_change = indicators['price_change'] if indicators else 0

    trend = '震荡'
    if price_change > 3:
        trend = '上涨'
    elif price_change < -3:
        trend = '下跌'

    news_sentiment = news_data[0].get('sentiment', {}) if news_data else {'sentiment': '中性'}
    sentiment = news_sentiment.get('sentiment', '中性')

    recommendation = '观望'
    if trend == '上涨' and sentiment in ['偏正面', '正面']:
        recommendation = '买入'
    elif trend == '震荡' and sentiment == '中性':
        recommendation = '持有'
    elif trend == '下跌' and sentiment in ['偏负面', '负面']:
        recommendation = '卖出'

    support_level = indicators['lowest'] * 1.02 if indicators else 0
    resistance_level = indicators['highest'] * 0.98 if indicators else 0

    key_events = [n['title'] for n in news_data[:5]] if news_data else []

    return {
        'stock_code': stock_code,
        'stock_name': stock_name,
        'analysis_date': datetime.now().strftime('%Y-%m-%d'),
        'technical_analysis': {
            'trend': trend,
            'support_level': round(support_level, 2),
            'resistance_level': round(resistance_level, 2),
            'indicators_summary': f"MA5:{indicators['ma5']}, MA10:{indicators['ma10']}, 涨跌:{indicators['price_change']:.2f}%" if indicators else '',
            'detail': ''
        },
        'news_analysis': {
            'sentiment': sentiment,
            'key_events': key_events,
            'market_feedback': f"正面{news_sentiment.get('positive_count', 0)}条 负面{news_sentiment.get('negative_count', 0)}条 中性{news_sentiment.get('neutral_count', 0)}条",
            'detail': ''
        },
        'recommendation': recommendation,
        'risk_level': '高' if abs(price_change) > 10 else '中' if abs(price_change) > 5 else '低',
        'summary': f'{stock_name}({stock_code})近期{trend}，消息面{sentiment}，建议{recommendation}。本分析为本地规则引擎生成，如需深度AI分析请配置API Key。',
        'investment_logic': f'基于技术指标判断趋势{trend}，消息面情绪{sentiment}，综合给出{recommendation}建议。',
        'risk_factors': ['本分析为本地规则引擎生成，仅供参考', '市场存在不确定性，请做好风险管理', '建议配置AI模型获取更深度分析'],
        'action_plan': '如需精准操作建议，请在设置页面配置AI API Key以启用AI深度分析。',
        'is_local_analysis': True
    }

def analyze_stock(code: str, name: str = '', days: int = 30, position: dict = None):
    """分析股票"""
    print(f"[数据服务] 分析 {name or code}({code})", file=sys.stderr)

    if not config['ai'].get('api_key'):
        raise ValueError("未配置 AI API Key，请在设置中配置后重试")

    kline_result = get_kline_data_eastmoney(code, days)
    if not kline_result:
        print(f"[数据服务] 使用模拟数据", file=sys.stderr)
        kline_result = get_kline_data_mock(code, days)

    stock_name = kline_result.get('name', name) if isinstance(kline_result, dict) else name
    kline_data = kline_result.get('data', []) if isinstance(kline_result, dict) else kline_result

    if not stock_name:
        stock_name = name or f'股票{code}'

    print(f"[数据服务] 股票名称: {stock_name}", file=sys.stderr)

    indicators = calculate_indicators(kline_data)
    print(f"[数据服务] 最新收盘价: {indicators['latest_close'] if indicators else 'N/A'}", file=sys.stderr)

    news_result = get_news_real(code, stock_name, 7)

    ai_result = analyze_with_ai(code, stock_name, kline_data, news_result['data'], config['ai'], position)

    if ai_result:
        print(f"[数据服务] AI 分析成功", file=sys.stderr)
        ai_result['stock_code'] = code
        ai_result['stock_name'] = stock_name
        ai_result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
        ai_result['is_local_analysis'] = False
        return ai_result
    else:
        raise RuntimeError("AI 分析失败，请检查 API Key 是否正确或网络是否畅通")

class DataHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        print(f"[HTTP GET] 路径: {path}, Query: {query}", file=sys.stderr)

        if path == '/api/health' or path == '/health':
            self.send_json({'status': 'ok', 'ai_configured': bool(config['ai'].get('api_key'))})

        elif path == '/api/kline' or path == '/kline':
            code = query.get('code', [''])[0]
            days = int(query.get('days', [30])[0])
            print(f"[K线请求] 股票代码: {code}, 天数: {days}", file=sys.stderr)
            kline_result = get_kline_data_eastmoney(code, days)
            if not kline_result:
                kline_result = get_kline_data_mock(code, days)

            kline_data = kline_result.get('data', []) if isinstance(kline_result, dict) else kline_result
            indicators = calculate_indicators(kline_data)
            print(f"[K线返回] 数据条数: {len(kline_data)}", file=sys.stderr)
            self.send_json({'data': kline_data, 'indicators': indicators})

        elif path == '/api/news' or path == '/news':
            code = query.get('code', [''])[0]
            days = int(query.get('days', [7])[0])
            print(f"[新闻请求] 股票代码: {code}, 天数: {days}", file=sys.stderr)
            kline_result = get_kline_data_eastmoney(code, 1)
            if kline_result and isinstance(kline_result, dict):
                name = kline_result.get('name', f'股票{code}')
            else:
                name = f'股票{code}'
            result = get_news_real(code, name, days)
            print(f"[新闻返回] 条数: {len(result.get('data', []))}", file=sys.stderr)
            self.send_json(result)

        elif path == '/api/config' or path == '/config':
            self.send_json({
                **config,
                'has_ai_config': bool(config['ai'].get('api_key')),
            })

        elif path == '/api/models' or path == '/models':
            self.send_json({'models': list(AI_MODELS.keys())})

        elif path == '/api/test-connection' or path == '/test-connection':
            api_key = config['ai'].get('api_key', '')
            if not api_key:
                self.send_json({'success': False, 'message': '未配置 API Key'})
                return
            try:
                from ai_analyzer import AIAnalyzer
                ai_cfg = config['ai']
                analyzer = AIAnalyzer(
                    ai_cfg.get('provider', 'deepseek'),
                    ai_cfg.get('api_key', ''),
                    ai_cfg.get('model', 'deepseek-v4-flash'),
                    ai_cfg.get('base_url', '')
                )
                ok, msg = analyzer.test_connection()
                self.send_json({'success': ok, 'message': msg})
            except Exception as e:
                self.send_json({'success': False, 'message': str(e)})

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode()
        print(f"[HTTP POST] 路径: {self.path}, Body: {body}", file=sys.stderr)

        if self.path == '/api/analyze' or self.path == '/analyze':
            try:
                data = json.loads(body)
                code = data.get('stock_code', '')
                name = data.get('stock_name', '')
                days = data.get('days', 30)
                position = data.get('position', None)
                print(f"[分析请求] 股票代码: {code}, 名称: {name}, 天数: {days}, 持仓: {position}", file=sys.stderr)

                if not code:
                    self.send_json({'error': '缺少股票代码'}, 400)
                    return

                result = analyze_stock(code, name, days, position)
                print(f"[分析结果] 股票名称: {result.get('stock_name')}, 推荐: {result.get('recommendation')}", file=sys.stderr)
                self.send_json(result)
            except json.JSONDecodeError:
                self.send_json({'error': '无效的请求数据'}, 400)
            except Exception as e:
                print(f"分析错误: {e}", file=sys.stderr)
                self.send_json({'error': str(e)}, 500)

        elif self.path == '/api/config' or self.path == '/config':
            try:
                data = json.loads(body)
                if 'ai' in data:
                    if data['ai'].get('api_key'):
                        config['ai'] = data['ai']
                if 'stock' in data:
                    config['stock'] = data['stock']
                save_config()
                self.send_json({'status': 'ok', 'has_ai_config': bool(config['ai'].get('api_key'))})
            except Exception as e:
                print(f"保存配置错误: {e}", file=sys.stderr)
                self.send_json({'error': str(e)}, 500)

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    load_config()
    PORT = 3000
    server = HTTPServer(('0.0.0.0', PORT), DataHandler)
    print(f"股票数据服务启动: http://localhost:{PORT}", file=sys.stderr)
    print(f"AI 配置状态: {'已配置' if config['ai'].get('api_key') else '未配置'}", file=sys.stderr)
    server.serve_forever()
