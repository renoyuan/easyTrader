#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

"""
#!/usr/bin/env python
-*- coding: utf-8 -*-
PROJECT_NAME: F:\opensource\easyTrader\trader\scorer
CREATE_TIME: 2026-05-12 
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno 
note:  格雷厄姆评分模型
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from trader.data.statement import StatementDownload


class XuXiangScorer:
    """
    徐翔风格评分
    ============
    基于 K 线行情数据的短期趋势交易评分系统，
    考量动量、成交量、连续上涨、新高突破、波动率等因素。
    """
    def __init__(self, data_service=None):
        self.data_service = data_service or StatementDownload()

    # =========================
    # 趋势强度（核心）
    # =========================
    def _momentum(self, close):
        c = close.dropna()
        if len(c) < 10:
            return 0

        return (c.iloc[-1] / c.iloc[-10] - 1) * 100

    # =========================
    # 成交量放大
    # =========================
    def _volume_score(self, volume):
        v = volume.dropna()
        if len(v) < 10:
            return 0

        recent = v.iloc[-1]
        avg = v.iloc[-10:].mean()

        if avg == 0:
            return 0

        ratio = recent / avg

        if ratio > 3:
            return 25
        elif ratio > 2:
            return 15
        elif ratio > 1.5:
            return 8
        return 0

    # =========================
    # 连续上涨（情绪）
    # =========================
    def _consecutive_up(self, close):
        c = close.dropna()
        if len(c) < 5:
            return 0

        up_days = (c.pct_change() > 0).tail(5).sum()

        if up_days >= 4:
            return 20
        elif up_days >= 3:
            return 10
        return 0

    # =========================
    # 主评分（使用外部K线数据）
    # =========================
    def score_from_kline(self, code, kline_df):
        """
        使用已加载的 K 线 DataFrame 进行评分（不回测中专用，避免评分器自行拉取数据）
        """
        print(f"[xuxiang] 评分(使用回测数据): {code}")
        if kline_df.empty:
            return None

        close = kline_df["close"] if "close" in kline_df else kline_df.iloc[:, 1]
        volume = kline_df["volume"] if "volume" in kline_df else kline_df.iloc[:, 4]

        return self._calc_score(code, close, volume)

    # =========================
    # 主评分（原始接口）
    # =========================
    def score(self, code, years=1):

        print(f"[xuxiang] 开始评分: {code}")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        print(f"[xuxiang] 获取K线数据...")

        kline = self.data_service.get_kline_df(code, start_str, end_str)
        if kline.empty:
            print(f"[xuxiang] 无K线数据: {code}")
            return None
        print(f"[xuxiang] K线数据获取完成, {len(kline)} 行")

        close = kline["close"] if "close" in kline else kline.iloc[:, 1]
        volume = kline["volume"] if "volume" in kline else kline.iloc[:, 4]

        return self._calc_score(code, close, volume)

    def _calc_score(self, code, close, volume):
        """核心评分计算（提取为独立方法供 score 和 score_from_kline 共用）"""
        score = 0

        # 1. 动量（核心）
        momentum = self._momentum(close)
        if momentum > 15:
            score += 25
        elif momentum > 8:
            score += 15
        elif momentum > 3:
            score += 8

        # 2. 成交量
        score += self._volume_score(volume)

        # 3. 连续上涨
        score += self._consecutive_up(close)

        # 4. 是否突破（新高）
        if close.iloc[-1] == close.max():
            score += 20

        # 5. 波动（强势但不崩）
        vol = close.pct_change().std()
        if not np.isnan(vol) and vol < 0.02:
            score += 10

        score = min(score, 100)

        # =========================
        # 评级
        # =========================
        if score >= 80:
            rating = "🔥 强势龙头（可参与）"
        elif score >= 60:
            rating = "⚡ 中等趋势（观察）"
        elif score >= 40:
            rating = "⚠️ 弱势震荡"
        else:
            rating = "❌ 无交易价值"

        # 从 feature 获取名称
        from trader.processor.feature import StockFeatureProcessor
        stock_name = StockFeatureProcessor().get_stock_name(code)

        return {
            "code": code,
            "name": stock_name,
            "score": score,
            "momentum": momentum,
            "rating": rating
        }

    def print_score(self, r):
        print(f"\n====== 📊 {r['code']} 徐翔风格评分 ======")
        print(f"趋势动量：{r['momentum']:.2f}%")
        print(f"综合评分：{r['score']}/100")
        print(f"交易评级：{r['rating']}")
        print("=" * 50)

if __name__ == "__main__":

    s = XuXiangScorer()
    code = input("请输入股票代码：").strip()
    res = s.score(code)
    if res:
        s.print_score(res)
    else:
        print("评分失败，请检查股票代码")
