#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  入场信号注册与归因模块

"""
入场信号归因模块 [必须]
=======================
记录每一笔开仓触发的指标、K 线形态、基本面因子、量价条件；
回测报告单条持仓附带触发原文，支持筛选某一类入场信号的收益表现；
统计各类入场信号胜率、盈亏比，定位优质开仓逻辑。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from datetime import date

from .trade import SignalSource, TickSnapshot, TradeRecord


class SignalStrength(Enum):
    """信号强度分级"""
    STRONG = "强信号"
    MEDIUM = "中等信号"
    WEAK = "弱信号"


@dataclass
class SignalResult:
    """
    信号判断结果
    ============
    """
    triggered: bool                    # 是否触发
    source: SignalSource = SignalSource.CUSTOM
    strength: SignalStrength = SignalStrength.MEDIUM
    score: float = 0.0                 # 信号置信度 0-100
    detail: Dict[str, Any] = field(default_factory=dict)
    # detail 示例:
    # {
    #   "scorer_name": "renoyuan核心评分",
    #   "scorer_score": 85,
    #   "trigger_indicators": {"股息率": 4.5, "ROE": 0.18},
    #   "kline_pattern": "早晨之星",
    #   "volume_condition": "放量突破20日均线, 量比2.3",
    #   "price_action": "收盘站上MA5, MA5金叉MA10",
    # }

    @property
    def summary(self) -> str:
        """生成信号触发摘要（供回测报告展示）"""
        if not self.triggered:
            return "未触发"
        parts = [f"[{self.source.value}] 强度:{self.strength.value} 置信度:{self.score:.0f}"]
        for k, v in self.detail.items():
            if v is not None and v != "":
                parts.append(f"{k}:{v}")
        return " | ".join(parts)


class BaseSignal(ABC):
    """
    入场信号基类
    ============
    所有入场信号策略必须继承此类。
    可与 scorer 模块配合使用。
    """

    def __init__(self, name: str, source: SignalSource = SignalSource.CUSTOM):
        self.name = name
        self.source = source

    @abstractmethod
    def evaluate(self, tick: TickSnapshot, context: Dict[str, Any]) -> SignalResult:
        """
        在单根K线上评估是否触发入场信号
        
        :param tick: 当前K线快照
        :param context: 上下文信息，包含历史K线、财务数据、评分结果等
        :return: SignalResult
        """
        ...

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class SignalRegistry:
    """
    信号注册中心 [必须]
    ===================
    管理所有入场信号策略，提供注册、取消、查询、评估功能。
    支持对每一类信号的胜率/盈亏比统计。
    """

    def __init__(self):
        self._signals: Dict[str, BaseSignal] = {}

    def register(self, signal: BaseSignal) -> None:
        """注册一个信号策略"""
        self._signals[signal.name] = signal

    def unregister(self, name: str) -> None:
        """取消注册"""
        self._signals.pop(name, None)

    def get_signal(self, name: str) -> Optional[BaseSignal]:
        return self._signals.get(name)

    @property
    def all_signals(self) -> List[BaseSignal]:
        return list(self._signals.values())

    @property
    def signal_names(self) -> List[str]:
        return list(self._signals.keys())

    def evaluate_all(self, tick: TickSnapshot, context: Dict[str, Any]) -> List[SignalResult]:
        """
        评估所有注册信号，返回触发结果列表
        """
        results = []
        for signal in self._signals.values():
            try:
                result = signal.evaluate(tick, context)
                results.append(result)
            except Exception as e:
                results.append(SignalResult(
                    triggered=False,
                    source=signal.source,
                    detail={"error": str(e)}
                ))
        return results

    def get_triggered(self, tick: TickSnapshot, context: Dict[str, Any]) -> List[SignalResult]:
        """仅返回触发的信号"""
        return [r for r in self.evaluate_all(tick, context) if r.triggered]

    # ── 信号归因统计 ──

    def analyze_signal_performance(self, trades: List[TradeRecord]) -> Dict[str, Any]:
        """
        对已完成交易按信号来源进行归因分析
        :return: {
            "信号类型A": {
                "total": N,
                "wins": N,
                "losses": N,
                "win_rate": %,
                "avg_pnl": 平均盈亏,
                "avg_pnl_pct": 平均盈亏%,
                "profit_factor": 盈亏比,
                "trades": [TradeRecord, ...]
            },
            ...
        }
        """
        from collections import defaultdict

        groups = defaultdict(list)
        for t in trades:
            key = f"{t.signal_source.value}"
            if t.signal_detail.get("scorer"):
                key = f"{t.signal_source.value}({t.signal_detail['scorer']})"
            groups[key].append(t)

        result = {}
        for signal_type, trade_list in sorted(groups.items()):
            wins = [t for t in trade_list if t.is_win]
            losses = [t for t in trade_list if t.is_loss]

            total_pnl = sum(t.pnl for t in trade_list)
            total_net_pnl = sum(t.net_pnl for t in trade_list)
            win_pnl = sum(t.pnl for t in wins)
            loss_pnl = abs(sum(t.pnl for t in losses)) if losses else 1

            result[signal_type] = {
                "total": len(trade_list),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(trade_list) * 100, 2) if trade_list else 0,
                "avg_pnl": round(total_pnl / len(trade_list), 2) if trade_list else 0,
                "avg_pnl_pct": round(sum(t.pnl_pct for t in trade_list) / len(trade_list) * 100, 4) if trade_list else 0,
                "profit_factor": round(win_pnl / loss_pnl, 2) if loss_pnl > 0 else float('inf'),
                "total_pnl": round(total_pnl, 2),
                "total_net_pnl": round(total_net_pnl, 2),
            }

        return result


# ── 内置信号策略示例 ──

class ScorerSignal(BaseSignal):
    """
    评分触发信号 [必须]
    ====================
    当 scorer 评分超过阈值时触发入场信号。
    这是回测模块与 scorer 模块的桥梁。
    """

    def __init__(self, scorer_name: str, min_score: float = 70.0):
        super().__init__(
            name=f"评分触发({scorer_name}>{min_score})",
            source=SignalSource.SCORER
        )
        self.scorer_name = scorer_name
        self.min_score = min_score

    def evaluate(self, tick: TickSnapshot, context: Dict[str, Any]) -> SignalResult:
        scorer_result = context.get("scorer_result", {})
        score_obj = scorer_result.get(self.scorer_name, {})

        score = score_obj.get("score", 0)
        if score is None or score < self.min_score:
            return SignalResult(triggered=False)

        indicators = score_obj.get("indicators", {})
        rating = score_obj.get("rating", "")

        return SignalResult(
            triggered=True,
            source=self.source,
            strength=SignalStrength.STRONG if score >= 85 else SignalStrength.MEDIUM,
            score=score,
            detail={
                "scorer_name": self.scorer_name,
                "scorer_score": score,
                "rating": rating,
                "trigger_indicators": {
                    k: v for k, v in indicators.items()
                    if v is not None and not (isinstance(v, float) and v != v)
                },
            }
        )


class TechnicalSignal(BaseSignal):
    """
    技术指标信号
    ============
    基于 K 线技术指标触发入场。
    """

    def __init__(self, name: str, condition_fn: Callable[[TickSnapshot, Dict[str, Any]], bool],
                 detail_fn: Optional[Callable[[TickSnapshot, Dict[str, Any]], Dict]] = None):
        super().__init__(name=name, source=SignalSource.TECHNICAL)
        self.condition_fn = condition_fn
        self.detail_fn = detail_fn

    def evaluate(self, tick: TickSnapshot, context: Dict[str, Any]) -> SignalResult:
        triggered = self.condition_fn(tick, context)

        if not triggered:
            return SignalResult(triggered=False)

        detail = self.detail_fn(tick, context) if self.detail_fn else {}

        return SignalResult(
            triggered=True,
            source=self.source,
            strength=SignalStrength.MEDIUM,
            score=60,
            detail=detail,
        )
