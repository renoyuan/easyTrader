#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  回测模块使用示例

"""
回测模块使用示例
=================
展示如何与 scorer 模块结合使用。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from trader.backtest import BacktestEngine, PerformanceStats
from trader.backtest.engine import quick_backtest
from trader.backtest.signal import ScorerSignal, TechnicalSignal
from trader.backtest.filter import TrendFilter, VolumeFilter, MACrossFilter
from trader.backtest.trade import TickSnapshot


def demo_single_stock():
    """
    示例1：单标的快速回测
    使用评分信号作为入场依据
    """
    print("\n" + "=" * 60)
    print("📊 示例1：单标的快速回测（与评分模块结合）")
    print("=" * 60)

    stats = quick_backtest(
        code="600519",           # 贵州茅台
        start_date="20230101",
        end_date="20241231",
        scorer_name="renoyuan核心评分",
        min_score=70.0,
        initial_capital=100000.0,
    )

    return stats


def demo_custom_strategy():
    """
    示例2：自定义策略回测
    展示如何组合技术指标信号 + 评分信号 + 过滤器
    """
    print("\n" + "=" * 60)
    print("📊 示例2：自定义策略回测")
    print("=" * 60)

    from trader.data.stock import Stock

    engine = BacktestEngine(initial_capital=100000.0)

    # 1. 注册入场信号
    # 评分信号
    engine.signal_registry.register(ScorerSignal("renoyuan核心评分", min_score=70))

    # 技术指标信号：收盘站上MA5且MA5金叉MA10
    def ma_cross_condition(tick: TickSnapshot, context: dict) -> bool:
        if tick.ma5 is None or tick.ma10 is None:
            return False
        return tick.close > tick.ma5 and tick.ma5 > tick.ma10

    engine.signal_registry.register(TechnicalSignal(
        name="MA5金叉MA10",
        condition_fn=ma_cross_condition,
        detail_fn=lambda t, c: {
            "close": round(t.close, 2),
            "ma5": round(t.ma5, 2) if t.ma5 else 0,
            "ma10": round(t.ma10, 2) if t.ma10 else 0,
        }
    ))

    # 2. 注册信号过滤器 [强烈建议]
    engine.signal_filter.add_filter(TrendFilter(ma_period=20))
    engine.signal_filter.add_filter(MACrossFilter(short_ma=5, mid_ma=10, long_ma=20))

    # 3. 加载数据
    code = "601318"  # 中国平安
    stock_srv = Stock()
    df = stock_srv.get_daily_kline(code, "20230101", "20241231")
    stock_srv.close()

    if df is not None and not df.empty:
        engine.load_kline(code, df)

        # 4. 运行回测
        stats = engine.run(code)

        # 5. 输出报告
        print(engine.print_summary())
        print(stats.print_report())

        # 6. 信号过滤对比
        print("\n── 信号过滤对比 ──")
        comparison = engine.get_signal_comparison()
        print(comparison.to_string(index=False))

        # 7. 交易记录
        print("\n── 交易记录前10笔 ──")
        trades_df = engine.get_trades_df()
        if not trades_df.empty:
            print(trades_df.head(10).to_string(index=False))

    return engine


def demo_batch_backtest():
    """
    示例3：多标的批量回测 [建议]
    """
    print("\n" + "=" * 60)
    print("📊 示例3：多标批量回测对比")
    print("=" * 60)

    codes = ["600519", "000858", "600036", "601318"]
    results = []

    for code in codes:
        print(f"\n▶ 回测 {code}...")
        stats = quick_backtest(
            code=code,
            start_date="20230101",
            end_date="20241231",
            scorer_name="renoyuan核心评分",
            min_score=65,
        )
        results.append({"code": code, "stats": stats})

    # 汇总对比
    print("\n" + "=" * 60)
    print("📊  多标回测对比汇总")
    print("=" * 60)
    for r in results:
        s = r["stats"]
        print(f"\n{r['code']:<8} 总交易:{s.total_trades:>3}  "
              f"胜率:{s.win_rate:>5.1f}%  盈亏比:{s.profit_factor:>5.2f}  "
              f"最大回撤:{s.max_drawdown:>5.1f}%  年化:{s.annual_return:>5.1f}%")

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # 命令行模式
        code = sys.argv[1]
        start = sys.argv[2] if len(sys.argv) > 2 else "20230101"
        end = sys.argv[3] if len(sys.argv) > 3 else "20241231"
        scorer = sys.argv[4] if len(sys.argv) > 4 else "renoyuan核心评分"

        stats = quick_backtest(code, start, end, scorer_name=scorer)
    else:
        # 交互模式
        print("请选择演示模式：")
        print("1 - 单标的快速回测")
        print("2 - 自定义策略回测")
        print("3 - 多标的批量回测")

        choice = input("请输入数字 (1/2/3): ").strip()

        if choice == "1":
            demo_single_stock()
        elif choice == "2":
            demo_custom_strategy()
        elif choice == "3":
            demo_batch_backtest()
        else:
            print("❌ 无效选择")
