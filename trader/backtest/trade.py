#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  交易记录与持仓数据结构

"""
交易记录与持仓数据结构
=======================
定义 TradeRecord（单笔交易记录）、Position（持仓快照）等核心数据结构。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime, date


class TradeSide(Enum):
    """交易方向"""
    LONG = "做多"
    SHORT = "做空"  # 预留，A 股暂不支持


class ExitReason(Enum):
    """离场原因枚举"""
    # [必须] 止损 / 止盈
    STOP_LOSS_FIXED = "固定比例止损"
    STOP_LOSS_ATR = "ATR动态止损"
    STOP_LOSS_KEY_PRICE = "关键价位止损"
    STOP_PROFIT_GRADED = "分级止盈"
    STOP_PROFIT_TARGET = "目标价止盈"
    STOP_PROFIT_RSI = "RSI超买止盈"

    # [强烈建议] 逻辑出场 / 时间止损 / 黑天鹅
    SIGNAL_INVALIDATED = "入场逻辑失效"
    TREND_REVERSAL = "趋势反转"
    DIVERGENCE = "指标背离"
    SUPPORT_BROKEN = "支撑跌破"
    TIME_STOP = "时间止损"
    BLACK_SWAN = "黑天鹅强制平仓"

    # 其他
    MANUAL = "手动平仓"
    EXPIRED = "策略结束"


class SignalSource(Enum):
    """入场信号来源（用于归因）"""
    SCORER = "评分触发"
    TECHNICAL = "技术指标"
    FUNDAMENTAL = "基本面因子"
    VOLUME_PRICE = "量价条件"
    CANDLE_PATTERN = "K线形态"
    CUSTOM = "自定义信号"


@dataclass
class TradeRecord:
    """
    单笔交易记录（完整归因）
    ========================
    记录一笔交易从入场到出场的全链路数据。
    """
    # ── 基本信息 ──
    trade_id: str                    # 唯一交易ID
    code: str                        # 股票代码
    name: str = ""                   # 股票名称
    side: TradeSide = TradeSide.LONG

    # ── 入场信息 ──
    entry_date: Optional[date] = None
    entry_price: float = 0.0
    entry_quantity: int = 0
    entry_value: float = 0.0         # 开仓金额

    # ── 入场信号归因 [必须] ──
    signal_source: SignalSource = SignalSource.CUSTOM
    signal_detail: Dict[str, Any] = field(default_factory=dict)
    # signal_detail 示例：
    # {
    #   "scorer": "renoyuan核心评分",
    #   "score": 85,
    #   "trigger_indicators": {"股息率": 4.5, "ROE": 0.18},
    #   "kline_pattern": "早晨之星",
    #   "volume_condition": "放量突破20日均线",
    # }

    # ── 出场信息 ──
    exit_date: Optional[date] = None
    exit_price: float = 0.0
    exit_quantity: int = 0
    exit_value: float = 0.0          # 平仓金额

    # ── 出场原因归因 ──
    exit_reason: ExitReason = ExitReason.EXPIRED
    exit_detail: str = ""            # 补充说明

    # ── 盈亏数据 ──
    pnl: float = 0.0                 # 盈亏金额（扣除费用前）
    pnl_pct: float = 0.0             # 盈亏百分比
    fee: float = 0.0                 # 手续费 + 滑点成本
    net_pnl: float = 0.0             # 净盈亏（扣除费用后）

    # ── 持仓信息 ──
    holding_period: int = 0          # 持仓天数
    max_drawdown: float = 0.0        # 持仓期间最大回撤%
    max_runup: float = 0.0           # 持仓期间最大浮盈%

    # ── 过滤信息 [强烈建议] ──
    passed_filter: bool = True       # 是否通过了信号过滤
    filter_detail: str = ""          # 过滤信息

    # ── 风控信息 ──
    stop_loss_triggered: bool = False
    stop_profit_triggered: bool = False
    black_swan_triggered: bool = False

    def __post_init__(self):
        if not self.trade_id:
            import uuid
            self.trade_id = str(uuid.uuid4())[:8]

    @property
    def is_win(self) -> bool:
        """是否盈利"""
        return self.net_pnl > 0

    @property
    def is_loss(self) -> bool:
        """是否亏损"""
        return self.net_pnl < 0

    @property
    def is_flat(self) -> bool:
        """是否保本"""
        return abs(self.net_pnl) < 1e-6

    @property
    def is_stopped(self) -> bool:
        """是否被止损/止盈平仓"""
        return self.stop_loss_triggered or self.stop_profit_triggered

    def summary(self) -> Dict[str, Any]:
        """返回交易摘要"""
        return {
            "trade_id": self.trade_id,
            "code": self.code,
            "name": self.name,
            "entry_date": str(self.entry_date) if self.entry_date else "",
            "exit_date": str(self.exit_date) if self.exit_date else "",
            "holding_period": self.holding_period,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl_pct": round(self.pnl_pct, 4),
            "pnl": round(self.pnl, 2),
            "net_pnl": round(self.net_pnl, 2),
            "exit_reason": self.exit_reason.value,
            "signal_source": self.signal_source.value,
            "is_win": self.is_win,
        }


@dataclass
class Position:
    """
    持仓快照
    ========
    回测过程中当前持仓状态的实时快照。
    """
    code: str
    quantity: int = 0
    avg_cost: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    entry_date: Optional[date] = None
    holding_days: int = 0

    # 风控标记
    stop_loss_price: Optional[float] = None     # 当前止损线
    stop_profit_price: Optional[float] = None   # 当前止盈线
    partial_exit_ratio: float = 1.0             # 剩余仓位比例（分级止盈用）

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_value(self) -> float:
        return self.quantity * self.avg_cost


@dataclass
class TickSnapshot:
    """
    回测单根K线快照
    ===============
    回测引擎在遍历每根K线时产生的环境快照，供信号判断和风控使用。
    """
    code: str
    date: date
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    pct_chg: float

    # 技术指标（由引擎计算后填充）
    atr: Optional[float] = None
    rsi: Optional[float] = None
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    volatility: Optional[float] = None
    volume_ma5: Optional[float] = None
    volume_ma20: Optional[float] = None
