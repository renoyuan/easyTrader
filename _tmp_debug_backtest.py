# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trader.backtest.engine import BacktestEngine
from trader.backtest.signal import ScorerSignal
from trader.data.stock import Stock

engine = BacktestEngine(initial_capital=1000000)
engine.fixed_position_ratio = 0.2
engine.signal_filter.enabled = False  # 关闭过滤器
engine.risk_manager.bs_enabled = False  # 关闭黑天鹅

engine.signal_registry.register(ScorerSignal('巴菲特价值评分', min_score=80))

# 加载K线
s = Stock()
df = s.get_daily_kline('300018', '20240101', '20241231')
s.close()
if df is None or df.empty:
    print('K线加载失败')
else:
    engine.load_kline('300018', df)
    stats = engine.run('300018', scorer_name='巴菲特价值评分', min_score=80)
    print(f'总交易次数: {len(engine.trades)}')
    if engine.trades:
        for t in engine.trades:
            print(f'  开仓: {t.entry_date} 价格:{t.entry_price:.2f} 数量:{t.entry_quantity}')
            print(f'  平仓: {t.exit_date} 价格:{t.exit_price:.2f} 盈亏:{t.pnl:.2f}')
    else:
        print('无交易')
        print(f'原始信号数: {len(engine.raw_signal_log)}')
        passed = [s for s in engine.filtered_signal_log if s.get("passed_filter")]
        print(f'过滤后信号数: {len(passed)}')
        # 检查第一次触发信号的详细情况
        if engine.raw_signal_log:
            first = engine.raw_signal_log[0]
            print(f'第一个信号: {first}')
        if engine.filtered_signal_log:
            firstf = engine.filtered_signal_log[0]
            print(f'过滤后第一个: {firstf}')
