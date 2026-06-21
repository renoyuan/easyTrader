#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-06-09
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  信号过滤模块

"""
信号过滤模块 [强烈建议]
========================
多层过滤：趋势过滤、成交量过滤、波动率过滤、均线多空过滤；
回测对比两套数据：不开过滤的原始信号盈亏曲线 / 开启过滤后曲线；
输出指标：过滤后信号数量、假信号下降比例、整体胜率提升幅度。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

from .trade import TickSnapshot, TradeRecord


class FilterLevel(Enum):
    """过滤层级"""
    TREND = "趋势过滤"
    VOLUME = "成交量过滤"
    VOLATILITY = "波动率过滤"
    MA_CROSS = "均线多空过滤"
    CUSTOM = "自定义过滤"


@dataclass
class FilterResult:
    """
    过滤结果
    ========
    """
    passed: bool = True                  # 是否通过过滤
    failed_level: Optional[str] = None   # 在哪一层被过滤
    failed_detail: str = ""              # 过滤原因
    filter_info: Dict[str, Any] = field(default_factory=dict)


class BaseFilter:
    """
    信号过滤器基类
    =============
    """

    def __init__(self, name: str, level: FilterLevel):
        self.name = name
        self.level = level
        self._stats = {"checked": 0, "passed": 0, "blocked": 0}

    def check(self, tick: TickSnapshot, context: Dict[str, Any]) -> FilterResult:
        """检查是否通过过滤，子类重写"""
        self._stats["checked"] += 1
        result = self._check(tick, context)
        if result.passed:
            self._stats["passed"] += 1
        else:
            self._stats["blocked"] += 1
        return result

    def _check(self, tick: TickSnapshot, context: Dict[str, Any]) -> FilterResult:
        """子类实现具体过滤逻辑"""
        return FilterResult(passed=True)

    def reset_stats(self):
        self._stats = {"checked": 0, "passed": 0, "blocked": 0}

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level.value,
            **self._stats,
            "pass_rate": round(self._stats["passed"] / max(self._stats["checked"], 1) * 100, 2),
            "block_rate": round(self._stats["blocked"] / max(self._stats["checked"], 1) * 100, 2),
        }


class SignalFilter:
    """
    信号过滤器 [强烈建议]
    =====================
    多层过滤管道，依次执行各层过滤器。
    默认开启，可临时关闭。
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._filters: List[BaseFilter] = []

    def add_filter(self, filter_obj: BaseFilter) -> None:
        """添加过滤器"""
        self._filters.append(filter_obj)

    def remove_filter(self, name: str) -> None:
        """移除过滤器"""
        self._filters = [f for f in self._filters if f.name != name]

    @property
    def all_filters(self) -> List[BaseFilter]:
        return self._filters

    def check_all(self, tick: TickSnapshot, context: Dict[str, Any]) -> FilterResult:
        """
        依次通过所有过滤器，任一不通过则返回失败。
        如果 filter 被禁用，直接返回通过。
        """
        if not self.enabled:
            return FilterResult(passed=True, filter_info={"filter_enabled": False})

        result = FilterResult(passed=True)
        for f in self._filters:
            result = f.check(tick, context)
            if not result.passed:
                return result

        return result

    def reset_all_stats(self):
        """重置所有过滤器统计"""
        for f in self._filters:
            f.reset_stats()

    def get_stats(self) -> List[Dict[str, Any]]:
        """获取各层过滤统计"""
        return [f.stats for f in self._filters]

    def get_summary(self) -> Dict[str, Any]:
        """获取过滤汇总"""
        total_checked = sum(s["checked"] for s in self.get_stats())
        total_blocked = sum(s["blocked"] for s in self.get_stats())
        return {
            "enabled": self.enabled,
            "filter_count": len(self._filters),
            "total_checked": total_checked,
            "total_blocked": total_blocked,
            "overall_block_rate": round(total_blocked / max(total_checked, 1) * 100, 2),
        }


# ── 内置过滤器 ──

class TrendFilter(BaseFilter):
    """
    趋势过滤 [强烈建议]
    ===================
    仅在大盘/个股处于上升趋势时允许入场。
    """

    def __init__(self, ma_period: int = 20):
        super().__init__(name=f"趋势过滤(MA{ma_period})", level=FilterLevel.TREND)
        self.ma_period = ma_period

    def _check(self, tick: TickSnapshot, context: Dict[str, Any]) -> FilterResult:
        ma_key = f"ma{self.ma_period}"
        ma_val = getattr(tick, ma_key, None)

        if ma_val is None:
            return FilterResult(passed=True, filter_info={"reason": "无均线数据"})

        # 收盘价在均线上方视为上升趋势
        if tick.close >= ma_val:
            return FilterResult(
                passed=True,
                filter_info={
                    "trend": "上升",
                    f"MA{self.ma_period}": round(ma_val, 2),
                    "close": round(tick.close, 2),
                }
            )
        else:
            return FilterResult(
                passed=False,
                failed_level=self.level.value,
                failed_detail=f"收盘价 {tick.close:.2f} < MA{self.ma_period} {ma_val:.2f}, 非上升趋势"
            )


class VolumeFilter(BaseFilter):
    """
    成交量过滤 [强烈建议]
    =====================
    成交量需要大于均量，避免无量空涨/无量反弹的假信号。
    """

    def __init__(self, volume_ma_period: int = 20, min_volume_ratio: float = 0.8):
        super().__init__(
            name=f"成交量过滤(MA{volume_ma_period}量>={min_volume_ratio})",
            level=FilterLevel.VOLUME
        )
        self.volume_ma_period = volume_ma_period
        self.min_volume_ratio = min_volume_ratio

    def _check(self, tick: TickSnapshot, context: Dict[str, Any]) -> FilterResult:
        vol_ma_key = f"volume_ma{self.volume_ma_period}"
        vol_ma = context.get(vol_ma_key, None)

        if vol_ma is None or vol_ma <= 0:
            return FilterResult(passed=True, filter_info={"reason": "无均量数据"})

        vol_ratio = tick.volume / vol_ma if vol_ma > 0 else 1

        if vol_ratio >= self.min_volume_ratio:
            return FilterResult(
                passed=True,
                filter_info={
                    "volume_ratio": round(vol_ratio, 2),
                    "volume": tick.volume,
                    f"volume_ma{self.volume_ma_period}": vol_ma,
                }
            )
        else:
            return FilterResult(
                passed=False,
                failed_level=self.level.value,
                failed_detail=f"成交量 {tick.volume} < {self.min_volume_ratio:.0%}*均量 {vol_ma:.0f}, 量比 {vol_ratio:.2f}"
            )


class VolatilityFilter(BaseFilter):
    """
    波动率过滤 [强烈建议]
    =====================
    波动率过高时过滤信号（避免追涨杀跌），波动率过低时也过滤（僵尸股）。
    """

    def __init__(self, min_volatility: float = 0.01, max_volatility: float = 0.08):
        super().__init__(
            name=f"波动率过滤({min_volatility:.1%}~{max_volatility:.1%})",
            level=FilterLevel.VOLATILITY
        )
        self.min_volatility = min_volatility
        self.max_volatility = max_volatility

    def _check(self, tick: TickSnapshot, context: Dict[str, Any]) -> FilterResult:
        vol = tick.volatility

        if vol is None:
            return FilterResult(passed=True, filter_info={"reason": "无波动率数据"})

        if self.min_volatility <= vol <= self.max_volatility:
            return FilterResult(
                passed=True,
                filter_info={
                    "volatility": round(vol, 4),
                    "volatility_range": f"{self.min_volatility:.1%}~{self.max_volatility:.1%}",
                }
            )
        else:
            return FilterResult(
                passed=False,
                failed_level=self.level.value,
                failed_detail=f"波动率 {vol:.2%} 不在 [{self.min_volatility:.1%}, {self.max_volatility:.1%}] 范围内"
            )


class MACrossFilter(BaseFilter):
    """
    均线多空过滤 [强烈建议]
    =======================
    均线多头排列（短期 > 中期 > 长期）才允许入场。
    """

    def __init__(self, short_ma: int = 5, mid_ma: int = 10, long_ma: int = 20):
        super().__init__(
            name=f"均线多空过滤(MA{short_ma}>{mid_ma}>{long_ma})",
            level=FilterLevel.MA_CROSS
        )
        self.short_ma = short_ma
        self.mid_ma = mid_ma
        self.long_ma = long_ma

    def _check(self, tick: TickSnapshot, context: Dict[str, Any]) -> FilterResult:
        short_val = getattr(tick, f"ma{self.short_ma}", None)
        mid_val = getattr(tick, f"ma{self.mid_ma}", None)
        long_val = getattr(tick, f"ma{self.long_ma}", None)

        if any(v is None for v in [short_val, mid_val, long_val]):
            return FilterResult(passed=True, filter_info={"reason": "均线数据不足"})

        if short_val >= mid_val >= long_val:
            return FilterResult(
                passed=True,
                filter_info={
                    "ma_short": round(short_val, 2),
                    "ma_mid": round(mid_val, 2),
                    "ma_long": round(long_val, 2),
                    "排列": "多头",
                }
            )
        else:
            return FilterResult(
                passed=False,
                failed_level=self.level.value,
                failed_detail=(f"均线非多头排列: MA{self.short_ma}={short_val:.2f}, "
                              f"MA{self.mid_ma}={mid_val:.2f}, MA{self.long_ma}={long_val:.2f}")
            )
