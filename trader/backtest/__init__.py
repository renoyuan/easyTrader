#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  回测模块 - 量化策略历史仿真校验

"""
backtest
========
量化策略历史仿真校验模块，用于验证入场、出场、风控整套逻辑的胜率、
盈亏比、最大回撤，避免实盘主观踩坑。

功能分级（与 scorer 模块配合使用）:
  [必须] 入场信号归因、止损机制、止盈机制
  [强烈建议] 信号过滤、时间止损、黑天鹅强制卖出
  [建议] 滑点手续费、仓位管理、多品种、过拟合检测、绩效看板、参数寻优
"""

from .engine import BacktestEngine
from .signal import SignalRegistry, BaseSignal
from .risk import RiskManager, StopLossMode, StopProfitMode, RiskResult
from .filter import SignalFilter, FilterResult
from .stats import PerformanceStats
from .trade import TradeRecord, TradeSide

__all__ = [
    "BacktestEngine",
    "SignalRegistry", "BaseSignal",
    "RiskManager", "StopLossMode", "StopProfitMode", "RiskResult",
    "SignalFilter", "FilterResult",
    "PerformanceStats",
    "TradeRecord", "TradeSide",
]
