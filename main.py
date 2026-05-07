#!/usr/bin/env python3
"""
Stock Analyst Agent - Main entry point
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agent import StockAnalystAgent


def init_config(config_path: str = None):
    """Initialize configuration file"""
    if config_path is None:
        config_path = Path(__file__).parent / "config" / "config.yaml"

    if Path(config_path).exists():
        response = input(f"配置文件已存在: {config_path}\n是否覆盖? (y/n): ")
        if response.lower() != 'y':
            print("取消初始化")
            return

    template = """ai:
  provider: "openai"
  api_key: "your-api-key-here"
  base_url: ""
  model: "gpt-4"

stock:
  default_market: "A股"
  default_period: "日线"
  default_days: 30

news:
  search_days: 7
  max_results: 10
  keywords_template: "{stock_code} {stock_name}"

data_source:
  kline_provider: "akshare"
"""

    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(template)

    print(f"配置文件已创建: {config_path}")
    print("请编辑配置文件填入您的 API Key")


def analyze_command(args):
    """Analyze single stock command"""
    agent = StockAnalystAgent(args.config)

    result = agent.analyze_stock(
        stock_code=args.code,
        stock_name=args.name,
        market=args.market,
        period=args.period,
        days=args.days,
        use_ai=not args.no_ai
    )

    agent.print_analysis(result)

    if args.output:
        report = agent.generate_report(result, 'json' if args.format == 'json' else 'text')
        if args.format == 'json':
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
        else:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
        print(f"\n报告已保存: {args.output}")


def batch_command(args):
    """Batch analyze command"""
    if not os.path.exists(args.file):
        print(f"文件不存在: {args.file}")
        return

    with open(args.file, 'r', encoding='utf-8') as f:
        if args.file.endswith('.json'):
            stocks = json.load(f)
        else:
            stocks = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    if len(parts) >= 2:
                        stocks.append({'code': parts[0].strip(), 'name': parts[1].strip()})

    if not stocks:
        print("未找到有效的股票数据")
        return

    print(f"将分析 {len(stocks)} 只股票")
    response = input("继续? (y/n): ")
    if response.lower() != 'y':
        print("取消")
        return

    agent = StockAnalystAgent(args.config)

    output_dir = args.output
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    results = agent.batch_analyze(stocks, output_dir)

    print(f"\n{'='*50}")
    print(f"批量分析完成，共分析 {len(results)} 只股票")

    if output_dir:
        print(f"报告已保存至: {output_dir}")


def interactive_command(args):
    """Interactive mode command"""
    agent = StockAnalystAgent(args.config)

    print("股票 AI 分析 Agent - 交互模式")
    print("输入 'help' 查看帮助，输入 'quit' 退出\n")

    while True:
        try:
            user_input = input("请输入股票代码和名称 (例如: 600519 贵州茅台): ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("再见!")
                break

            if user_input.lower() == 'help':
                print("""
帮助信息:
  - 输入格式: 股票代码 股票名称 [市场] [周期] [天数]
  - 例如: 600519 贵州茅台 A股 日线 30
  - 支持的市场: A股, 港股, 美股
  - 支持的周期: 日线, 周线, 月线
  - 输入 'quit' 退出
""")
                continue

            parts = user_input.split()
            if len(parts) < 2:
                print("输入格式错误，请重试")
                continue

            stock_code = parts[0]
            stock_name = parts[1]
            market = parts[2] if len(parts) > 2 else None
            period = parts[3] if len(parts) > 3 else None
            days = int(parts[4]) if len(parts) > 4 else None

            result = agent.analyze_stock(
                stock_code=stock_code,
                stock_name=stock_name,
                market=market,
                period=period,
                days=days,
                use_ai=not args.no_ai
            )

            agent.print_analysis(result)
            print()

        except KeyboardInterrupt:
            print("\n再见!")
            break
        except Exception as e:
            print(f"错误: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Stock Analyst Agent - AI-powered stock analysis tool',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '-c', '--config',
        help='配置文件路径',
        default=None
    )

    subparsers = parser.add_subparsers(dest='command', help='子命令')

    init_parser = subparsers.add_parser('init-config', help='初始化配置文件')
    init_parser.add_argument('-o', '--output', help='输出配置文件路径', default=None)

    analyze_parser = subparsers.add_parser('analyze', help='分析单只股票')
    analyze_parser.add_argument('--code', '-k', required=True, help='股票代码')
    analyze_parser.add_argument('--name', '-n', required=True, help='股票名称')
    analyze_parser.add_argument('--market', '-m', default='A股', help='市场 (A股/港股/美股)')
    analyze_parser.add_argument('--period', '-p', default='日线', help='周期 (日线/周线/月线)')
    analyze_parser.add_argument('--days', '-d', type=int, default=30, help='分析天数')
    analyze_parser.add_argument('--output', '-o', help='输出文件路径')
    analyze_parser.add_argument('--format', '-f', choices=['text', 'json'], default='text', help='输出格式')
    analyze_parser.add_argument('--no-ai', action='store_true', help='不使用AI分析')

    batch_parser = subparsers.add_parser('batch', help='批量分析股票')
    batch_parser.add_argument('--file', '-f', required=True, help='股票列表文件')
    batch_parser.add_argument('--output', '-o', help='输出目录')
    batch_parser.add_argument('--no-ai', action='store_true', help='不使用AI分析')

    interactive_parser = subparsers.add_parser('interactive', help='交互模式')
    interactive_parser.add_argument('--no-ai', action='store_true', help='不使用AI分析')

    args = parser.parse_args()

    if args.command == 'init-config':
        init_config(args.output)
    elif args.command == 'analyze':
        analyze_command(args)
    elif args.command == 'batch':
        batch_command(args)
    elif args.command == 'interactive':
        interactive_command(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
