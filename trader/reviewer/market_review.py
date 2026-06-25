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

    def get_index_performance(self) -> dict:
        """
        获取主要指数今日/近一周/近三月涨跌幅及今日成交量 vs 近3月均成交量。
        使用新浪日线接口（ak.stock_zh_index_daily），比东方财富实时行情更稳定。

        返回:
            {
                "上证指数": {
                    "today": +0.35,       # 今日涨跌幅%
                    "week_1": +1.02,      # 近一周涨跌幅%
                    "month_3": -2.15,     # 近3月涨跌幅%
                    "volume_today": 3500, # 今日成交量(亿)
                    "volume_avg_3m": 3800,# 近3月日均成交量(亿)
                },
                ...
            }
        """
        # 新浪指数代码
        index_codes = {
            "上证指数": "sh000001",
            "深证成指": "sz399001",
            "创业板指": "sz399006",
            "科创50": "sh000688",
        }
        result = {}
        for name, symbol in index_codes.items():
            try:
                df = ak.stock_zh_index_daily(symbol=symbol)
                if df is None or df.empty or len(df) < 2:
                    continue

                df = df.sort_values("date").reset_index(drop=True)
                closes = df["close"]
                volumes = df["volume"]

                # 今日涨跌幅 = (最新收盘 - 昨日收盘) / 昨日收盘
                today_pct = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100
                # 今日成交量
                volume_today = float(volumes.iloc[-1])

                # 近一周（5个交易日）
                week_pct = 0.0
                if len(closes) >= 6:
                    week_pct = (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100

                # 近三月（约60个交易日）
                month3_pct = 0.0
                if len(closes) >= 61:
                    month3_pct = (closes.iloc[-1] - closes.iloc[-61]) / closes.iloc[-61] * 100

                # 近3月日均成交量
                vol_avg_3m = 0.0
                if len(volumes) >= 60:
                    vol_avg_3m = float(volumes.iloc[-60:].mean())

                result[name] = {
                    "today": round(today_pct, 2),
                    "week_1": round(week_pct, 2),
                    "month_3": round(month3_pct, 2),
                    "volume_today": round(volume_today / 1e8, 2) if volume_today > 1e6 else round(volume_today, 2),
                    "volume_avg_3m": round(vol_avg_3m / 1e8, 2) if vol_avg_3m > 1e6 else round(vol_avg_3m, 2),
                }
            except Exception as e:
                print(f"⚠️ 获取 {name} 行情失败: {e}")
                continue

        return result

    # ── 原 get_index_summary 保留为情绪指标补充 ──
    def get_market_sentiment(self) -> dict:
        """
        获取市场情绪指标（连续涨跌、量价、创新高等）
        作为指数表现的补充。
        """

    def get_top_stocks(self, top_n: int = 5) -> dict:
        """
        获取涨幅榜/跌幅榜 Top5（使用同花顺接口）
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
                            stock_code = row.get(code_col, '')
                            item = {
                                'code': stock_code,
                                'name': row.get('股票简称', ''),
                                'pct_chg': float(row.get(pct_col, 0)),
                            }
                            # 补上近一周和近三月涨跌幅（通过新浪日线）
                            try:
                                daily = ak.stock_zh_a_daily(symbol=stock_code, start_date="", end_date="", adjust="qfq")
                                if daily is not None and not daily.empty:
                                    daily = daily.sort_values("date").reset_index(drop=True)
                                    closes = daily["close"]
                                    if len(closes) >= 6:
                                        w1 = (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100
                                        item['week_1'] = round(w1, 2)
                                    if len(closes) >= 61:
                                        m3 = (closes.iloc[-1] - closes.iloc[-61]) / closes.iloc[-61] * 100
                                        item['month_3'] = round(m3, 2)
                            except Exception:
                                pass
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
