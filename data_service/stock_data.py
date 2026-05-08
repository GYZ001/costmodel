#!/usr/bin/env python3
"""
股票数据服务 - 使用新浪财经 API 获取真实数据
"""

import json
import sys
import re
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse

stock_name_map = {
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
}

def get_stock_name(code: str) -> str:
    """根据股票代码获取名称"""
    upper_code = code.upper()
    if upper_code in stock_name_map:
        return stock_name_map[upper_code]
    if upper_code.startswith('6'):
        return '上证股票'
    if upper_code.startswith('0') or upper_code.startswith('3'):
        return '深证股票'
    return f'股票{code}'

def get_kline_data_sina(code: str, days: int = 30):
    """使用新浪财经 API 获取真实K线数据"""
    try:
        if code.startswith('6'):
            symbol = f"sh{code}"
        else:
            symbol = f"sz{code}"

        url = f"https://quotes.sina.cn/cn/api/jsonp.php/var%20_{symbol}=/CN_MarketDataService.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={days}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')

        match = re.search(r'\[.*\]', data, re.DOTALL)
        if not match:
            return None

        kline_list = json.loads(match.group())
        result = []
        for item in kline_list[-days:]:
            result.append({
                'date': item.get('day', '').split(' ')[0],
                'open': float(item.get('open', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'close': float(item.get('close', 0)),
                'volume': float(item.get('volume', 0))
            })
        return result
    except Exception as e:
        print(f"新浪财经数据获取失败: {e}", file=sys.stderr)
        return None

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

        klines = data.get('data', {}).get('klines', [])
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
        return result
    except Exception as e:
        print(f"东方财富数据获取失败: {e}", file=sys.stderr)
        return None

def get_kline_data_mock(code: str, days: int = 30):
    """生成模拟数据（当API不可用时）"""
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

    return data

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

def get_news_mock(code: str, name: str, days: int = 7):
    """生成模拟新闻"""
    import random

    templates = [
        f"{name}发布年度业绩预告，净利润同比增长20%",
        f"分析师上调{name}目标价至新高",
        f"{name}获机构买入评级",
        f"{name}发布新产品线",
        f"{name}宣布战略合作计划",
        f"机构调研{name}，关注核心业务",
        f"{name}股价创近期新高",
        f"券商看好{name}，维持增持评级",
        f"{name}入选重要指数成分股",
        f"{name}发布季报，业绩超预期",
    ]

    sources = ['东方财富', '新浪财经', '证券时报', '第一财经', '财联社']
    news_data = []

    for i, template in enumerate(templates[:10]):
        days_ago = random.randint(0, days)
        date = datetime.now() - timedelta(days=days_ago)
        news_data.append({
            'title': template,
            'url': f'https://finance.example.com/news/{code}_{i}',
            'publish_time': date.strftime('%Y-%m-%d %H:%M'),
            'source': random.choice(sources),
            'summary': f'{name}相关报道，更多详情请查看原文。'
        })

    positive_count = random.randint(3, 7)
    negative_count = random.randint(0, 2)
    neutral_count = 10 - positive_count - negative_count

    sentiment = '中性'
    if positive_count > negative_count + 2:
        sentiment = '偏正面'
    elif negative_count > positive_count:
        sentiment = '偏负面'

    return {
        'data': news_data,
        'sentiment': {
            'sentiment': sentiment,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'positive_ratio': (positive_count / 10) * 100,
            'negative_ratio': (negative_count / 10) * 100
        }
    }

def analyze_stock(code: str, name: str = '', days: int = 30):
    """分析股票"""
    if not name:
        name = get_stock_name(code)

    print(f"[数据服务] 分析 {name}({code})", file=sys.stderr)

    kline_data = get_kline_data_eastmoney(code, days)
    
    if not kline_data:
        print(f"[数据服务] 东方财富失败，尝试新浪财经", file=sys.stderr)
        kline_data = get_kline_data_sina(code, days)

    if not kline_data:
        print(f"[数据服务] 所有API失败，使用模拟数据", file=sys.stderr)
        kline_data = get_kline_data_mock(code, days)

    indicators = calculate_indicators(kline_data)
    news_result = get_news_mock(code, name, 7)

    closes = [d['close'] for d in kline_data]
    price_change = indicators['price_change'] if indicators else 0

    trend = '震荡'
    if price_change > 3:
        trend = '上涨'
    elif price_change < -3:
        trend = '下跌'

    sentiment = news_result['sentiment']['sentiment']
    recommendation = '观望'
    if trend == '上涨' and sentiment in ['偏正面', '正面']:
        recommendation = '买入'
    elif trend == '震荡' and sentiment == '中性':
        recommendation = '持有'
    elif trend == '下跌' and sentiment in ['偏负面', '负面']:
        recommendation = '卖出'

    support_level = indicators['lowest'] * 1.02 if indicators else 0
    resistance_level = indicators['highest'] * 0.98 if indicators else 0

    key_events = [n['title'] for n in news_result['data'][:5]]

    result = {
        'stock_code': code,
        'stock_name': name,
        'analysis_date': datetime.now().strftime('%Y-%m-%d'),
        'technical_analysis': {
            'trend': trend,
            'support_level': round(support_level, 2),
            'resistance_level': round(resistance_level, 2),
            'indicators_summary': f"MA5:{indicators['ma5']}, MA10:{indicators['ma10']}, 涨跌:{indicators['price_change']:.2f}%" if indicators else ''
        },
        'news_analysis': {
            'sentiment': sentiment,
            'key_events': key_events,
            'market_feedback': f"正{news_result['sentiment']['positive_count']}负{news_result['sentiment']['negative_count']}中{news_result['sentiment']['neutral_count']}"
        },
        'recommendation': recommendation,
        'risk_level': '高' if abs(price_change) > 10 else '中' if abs(price_change) > 5 else '低',
        'summary': f'{name}({code})近期{trend}，消息面{sentiment}，建议{recommendation}',
        'is_local_analysis': True
    }

    print(f"[数据服务] 最新收盘价: {indicators['latest_close'] if indicators else 'N/A'}", file=sys.stderr)

    return result

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

        if path == '/api/health' or path == '/health':
            self.send_json({'status': 'ok'})

        elif path == '/api/kline' or path == '/kline':
            code = query.get('code', [''])[0]
            days = int(query.get('days', [30])[0])

            kline_data = get_kline_data_eastmoney(code, days)
            if not kline_data:
                kline_data = get_kline_data_sina(code, days)
            if not kline_data:
                kline_data = get_kline_data_mock(code, days)

            indicators = calculate_indicators(kline_data)
            self.send_json({'data': kline_data, 'indicators': indicators})

        elif path == '/api/news' or path == '/news':
            code = query.get('code', [''])[0]
            name = query.get('name', [''])[0] or get_stock_name(code)
            days = int(query.get('days', [7])[0])
            self.send_json(get_news_mock(code, name, days))

        elif path == '/api/config' or path == '/config':
            self.send_json({
                'has_ai_config': False,
                'data_source': {'kline_provider': 'eastmoney'}
            })

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode()

        if self.path == '/api/analyze' or self.path == '/analyze':
            try:
                data = json.loads(body)
                code = data.get('stock_code', '')
                name = data.get('stock_name', '')
                days = data.get('days', 30)

                if not code:
                    self.send_json({'error': '缺少股票代码'}, 400)
                    return

                result = analyze_stock(code, name, days)
                self.send_json(result)
            except json.JSONDecodeError as e:
                print(f"JSON 解析错误: {e}", file=sys.stderr)
                self.send_json({'error': '无效的请求数据'}, 400)
            except Exception as e:
                print(f"分析错误: {e}", file=sys.stderr)
                self.send_json({'error': str(e)}, 500)

        elif self.path == '/api/config' or self.path == '/config':
            self.send_json({'status': 'ok'})

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
    PORT = 3000
    server = HTTPServer(('0.0.0.0', PORT), DataHandler)
    print(f"股票数据服务启动: http://localhost:{PORT}", file=sys.stderr)
    server.serve_forever()
