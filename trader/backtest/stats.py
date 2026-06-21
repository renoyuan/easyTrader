#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  绩效统计与报表模块

"""
绩效统计模块 [建议]
====================
包含：夏普比率、最大回撤、年化收益、盈亏比、连续亏损次数等绩效指标。
以及完整的回测报告生成功能。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math
from collections import defaultdict

from .trade import TradeRecord, ExitReason, SignalSource


@dataclass
class PerformanceStats:
    """
    绩效统计
    ========
    回测完成后生成的全维度绩效报告。
    """

    # ── 基本统计 ──
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    flat_count: int = 0
    win_rate: float = 0.0

    # ── 收益指标 ──
    total_pnl: float = 0.0        # 总盈亏
    total_net_pnl: float = 0.0    # 净盈亏（扣费后）
    total_fee: float = 0.0        # 总费用
    avg_pnl: float = 0.0          # 平均每笔盈亏
    avg_pnl_pct: float = 0.0      # 平均每笔盈亏%
    med_pnl_pct: float = 0.0      # 中位数盈亏%

    # ── 盈亏比 ──
    avg_win_pnl: float = 0.0      # 平均盈利
    avg_loss_pnl: float = 0.0     # 平均亏损
    profit_factor: float = 0.0    # 盈亏比
    expectancy: float = 0.0       # 期望值

    # ── 风控指标 ──
    max_drawdown: float = 0.0     # 最大回撤%
    max_drawdown_value: float = 0.0  # 最大回撤金额
    max_consecutive_losses: int = 0  # 最大连续亏损次数
    max_consecutive_wins: int = 0    # 最大连续盈利次数

    # ── 年化指标 ──
    annual_return: float = 0.0    # 年化收益率
    sharpe_ratio: float = 0.0     # 夏普比率
    sortino_ratio: float = 0.0    # 索提诺比率
    calmar_ratio: float = 0.0     # 卡玛比率

    # ── 持仓统计 ──
    avg_holding_period: float = 0.0  # 平均持仓天数
    max_holding_period: int = 0
    min_holding_period: int = 0

    # ── 归因分析 ──
    exit_reason_stats: Dict[str, Any] = field(default_factory=dict)
    signal_source_stats: Dict[str, Any] = field(default_factory=dict)

    # ── 资金曲线 ──
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转字典用于展示"""
        return {
            "基本统计": {
                "总交易次数": self.total_trades,
                "盈利次数": self.win_count,
                "亏损次数": self.loss_count,
                "胜率": f"{self.win_rate:.2f}%",
            },
            "收益指标": {
                "总盈亏": f"{self.total_pnl:.2f}",
                "净盈亏(扣费后)": f"{self.total_net_pnl:.2f}",
                "总费用": f"{self.total_fee:.2f}",
                "平均每笔盈亏": f"{self.avg_pnl:.2f}",
                "平均每笔盈亏%": f"{self.avg_pnl_pct:.2f}%",
                "中位数盈亏%": f"{self.med_pnl_pct:.2f}%",
            },
            "盈亏比": {
                "平均盈利": f"{self.avg_win_pnl:.2f}",
                "平均亏损": f"{self.avg_loss_pnl:.2f}",
                "盈亏比": f"{self.profit_factor:.2f}",
                "期望值": f"{self.expectancy:.2f}",
            },
            "风控指标": {
                "最大回撤%": f"{self.max_drawdown:.2f}%",
                "最大回撤金额": f"{self.max_drawdown_value:.2f}",
                "最大连续亏损次数": self.max_consecutive_losses,
                "最大连续盈利次数": self.max_consecutive_wins,
            },
            "年化指标": {
                "年化收益率": f"{self.annual_return:.2f}%",
                "夏普比率": f"{self.sharpe_ratio:.2f}",
                "索提诺比率": f"{self.sortino_ratio:.2f}",
                "卡玛比率": f"{self.calmar_ratio:.2f}",
            },
            "持仓统计": {
                "平均持仓天数": f"{self.avg_holding_period:.1f}",
                "最长持仓": self.max_holding_period,
                "最短持仓": self.min_holding_period,
            },
        }

    def print_report(self) -> str:
        """打印完整回测报告"""
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("📊  回测绩效报告")
        lines.append("=" * 60)

        for category, metrics in self.to_dict().items():
            lines.append(f"\n── {category} ──")
            for k, v in metrics.items():
                lines.append(f"  {k:<20} {v}")

        # ── 离场原因归因 ──
        if self.exit_reason_stats:
            lines.append(f"\n── 离场原因归因 ──")
            for reason, info in sorted(self.exit_reason_stats.items(),
                                       key=lambda x: x[1].get("count", 0) if isinstance(x[1], dict) else 0,
                                       reverse=True):
                if not isinstance(info, dict):
                    lines.append(f"  {reason:<20} {info}")
                    continue
                lines.append(f"  {reason:<20} 次数:{info.get('count', 0):>4}  "
                            f"胜率:{info.get('win_rate', 0):.1f}%  平均盈亏:{info.get('avg_pnl', 0):>+.2f}")

        # ── 入场信号归因 ──
        if self.signal_source_stats:
            lines.append(f"\n── 入场信号归因 ──")
            for signal, info in sorted(self.signal_source_stats.items(),
                                       key=lambda x: x[1].get("count", 0) if isinstance(x[1], dict) else 0,
                                       reverse=True):
                if not isinstance(info, dict):
                    lines.append(f"  {signal:<30} {info}")
                    continue
                lines.append(f"  {signal:<30} 次数:{info.get('count', 0):>4}  "
                            f"胜率:{info.get('win_rate', 0):.1f}%  盈亏比:{info.get('profit_factor', 0):.2f}")

        lines.append("=" * 60)
        return "\n".join(lines)


def compute_performance(trades: List[TradeRecord],
                        initial_capital: float = 100000.0) -> PerformanceStats:
    """
    从交易记录列表计算完整绩效统计
    """
    stats = PerformanceStats()
    if not trades:
        return stats

    # ── 基础统计 ──
    stats.total_trades = len(trades)
    stats.win_count = sum(1 for t in trades if t.is_win)
    stats.loss_count = sum(1 for t in trades if t.is_loss)
    stats.flat_count = sum(1 for t in trades if t.is_flat)
    stats.win_rate = stats.win_count / stats.total_trades * 100 if stats.total_trades > 0 else 0

    # ── 收益统计 ──
    stats.total_pnl = sum(t.pnl for t in trades)
    stats.total_net_pnl = sum(t.net_pnl for t in trades)
    stats.total_fee = sum(t.fee for t in trades)
    stats.avg_pnl = stats.total_pnl / stats.total_trades if stats.total_trades > 0 else 0
    stats.avg_pnl_pct = sum(t.pnl_pct for t in trades) / stats.total_trades * 100 if stats.total_trades > 0 else 0

    pnl_pcts = sorted([t.pnl_pct for t in trades])
    if pnl_pcts:
        mid = len(pnl_pcts) // 2
        stats.med_pnl_pct = pnl_pcts[mid] * 100 if len(pnl_pcts) % 2 == 1 else \
            (pnl_pcts[mid - 1] + pnl_pcts[mid]) / 2 * 100

    # ── 盈亏比 ──
    wins = [t for t in trades if t.is_win]
    losses = [t for t in trades if t.is_loss]

    stats.avg_win_pnl = sum(t.pnl for t in wins) / len(wins) if wins else 0
    stats.avg_loss_pnl = sum(t.pnl for t in losses) / len(losses) if losses else 0

    total_win_pnl = sum(t.pnl for t in wins)
    total_loss_pnl = abs(sum(t.pnl for t in losses))
    stats.profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else float('inf')

    stats.expectancy = (stats.win_rate / 100 * stats.avg_win_pnl +
                        (1 - stats.win_rate / 100) * stats.avg_loss_pnl)

    # ── 连续盈亏统计 ──
    max_win_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    current_loss_streak = 0

    for t in trades:
        if t.is_win:
            current_win_streak += 1
            current_loss_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
        elif t.is_loss:
            current_loss_streak += 1
            current_win_streak = 0
            max_loss_streak = max(max_loss_streak, current_loss_streak)
        else:
            current_win_streak = 0
            current_loss_streak = 0

    stats.max_consecutive_wins = max_win_streak
    stats.max_consecutive_losses = max_loss_streak

    # ── 持仓统计 ──
    periods = [t.holding_period for t in trades]
    stats.avg_holding_period = sum(periods) / len(periods) if periods else 0
    stats.max_holding_period = max(periods) if periods else 0
    stats.min_holding_period = min(periods) if periods else 0

    # ── 资金曲线计算 ──
    capital = initial_capital
    equity_curve = [capital]
    peak = capital
    max_dd = 0
    max_dd_value = 0

    for t in trades:
        capital += t.net_pnl  # 更新资金
        equity_curve.append(capital)

        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak * 100  # 回撤%
        dd_value = peak - capital
        if dd > max_dd:
            max_dd = dd
            max_dd_value = dd_value

    stats.equity_curve = equity_curve
    stats.max_drawdown = max_dd
    stats.max_drawdown_value = max_dd_value

    # ── 年化收益 ──
    # 根据总交易时长估算年化
    if len(trades) >= 2 and trades[0].entry_date and trades[-1].exit_date:
        total_days = (trades[-1].exit_date - trades[0].entry_date).days
        if total_days > 0:
            years = total_days / 365.0
            total_return = (capital - initial_capital) / initial_capital
            stats.annual_return = ((1 + total_return) ** (1 / years) - 1) * 100 if total_return > -1 else -100

    # ── 夏普比率 ──
    # 使用每笔收益率计算
    returns = [t.pnl_pct for t in trades]
    if len(returns) > 1 and stats.annual_return != -100:
        avg_return = sum(returns) / len(returns)
        std_return = math.sqrt(sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1))
        if std_return > 0:
            # 假设无风险利率 2%
            risk_free = 0.02 / 252  # 日化
            stats.sharpe_ratio = (avg_return - risk_free) / std_return * math.sqrt(252)

    # ── 索提诺比率（仅下行波动） ──
    if len(returns) > 1:
        negative_returns = [r for r in returns if r < 0]
        if negative_returns:
            downside_std = math.sqrt(sum(r ** 2 for r in negative_returns) / len(negative_returns))
            if downside_std > 0:
                stats.sortino_ratio = (avg_return - risk_free) / downside_std * math.sqrt(252) if stats.annual_return != -100 else 0

    # ── 卡玛比率 ──
    if max_dd > 0 and stats.annual_return != -100:
        stats.calmar_ratio = stats.annual_return / max_dd

    # ── 离场原因归因统计 ──
    exit_groups = defaultdict(list)
    for t in trades:
        exit_groups[t.exit_reason.value].append(t)

    for reason, group in exit_groups.items():
        win_cnt = sum(1 for t in group if t.is_win)
        stats.exit_reason_stats[reason] = {
            "count": len(group),
            "wins": win_cnt,
            "win_rate": win_cnt / len(group) * 100 if group else 0,
            "avg_pnl": sum(t.pnl for t in group) / len(group) if group else 0,
            "avg_pnl_pct": sum(t.pnl_pct for t in group) / len(group) * 100 if group else 0,
            "total_pnl": sum(t.pnl for t in group),
        }

    # ── 入场信号归因统计 ──
    signal_groups = defaultdict(list)
    for t in trades:
        key = t.signal_source.value
        if t.signal_detail.get("scorer"):
            key = f"{t.signal_source.value}({t.signal_detail['scorer']})"
        signal_groups[key].append(t)

    for signal, group in signal_groups.items():
        win_cnt = sum(1 for t in group if t.is_win)
        win_pnl = sum(t.pnl for t in group if t.is_win)
        loss_pnl = abs(sum(t.pnl for t in group if t.is_loss))
        stats.signal_source_stats[signal] = {
            "count": len(group),
            "wins": win_cnt,
            "win_rate": win_cnt / len(group) * 100 if group else 0,
            "avg_pnl": sum(t.pnl for t in group) / len(group) if group else 0,
            "profit_factor": win_pnl / loss_pnl if loss_pnl > 0 else float('inf'),
            "total_pnl": sum(t.pnl for t in group),
        }

    return stats
