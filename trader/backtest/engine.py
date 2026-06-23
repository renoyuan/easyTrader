#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  回测引擎 - 核心执行模块

"""
回测引擎 [核心]
================
完整闭环执行流程：

1. 导入历史 K 线 / 因子数据
2. 遍历每根 K 线生成原始入场信号
3. 信号过滤层筛选，剔除无效假信号
4. 满足开仓条件则建仓，记录入场逻辑
5. 持仓循环校验五大平仓条件（任一触发即离场）
   ① 逻辑反转出场 ｜ ② 价格止损 ｜ ③ 价格止盈 ｜ ④ 时间止损 ｜ ⑤ 黑天鹅强制平仓
6. 每笔交易记录离场原因、盈亏、持仓时长
7. 全周期汇总输出绩效报表、分层归因分析
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
import uuid

from .trade import (
    TradeRecord, Position, TickSnapshot, TradeSide,
    ExitReason, SignalSource
)
from .signal import SignalRegistry, SignalResult, ScorerSignal
from .risk import RiskManager, RiskResult
from .filter import SignalFilter, FilterResult
from .stats import PerformanceStats, compute_performance


class BacktestEngine:
    """
    回测引擎
    ========
    核心执行器，管理回测全流程。
    支持与 scorer 模块对接，使用评分结果作为入场信号。
    """

    def __init__(self,
                 initial_capital: float = 100000.0,
                 commission_pct: float = 0.0003,    # 佣金万分之三 [建议]
                 slippage_pct: float = 0.001,         # 滑点 0.1% [建议]
                 stamp_tax_pct: float = 0.001,        # 印花税千分之一（卖出）[建议]
                 ):
        # ── 资金配置 ──
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.peak_capital = initial_capital

        # ── 费用配置 [建议] ──
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.stamp_tax_pct = stamp_tax_pct

        # ── 模块注入 ──
        self.signal_registry = SignalRegistry()       # [必须] 信号注册
        self.risk_manager = RiskManager()             # [必须] 风控管理
        self.signal_filter = SignalFilter(enabled=True)  # [强烈建议] 信号过滤

        # ── [建议] 仓位管理配置 ──
        self.position_mode = "fixed"       # fixed / pyramid / kelly
        self.fixed_position_ratio = 0.2    # 固定仓位：20% 资金

        # ── 运行时状态 ──
        self.trades: List[TradeRecord] = []          # 已完成交易
        self.current_positions: Dict[str, Position] = {}  # 当前持仓（按代码）
        self.current_timestamp: Optional[date] = None
        self.kline_data: Dict[str, pd.DataFrame] = {}    # K线数据缓存
        self.equity_curve: List[float] = [initial_capital]

        # ── 原始信号记录（对比过滤效果） ──
        self.raw_signal_log: List[Dict] = []   # 未过滤前的信号
        self.filtered_signal_log: List[Dict] = []  # 过滤后的信号

        # ── 回调函数 ──
        self.on_trade_callback: Optional[Callable[[TradeRecord], None]] = None

        # ── [新增] 每日日志回调与配置 ──
        self.on_daily_log_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._daily_log_enabled: bool = True
        self._daily_log_interval: int = 1       # 每次 K 线输出一次
        self._daily_log_skip_days: int = 5      # 连续无交易超过此天数则跳过输出，节省空间

    # ═══════════════════════════════════════════
    #  数据加载
    # ═══════════════════════════════════════════

    def load_kline(self, code: str, df: pd.DataFrame) -> None:
        """
        加载 K 线数据
        :param code: 股票代码
        :param df: 包含 date/open/close/high/low/volume/amount/pct_chg 列的 DataFrame
        """
        required = ['date', 'open', 'close', 'high', 'low', 'volume']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"K线数据缺少必需列: {col}")

        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        self.kline_data[code] = df

    def load_kline_from_db(self, code: str, start_date: str, end_date: str) -> bool:
        """
        从本地数据库加载 K 线数据
        :return: 是否加载成功
        """
        try:
            from trader.data.stock import Stock
            stock_srv = Stock()
            df = stock_srv.get_daily_kline(code, start_date, end_date)
            stock_srv.close()
            if df is not None and not df.empty:
                self.load_kline(code, df)
                return True
            return False
        except Exception as e:
            print(f"加载K线失败 {code}: {e}")
            return False

    # ═══════════════════════════════════════════
    #  技术指标计算
    # ═══════════════════════════════════════════

    def _calc_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算常用技术指标（ATR, RSI, MA, 波动率等）"""
        df = df.copy()

        # 均线
        for period in [5, 10, 20, 60]:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()

        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=14).mean()

        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))

        # 波动率（20日标准差）
        df['volatility'] = df['pct_chg'].rolling(window=20).std() / 100 if 'pct_chg' in df.columns else None

        # 成交量均线
        df['volume_ma5'] = df['volume'].rolling(window=5).mean()
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()

        return df

    # ═══════════════════════════════════════════
    #  执行回测
    # ═══════════════════════════════════════════

    def run(self, code: str,
            scorer_name: Optional[str] = None,
            min_score: float = 80.0,
            progress_callback: Optional[Callable[[int, int, str], None]] = None,
            debug: bool = True,  # 开启调试日志
            ) -> PerformanceStats:
        """
        执行单标的回测

        :param code: 股票代码
        :param scorer_name: 评分体系名称（可选），传入后会自动对接 scorer 进行评分
        :param min_score: 最小触发评分阈值
        :param progress_callback: 进度回调
        :return: PerformanceStats
        """
        if code not in self.kline_data:
            raise ValueError(f"未加载 {code} 的K线数据，请先调用 load_kline() 或 load_kline_from_db()")

        df_raw = self.kline_data[code].copy()
        df = self._calc_indicators(df_raw)
        total_bars = len(df)

        # ── 初始化状态 ──
        self.trades = []
        self.current_positions = {}
        self.capital = self.initial_capital
        self.peak_capital = self.initial_capital
        self.equity_curve = [self.initial_capital]
        self.raw_signal_log = []
        self.filtered_signal_log = []

        # ── 如果指定了评分体系，注册评分信号 ──
        if scorer_name:
            self.signal_registry.register(ScorerSignal(scorer_name, min_score))
            if debug:
                print(f"[DEBUG] 评分信号已注册: {scorer_name}, 阈值={min_score}")

        # ── 先执行一次评分并输出结果（调试用） ──
        if scorer_name and debug:
            try:
                from trader.scorer.market_scanner import SCORER_MAP
                scorer_cls = SCORER_MAP.get(scorer_name)
                if scorer_cls:
                    scorer_inst = scorer_cls()
                    result = scorer_inst.score(code)
                    if result is None:
                        print(f"[DEBUG] 评分器 {scorer_name} 返回 None")
                    elif isinstance(result, dict):
                        score_val = result.get("score", result.get("total_score", "N/A"))
                        rating = result.get("rating", result.get("评级", "N/A"))
                        print(f"[DEBUG] 评分结果: score={score_val}, rating={rating}, keys={list(result.keys())}")
                    else:
                        print(f"[DEBUG] 评分结果(非dict): {type(result)} = {result}")
                else:
                    print(f"[DEBUG] 评分器类未找到: {scorer_name}")
            except Exception as e:
                print(f"[DEBUG] 评分器调用异常: {e}")
                import traceback
                traceback.print_exc()

        # ── 遍历每根 K 线 ──
        for idx, row in df.iterrows():
            if idx < 20:  # 前20根K线用于计算指标，跳过
                continue

            self.current_timestamp = row['date'].date() if hasattr(row['date'], 'date') else row['date']

            tick = self._row_to_tick(row, code)
            context = self._build_context(code, df, idx)

            # ── 设置评分体系名称 ──
            if scorer_name:
                context["scorer_name"] = scorer_name

            # ── 实时评分：调用 scorer 获取当前评分填入 context ──
            if scorer_name:
                scorer_result = self._evaluate_scorer(code, tick, context, idx, df)
                context["scorer_result"] = scorer_result

            # ── 调试：每 50 根 K 线输出一次评分状态 ──
            if debug and scorer_name and idx % 50 == 0:
                sr = context.get("scorer_result", {}).get(scorer_name, {})
                print(f"[DEBUG] idx={idx}, date={self.current_timestamp}, scorer_score={sr.get('score', 'N/A')}")

            # ── 如果有持仓，先执行持仓风控检查 ──
            if code in self.current_positions:
                pos = self.current_positions[code]
                pos.current_price = tick.close
                pos.holding_days += 1

                # 更新持仓最高/最低价
                pos.highest_price = max(pos.highest_price, tick.high)
                pos.lowest_price = min(pos.lowest_price, tick.low)

                # 全维度风控检查
                risk_result = self.risk_manager.check_all(
                    pos=pos,
                    tick=tick,
                    entry_price=pos.avg_cost,
                    entry_date=pos.entry_date,
                    current_date=self.current_timestamp,
                    market_pct_chg=context.get("market_pct_chg", 0),
                )

                if risk_result.triggered:
                    self._close_position(code, tick, risk_result, pos, context)

            # ── 如果没有持仓，执行入场信号判断 ──
            signal_triggered = False
            signal_reason = ""
            filter_passed = False
            filter_reason = ""
            open_skipped_reason = ""
            today_score = 0
            today_rating = ""

            if code not in self.current_positions:
                # 获取当日评分
                sr = context.get("scorer_result", {}).get(scorer_name, {}) if scorer_name else {}
                today_score = sr.get("score", 0)
                today_rating = sr.get("rating", "")

                # 1. 生成原始入场信号
                signal_results = self.signal_registry.get_triggered(tick, context)

                if signal_results:
                    signal_triggered = True
                    signal_reason = signal_results[0].summary if signal_results else ""

                if debug and signal_results and idx % 50 == 0:
                    for sr in signal_results:
                        print(f"[DEBUG] 信号触发! idx={idx}, {sr.summary}")

                if signal_results:
                    # 记录原始信号（用于过滤对比）
                    for sr in signal_results:
                        self.raw_signal_log.append({
                            "date": str(self.current_timestamp),
                            "code": code,
                            "signal": sr.summary,
                            "score": sr.score,
                        })

                    # 2. 信号过滤 [强烈建议]
                    filter_result = self.signal_filter.check_all(tick, context)
                    filter_passed = filter_result.passed
                    filter_reason = filter_result.failed_detail if not filter_result.passed else ""

                    # 记录过滤后信号
                    for sr in signal_results:
                        self.filtered_signal_log.append({
                            "date": str(self.current_timestamp),
                            "code": code,
                            "signal": sr.summary,
                            "score": sr.score,
                            "passed_filter": filter_passed,
                            "filter_detail": filter_reason,
                        })

                    # 3. 如果通过过滤，开仓
                    if filter_passed:
                        opened = self._open_position(code, tick, signal_results, filter_result, context)
                        if not opened:
                            open_skipped_reason = "资金不足/数量为0(股价过高)"
                else:
                    # 信号未触发，找出原因
                    if scorer_name:
                        if today_score < min_score:
                            signal_reason = f"评分{today_score}<阈值{min_score}"
                        else:
                            signal_reason = f"评分达标({today_score})但未达入场条件"
                    else:
                        signal_reason = "无评分体系/技术信号未触发"

            # ── [新增] 每日日志输出 ──
            if self._daily_log_enabled and self.on_daily_log_callback:
                # 收集当日日志信息
                has_position = code in self.current_positions
                just_opened = (has_position and
                               self.current_positions[code].holding_days == 0 and
                               hasattr(self.current_positions[code], '_trade_ref'))
                just_closed = False
                # 检查最近是否有平仓（trade 记录的最后一条是今天平仓的）
                if self.trades and self.trades[-1].exit_date == self.current_timestamp:
                    just_closed = True

                pos = self.current_positions.get(code)
                daily_info = {
                    "date": str(self.current_timestamp),
                    "capital": round(self.capital, 2),
                    "has_position": has_position,
                    "just_opened": just_opened,
                    "just_closed": just_closed,
                    "position_quantity": pos.quantity if pos else 0,
                    "position_cost": round(pos.avg_cost, 2) if pos else 0.0,
                    "position_current_price": round(pos.current_price, 2) if pos else 0.0,
                    "position_unrealized_pnl": round((pos.market_value - pos.cost_value), 2) if pos else 0.0,
                    "position_unrealized_pnl_pct": round(((pos.market_value - pos.cost_value) / pos.cost_value * 100), 2) if pos and pos.cost_value > 0 else 0.0,
                    "position_holding_days": pos.holding_days if pos else 0,
                    "today_open": round(tick.open, 2),
                    "today_close": round(tick.close, 2),
                    "today_high": round(tick.high, 2),
                    "today_low": round(tick.low, 2),
                    "today_pct_chg": round(tick.pct_chg, 2),
                    "today_volume": int(tick.volume) if tick.volume else 0,
                    "total_fee": round(sum(t.fee for t in self.trades), 2),
                    "total_trades": len(self.trades),
                    "total_value": round(self.capital + (pos.market_value - pos.cost_value if pos else 0), 2),
                # ── 空仓原因相关 ──
                    "today_score": today_score,
                    "today_rating": today_rating,
                    "signal_triggered": signal_triggered,
                    "signal_reason": signal_reason,
                    "filter_passed": filter_passed,
                    "filter_reason": filter_reason,
                    "open_skipped_reason": open_skipped_reason,
                }
                self.on_daily_log_callback(daily_info)

            # ── 更新资金曲线 ──
            total_value = self.capital
            if code in self.current_positions:
                pos = self.current_positions[code]
                total_value += pos.market_value - pos.cost_value
            self.equity_curve.append(total_value)

            if total_value > self.peak_capital:
                self.peak_capital = total_value

            # 进度回调
            if progress_callback:
                progress_callback(idx + 1, total_bars, f"{code}")

        # ── 回测结束，强制平仓所有持仓 ──
        for code in list(self.current_positions.keys()):
            pos = self.current_positions[code]
            tick = self._get_last_tick(code, df)
            if tick:
                self._close_position(code, tick, RiskResult(
                    triggered=True,
                    exit_reason=ExitReason.EXPIRED,
                    exit_price=tick.close,
                    exit_detail="策略结束强制平仓",
                ), pos, context)

        # ── 计算绩效 ──
        stats = compute_performance(self.trades, self.initial_capital)

        # ── 附加过滤对比数据 ──
        stats.exit_reason_stats["_filter_stats"] = self._get_filter_comparison()

        return stats

    # ═══════════════════════════════════════════
    #  开仓 / 平仓
    # ═══════════════════════════════════════════

    def _open_position(self, code: str, tick: TickSnapshot,
                       signal_results: List[SignalResult],
                       filter_result: FilterResult,
                       context: Dict[str, Any]) -> bool:
        """执行开仓，返回是否成功开仓"""
        # [建议] 计算开仓数量
        position_value = self.capital * self.fixed_position_ratio
        quantity = int(position_value / tick.close / 100) * 100  # 按手
        if quantity <= 0:
            return False

        cost = quantity * tick.close
        fee = cost * (self.commission_pct + self.slippage_pct)

        if cost + fee > self.capital:
            # 资金不足
            return False

        self.capital -= (cost + fee)

        # 合并信号结果
        primary_signal = signal_results[0]  # 主要信号

        # 创建持仓
        pos = Position(
            code=code,
            quantity=quantity,
            avg_cost=tick.close,
            current_price=tick.close,
            highest_price=tick.high,
            lowest_price=tick.low,
            entry_date=self.current_timestamp,
            holding_days=0,
        )
        self.current_positions[code] = pos

        # 创建交易记录（出场后在补齐）
        trade = TradeRecord(
            trade_id=str(uuid.uuid4())[:8],
            code=code,
            name=context.get("stock_name", ""),
            entry_date=self.current_timestamp,
            entry_price=tick.close,
            entry_quantity=quantity,
            entry_value=cost,
            signal_source=primary_signal.source,
            signal_detail=primary_signal.detail,
            passed_filter=filter_result.passed,
            filter_detail=filter_result.failed_detail if not filter_result.passed else "",
            fee=fee,
        )
        # 暂存到持仓对象中
        pos._trade_ref = trade
        return True

    def _close_position(self, code: str, tick: TickSnapshot,
                        risk_result: RiskResult,
                        pos: Position,
                        context: Dict[str, Any]) -> None:
        """执行平仓"""
        exit_price = risk_result.exit_price or tick.close
        quantity = pos.quantity

        # 考虑滑点 [建议]
        if self.slippage_pct > 0:
            if risk_result.exit_reason in [ExitReason.STOP_LOSS_FIXED,
                                            ExitReason.STOP_LOSS_ATR,
                                            ExitReason.STOP_LOSS_KEY_PRICE]:
                exit_price *= (1 - self.slippage_pct)  # 止损滑点更不利
            else:
                exit_price *= (1 - self.slippage_pct)

        exit_value = quantity * exit_price

        # 费用（卖出收佣金 + 印花税）
        fee = exit_value * (self.commission_pct + self.stamp_tax_pct)
        net_exit_value = exit_value - fee

        # 盈亏计算
        pnl = net_exit_value - pos.cost_value
        pnl_pct = pnl / pos.cost_value if pos.cost_value > 0 else 0

        # 补齐交易记录
        trade = getattr(pos, '_trade_ref', TradeRecord(trade_id=str(uuid.uuid4())[:8], code=code))
        trade.exit_date = self.current_timestamp
        trade.exit_price = exit_price
        trade.exit_quantity = quantity
        trade.exit_value = exit_value
        trade.exit_reason = risk_result.exit_reason or ExitReason.EXPIRED
        trade.exit_detail = risk_result.exit_detail
        trade.pnl = pnl
        trade.pnl_pct = pnl_pct
        trade.fee += fee
        trade.net_pnl = pnl - fee
        trade.holding_period = pos.holding_days
        trade.max_drawdown = (pos.lowest_price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
        trade.max_runup = (pos.highest_price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
        trade.stop_loss_triggered = risk_result.stop_loss_triggered
        trade.stop_profit_triggered = risk_result.stop_profit_triggered
        trade.black_swan_triggered = risk_result.black_swan_triggered

        # 更新资金
        self.capital += net_exit_value

        # 记录交易
        self.trades.append(trade)

        # 移除持仓
        del self.current_positions[code]

        # 回调
        if self.on_trade_callback:
            self.on_trade_callback(trade)

    # ═══════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════

    def _row_to_tick(self, row: pd.Series, code: str) -> TickSnapshot:
        """DataFrame 行转 TickSnapshot"""
        return TickSnapshot(
            code=code,
            date=row['date'].date() if hasattr(row['date'], 'date') else row['date'],
            open=float(row['open']),
            close=float(row['close']),
            high=float(row['high']),
            low=float(row['low']),
            volume=float(row.get('volume', 0)),
            amount=float(row.get('amount', 0)),
            pct_chg=float(row.get('pct_chg', 0)),
            atr=float(row['atr']) if pd.notna(row.get('atr')) else None,
            rsi=float(row['rsi']) if pd.notna(row.get('rsi')) else None,
            ma5=float(row['ma5']) if pd.notna(row.get('ma5')) else None,
            ma10=float(row['ma10']) if pd.notna(row.get('ma10')) else None,
            ma20=float(row['ma20']) if pd.notna(row.get('ma20')) else None,
            ma60=float(row['ma60']) if pd.notna(row.get('ma60')) else None,
            volatility=float(row['volatility']) if pd.notna(row.get('volatility')) else None,
            volume_ma5=float(row['volume_ma5']) if pd.notna(row.get('volume_ma5')) else None,
            volume_ma20=float(row['volume_ma20']) if pd.notna(row.get('volume_ma20')) else None,
        )

    def _evaluate_scorer(self, code: str, tick: TickSnapshot,
                     context: Dict[str, Any],
                     idx: int, df: pd.DataFrame) -> Dict[str, Any]:
        """
        在单根 K 线上调用评分器进行实时评分
        评分器使用截至当前 K 线的数据，避免未来函数。
        每根 K 线都会触发评分（财务类评分器按季度缓存，K 线类评分器每根 K 线重算）。

        :return: scorer_result 字典，结构如 {"renoyuan核心评分": {"score": 85, "rating": "A+", ...}}
        """
        from trader.scorer.market_scanner import SCORER_MAP

        # 获取该评分体系对应的评分器
        scorer_info = context.get("scorer_name", "")
        if not scorer_info:
            return {}

        scorer_cls = SCORER_MAP.get(scorer_info)
        if not scorer_cls:
            return {}

        try:
            # 评分器实例缓存
            inst_cache_key = f"_scorer_instance_{scorer_info}"
            scorer = getattr(self, inst_cache_key, None)
            if scorer is None:
                scorer = scorer_cls()
                setattr(self, inst_cache_key, scorer)

            # 当前回测日期
            as_of_date = tick.date if tick.date else self.current_timestamp

            # ── 判断评分器类型 ──
            # K 线类评分器（徐翔、方老哥、石头姐、葛兰等）：每根 K 线都需重新评分
            kline_scorers = ["徐翔趋势评分", "方老哥筹码趋势评分", "石头姐科技成长评分", "葛兰医药行业评分"]
            # 财务类评分器（巴菲特、格雷厄姆、xubin排雷、renoyuan核心）：按季度缓存即可
            financial_scorers = ["巴菲特价值评分", "格雷厄姆价值评分", "xubin财报排雷评分", "renoyuan核心评分"]

            result = None
            current_kline = df.iloc[:idx + 1] if idx > 0 else df

            if scorer_info in kline_scorers:
                # ── K 线类评分器：每根 K 线使用截至当前的数据评分 ──
                # 徐翔已支持 score_from_kline
                if hasattr(scorer, 'score_from_kline'):
                    result = scorer.score_from_kline(code, current_kline)
                else:
                    # 其他 K 线评分器，传入 as_of_date 和截至当前的 K 线
                    result = scorer.score(code, as_of_date=as_of_date, kline_df=current_kline)
            elif scorer_info in financial_scorers:
                # ── 财务类评分器：按季度缓存，同一季度内复用评分 ──
                quarter_key = f"{as_of_date.year}Q{(as_of_date.month - 1) // 3 + 1}"
                cache_key = f"_cached_scorer_{scorer_info}_{code}_{quarter_key}"
                cached = getattr(self, cache_key, None)
                if cached is not None:
                    return cached

                # 传入回测日期，使评分器只使用该日期之前的财报数据
                result = scorer.score(code, years=5, as_of_date=as_of_date)

                # 缓存季度评分
                if result:
                    setattr(self, cache_key, {scorer_info: {**result}})
                    return {scorer_info: {**result}}
            else:
                # ── 未知类型：回退到原始调用（不缓存、不传日期） ──
                result = scorer.score(code)

            if result is None:
                return {}

            # 统一评分结果格式
            if isinstance(result, dict):
                score_val = result.get("score", result.get("total_score", 0))
                rating = result.get("rating", result.get("评级", ""))
                indicators = result.get("indicators", result.get("dimensions", result.get("details", {})))
            else:
                score_val = result if isinstance(result, (int, float)) else 0
                rating = ""
                indicators = {}

            if score_val is None:
                score_val = 0

            return {
                scorer_info: {
                    "score": score_val,
                    "rating": rating,
                    "indicators": indicators,
                }
            }

        except Exception as e:
            # 评分失败时静默处理，不中断回测
            return {}

    def _build_context(self, code: str, df: pd.DataFrame, idx: int) -> Dict[str, Any]:
        """构建上下文信息，包含历史数据、评分结果等"""
        context = {
            "stock_code": code,
            "stock_name": "",
            "scorer_name": "",
            "market_pct_chg": 0.0,
            "scorer_result": {},
            "historical_high": float(df['high'].iloc[:idx + 1].max()) if idx >= 0 else 0,
            "historical_low": float(df['low'].iloc[:idx + 1].min()) if idx >= 0 else 0,
            f"volume_ma20": float(df['volume_ma20'].iloc[idx]) if pd.notna(df['volume_ma20'].iloc[idx]) else None,
        }

        # 尝试获取股票名称
        try:
            from trader.db.orm import SessionLocal, StockBasic
            with SessionLocal() as session:
                row = session.query(StockBasic).filter(StockBasic.code == code).first()
                if row:
                    context["stock_name"] = row.name
        except Exception:
            pass

        return context

    def _get_last_tick(self, code: str, df: pd.DataFrame) -> Optional[TickSnapshot]:
        """获取最后一行作为 tick"""
        if df.empty:
            return None
        last_row = df.iloc[-1]
        return self._row_to_tick(last_row, code)

    def _get_filter_comparison(self) -> Dict[str, Any]:
        """
        获取过滤对比数据
        [强烈建议] 回测对比：不开过滤的原始信号盈亏曲线 / 开启过滤后曲线
        """
        raw_count = len(self.raw_signal_log)
        filtered_count = len([s for s in self.filtered_signal_log if s.get("passed_filter")])

        return {
            "原始信号数量": raw_count,
            "过滤后信号数量": filtered_count,
            "过滤比例": f"{(raw_count - filtered_count) / max(raw_count, 1) * 100:.1f}%",
        }

    # ═══════════════════════════════════════════
    #  报告输出
    # ═══════════════════════════════════════════

    def get_trades_df(self) -> pd.DataFrame:
        """获取交易记录的 DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        records = [t.summary() for t in self.trades]
        return pd.DataFrame(records)

    def get_signal_comparison(self) -> pd.DataFrame:
        """
        信号过滤对比表
        [强烈建议] 对比不开过滤 vs 开启过滤的信号数据
        """
        raw_df = pd.DataFrame(self.raw_signal_log)
        filtered_df = pd.DataFrame(self.filtered_signal_log)

        # 对比分析
        comparison = {
            "指标": ["原始信号数", "过滤后信号数", "被过滤数", "过滤比例"],
            "数值": [
                len(raw_df),
                len(filtered_df[filtered_df["passed_filter"] == True]) if not filtered_df.empty else 0,
                len(filtered_df[filtered_df["passed_filter"] == False]) if not filtered_df.empty else 0,
                f"{(len(raw_df) - len(filtered_df[filtered_df['passed_filter'] == True])) / max(len(raw_df), 1) * 100:.1f}%"
                if not filtered_df.empty else "0%",
            ]
        }
        return pd.DataFrame(comparison)

    def print_summary(self) -> str:
        """打印回测摘要"""
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("📈  回测摘要")
        lines.append("=" * 60)
        lines.append(f"初始资金: {self.initial_capital:,.2f}")
        lines.append(f"最终资金: {self.capital:,.2f}")
        lines.append(f"总盈亏: {self.capital - self.initial_capital:+,.2f}")
        lines.append(f"总交易: {len(self.trades)} 笔")
        lines.append(f"收益率: {(self.capital - self.initial_capital) / self.initial_capital * 100:+.2f}%")
        lines.append("=" * 60)
        return "\n".join(lines)


# ═══════════════════════════════════════════
#  便捷函数
# ═══════════════════════════════════════════

def quick_backtest(code: str,
                   start_date: str = "20230101",
                   end_date: str = "20241231",
                   scorer_name: str = "renoyuan核心评分",
                   min_score: float = 80.0,
                   initial_capital: float = 100000.0,
                   ) -> PerformanceStats:
    """
    快速执行一次完整回测（从数据库取数据 -> 跑回测 -> 出报告）

    :param code: 股票代码
    :param start_date: 起始日期
    :param end_date: 结束日期
    :param scorer_name: 评分体系名称（可选，None 则只使用技术指标信号）
    :param min_score: 评分触发阈值
    :param initial_capital: 初始资金
    :return: PerformanceStats
    """
    from trader.scorer.market_scanner import SCORER_MAP

    engine = BacktestEngine(initial_capital=initial_capital)

    # 加载 K 线数据
    print(f"📥 加载 {code} K线数据 {start_date}~{end_date}...")
    success = engine.load_kline_from_db(code, start_date, end_date)
    if not success:
        print(f"❌ 加载失败: {code}")
        return PerformanceStats()

    # 运行回测
    print(f"🚀 开始回测 {code}...")
    stats = engine.run(code, scorer_name=scorer_name, min_score=min_score)

    # 打印报告
    print(stats.print_report())

    return stats
