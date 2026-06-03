# -*- coding: utf-8 -*-
"""
全市场批量评分扫描器
====================
从 stock_basic 表获取各市场股票列表，批量执行评分，输出前 N 名。
支持进度回调，可在 GUI 中显示进度条。
"""
import sys
import os
import time
import threading
from typing import Callable, Optional, List, Dict, Any

import pandas as pd
import numpy as np

from trader.db.orm import SessionLocal, StockBasic
from trader.scorer.buffett import BuffettScorer
from trader.scorer.graham import GrahamScorer
from trader.scorer.xuxiang import XuXiangScorer
from trader.scorer.renoyuan import RenoyuanScorer
from trader.scorer.xubin import XuBinScorer


# ── 市场代码映射 ──
MARKET_MAP = {
    "全市场": None,           # None 表示不筛选
    "沪市主板": "SH",
    "深市主板": "SZ_MAIN",    # 00 开头
    "创业板": "CYB",          # 300 开头
    "科创板": "KCB",          # 688 开头
    "北交所": "BJ",           # 8,9 开头
}

# ── 评分体系映射 ──
SCORER_MAP = {
    "巴菲特价值评分": BuffettScorer,
    "格雷厄姆价值评分": GrahamScorer,
    "徐翔趋势评分": XuXiangScorer,
    "renoyuan核心评分": RenoyuanScorer,
    "xubin财报排雷评分": XuBinScorer,
}


def get_stock_list_by_market(markets: List[str]) -> List[Dict[str, str]]:
    """
    从 stock_basic 表获取指定市场股票列表
    
    :param markets: 市场代码列表。支持多种筛选：
                    'ALL'=全市场, 'SH'=沪市(60,68), 'SZ_MAIN'=深市主板(00),
                    'CYB'=创业板(300), 'KCB'=科创板(688), 'BJ'=北交所(8,9)
    :return: [{"code": "600519", "name": "贵州茅台"}, ...]
    """
    if not markets:
        return []
    
    is_all = "ALL" in markets
    
    try:
        with SessionLocal() as session:
            query = session.query(StockBasic).filter(StockBasic.list_status == "L")
            rows = query.all()
        
        result = []
        for row in rows:
            code = row.code.strip()
            name = row.name.strip() if row.name else ""
            
            if is_all:
                # 全市场 - 不过滤
                pass
            else:
                # 检查股票代码是否匹配任一选中的市场
                matched = False
                for m in markets:
                    if m == "SH":
                        if code.startswith("60") or code.startswith("68"):
                            matched = True
                            break
                    elif m == "SZ_MAIN":
                        if code.startswith("00"):
                            matched = True
                            break
                    elif m == "CYB":
                        if code.startswith("300"):
                            matched = True
                            break
                    elif m == "KCB":
                        if code.startswith("688"):
                            matched = True
                            break
                    elif m == "BJ":
                        if code.startswith("8") or code.startswith("9"):
                            matched = True
                            break
                if not matched:
                    continue
            
            result.append({"code": code, "name": name})
        
        return result
    except Exception as e:
        print(f"[market_scanner] 获取股票列表失败: {e}")
        return []


def get_stock_names_by_codes(codes: List[str]) -> Dict[str, str]:
    """
    根据股票代码列表，从数据库查出对应的股票名称
    :param codes: 6 位股票代码列表
    :return: { "600519": "贵州茅台", ... }
    """
    if not codes:
        return {}
    try:
        with SessionLocal() as session:
            rows = session.query(StockBasic).filter(
                StockBasic.code.in_(codes)
            ).all()
        return {row.code.strip(): row.name.strip() if row.name else "" for row in rows}
    except Exception as e:
        print(f"[market_scanner] 查询股票名称失败: {e}")
        return {}


class MarketScanner:
    """
    全市场批量评分扫描器
    在后台线程执行，通过回调更新进度和结果。
    """

    def __init__(self):
        self._stop_flag = False
        self._scorer_cache = {}

    def stop(self):
        """请求停止扫描"""
        self._stop_flag = True

    def scan(
        self,
        markets: List[str],
        scorer_name: str,
        top_n: int = 5,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        result_callback: Optional[Callable[[List[Dict]], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        批量扫描评分（在调用线程中执行，建议用 threading 启动）
        
        :param markets: 市场代码列表，如 ["SH","CYB"] 或 ["ALL"]
        :param scorer_name: 评分体系名称
        :param top_n: 返回前 N 名
        :param progress_callback: (current, total, stock_name) 进度回调
        :param result_callback: (results) 完成回调，results 是已排序的前 top_n 结果
        :param log_callback: (msg) 日志回调
        """
        self._stop_flag = False
        
        # 1. 获取股票列表
        market_label = "全市场" if "ALL" in markets else "+".join(markets)
        if log_callback:
            log_callback(f"📋 正在获取 {market_label} 股票列表...")
        
        stock_list = get_stock_list_by_market(markets)
        if not stock_list:
            if log_callback:
                log_callback(f"❌ 未获取到股票数据，请先同步股票基础信息")
            return
        
        total = len(stock_list)
        if log_callback:
            log_callback(f"📊 {market_label} 共 {total} 只股票，开始扫描...")
        
        # 2. 初始化评分器
        scorer_cls = SCORER_MAP.get(scorer_name)
        if not scorer_cls:
            if log_callback:
                log_callback(f"❌ 未知评分体系: {scorer_name}")
            return
        
        scorer = scorer_cls()
        
        # 3. 批量评分
        all_results = []
        fail_count = 0
        skip_count = 0
        
        for idx, stock in enumerate(stock_list):
            if self._stop_flag:
                if log_callback:
                    log_callback(f"⏹ 扫描已停止，已完成 {idx}/{total}")
                break
            
            code = stock["code"]
            name = stock["name"]
            
            # 跳过北交所股票（数据不全），除非用户明确选了北交所
            if "BJ" not in markets and (code.startswith("8") or code.startswith("9")):
                skip_count += 1
                if progress_callback:
                    progress_callback(idx + 1, total, f"{name}({code}) - 跳过(北交所)")
                continue
            
            if progress_callback:
                progress_callback(idx + 1, total, f"{name}({code})")
            
            try:
                result = scorer.score(code)
                
                if result and result.get("score") is not None:
                    result["name"] = name
                    all_results.append(result)
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                if log_callback:
                    log_callback(f"  ⚠️ {name}({code}) 评分异常: {str(e)[:50]}")
            
            # 避免请求过快
            time.sleep(0.1)
        
        # 4. 排序取前 N
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_results = all_results[:top_n]
        
        if log_callback:
            log_callback(
                f"\n{'='*50}"
                f"\n✅ 扫描完成!"
                f"\n   {market_label} - {scorer_name}"
                f"\n   总计: {total} 只"
                f"\n   成功: {len(all_results)} 只"
                f"\n   失败: {fail_count} 只"
                f"\n   跳过: {skip_count} 只"
                f"\n{'='*50}"
            )
        
        if result_callback:
            result_callback(top_results)

    def scan_custom(
        self,
        codes: List[str],
        scorer_name: str,
        top_n: int = 5,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        result_callback: Optional[Callable[[List[Dict]], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        自定义股票代码批量评分（比 scan 更快，只评分指定股票）
        
        :param codes: 6 位股票代码列表
        :param scorer_name: 评分体系名称
        :param top_n: 返回前 N 名
        :param progress_callback: (current, total, stock_name) 进度回调
        :param result_callback: (results) 完成回调
        :param log_callback: (msg) 日志回调
        """
        self._stop_flag = False
        total = len(codes)

        if log_callback:
            log_callback(f"📋 自定义 {total} 只股票，开始扫描...")

        # 查出股票名称
        name_map = get_stock_names_by_codes(codes)

        # 初始化评分器
        scorer_cls = SCORER_MAP.get(scorer_name)
        if not scorer_cls:
            if log_callback:
                log_callback(f"❌ 未知评分体系: {scorer_name}")
            return

        scorer = scorer_cls()
        all_results = []
        fail_count = 0

        for idx, code in enumerate(codes):
            if self._stop_flag:
                if log_callback:
                    log_callback(f"⏹ 扫描已停止，已完成 {idx}/{total}")
                break

            name = name_map.get(code, "")

            if progress_callback:
                progress_callback(idx + 1, total, f"{name}({code})")

            try:
                result = scorer.score(code)
                if result and result.get("score") is not None:
                    result["name"] = name
                    all_results.append(result)
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                if log_callback:
                    log_callback(f"  ⚠️ {name}({code}) 评分异常: {str(e)[:50]}")

            time.sleep(0.1)

        # 排序取前 N
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_results = all_results[:top_n]

        if log_callback:
            log_callback(
                f"\n{'='*50}"
                f"\n✅ 自定义扫描完成!"
                f"\n   {scorer_name}"
                f"\n   总计: {total} 只"
                f"\n   成功: {len(all_results)} 只"
                f"\n   失败: {fail_count} 只"
                f"\n{'='*50}"
            )

        if result_callback:
            result_callback(top_results)


def format_top_results(results: List[Dict], scorer_name: str) -> str:
    """格式化前 N 名结果为可读文本"""
    if not results:
        return "❌ 未获取到有效评分结果"
    
    lines = []
    lines.append(f"\n{'='*55}")
    lines.append(f"🏆  {scorer_name} - 全市场 TOP {len(results)}")
    lines.append(f"{'='*55}")
    
    for i, r in enumerate(results, 1):
        code = r.get("code", "N/A")
        name = r.get("name", "")
        score = r.get("score", 0)
        rating = r.get("rating", "N/A")
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:>2}."
        lines.append(f"\n{medal}  {name}({code})")
        lines.append(f"    总分: {score}/100  |  评级: {rating}")
        
        # 附加关键指标
        indicators = r.get("indicators", {})
        # 兼容 pandas Series 和 dict
        if isinstance(indicators, dict):
            indicator_items = list(indicators.items())
        elif isinstance(indicators, pd.Series):
            indicator_items = [(k, v) for k, v in indicators.items()]
        else:
            indicator_items = []
        
        if indicator_items:
            # 显示前3个关键指标
            shown = 0
            for k, v in indicator_items:
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    continue
                if shown >= 3:
                    break
                if isinstance(v, float):
                    if abs(v) < 1:
                        lines.append(f"    {k}: {v:.2%}")
                    else:
                        lines.append(f"    {k}: {v:.2f}")
                else:
                    lines.append(f"    {k}: {v}")
                shown += 1
    
    lines.append(f"\n{'='*55}")
    return "\n".join(lines)
