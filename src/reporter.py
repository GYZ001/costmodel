"""
Report generator module
"""

from datetime import datetime
from typing import Any, Dict, List


class Reporter:
    def __init__(self):
        self.template = """
================================================================================
                        股票 AI 分析报告
================================================================================

股票代码: {stock_code}
股票名称: {stock_name}
分析日期: {analysis_date}

--------------------------------------------------------------------------------
                              技术面分析
--------------------------------------------------------------------------------
趋势判断: {trend}
支撑位:   {support_level}
压力位:   {resistance_level}
指标总结: {indicators_summary}

--------------------------------------------------------------------------------
                              消息面分析
--------------------------------------------------------------------------------
情绪判断: {sentiment}
关键事件:
{key_events}
市场反馈: {market_feedback}

--------------------------------------------------------------------------------
                              综合建议
--------------------------------------------------------------------------------
投资建议: {recommendation}
风险等级: {risk_level}

================================================================================
                              分析总结
================================================================================
{summary}

================================================================================
"""

    def generate_report(self, analysis_result: Dict[str, Any]) -> str:
        """
        Generate text report from analysis result

        Args:
            analysis_result: Analysis result dictionary

        Returns:
            Formatted report string
        """
        tech = analysis_result.get('technical_analysis', {})
        news = analysis_result.get('news_analysis', {})

        key_events = news.get('key_events', [])
        if isinstance(key_events, list) and key_events:
            events_text = '\n'.join([f"  • {event}" for event in key_events[:5]])
        else:
            events_text = "  • 无关键事件"

        report = self.template.format(
            stock_code=analysis_result.get('stock_code', 'N/A'),
            stock_name=analysis_result.get('stock_name', 'N/A'),
            analysis_date=analysis_result.get('analysis_date', datetime.now().strftime('%Y-%m-%d')),
            trend=tech.get('trend', '未知'),
            support_level=tech.get('support_level', 'N/A'),
            resistance_level=tech.get('resistance_level', 'N/A'),
            indicators_summary=tech.get('indicators_summary', '无数据'),
            sentiment=news.get('sentiment', '未知'),
            key_events=events_text,
            market_feedback=news.get('market_feedback', '无数据'),
            recommendation=analysis_result.get('recommendation', '未知'),
            risk_level=analysis_result.get('risk_level', '未知'),
            summary=analysis_result.get('summary', '无总结')
        )

        return report

    def save_report(self, report: str, file_path: str) -> bool:
        """
        Save report to file

        Args:
            report: Report content
            file_path: File path to save

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            return True
        except Exception as e:
            print(f"Failed to save report: {e}")
            return False

    def generate_json_report(self, analysis_result: Dict[str, Any]) -> str:
        """
        Generate JSON formatted report

        Args:
            analysis_result: Analysis result dictionary

        Returns:
            JSON string
        """
        import json

        output = {
            'report_info': {
                'stock_code': analysis_result.get('stock_code'),
                'stock_name': analysis_result.get('stock_name'),
                'analysis_date': analysis_result.get('analysis_date', datetime.now().strftime('%Y-%m-%d')),
                'generated_at': datetime.now().isoformat()
            },
            'technical_analysis': analysis_result.get('technical_analysis', {}),
            'news_analysis': analysis_result.get('news_analysis', {}),
            'recommendation': {
                'action': analysis_result.get('recommendation'),
                'risk_level': analysis_result.get('risk_level'),
                'summary': analysis_result.get('summary')
            }
        }

        return json.dumps(output, ensure_ascii=False, indent=2)
