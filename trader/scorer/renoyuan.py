#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

#!/usr/bin/env python
"""
PROJECT_NAME: F:\opensource\easyTrader\trader\scorer
CREATE_TIME: 2026-05-22
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno
note: renoyuan 核心评分模型（红利低波/现金流永续）
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime

from trader.processor.feature import StockFeatureProcessor


class RenoyuanScorer:

    """
    renoyuan 核心评分模型
    =====================

    核心思想：
    - 用高分红稳定资产模拟"养老金永续债"
    - 不追求暴涨，不追求赛道
    - 核心评分因子：
        1. 股息率（最高权重 35 分）
        2. ROE 稳定性（25 分）
        3. 经营现金流稳定性（20 分）
        4. 低负债率（10 分）
        5. 利润稳定性（10 分）
        6. 低估值加分（10 分）

    适合：
    - 长江电力
    - 中国神华
    - 高速公路
    - 运营商
    - 银行股
    """

    def __init__(self):
        self.proc = StockFeatureProcessor()

    # =========================
    # 通过 feature 获取估值 + 股息
    # =========================
    def get_valuation(self, code):

        result = {
            "pe": None,
            "pb": None,
            "dividend_yield": None,
            "missing_fields": [],
        }

        print(f"[renoyuan] 获取股息率...")
        dy = self.proc.calculate_dividend_yield(code)
        if not np.isnan(dy):
            result["dividend_yield"] = dy
        else:
            result["missing_fields"].append("股息率")

        print(f"[renoyuan] 获取 PE/PB...")
        pe, pb = self.proc.calculate_pe_pb(code)
        if pe is not None:
            result["pe"] = pe
        else:
            result["missing_fields"].append("PE")
        if pb is not None:
            result["pb"] = pb
        else:
            result["missing_fields"].append("PB")

        print(f"[renoyuan] 数据完成: PE={result['pe']}, PB={result['pb']}, 股息率={result['dividend_yield']}")
        return result

    # =========================
    # 核心评分
    # =========================
    def score(self, code, years=5):

        print(f"[renoyuan] 开始评分: {code}")

        # ---- 通过 StockFeatureProcessor 拿财务指标 ----
        current_year = datetime.now().year
        years_list = list(range(current_year - years, current_year + 1))
        print(f"[renoyuan] 计算财务指标: {years_list}")

        yearly = self.proc.calculate_yearly_features(code, years_list)
        if yearly.empty or len(yearly) < 2:
            print(f"[renoyuan] 财务指标数据不足: {code}")
            return None
        print(f"[renoyuan] 财务指标完成, {len(yearly)} 行")

        # ---- 估值 + 股息 ----
        print(f"[renoyuan] 获取估值...")
        val = self.get_valuation(code)
        print(f"[renoyuan] 估值完成: PE={val.get('pe')}, PB={val.get('pb')}, 股息率={val.get('dividend_yield')}")

        score = 0
        indicators = {}
        warnings = list(val["missing_fields"])

        # ---- 均值指标 ----
        num_cols = yearly.select_dtypes(include=[np.number]).columns
        ind = yearly[num_cols].mean()

        # =========================
        # 1. 股息率（最高权重）
        # =========================
        dy = val.get("dividend_yield")
        indicators["股息率"] = dy

        if dy is None:
            warnings.append("股息率缺失 -> 评分可能严重失真")
        else:
            # akshare 有些返回 4.5（%），有些返回 0.045
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

                if roe_std < 0.03:
                    score += 10
                elif roe_std < 0.05:
                    score += 5
        else:
            warnings.append("ROE缺失")

        # =========================
        # 3. 经营现金流稳定性
        # =========================
        # feature 中经营现金流列名可能是 "经营现金流/净利润"
        ocf_col = None
        for col in ["经营现金流", "经营现金流/净利润", "经营活动现金流", "OCF"]:
            if col in yearly.columns:
                ocf_col = col
                break

        if ocf_col:
            ocf = yearly[ocf_col].dropna()
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
        if debt is not None and not np.isnan(debt):
            if debt < 0.40:
                score += 10
            elif debt < 0.60:
                score += 5

        # =========================
        # 5. 利润稳定性
        # =========================
        if "净利润增长率" in yearly.columns:
            profit_g = yearly["净利润增长率"].dropna()
            if len(profit_g):
                volatility = profit_g.std()
                indicators["利润波动率"] = volatility
                if volatility < 0.15:
                    score += 10
                elif volatility < 0.30:
                    score += 5

        # =========================
        # 6. 估值加分（弱化）
        # =========================
        pe = val.get("pe")
        pb = val.get("pb")
        indicators["PE"] = pe
        indicators["PB"] = pb

        if pe is not None and pe > 0:
            if pe < 15:
                score += 5
            elif pe < 20:
                score += 3

        if pb is not None and pb > 0:
            if pb < 2:
                score += 5
            elif pb < 3:
                score += 3

        # =========================
        # 可信度
        # =========================
        confidence = "HIGH" if "股息率" not in warnings else "LOW"

        # =========================
        # 最终评级
        # =========================
        score = min(score, 100)

        if score >= 85:
            rating = "🏦 优质红利永续"
        elif score >= 70:
            rating = "✅ 优质现金流资产"
        elif score >= 55:
            rating = "⚠️ 普通红利资产"
        else:
            rating = "❌ 不适合永续持有"

        return {
            "code": code,
            "name": self.proc.get_stock_name(code),
            "score": score,
            "rating": rating,
            "confidence": confidence,
            "warnings": warnings,
            "indicators": indicators,
        }

    # =========================
    # 打印结果
    # =========================
    def print_score(self, r):
        print(f"\n====== 🏦 {r['code']} renoyuan核心评分 ======")
        print(f"综合总分：{r['score']}/100")
        print(f"投资评级：{r['rating']}")
        print(f"评分可信度：{r['confidence']}")
        if r["warnings"]:
            print("⚠️ 数据警告：")
            for w in r["warnings"]:
                print(f"  - {w}")
        print("-" * 60)
        for k, v in r["indicators"].items():
            if v is None or pd.isna(v):
                continue
            if "率" in k or "ROE" in k or "波动" in k or "稳定性" in k:
                print(f"{k:<20} {v:.2%}")
            else:
                print(f"{k:<20} {v:.2f}")
        print("=" * 60)


if __name__ == "__main__":
    s = RenoyuanScorer()
    code = input("请输入股票代码：").strip()
    res = s.score(code)
    if res:
        s.print_score(res)
    else:
        print("评分失败，请检查股票代码或财报数据")
