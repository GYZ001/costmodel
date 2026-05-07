"""
Stock Analyst Agent - Main agent logic
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .config_loader import ConfigLoader
from .data_fetcher import KlineDataFetcher
from .news_fetcher import NewsFetcher
from .ai_analyzer import AIAnalyzer
from .reporter import Reporter


class StockAnalystAgent:
    def __init__(self, config_path: Optional[str] = None):
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()

        ai_config = self.config_loader.get_ai_config()
        stock_config = self.config_loader.get_stock_config()
        news_config = self.config_loader.get_news_config()
        data_source_config = self.config_loader.get_data_source_config()

        self.kline_fetcher = KlineDataFetcher(
            provider=data_source_config.get('kline_provider', 'akshare')
        )

        self.news_fetcher = NewsFetcher(
            search_days=news_config.get('search_days', 7),
            max_results=news_config.get('max_results', 10)
        )

        self.ai_analyzer = AIAnalyzer(
            provider=ai_config.get('provider', 'openai'),
            api_key=ai_config.get('api_key', ''),
            base_url=ai_config.get('base_url', ''),
            model=ai_config.get('model', 'gpt-4')
        )

        self.reporter = Reporter()

        self.default_market = stock_config.get('default_market', 'A股')
        self.default_period = stock_config.get('default_period', '日线')
        self.default_days = stock_config.get('default_days', 30)

    def analyze_stock(
        self,
        stock_code: str,
        stock_name: str,
        market: Optional[str] = None,
        period: Optional[str] = None,
        days: Optional[int] = None,
        use_ai: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze a single stock

        Args:
            stock_code: Stock code
            stock_name: Stock name
            market: Market type (default: config default)
            period: Time period (default: config default)
            days: Number of days for analysis (default: config default)
            use_ai: Whether to use AI for analysis

        Returns:
            Analysis result dictionary
        """
        market = market or self.default_market
        period = period or self.default_period
        days = days or self.default_days

        print(f"正在分析股票: {stock_name}({stock_code}) - {market} {period}")

        print("  正在获取K线数据...")
        kline_data = self.kline_fetcher.get_kline_data(
            stock_code=stock_code,
            market=market,
            period=period,
            days=days
        )
        print(f"  已获取 {len(kline_data)} 条K线数据")

        print("  正在获取新闻数据...")
        news_data = self.news_fetcher.search_news(
            stock_code=stock_code,
            stock_name=stock_name,
            days=self.config_loader.get_news_config().get('search_days', 7)
        )
        print(f"  已获取 {len(news_data)} 条新闻")

        if use_ai:
            print("  正在进行AI分析...")
            analysis_result = self.ai_analyzer.analyze(
                stock_code=stock_code,
                stock_name=stock_name,
                kline_data=kline_data,
                news_data=news_data
            )
        else:
            print("  正在生成本地分析...")
            analysis_result = self._local_analysis(
                stock_code=stock_code,
                stock_name=stock_name,
                kline_data=kline_data,
                news_data=news_data
            )

        analysis_result['stock_code'] = stock_code
        analysis_result['stock_name'] = stock_name
        analysis_result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')

        return analysis_result

    def _local_analysis(
        self,
        stock_code: str,
        stock_name: str,
        kline_data: List[Dict],
        news_data: List[Dict]
    ) -> Dict[str, Any]:
        """Local analysis without AI"""
        indicators = self.kline_fetcher.calculate_indicators(kline_data)
        sentiment = self.news_fetcher.analyze_sentiment(news_data)

        trend = '震荡'
        if indicators.get('price_change', 0) > 3:
            trend = '上涨'
        elif indicators.get('price_change', 0) < -3:
            trend = '下跌'

        recommendation = '观望'
        if trend == '上涨' and sentiment['sentiment'] in ['偏正面', '正面']:
            recommendation = '买入'
        elif trend == '下跌' and sentiment['sentiment'] in ['偏负面', '负面']:
            recommendation = '卖出'
        elif trend == '震荡':
            recommendation = '持有'

        return {
            'technical_analysis': {
                'trend': trend,
                'support_level': indicators.get('lowest', 0) * 1.02,
                'resistance_level': indicators.get('highest', 0) * 0.98,
                'indicators_summary': f"MA5:{indicators.get('ma5', 0):.2f}, MA10:{indicators.get('ma10', 0):.2f}, "
                                    f"涨跌:{indicators.get('price_change', 0):.2f}%"
            },
            'news_analysis': {
                'sentiment': sentiment['sentiment'],
                'key_events': [n['title'] for n in news_data[:5]],
                'market_feedback': f"正{sentiment['positive_count']}负{sentiment['negative_count']}中{sentiment['neutral_count']}"
            },
            'recommendation': recommendation,
            'risk_level': '中',
            'summary': f"{stock_name}近期{trend}，消息面{sentiment['sentiment']}，建议{recommendation}"
        }

    def batch_analyze(
        self,
        stocks: List[Dict[str, str]],
        output_dir: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple stocks

        Args:
            stocks: List of stock dictionaries with 'code' and 'name' keys
            output_dir: Directory to save reports

        Returns:
            List of analysis results
        """
        results = []

        for i, stock in enumerate(stocks, 1):
            print(f"\n[{i}/{len(stocks)}] 分析中...")
            try:
                result = self.analyze_stock(
                    stock_code=stock.get('code', ''),
                    stock_name=stock.get('name', ''),
                    market=stock.get('market'),
                    period=stock.get('period'),
                    days=stock.get('days')
                )
                results.append(result)

                if output_dir:
                    import os
                    filename = f"{stock['code']}_{stock['name']}_analysis.txt"
                    filepath = os.path.join(output_dir, filename)
                    report = self.reporter.generate_report(result)
                    self.reporter.save_report(report, filepath)
                    print(f"  报告已保存: {filepath}")

            except Exception as e:
                print(f"  分析失败: {e}")

        return results

    def generate_report(
        self,
        analysis_result: Dict[str, Any],
        format: str = 'text'
    ) -> str:
        """
        Generate report from analysis result

        Args:
            analysis_result: Analysis result
            format: Report format ('text' or 'json')

        Returns:
            Formatted report
        """
        if format == 'json':
            return self.reporter.generate_json_report(analysis_result)
        else:
            return self.reporter.generate_report(analysis_result)

    def print_analysis(self, analysis_result: Dict[str, Any]) -> None:
        """Print analysis result to console"""
        report = self.generate_report(analysis_result, 'text')
        print(report)
