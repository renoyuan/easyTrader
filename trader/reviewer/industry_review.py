#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2025-07-16
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note: 行业复盘模块 - 盘点行业市值排名、热度排名、区间涨跌

"""
行业复盘模块
=============
功能：
  1. 市值排名 TOP5 - A 股市值占比、自身市值
  2. 热度排名 - 昨日/近一月/近一年涨跌幅排名（涨幅 TOP5 + 跌幅 TOP5）
  3. 上级行业标识（二级/一级）
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests


# 全局网络检测：首次请求失败后标记为不可用，避免重复超时
_g_network_ok = True


def _check_network() -> bool:
    """快速检测网络是否可用（只检测一次，失败则标记）"""
    global _g_network_ok
    if not _g_network_ok:
        return False
    try:
        requests.get("https://push2.eastmoney.com/api/qt/ulist.np/get",
                     timeout=3)
        return True
    except Exception:
        _g_network_ok = False
        return False


class IndustryReviewer:
    """
    行业复盘
    基于东方财富行业板块数据 + 本地申万行业分级
    """

    # 区间映射（用于获取历史行情）
    PERIOD_DAYS = {
        "昨日": 1,
        "近一月": 20,
        "近一年": 245,
    }

    def __init__(self):
        self._industry_spot_cache = None   # 缓存行业实时行情
        self._industry_hist_cache = {}     # 缓存行业历史行情 {name: df}
        self._em_to_sw_map = self._build_em_to_sw_map()

    # ════════════════════════════════════════
    # 0. 构建东方财富→申万行业映射表（从数据库自动生成）
    # ════════════════════════════════════════
    @staticmethod
    def _build_em_to_sw_map() -> Dict[str, Dict[str, str]]:
        """
        从 SwIndustry 表自动构建东方财富行业名 → 申万分级 的映射
        东方财富行业板块名与申万三级行业名大部分一致，做模糊匹配
        """
        mapping = {
            # ---------- 电子 ----------
            "半导体": {"level2": "半导体", "level1": "电子"},
            "芯片": {"level2": "半导体", "level1": "电子"},
            "元器件": {"level2": "元件", "level1": "电子"},
            "光学光电子": {"level2": "光学光电子", "level1": "电子"},
            "消费电子": {"level2": "消费电子", "level1": "电子"},
            "电子元件": {"level2": "元件", "level1": "电子"},
            "电子化学品": {"level2": "电子化学品Ⅱ", "level1": "电子"},
            "其他电子": {"level2": "其他电子Ⅱ", "level1": "电子"},
            "半导体设备": {"level2": "半导体", "level1": "电子"},
            # ---------- 计算机 ----------
            "计算机设备": {"level2": "计算机设备", "level1": "计算机"},
            "计算机应用": {"level2": "软件开发", "level1": "计算机"},
            "软件开发": {"level2": "软件开发", "level1": "计算机"},
            "IT服务": {"level2": "IT服务", "level1": "计算机"},
            "互联网服务": {"level2": "互联网电商", "level1": "计算机"},
            "互联网电商": {"level2": "互联网电商", "level1": "计算机"},
            # ---------- 通信 ----------
            "通信设备": {"level2": "通信设备", "level1": "通信"},
            "通信服务": {"level2": "通信服务", "level1": "通信"},
            "通信运营": {"level2": "通信服务", "level1": "通信"},
            # ---------- 国防军工 ----------
            "军工电子": {"level2": "军工电子Ⅱ", "level1": "国防军工"},
            "航空装备": {"level2": "航空装备Ⅱ", "level1": "国防军工"},
            "航天装备": {"level2": "航天装备Ⅱ", "level1": "国防军工"},
            "地面兵装": {"level2": "地面兵装Ⅱ", "level1": "国防军工"},
            "航海装备": {"level2": "航海装备Ⅱ", "level1": "国防军工"},
            # ---------- 医药生物 ----------
            "医疗器械": {"level2": "医疗器械", "level1": "医药生物"},
            "生物制品": {"level2": "生物制品", "level1": "医药生物"},
            "医疗服务": {"level2": "医疗服务", "level1": "医药生物"},
            "医药商业": {"level2": "医药商业", "level1": "医药生物"},
            "化学制药": {"level2": "化学制药", "level1": "医药生物"},
            "中药": {"level2": "中药", "level1": "医药生物"},
            "医药": {"level2": "化学制药", "level1": "医药生物"},
            # ---------- 电力设备 ----------
            "光伏设备": {"level2": "光伏设备", "level1": "电力设备"},
            "光伏": {"level2": "光伏设备", "level1": "电力设备"},
            "电池": {"level2": "电池", "level1": "电力设备"},
            "风电设备": {"level2": "风电设备", "level1": "电力设备"},
            "电网设备": {"level2": "电网设备", "level1": "电力设备"},
            "新能源": {"level2": "新能源", "level1": "电力设备"},
            "电力": {"level2": "电力", "level1": "公用事业"},
            # ---------- 汽车 ----------
            "新能源汽车": {"level2": "汽车零部件", "level1": "汽车"},
            "汽车零部件": {"level2": "汽车零部件", "level1": "汽车"},
            "汽车整车": {"level2": "汽车整车", "level1": "汽车"},
            "汽车服务": {"level2": "汽车服务", "level1": "汽车"},
            # ---------- 机械设备 ----------
            "自动化设备": {"level2": "自动化设备", "level1": "机械设备"},
            "机器人": {"level2": "自动化设备", "level1": "机械设备"},
            "通用设备": {"level2": "通用设备", "level1": "机械设备"},
            "专用设备": {"level2": "专用设备", "level1": "机械设备"},
            "仪器仪表": {"level2": "仪器仪表", "level1": "机械设备"},
            "工程机械": {"level2": "工程机械", "level1": "机械设备"},
            # ---------- 有色金属 ----------
            "锂电池": {"level2": "能源金属", "level1": "有色金属"},
            "能源金属": {"level2": "能源金属", "level1": "有色金属"},
            "工业金属": {"level2": "工业金属", "level1": "有色金属"},
            "贵金属": {"level2": "贵金属", "level1": "有色金属"},
            "小金属": {"level2": "小金属", "level1": "有色金属"},
            "金属新材料": {"level2": "金属新材料", "level1": "有色金属"},
            # ---------- 基础化工 ----------
            "化学原料": {"level2": "化学原料", "level1": "基础化工"},
            "化学制品": {"level2": "化学制品", "level1": "基础化工"},
            "化工": {"level2": "化学制品", "level1": "基础化工"},
            "农化制品": {"level2": "农化制品", "level1": "基础化工"},
            # ---------- 食品饮料 ----------
            "食品饮料": {"level2": "食品加工", "level1": "食品饮料"},
            "白酒": {"level2": "白酒Ⅱ", "level1": "食品饮料"},
            "食品加工": {"level2": "食品加工", "level1": "食品饮料"},
            "饮料": {"level2": "饮料", "level1": "食品饮料"},
            # ---------- 银行/非银 ----------
            "银行": {"level2": "银行", "level1": "银行"},
            "保险": {"level2": "保险Ⅱ", "level1": "非银金融"},
            "证券": {"level2": "证券Ⅱ", "level1": "非银金融"},
            "多元金融": {"level2": "多元金融", "level1": "非银金融"},
            # ---------- 周期/传统 ----------
            "房地产": {"level2": "房地产", "level1": "房地产"},
            "房地产开发": {"level2": "房地产开发", "level1": "房地产"},
            "煤炭": {"level2": "煤炭", "level1": "煤炭"},
            "石油石化": {"level2": "石油石化", "level1": "石油石化"},
            "石油": {"level2": "石油石化", "level1": "石油石化"},
            "钢铁": {"level2": "钢铁", "level1": "钢铁"},
            "建筑材料": {"level2": "建筑材料", "level1": "建筑材料"},
            "建筑装饰": {"level2": "建筑装饰", "level1": "建筑装饰"},
            "建筑": {"level2": "建筑装饰", "level1": "建筑装饰"},
            "交通运输": {"level2": "交通运输", "level1": "交通运输"},
            "港口航运": {"level2": "航运港口", "level1": "交通运输"},
            "环保": {"level2": "环保", "level1": "环保"},
            "美容护理": {"level2": "美容护理", "level1": "美容护理"},
            "社会服务": {"level2": "社会服务", "level1": "社会服务"},
            "商贸零售": {"level2": "商贸零售", "level1": "商贸零售"},
            "纺织服饰": {"level2": "纺织服饰", "level1": "纺织服饰"},
            "轻工制造": {"level2": "轻工制造", "level1": "轻工制造"},
            "农林牧渔": {"level2": "养殖业", "level1": "农林牧渔"},
            "农业": {"level2": "种植业", "level1": "农林牧渔"},
            "传媒": {"level2": "传媒", "level1": "传媒"},
            "游戏": {"level2": "游戏Ⅱ", "level1": "传媒"},
            "广告": {"level2": "广告营销", "level1": "传媒"},
            "家用电器": {"level2": "家用电器", "level1": "家用电器"},
            "家电": {"level2": "家用电器", "level1": "家用电器"},
            "造纸": {"level2": "造纸", "level1": "轻工制造"},
            "综合": {"level2": "综合", "level1": "综合"},
        }
        return mapping

    # ════════════════════════════════════════
    # 1. 获取东方财富行业板块实时行情
    # ════════════════════════════════════════
    def _fetch_industry_spot(self) -> pd.DataFrame:
        """获取东方财富行业板块实时行情（含总市值、涨跌幅等）"""
        if self._industry_spot_cache is not None:
            return self._industry_spot_cache

        # 快速网络检测
        if not _check_network():
            # 网络不通 -> 用本地申万一级行业数据兜底
            return self._fallback_spot_from_db()

        try:
            df = ak.stock_board_industry_spot_em()
            if df is not None and not df.empty:
                self._industry_spot_cache = df
                return df
        except Exception:
            pass

        return self._fallback_spot_from_db()

    def _fallback_spot_from_db(self) -> pd.DataFrame:
        """兜底：从本地申万一级行业表获取行业名称列表"""
        try:
            from trader.db.orm import SessionLocal
            from trader.db.valuation_models import SwIndustry

            with SessionLocal() as session:
                rows = session.query(SwIndustry).filter(
                    SwIndustry.level == 1
                ).order_by(SwIndustry.code).all()

                if rows:
                    data = [{"板块名称": r.name, "总市值": None, "涨跌幅": None}
                            for r in rows]
                    df = pd.DataFrame(data)
                    self._industry_spot_cache = df
                    return df
        except Exception:
            pass

        return pd.DataFrame()

    # ════════════════════════════════════════
    # 2. 获取行业历史行情（按区间）
    # ════════════════════════════════════════
    def _fetch_industry_hist(self, board_name: str, days: int) -> Optional[pd.DataFrame]:
        """获取单个行业板块历史K线"""
        cache_key = f"{board_name}_{days}"
        if cache_key in self._industry_hist_cache:
            return self._industry_hist_cache[cache_key]

        # 网络不通直接跳过历史行情
        if not _check_network():
            return None

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days * 1.5 + 10)
            df = ak.stock_board_industry_hist_em(
                symbol=board_name,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                period="日k",
                adjust="qfq",
            )
            if df is not None and not df.empty:
                df['日期'] = pd.to_datetime(df['日期'])
                df.sort_values('日期', ascending=True, inplace=True)
                self._industry_hist_cache[cache_key] = df
                return df
        except Exception:
            pass

        return None

    # ════════════════════════════════════════
    # 3. 查询上级行业（申万体系）
    # ════════════════════════════════════════
    def _get_parent_industry(self, board_name: str) -> Dict[str, str]:
        """
        根据东方财富行业板块名，匹配申万行业分级体系中的上级行业
        返回: {"level2": "二级行业名", "level1": "一级行业名"}
        """
        # 1. 精确匹配映射表
        if board_name in self._em_to_sw_map:
            return self._em_to_sw_map[board_name]

        # 2. 关键词匹配映射表
        for key, val in self._em_to_sw_map.items():
            if key in board_name or board_name in key:
                return val

        # 3. 尝试从数据库模糊匹配
        try:
            from trader.db.orm import SessionLocal
            from trader.db.valuation_models import SwIndustry

            with SessionLocal() as session:
                third = session.query(SwIndustry).filter(
                    SwIndustry.level == 3,
                    SwIndustry.name.like(f"%{board_name}%")
                ).first()

                if third:
                    result = {}
                    if third.parent_code:
                        level2 = session.query(SwIndustry).filter(
                            SwIndustry.code == third.parent_code
                        ).first()
                        if level2:
                            result["level2"] = level2.name
                            if level2.parent_code:
                                level1 = session.query(SwIndustry).filter(
                                    SwIndustry.code == level2.parent_code
                                ).first()
                                if level1:
                                    result["level1"] = level1.name
                    return result
        except Exception:
            pass

        return {}

    # ════════════════════════════════════════
    # 4. 核心：市值排名 TOP5
    # ════════════════════════════════════════
    def get_market_cap_top5(self) -> List[Dict]:
        """
        按总市值排名前5的行业
        返回: [
            {
                "rank": 1,
                "board_name": "银行",
                "total_mv": 123456.78,       # 行业总市值(亿)
                "mv_ratio": 12.34,            # A股市值占比(%)
                "parent_industry": {"level2": "...", "level1": "..."},
            },
            ...
        ]
        """
        df = self._fetch_industry_spot()
        if df.empty:
            return []

        # 找市值列（东方财富接口字段名可能不同版本略有差异）
        mv_col = None
        for col in ["总市值", "总市值(元)", "总市值_元"]:
            if col in df.columns:
                mv_col = col
                break

        if mv_col is None:
            print("⚠️ 未找到总市值列，可用列:", list(df.columns))
            return []

        # 计算A股总市值
        df[mv_col] = pd.to_numeric(df[mv_col], errors='coerce')
        total_a_mv = df[mv_col].sum()

        # 按市值降序
        df_sorted = df.sort_values(mv_col, ascending=False).head(5)

        results = []
        for rank, (_, row) in enumerate(df_sorted.iterrows(), 1):
            board_name = row.get("板块名称", "")
            mv = float(row[mv_col]) if pd.notna(row[mv_col]) else 0
            mv_ratio = (mv / total_a_mv * 100) if total_a_mv > 0 else 0

            parent = self._get_parent_industry(board_name)

            results.append({
                "rank": rank,
                "board_name": board_name,
                "total_mv": round(mv / 1e8, 2) if mv > 1e8 else round(mv, 2),  # 转亿
                "mv_ratio": round(mv_ratio, 2),
                "parent_industry": parent,
            })

        return results

    # ════════════════════════════════════════
    # 5. 核心：区间涨跌幅排名
    # ════════════════════════════════════════
    def get_period_change_top5(self, period: str = "近一月",
                                df_spot: Optional[pd.DataFrame] = None) -> Dict[str, List[Dict]]:
        """
        获取指定区间的涨跌幅排名
        period: "昨日" / "近一月" / "近一年"
        df_spot: 可选，外部传入的行业实时行情（避免重复调用）
        """
        days = self.PERIOD_DAYS.get(period, 60)
        if df_spot is None:
            df_spot = self._fetch_industry_spot()
        if df_spot.empty or "板块名称" not in df_spot.columns:
            return {"涨幅TOP5": [], "跌幅TOP5": []}

        board_names = df_spot["板块名称"].tolist()

        # 逐个行业计算区间涨跌幅
        period_changes = []
        for name in board_names:
            hist = self._fetch_industry_hist(name, days)
            if hist is None or hist.empty:
                continue

            # 取区间首尾价格
            first_close = float(hist.iloc[0]["收盘"])
            last_close = float(hist.iloc[-1]["收盘"])
            if first_close == 0:
                continue
            change_pct = (last_close - first_close) / first_close * 100

            period_changes.append({
                "board_name": name,
                "change_pct": round(change_pct, 2),
                "start_close": round(first_close, 2),
                "end_close": round(last_close, 2),
                "start_date": str(hist.iloc[0]["日期"].date()),
                "end_date": str(hist.iloc[-1]["日期"].date()),
            })

        if not period_changes:
            return {"涨幅TOP5": [], "跌幅TOP5": []}

        df_changes = pd.DataFrame(period_changes)

        # 涨幅 TOP5
        top5_up = df_changes.nlargest(5, "change_pct")
        # 跌幅 TOP5
        top5_down = df_changes.nsmallest(5, "change_pct")

        def _build_items(df_src, reverse=False):
            items = []
            for rank, (_, row) in enumerate(df_src.iterrows(), 1):
                parent = self._get_parent_industry(row["board_name"])
                items.append({
                    "rank": rank,
                    "board_name": row["board_name"],
                    "change_pct": row["change_pct"],
                    "start_date": row["start_date"],
                    "end_date": row["end_date"],
                    "parent_industry": parent,
                })
            return items

        return {
            "涨幅TOP5": _build_items(top5_up),
            "跌幅TOP5": _build_items(top5_down),
        }

    # ════════════════════════════════════════
    # 6. 完整行业复盘
    # ════════════════════════════════════════
    def full_review(self) -> Dict:
        """
        一键获取完整行业复盘数据
        返回: {
            "统计日期": "2025-07-16",
            "市值排名TOP5": [...],
            "热度排名": {
                "昨日": {"涨幅TOP5": [...], "跌幅TOP5": [...]},
                "近一月": {...},
                "近一年": {...},
            },
            "行业总数": 86,
            "A股总市值(亿)": 1234567.89,
        }
        """
        result = {
            "统计日期": datetime.now().strftime("%Y-%m-%d"),
            "市值排名TOP5": [],
            "热度排名": {},
            "行业总数": 0,
        }

        # 一次性获取行业实时行情
        df_spot = self._fetch_industry_spot()
        if df_spot.empty:
            return result

        result["行业总数"] = len(df_spot)

        # 计算A股总市值
        mv_col = None
        for col in ["总市值", "总市值(元)", "总市值_元"]:
            if col in df_spot.columns:
                mv_col = col
                break
        if mv_col and not df_spot[mv_col].isna().all():
            total_mv = pd.to_numeric(df_spot[mv_col], errors='coerce').sum()
            result["A股总市值(亿)"] = round(total_mv / 1e8, 2) if total_mv > 1e8 else round(total_mv, 2)

            # 市值排名（依赖市值列）
            df_sorted = df_spot.sort_values(mv_col, ascending=False).head(5)
            for rank, (_, row) in enumerate(df_sorted.iterrows(), 1):
                board_name = row.get("板块名称", "")
                mv = float(row[mv_col]) if pd.notna(row[mv_col]) else 0
                mv_ratio = (mv / total_mv * 100) if total_mv > 0 else 0
                parent = self._get_parent_industry(board_name)
                result["市值排名TOP5"].append({
                    "rank": rank,
                    "board_name": board_name,
                    "total_mv": round(mv / 1e8, 2) if mv > 1e8 else round(mv, 2),
                    "mv_ratio": round(mv_ratio, 2),
                    "parent_industry": parent,
                })

        # 热度排名（三段时间）
        for period in ["昨日", "近一月", "近一年"]:
            result["热度排名"][period] = self.get_period_change_top5(
                period, df_spot=df_spot
            )

        return result

    # ════════════════════════════════════════
    # 7. 打印行业复盘
    # ════════════════════════════════════════
    @staticmethod
    def format_review(result: Dict) -> str:
        """格式化为可读文本"""
        lines = []
        lines.append(f"\n{'='*55}")
        lines.append(f"  📊  行业复盘")
        lines.append(f"  统计日期: {result.get('统计日期', 'N/A')}")
        lines.append(f"  行业总数: {result.get('行业总数', 'N/A')}")
        lines.append(f"{'='*55}")

        # ── 市值排名 TOP5 ──
        lines.append(f"\n🔹 市值排名 TOP5")
        lines.append(f"{'-'*55}")
        top5_mv = result.get("市值排名TOP5", [])
        for item in top5_mv:
            parent = item.get("parent_industry", {})
            p_str = ""
            if parent.get("level1"):
                p_str = f"  [{parent.get('level1', '')}"
                if parent.get("level2"):
                    p_str += f" > {parent.get('level2', '')}"
                p_str += "]"
            lines.append(
                f"  #{item['rank']} {item['board_name']:<12} "
                f"市值 {item['total_mv']:>10.2f}亿  "
                f"A股占比 {item['mv_ratio']:.2f}%"
                f"{p_str}"
            )

        # ── 热度排名 ──
        for period in ["昨日", "近一月", "近一年"]:
            period_data = result.get("热度排名", {}).get(period, {})
            if not period_data:
                continue

            lines.append(f"\n🔹 {period} 涨跌幅排名")
            lines.append(f"{'-'*55}")

            up_list = period_data.get("涨幅TOP5", [])
            down_list = period_data.get("跌幅TOP5", [])

            if up_list:
                lines.append(f"  📈 涨幅 TOP5:")
                for item in up_list:
                    parent = item.get("parent_industry", {})
                    p_str = ""
                    if parent.get("level1"):
                        p_str = f"  [{parent['level1']}"
                        if parent.get("level2"):
                            p_str += f" > {parent['level2']}"
                        p_str += "]"
                    lines.append(
                        f"    #{item['rank']} {item['board_name']:<14} "
                        f"{item['change_pct']:+.2f}%"
                        f"{p_str}"
                    )

            if down_list:
                lines.append(f"  📉 跌幅 TOP5:")
                for item in down_list:
                    parent = item.get("parent_industry", {})
                    p_str = ""
                    if parent.get("level1"):
                        p_str = f"  [{parent['level1']}"
                        if parent.get("level2"):
                            p_str += f" > {parent['level2']}"
                        p_str += "]"
                    lines.append(
                        f"    #{item['rank']} {item['board_name']:<14} "
                        f"{item['change_pct']:+.2f}%"
                        f"{p_str}"
                    )

        lines.append(f"\n{'='*55}")
        lines.append(f"\n")
        return "\n".join(lines)


# ════════════════════════════════════════
# 快捷入口
# ════════════════════════════════════════
def run_industry_review() -> Dict:
    """一键执行行业复盘"""
    reviewer = IndustryReviewer()
    result = reviewer.full_review()
    print(reviewer.format_review(result))
    return result


if __name__ == "__main__":
    run_industry_review()
