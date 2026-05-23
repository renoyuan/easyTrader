#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PROJECT_NAME: F:\opensource\easyTrader\trader\scorer
CREATE_TIME: 2026-05-22
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno
note: 养老金现金流评分模型（权益永续债模型）V2
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import numpy as np
import pandas as pd
import akshare as ak

from trader.data.db import DBReader
from trader.processor.financial import FinancialProcessor


class PensionCashFlowScorer:

    """
    养老金现金流模型 V2
    ============================

    核心思想：
    - 用高分红稳定资产模拟“养老金永续债”
    - 不追求暴涨
    - 不追求赛道
    - 核心是：
        1. 股息
        2. 分红稳定
        3. 现金流
        4. 波动率
        5. 安全性

    适合：
    - 长江电力
    - 中国神华
    - 高速公路
    - 运营商
    - 银行股
    """

    def __init__(self):
        self.db = DBReader()

    # =========================
    # 获取估值 + 股息
    # =========================
    def get_valuation(self, code):

        result = {
            "pe": None,
            "pb": None,
            "dividend_yield": None,
            "missing_fields": []
        }

        try:

            df = ak.stock_value_em(symbol=code)

            if df.empty:
                result["missing_fields"].append("valuation_data")
                return result

            df["date"] = pd.to_datetime(df["数据日期"])
            df = df.sort_values("date")

            # -------------------------
            # PE
            # -------------------------
            if "PE(TTM)" in df.columns:

                pe = df["PE(TTM)"].dropna()

                if len(pe):
                    result["pe"] = pe.iloc[-1]
                else:
                    result["missing_fields"].append("PE")

            else:
                result["missing_fields"].append("PE")

            # -------------------------
            # PB
            # -------------------------
            if "市净率" in df.columns:

                pb = df["市净率"].dropna()

                if len(pb):
                    result["pb"] = pb.iloc[-1]
                else:
                    result["missing_fields"].append("PB")

            else:
                result["missing_fields"].append("PB")

            # -------------------------
            # 股息率
            # -------------------------
            dy_columns = [
                "股息率",
                "股息率(%)",
                "DV_RATIO",
                "DIVIDEND_YIELD"
            ]

            found = False

            for col in dy_columns:

                if col in df.columns:

                    dy = df[col].dropna()

                    if len(dy):

                        result["dividend_yield"] = float(dy.iloc[-1])

                        found = True
                        break

            if not found:
                result["missing_fields"].append("股息率")

            return result

        except Exception as e:

            print(f"valuation error: {e}")

            result["missing_fields"].append("valuation_exception")

            return result

    # =========================
    # 核心评分
    # =========================
    def score(self, code, years=5):

        income = self.db.get_financial_data(code, "income", years)
        balance = self.db.get_financial_data(code, "balance", years)
        cashflow = self.db.get_financial_data(code, "cashflow", years)

        if income.empty or balance.empty:
            return None

        yearly = FinancialProcessor().calculate_yearly_indicators(
            income,
            balance,
            cashflow
        )

        if yearly is None or yearly.empty:
            return None

        score = 0

        indicators = {}

        warnings = []

        ind = yearly.mean()

        # =========================
        # 获取估值
        # =========================
        val = self.get_valuation(code)

        warnings.extend(val["missing_fields"])

        # =========================
        # 1. 股息率（最高权重）
        # =========================
        dy = val.get("dividend_yield")

        indicators["股息率"] = dy

        if dy is None:

            warnings.append("股息率缺失 -> 评分可能严重失真")

        else:

            # 注意：
            # akshare 有些是 4.5
            # 有些是 0.045

            if dy < 1:
                dy = dy * 100

            if dy >= 7:
                score += 35

            elif dy >= 5:
                score += 28

            elif dy >= 4:
                score += 22

            elif dy >= 3:
                score += 15

            elif dy >= 2:
                score += 8

        # =========================
        # 2. ROE 稳定性
        # =========================
        if "ROE" in yearly.columns:

            roe = yearly["ROE"].dropna()

            if len(roe):

                roe_mean = roe.mean()
                roe_std = roe.std()

                indicators["ROE"] = roe_mean
                indicators["ROE波动"] = roe_std

                if roe_mean > 0.15:
                    score += 15

                elif roe_mean > 0.10:
                    score += 10

                elif roe_mean > 0.08:
                    score += 5

                # 稳定性
                if roe_std < 0.03:
                    score += 10

                elif roe_std < 0.05:
                    score += 5

        else:
            warnings.append("ROE缺失")

        # =========================
        # 3. 经营现金流稳定性
        # =========================
        if "经营现金流" in yearly.columns:

            ocf = yearly["经营现金流"].dropna()

            if len(ocf):

                positive_ratio = (ocf > 0).mean()

                indicators["经营现金流稳定性"] = positive_ratio

                if positive_ratio >= 1:
                    score += 20

                elif positive_ratio >= 0.8:
                    score += 12

        else:
            warnings.append("经营现金流缺失")

        # =========================
        # 4. 负债率
        # =========================
        debt = ind.get("资产负债率")

        indicators["资产负债率"] = debt

        if debt is not None:

            if debt < 0.40:
                score += 10

            elif debt < 0.60:
                score += 5

        # =========================
        # 5. 利润稳定性
        # =========================
        if "净利润" in yearly.columns:

            profit = yearly["净利润"].dropna()

            if len(profit):

                volatility = np.std(profit) / (np.mean(profit) + 1e-6)

                indicators["利润波动率"] = volatility

                if volatility < 0.15:
                    score += 10

                elif volatility < 0.30:
                    score += 5

        # =========================
        # 6. 估值（弱化）
        # =========================
        pe = val.get("pe")
        pb = val.get("pb")

        indicators["PE"] = pe
        indicators["PB"] = pb

        if pe is not None:

            if pe < 15:
                score += 5

            elif pe < 20:
                score += 3

        if pb is not None:

            if pb < 2:
                score += 5

            elif pb < 3:
                score += 3

        # =========================
        # 可信度
        # =========================
        critical_fields = [
            "股息率"
        ]

        missing_critical = [
            x for x in critical_fields
            if x in warnings
        ]

        if len(missing_critical) == 0:
            confidence = "HIGH"

        elif len(missing_critical) == 1:
            confidence = "LOW"

        else:
            confidence = "VERY LOW"

        # =========================
        # 最终评级
        # =========================
        score = min(score, 100)

        if score >= 85:
            rating = "🏦 养老金永续债"

        elif score >= 70:
            rating = "✅ 优质现金流资产"

        elif score >= 55:
            rating = "⚠️ 普通红利资产"

        else:
            rating = "❌ 不适合作为养老金资产"

        return {
            "code": code,
            "score": score,
            "rating": rating,
            "confidence": confidence,
            "warnings": warnings,
            "indicators": indicators
        }

    # =========================
    # 打印结果
    # =========================
    def print_score(self, r):

        print(f"\n====== 🏦 {r['code']} 养老金现金流评分 ======")

        print(f"综合总分：{r['score']}/100")

        print(f"投资评级：{r['rating']}")

        print(f"评分可信度：{r['confidence']}")

        print("-" * 60)

        # -------------------------
        # 警告
        # -------------------------
        if r["warnings"]:

            print("⚠️ 数据警告：")

            for w in r["warnings"]:
                print(f"  - {w}")

            print("-" * 60)

        # -------------------------
        # 指标
        # -------------------------
        for k, v in r["indicators"].items():

            if v is None or pd.isna(v):
                continue

            if isinstance(v, (int, float)):

                if (
                    "率" in k
                    or "ROE" in k
                    or "波动" in k
                    or "稳定性" in k
                ):

                    print(f"{k:<20} {v:.2%}")

                else:
                    print(f"{k:<20} {v:.2f}")

        print("=" * 60)


if __name__ == "__main__":

    s = PensionCashFlowScorer()

    code = input("请输入股票代码：").strip()

    res = s.score(code)

    if res:
        s.print_score(res)
    else:
        print("评分失败，请检查股票代码或财报数据")