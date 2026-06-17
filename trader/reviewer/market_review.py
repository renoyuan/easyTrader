#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

"""
市场复盘模块（同花顺接口版）
============================
使用同花顺（ths）数据中心接口获取市场统计数据，避免东方财富接口的稳定性问题。
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import traceback


class MarketReviewer:
    """市场复盘（同花顺接口）"""

    @staticmethod
    def _get_board(code: str) -> str:
        """判断股票所属板块"""
        if code.startswith(("60", "68")):
            return "主板" if code.startswith("60") else "科创板"
        elif code.startswith(("00", "30")):
            return "主板" if code.startswith("00") else "创业板"
        return "其他"

    def get_index_summary(self) -> dict:
        """
        使用 stock_rank_lxsz_ths（连续上涨）+ stock_rank_lxxd_ths（连续下跌）
        数据来推断市场热度。不直接获取指数涨跌（同花顺接口无指数实时数据）。
        """
        result = {}
        try:
            # 用连续上涨+下跌的数据来反映市场情绪
            up_df = ak.stock_rank_lxsz_ths()
            down_df = ak.stock_rank_lxxd_ths()
            if up_df is not None and not up_df.empty:
                result["连续上涨股票"] = {
                    "count": len(up_df),
                    "avg_pct": float(up_df['连续涨跌幅'].mean()) if '连续涨跌幅' in up_df.columns else None,
                    "max_days": int(up_df['连涨天数'].max()) if '连涨天数' in up_df.columns else None,
                }
            if down_df is not None and not down_df.empty:
                result["连续下跌股票"] = {
                    "count": len(down_df),
                    "avg_pct": float(down_df['连续涨跌幅'].mean()) if '连续涨跌幅' in down_df.columns else None,
                    "max_days": int(down_df['连涨天数'].max()) if '连涨天数' in down_df.columns else None,
                }
        except Exception as e:
            print(f"⚠️ 获取连续涨跌数据失败: {e}")

        # 用量价齐升/齐跌数据
        try:
            ljqs_df = ak.stock_rank_ljqs_ths()
            ljqd_df = ak.stock_rank_ljqd_ths()
            if ljqs_df is not None and not ljqs_df.empty:
                result["量价齐升"] = {"count": len(ljqs_df)}
            if ljqd_df is not None and not ljqd_df.empty:
                result["量价齐跌"] = {"count": len(ljqd_df)}
        except Exception as e:
            print(f"⚠️ 获取量价数据失败: {e}")

        # 用创新高/新低数据（带兼容处理）
        try:
            for symbol_name in ["创月新高", "半年新高", "一年新高", "历史新高"]:
                try:
                    df = ak.stock_rank_cxg_ths(symbol=symbol_name)
                    if df is not None and not df.empty:
                        result[symbol_name] = {"count": len(df)}
                except Exception:
                    continue
        except Exception:
            pass

        try:
            for symbol_name in ["创月新低", "半年新低", "一年新低", "历史新低"]:
                try:
                    df = ak.stock_rank_cxd_ths(symbol=symbol_name)
                    if df is not None and not df.empty:
                        result[symbol_name] = {"count": len(df)}
                except Exception:
                    continue
        except Exception:
            pass

        # 向上/向下突破均线
        try:
            df = ak.stock_rank_xstp_ths(symbol="20日均线")
            if df is not None and not df.empty:
                up_count = len(df[df['涨跌幅'] > 0]) if '涨跌幅' in df.columns else len(df)
                down_count = len(df[df['涨跌幅'] < 0]) if '涨跌幅' in df.columns else 0
                result["向上突破20日均线"] = {"count": up_count, "total": len(df)}
        except Exception as e:
            print(f"⚠️ 获取向上突破数据失败: {e}")

        return result

    def get_top_stocks(self, top_n: int = 10) -> dict:
        """
        获取涨幅榜/跌幅榜 Top10（使用同花顺接口）
        用向上突破20日均线榜单来获取热门股
        """
        result = {
            "主板": {"涨幅榜": [], "跌幅榜": []},
            "科创创业": {"涨幅榜": [], "跌幅榜": []},
        }

        def _classify(df, code_col='股票代码', pct_col='涨跌幅', show_price=False):
            """按板块分类并排序"""
            if df is None or df.empty:
                return
            df['board'] = df[code_col].apply(self._get_board)
            df['board_group'] = df['board'].apply(
                lambda b: '主板' if b == '主板' else '科创创业' if b in ('科创板', '创业板') else '其他'
            )
            for group in ('主板', '科创创业'):
                subset = df[df['board_group'] == group].copy()
                if subset.empty:
                    continue
                if pct_col in subset.columns:
                    up = subset.nlargest(top_n, pct_col)
                    down = subset.nsmallest(top_n, pct_col)
                    for label, src in [("涨幅榜", up), ("跌幅榜", down)]:
                        items = []
                        for _, row in src.iterrows():
                            item = {
                                'code': row.get(code_col, ''),
                                'name': row.get('股票简称', ''),
                                'pct_chg': float(row.get(pct_col, 0)),
                            }
                            # 同花顺突破均线接口有最新价
                            if show_price:
                                price = row.get('最新价', None)
                                item['price'] = float(price) if pd.notna(price) else None
                            items.append(item)
                        result[group][label] = items

        # 用向上突破榜（有涨跌幅和最新价）
        try:
            xstp = ak.stock_rank_xstp_ths(symbol="20日均线")
            if xstp is not None and not xstp.empty:
                _classify(xstp, code_col='股票代码', pct_col='涨跌幅', show_price=True)
        except Exception:
            pass

        return result

    def get_weekly_summary(self) -> dict:
        """
        获取市场统计（同花顺版）
        """
        result = {
            "指数表现": {},
            "个股统计": {"上涨家数": 0, "下跌家数": 0, "涨停": 0, "跌停": 0},
        }
        try:
            # 连续上涨 -> 上涨家数估
            up_df = ak.stock_rank_lxsz_ths()
            down_df = ak.stock_rank_lxxd_ths()
            if up_df is not None and not up_df.empty:
                result["个股统计"]["连续上涨股"] = len(up_df)
            if down_df is not None and not down_df.empty:
                result["个股统计"]["连续下跌股"] = len(down_df)

            # 创新高/新低
            try:
                high = ak.stock_rank_cxg_ths(symbol="创月新高")
                low = ak.stock_rank_cxd_ths(symbol="创月新低")
                if high is not None:
                    result["个股统计"]["创月新高"] = len(high)
                if low is not None:
                    result["个股统计"]["创月新低"] = len(low)
            except Exception:
                pass

            # 量价齐升/齐跌
            try:
                ljqs = ak.stock_rank_ljqs_ths()
                ljqd = ak.stock_rank_ljqd_ths()
                if ljqs is not None:
                    result["个股统计"]["量价齐升"] = len(ljqs)
                if ljqd is not None:
                    result["个股统计"]["量价齐跌"] = len(ljqd)
            except Exception:
                pass

            # 连续放量/缩量
            try:
                cxfl = ak.stock_rank_cxfl_ths()
                cxsl = ak.stock_rank_cxsl_ths()
                if cxfl is not None:
                    result["个股统计"]["持续放量"] = len(cxfl)
                if cxsl is not None:
                    result["个股统计"]["持续缩量"] = len(cxsl)
            except Exception:
                pass

        except Exception as e:
            print(f"⚠️ 获取周度复盘失败: {e}")

        return result
