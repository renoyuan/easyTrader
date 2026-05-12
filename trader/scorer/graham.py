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


class GrahamScorer:
    def __init__(self):
        self.db = DBReader()

    # =========================
    # 趋势（弱化，只看稳定性）
    # =========================
    def _stability(self, series):
        s = series.dropna()
        if len(s) < 3:
            return 0

        # 波动率（越低越好）
        return 1 / (np.std(s) + 1e-6)

    # =========================
    # 获取估值（PE / PB）
    # =========================
    def get_valuation(self, code):

        df = ak.stock_value_em(symbol=code)

        if df.empty:
            return None

        df["date"] = pd.to_datetime(df["数据日期"])

        df = df.sort_values("date")

        pe = df["PE(TTM)"].dropna()
        pb = df["市净率"].dropna()

        if len(pe) == 0 or len(pb) == 0:
            return None

        return {
            "pe": pe.iloc[-1],
            "pb": pb.iloc[-1],
            "pe_min": pe.min(),
            "pb_min": pb.min(),
            "pe_pct": (pe < pe.iloc[-1]).mean(),
            "pb_pct": (pb < pb.iloc[-1]).mean()
        }

    # =========================
    # 格雷厄姆评分核心
    # =========================
    def score(self, code, years=5):

        income = self.db.get_financial_data(code, "income", years)
        balance = self.db.get_financial_data(code, "balance", years)
        cashflow = self.db.get_financial_data(code, "cashflow", years)

        if income.empty or balance.empty:
            return None

        yearly = FinancialProcessor().calculate_yearly_indicators(
            income, balance, cashflow
        )

        if yearly is None:
            return None

        ind = yearly.mean()

        score = 0

        # =========================
        # 1. PE（核心）
        # =========================
        val = self.get_valuation(code)

        if val:
            pe = val["pe"]

            if pe < 10:
                score += 30
            elif pe < 15:
                score += 20
            elif pe < 25:
                score += 10

            pb = val["pb"]

            if pb < 1:
                score += 25
            elif pb < 1.5:
                score += 15
            elif pb < 2:
                score += 5

        # =========================
        # 2. 盈利稳定性（不追求增长）
        # =========================
        if "净利润增长率" in yearly:

            growth = yearly["净利润增长率"]

            # 连续盈利比增长更重要
            positive_ratio = (growth > 0).mean()

            if positive_ratio > 0.8:
                score += 15
            elif positive_ratio > 0.6:
                score += 8

        # =========================
        # 3. 财务安全
        # =========================
        debt = ind.get("资产负债率", 1)

        if debt < 0.3:
            score += 20
        elif debt < 0.5:
            score += 10

        # =========================
        # 4. 流动资产安全边际（核心格雷厄姆）
        # =========================
        if "流动资产" in ind and "流动负债" in ind:

            net_working_capital = ind["流动资产"] - ind["流动负债"]

            if net_working_capital > 0:
                score += 10

        # =========================
        # 最终评分
        # =========================
        score = min(score, 100)

        if score >= 80:
            rating = "🔥 深度低估（格雷厄姆机会）"
        elif score >= 60:
            rating = "✅ 价值股"
        elif score >= 40:
            rating = "⚠️ 普通"
        else:
            rating = "❌ 高估"

        return {
            "code": code,
            "score": score,
            "pe": val["pe"] if val else None,
            "pb": val["pb"] if val else None,
            "rating": rating
        }
    def print_score(self, r):
        print(f"\n====== 📊 {r['code']} 巴菲特完整评分（质地+趋势+估值）======")
        print(f"质地趋势分：{r['base']}/80  |  估值分：{r['val_score']}/20")
        print(f"综合总分：{r['score']}/100")
        print(f"趋势状态：{r['trend_label']}  |  估值状态：{r['val_label']}")
        print(f"投资评级：{r['rating']}")
        print("-" * 50)
        for k, v in r["indicators"].items():
            if pd.isna(v):
                continue
            print(f"{k:<18} {v:.2%}")
        print("=" * 60)


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