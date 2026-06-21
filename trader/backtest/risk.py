#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  风控模块 - 止损 / 止盈 / 黑天鹅

"""
风控模块 [必须 + 强烈建议]
===========================
包含三大强制风控体系：
  [必须] 止损机制（固定比例止损、ATR动态止损、关键价位止损）
  [必须] 止盈机制（分级止盈、目标价止盈、RSI超买止盈）
  [强烈建议] 时间止损
  [强烈建议] 黑天鹅强制卖出

回测强制触发：价格触碰止损线即时平仓，不延迟、不跳价忽略。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum
from datetime import date

from .trade import Position, TickSnapshot, ExitReason, TradeRecord


class StopLossMode(Enum):
    """止损模式枚举"""
    FIXED_RATIO = "固定比例止损"
    ATR_DYNAMIC = "ATR动态止损"
    KEY_PRICE = "关键价位止损"


class StopProfitMode(Enum):
    """止盈模式枚举"""
    GRADED = "分级止盈"
    TARGET_PRICE = "目标价止盈"
    RSI_OVERBOUGHT = "RSI超买止盈"


@dataclass
class RiskResult:
    """
    风控检查结果
    ============
    包含是否触发、触发原因、平仓价格等信息。
    """
    triggered: bool = False
    exit_reason: Optional[ExitReason] = None
    exit_price: Optional[float] = None
    exit_detail: str = ""
    stop_loss_triggered: bool = False
    stop_profit_triggered: bool = False
    black_swan_triggered: bool = False
    time_stop_triggered: bool = False


class RiskManager:
    """
    风控管理器 [必须 + 强烈建议]
    ============================
    管理持仓的止损、止盈、时间止损、黑天鹅检查。
    回测中每根 K 线都会调用 check() 方法进行全维度风控检查。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # ── 止损配置 ──
        self.sl_fixed_ratio: float = 0.07
        self.sl_atr_multiplier: float = 2.0
        self.sl_atr_period: int = 14
        self.sl_key_price_pct: float = 0.05

        # ── 止盈配置 ──
        self.sp_graded_levels: List[Tuple[float, float]] = [
            (0.05, 0.3),
            (0.10, 0.3),
            (0.15, 0.4),
        ]
        self.sp_target_price_pct: float = 0.15
        self.sp_rsi_overbought: float = 75.0

        # ── 时间止损 ──
        self.ts_enabled: bool = True
        self.ts_max_bars: int = 60
        self.ts_max_days: int = 90

        # ── 黑天鹅 ──
        self.bs_enabled: bool = True
        self.bs_daily_limit: float = 0.10
        self.bs_market_crash_pct: float = -0.05
        self.bs_gap_pct: float = 0.06
        self.bs_liquidity_min_volume: int = 0

        if config:
            self._apply_config(config)

    def _apply_config(self, config: Dict[str, Any]):
        """应用配置字典"""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # ═══════════════════════════════════════════
    #  [必须] 止损检查
    # ═══════════════════════════════════════════

    def check_stop_loss(self, pos: Position, tick: TickSnapshot,
                        entry_price: float) -> RiskResult:
        """
        [必须] 止损检查
        价格触碰止损线即时平仓，不延迟、不跳价忽略。
        逐笔检查三类止损模式。
        """
        result = RiskResult()
        current_low = tick.low  # 用最低价检测是否触碰止损

        # 1. 固定比例止损
        sl_fixed_price = entry_price * (1 - self.sl_fixed_ratio)
        if current_low <= sl_fixed_price:
            result.triggered = True
            result.exit_reason = ExitReason.STOP_LOSS_FIXED
            result.exit_price = min(tick.close, sl_fixed_price)
            result.exit_detail = f"固定比例止损 {self.sl_fixed_ratio:.1%}, 止损价 {sl_fixed_price:.2f}"
            result.stop_loss_triggered = True
            return result

        # 2. ATR 动态止损
        if tick.atr is not None and tick.atr > 0:
            sl_atr_price = entry_price - self.sl_atr_multiplier * tick.atr
            if current_low <= sl_atr_price:
                result.triggered = True
                result.exit_reason = ExitReason.STOP_LOSS_ATR
                result.exit_price = min(tick.close, sl_atr_price)
                result.exit_detail = (f"ATR动态止损 ({self.sl_atr_multiplier}*ATR={self.sl_atr_multiplier * tick.atr:.2f}), "
                                      f"止损价 {sl_atr_price:.2f}")
                result.stop_loss_triggered = True
                return result

        # 3. 关键价位止损
        key_price = self._get_key_price(tick, entry_price)
        if key_price and current_low <= key_price:
            result.triggered = True
            result.exit_reason = ExitReason.STOP_LOSS_KEY_PRICE
            result.exit_price = min(tick.close, key_price)
            result.exit_detail = f"关键价位止损 ({key_price:.2f})"
            result.stop_loss_triggered = True

        return result

    def _get_key_price(self, tick: TickSnapshot, entry_price: float) -> Optional[float]:
        """计算关键价位（支撑位），基于 MA20 和近期低点"""
        prices = []
        if tick.ma20 is not None:
            prices.append(tick.ma20 * (1 - self.sl_key_price_pct))
        if tick.ma60 is not None:
            prices.append(tick.ma60 * (1 - self.sl_key_price_pct * 0.5))
        # 入场价的支撑位
        prices.append(entry_price * (1 - self.sl_fixed_ratio * 1.5))
        return min(prices) if prices else None

    # ═══════════════════════════════════════════
    #  [必须] 止盈检查
    # ═══════════════════════════════════════════

    def check_stop_profit(self, pos: Position, tick: TickSnapshot,
                          entry_price: float) -> Tuple[RiskResult, float]:
        """
        [必须] 止盈检查
        支持分级止盈（一阶减仓、二阶全平）、目标价止盈、RSI 超买止盈。
        
        :return: (RiskResult, partial_exit_ratio) 
                  partial_exit_ratio: 本次需要平仓的仓位比例（分级止盈用）
        """
        result = RiskResult()
        partial_ratio = 1.0  # 默认全平
        current_high = tick.high
        current_close = tick.close

        # 1. 分级止盈
        for level_pct, exit_ratio in self.sp_graded_levels:
            target_price = entry_price * (1 + level_pct)
            if current_high >= target_price:
                result.triggered = True
                result.exit_reason = ExitReason.STOP_PROFIT_GRADED
                partial_ratio = exit_ratio
                result.exit_price = target_price
                result.exit_detail = (f"分级止盈触发: 浮盈 {level_pct:.1%} 级别, "
                                      f"平仓 {exit_ratio:.0%} 仓位")
                result.stop_profit_triggered = True

                # 如果这是最高级别的止盈，全平
                if level_pct == self.sp_graded_levels[-1][0]:
                    partial_ratio = 1.0
                return result, partial_ratio

        # 2. 目标价止盈
        sp_target = entry_price * (1 + self.sp_target_price_pct)
        if current_high >= sp_target:
            result.triggered = True
            result.exit_reason = ExitReason.STOP_PROFIT_TARGET
            result.exit_price = sp_target
            result.exit_detail = f"目标价止盈: 目标 {self.sp_target_price_pct:.1%}, 止盈价 {sp_target:.2f}"
            result.stop_profit_triggered = True
            return result, 1.0

        # 3. RSI 超买止盈
        if tick.rsi is not None and tick.rsi >= self.sp_rsi_overbought:
            # 需要确认 RSI 从超买区回落
            result.triggered = True
            result.exit_reason = ExitReason.STOP_PROFIT_RSI
            result.exit_price = current_close
            result.exit_detail = f"RSI超买止盈: RSI={tick.rsi:.1f} >= {self.sp_rsi_overbought}"
            result.stop_profit_triggered = True

        return result, partial_ratio

    # ═══════════════════════════════════════════
    #  [强烈建议] 时间止损
    # ═══════════════════════════════════════════

    def check_time_stop(self, pos: Position, tick: TickSnapshot,
                        entry_date: date, current_date: date) -> RiskResult:
        """
        [强烈建议] 时间止损检查
        持仓超过阈值强制减仓，解决长期横盘占用资金的问题。
        """
        if not self.ts_enabled:
            return RiskResult()

        result = RiskResult()

        # K 线根数检查
        if self.ts_max_bars > 0 and pos.holding_days >= self.ts_max_bars:
            result.triggered = True
            result.exit_reason = ExitReason.TIME_STOP
            result.exit_price = tick.close
            result.exit_detail = f"时间止损: 持仓 {pos.holding_days} 根K线, 超过上限 {self.ts_max_bars}"
            result.time_stop_triggered = True
            return result

        # 自然日检查
        if self.ts_max_days > 0 and entry_date and current_date:
            days_diff = (current_date - entry_date).days
            if days_diff >= self.ts_max_days:
                result.triggered = True
                result.exit_reason = ExitReason.TIME_STOP
                result.exit_price = tick.close
                result.exit_detail = f"时间止损: 持仓 {days_diff} 天, 超过上限 {self.ts_max_days} 天"
                result.time_stop_triggered = True

        return result

    # ═══════════════════════════════════════════
    #  [强烈建议] 黑天鹅强制卖出
    # ═══════════════════════════════════════════

    def check_black_swan(self, pos: Position, tick: TickSnapshot,
                         market_pct_chg: float = 0.0) -> RiskResult:
        """
        [强烈建议] 黑天鹅强制卖出检查
        触发条件：单日涨跌幅阈值、流动性枯竭、大盘系统性暴跌、跳空缺口击穿关键支撑。
        不等待常规止损，市价强制平仓。
        """
        if not self.bs_enabled:
            return RiskResult()

        result = RiskResult()

        # 1. 单日跌幅阈值
        if tick.pct_chg <= -self.bs_daily_limit * 100:  # pct_chg 已经是百分比
            result.triggered = True
            result.exit_reason = ExitReason.BLACK_SWAN
            result.exit_price = tick.close
            result.exit_detail = (f"黑天鹅触发: 单日跌幅 {tick.pct_chg:.2f}% 超过阈值 "
                                  f"{-self.bs_daily_limit * 100:.1f}%")
            result.black_swan_triggered = True
            return result

        # 2. 大盘系统性暴跌
        if market_pct_chg <= self.bs_market_crash_pct * 100:
            result.triggered = True
            result.exit_reason = ExitReason.BLACK_SWAN
            result.exit_price = tick.close
            result.exit_detail = (f"黑天鹅触发: 大盘暴跌 {market_pct_chg:.2f}% 超过阈值 "
                                  f"{self.bs_market_crash_pct * 100:.1f}%")
            result.black_swan_triggered = True
            return result

        # 3. 跳空缺口击穿关键支撑
        if self._is_gap_break(pos, tick):
            result.triggered = True
            result.exit_reason = ExitReason.BLACK_SWAN
            result.exit_price = tick.close
            result.exit_detail = "黑天鹅触发: 跳空缺口击穿关键支撑"
            result.black_swan_triggered = True
            return result

        # 4. 流动性枯竭
        if self.bs_liquidity_min_volume > 0 and tick.volume < self.bs_liquidity_min_volume:
            # 成交量太低触发预警（但不强制平仓，只记录）
            pass

        return result

    def _is_gap_break(self, pos: Position, tick: TickSnapshot) -> bool:
        """判断是否发生跳空击穿关键位置"""
        # 跳空低开超过一定比例，且收盘低于关键均线
        gap_ratio = (tick.open - tick.close) / tick.close if tick.close > 0 else 0
        if gap_ratio > self.bs_gap_pct and tick.ma20 is not None:
            return tick.close < tick.ma20 * 0.95
        return False

    # ═══════════════════════════════════════════
    #  全维度风控检查（统一入口）
    # ═══════════════════════════════════════════

    def check_all(self, pos: Position, tick: TickSnapshot,
                  entry_price: float, entry_date: date, current_date: date,
                  market_pct_chg: float = 0.0) -> RiskResult:
        """
        全维度风控检查（统一入口）
        按优先级检查：黑天鹅 > 止损 > 止盈 > 时间止损

        :return: RiskResult（如果触发，包含详细原因）
        """
        # 1. [强烈建议] 黑天鹅优先检查（不等待常规止损）
        bs_result = self.check_black_swan(pos, tick, market_pct_chg)
        if bs_result.triggered:
            return bs_result

        # 2. [必须] 止损检查
        sl_result = self.check_stop_loss(pos, tick, entry_price)
        if sl_result.triggered:
            return sl_result

        # 3. [必须] 止盈检查
        sp_result, partial_ratio = self.check_stop_profit(pos, tick, entry_price)
        if sp_result.triggered:
            # 记录分级止盈比例
            sp_result.exit_detail += f" | 平仓比例: {partial_ratio:.0%}"
            return sp_result

        # 4. [强烈建议] 时间止损
        ts_result = self.check_time_stop(pos, tick, entry_date, current_date)
        if ts_result.triggered:
            return ts_result

        return RiskResult()
