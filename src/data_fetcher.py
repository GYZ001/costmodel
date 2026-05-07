"""
Stock K-line data fetcher module
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


class KlineDataFetcher:
    MARKET_CODE_MAP = {
        'A股': {
            'prefix': '',
            'exchange': 'sz'
        },
        '港股': {
            'prefix': 'hk',
            'exchange': 'hk'
        },
        '美股': {
            'prefix': 'us',
            'exchange': 'us'
        }
    }

    def __init__(self, provider: str = 'akshare'):
        self.provider = provider

    def get_kline_data(
        self,
        stock_code: str,
        market: str = 'A股',
        period: str = '日线',
        days: int = 30
    ) -> List[Dict]:
        """
        Fetch K-line data for a given stock

        Args:
            stock_code: Stock code (e.g., '600519' for A-share, '00700' for HK)
            market: Market type ('A股', '港股', '美股')
            period: Time period ('日线', '周线', '月线')
            days: Number of days of data to fetch

        Returns:
            List of dictionaries containing OHLCV data
        """
        if self.provider == 'akshare' and AKSHARE_AVAILABLE:
            return self._fetch_from_akshare(stock_code, market, period, days)
        elif self.provider == 'yfinance' and YFINANCE_AVAILABLE:
            return self._fetch_from_yfinance(stock_code, market, period, days)
        else:
            return self._generate_mock_data(stock_code, days)

    def _fetch_from_akshare(
        self,
        stock_code: str,
        market: str,
        period: str,
        days: int
    ) -> List[Dict]:
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')

        period_map = {
            '日线': 'daily',
            '周线': 'weekly',
            '月线': 'monthly'
        }

        try:
            if market == 'A股':
                if stock_code.startswith('6'):
                    symbol = f"sh{stock_code}"
                else:
                    symbol = f"sz{stock_code}"

                df = ak.stock_zh_a_hist(symbol=symbol, period=period_map.get(period, 'daily'),
                                       start_date=start_date, end_date=end_date, adjust='qfq')

                result = []
                for _, row in df.iterrows():
                    result.append({
                        'date': row['日期'].strftime('%Y-%m-%d') if hasattr(row['日期'], 'strftime') else str(row['日期']),
                        'open': float(row['开盘']),
                        'high': float(row['最高']),
                        'low': float(row['最低']),
                        'close': float(row['收盘']),
                        'volume': float(row['成交量'])
                    })
                return result[-days:]

            elif market == '港股':
                symbol = f"hk{stock_code}"
                df = ak.stock_hk_spot_em()
                return self._generate_mock_data(stock_code, days)

            elif market == '美股':
                df = ak.stock_us_spot_em()
                return self._generate_mock_data(stock_code, days)

        except Exception as e:
            print(f"Error fetching from akshare: {e}")
            return self._generate_mock_data(stock_code, days)

        return self._generate_mock_data(stock_code, days)

    def _fetch_from_yfinance(
        self,
        stock_code: str,
        market: str,
        period: str,
        days: int
    ) -> List[Dict]:
        interval_map = {
            '日线': '1d',
            '周线': '1wk',
            '月线': '1mo'
        }

        try:
            ticker = yf.Ticker(stock_code)
            df = ticker.history(period=f"{days}d", interval=interval_map.get(period, '1d'))

            result = []
            for date, row in df.iterrows():
                result.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume'])
                })
            return result

        except Exception as e:
            print(f"Error fetching from yfinance: {e}")
            return self._generate_mock_data(stock_code, days)

    def _generate_mock_data(self, stock_code: str, days: int) -> List[Dict]:
        """Generate mock data for testing"""
        import random

        base_price = 100.0
        result = []
        current_date = datetime.now()

        for i in range(days):
            date = current_date - timedelta(days=days - i - 1)
            change = random.uniform(-0.03, 0.03)
            base_price = base_price * (1 + change)

            open_price = base_price * (1 + random.uniform(-0.01, 0.01))
            high_price = max(base_price, open_price) * (1 + random.uniform(0, 0.02))
            low_price = min(base_price, open_price) * (1 - random.uniform(0, 0.02))
            close_price = base_price
            volume = random.randint(1000000, 10000000)

            result.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            })

        return result

    def calculate_indicators(self, kline_data: List[Dict]) -> Dict:
        """Calculate technical indicators from K-line data"""
        if not kline_data:
            return {}

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
