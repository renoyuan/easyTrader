"""
#!/usr/bin/env python
-*- coding: utf-8 -*-
PROJECT_NAME: F:\opensource\easyTrader\trader\scorer
CREATE_TIME: 2026-05-12 
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno 
note:  格雷厄姆评分模型
"""

import sys,os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
print(sys.path)
import numpy as np
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trader.data.db import DBReader
from trader.processor.financial import FinancialProcessor


class XuXiangScorer:
    def __init__(self):
        self.db = DBReader()

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
    # 主评分
    # =========================
    def score(self, code, years=1):

        # 👉 徐翔只看行情（不看财报）
        price = self.db.get_financial_data(code, "price", years)

        if price.empty:
            return None

        # 假设字段
        close = price["close"]
        volume = price["volume"]

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
        if vol < 0.02:
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

        return {
            "code": code,
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

    s = GrahamScorer()
    code = input("请输入股票代码：").strip()
    res = s.score(code)
    if res:
        print(f"\n====== 📊 {res['code']} 格雷厄姆评分 ======")
        print(f"综合总分：{res['score']}/100")
        print(f"PE：{res['pe']}")
        print(f"PB：{res['pb']}")
        print(f"投资评级：{res['rating']}")
    else:
        print("评分失败，请检查股票代码或财报数据")