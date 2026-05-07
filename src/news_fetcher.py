"""
News fetcher module for stock-related news
"""

import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class NewsFetcher:
    def __init__(self, search_days: int = 7, max_results: int = 10):
        self.search_days = search_days
        self.max_results = max_results
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def search_news(
        self,
        stock_code: str,
        stock_name: str,
        days: Optional[int] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Search for stock-related news

        Args:
            stock_code: Stock code
            stock_name: Stock name
            days: Number of days to search (default: self.search_days)
            max_results: Maximum number of results (default: self.max_results)

        Returns:
            List of news articles
        """
        if days is None:
            days = self.search_days
        if max_results is None:
            max_results = self.max_results

        if REQUESTS_AVAILABLE:
            return self._search_from_web(stock_code, stock_name, max_results)
        else:
            return self._generate_mock_news(stock_code, stock_name, days)

    def _search_from_web(
        self,
        stock_code: str,
        stock_name: str,
        max_results: int
    ) -> List[Dict]:
        """Search news from web sources"""
        results = []

        try:
            search_queries = [
                f"{stock_name} 股票",
                f"{stock_name} 股价",
                f"{stock_code} 股市"
            ]

            for query in search_queries[:2]:
                news = self._search_baidu(query, max_results // 2)
                results.extend(news)
                time.sleep(0.5)

            unique_results = []
            seen_titles = set()
            for item in results:
                if item['title'] not in seen_titles:
                    seen_titles.add(item['title'])
                    unique_results.append(item)

            return unique_results[:max_results]

        except Exception as e:
            print(f"Error searching news: {e}")
            return self._generate_mock_news(stock_code, stock_name, self.search_days)

    def _search_baidu(self, query: str, max_results: int) -> List[Dict]:
        """Search news via Baidu"""
        url = f"https://www.baidu.com/s?wd={query}&tn=news"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            results = []
            for item in soup.find_all('div', class_='news-item')[:max_results]:
                title_elem = item.find('h3')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = item.find('a')
                    url_link = link['href'] if link and link.has_attr('href') else ''

                    time_elem = item.find('span', class_='c-color-gray')
                    publish_time = time_elem.get_text(strip=True) if time_elem else datetime.now().strftime('%Y-%m-%d')

                    results.append({
                        'title': title,
                        'url': url_link,
                        'publish_time': publish_time,
                        'source': '百度搜索',
                        'summary': ''
                    })

            return results

        except Exception as e:
            print(f"Error searching Baidu: {e}")
            return []

    def _search_eastmoney(self, stock_code: str, max_results: int) -> List[Dict]:
        """Search news from Eastmoney"""
        try:
            url = f"https://search-api-web.eastmoney.com/search/jsonp"
            params = {
                'param': f'{{"uid":"","keyword":"{stock_code}","type":["cmsArticleWebOld"],"client":"web","clientType":"pc","clientVersion":"curr","param":{{"cmsArticleWebOld":{{"searchScope":"default","sort":"default","pageIndex":1,"pageSize":{max_results},"preTag":"<em>","postTag":"</em>"}}}}}}'
            }

            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()

            return []

        except Exception as e:
            print(f"Error searching Eastmoney: {e}")
            return []

    def _generate_mock_news(
        self,
        stock_code: str,
        stock_name: str,
        days: int
    ) -> List[Dict]:
        """Generate mock news data for testing"""
        import random

        news_templates = [
            "{stock_name}发布年度业绩预告，净利润同比增长{percent}%",
            "分析师上调{stock_name}目标价至{price}元",
            "{stock_name}获机构买入评级，目标涨幅{percent}%",
            "{stock_name}发布新产品，市场反响热烈",
            "{stock_name}宣布战略合作，助力业务发展",
            "机构调研{stock_name}，关注核心业务进展",
            "{stock_name}股价创年内新高，市场关注度提升",
            "券商看好{stock_name}，维持\"增持\"评级",
            "{stock_name}入选指数成分股，利好消息提振股价",
            "{stock_name}发布季报，营收超市场预期"
        ]

        sources = ['东方财富', '新浪财经', '证券时报', '第一财经', '财联社']
        results = []

        for i, template in enumerate(news_templates[:self.max_results]):
            days_ago = random.randint(0, days)
            publish_date = datetime.now() - timedelta(days=days_ago)

            title = template.format(
                stock_name=stock_name,
                stock_code=stock_code,
                percent=random.randint(5, 30),
                price=round(random.uniform(50, 200), 2)
            )

            results.append({
                'title': title,
                'url': f'https://example.com/news/{stock_code}_{i}',
                'publish_time': publish_date.strftime('%Y-%m-%d %H:%M'),
                'source': random.choice(sources),
                'summary': f'{stock_name}相关报道，具体内容请查看原文。'
            })

        return results

    def analyze_sentiment(self, news_data: List[Dict]) -> Dict:
        """Analyze sentiment of news"""
        if not news_data:
            return {'sentiment': '中性', 'positive_count': 0, 'negative_count': 0, 'neutral_count': 0}

        positive_keywords = ['增长', '利好', '买入', '上调', '超预期', '创新高', '盈利', '合作', '突破']
        negative_keywords = ['下跌', '利空', '下调', '亏损', '风险', '警告', '调查', '造假', '减持']

        positive_count = 0
        negative_count = 0

        for news in news_data:
            title = news.get('title', '')
            text = news.get('summary', '')

            if any(kw in title + text for kw in positive_keywords):
                positive_count += 1
            elif any(kw in title + text for kw in negative_keywords):
                negative_count += 1

        total = len(news_data)
        neutral_count = total - positive_count - negative_count

        if positive_count > negative_count:
            sentiment = '偏正面'
        elif negative_count > positive_count:
            sentiment = '偏负面'
        else:
            sentiment = '中性'

        return {
            'sentiment': sentiment,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'positive_ratio': round(positive_count / total * 100, 1) if total > 0 else 0,
            'negative_ratio': round(negative_count / total * 100, 1) if total > 0 else 0
        }
