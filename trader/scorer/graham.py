#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  格雷厄姆评分模型

import sys, os
# 注：sys.path 应在入口统一处理，此处保留兼容旧调用方式
import numpy as np
import pandas as pd
from datetime import datetime

from trader.processor.feature import StockFeatureProcessor


class GrahamScorer:
    def __init__(self):
        self.proc = StockFeatureProcessor()

    # =========================
    # 获取估值（PE / PB）
    # =========================
    def get_valuation(self, code):
        pe, pb = self.proc.calculate_pe_pb(code)
        if pe is None or pb is None:
            return None
        return {
            "pe": pe,
            "pb": pb,
        }

    # =========================
    # 格雷厄姆评分核心
    # =========================
    def score(self, code, years=5):

        print(f"[graham] 开始评分: {code}")
        current_year = datetime.now().year
        years_list = list(range(current_year - years, current_year + 1))
        print(f"[graham] 计算财务指标...")

        yearly = self.proc.calculate_yearly_features(code, years_list)

        if yearly.empty:
            print(f"[graham] 财务指标数据不足: {code}")
            return None
        print(f"[graham] 财务指标完成, {len(yearly)} 行")

        num_cols = yearly.select_dtypes(include=[np.number]).columns
        ind = yearly[num_cols].mean()

        score = 0

        # =========================
        # 1. PE / PB 估值（核心）
        # =========================
        print(f"[graham] 获取估值...")
        val = self.get_valuation(code)
        has_val = val is not None
        print(f"[graham] 估值完成: PE={val.get('pe') if has_val else 'N/A'}")

        if has_val:
            pe = val["pe"]
            if pe is not None and pe > 0:
                if pe < 10:
                    score += 30
                elif pe < 15:
                    score += 20
                elif pe < 25:
                    score += 10

            pb = val["pb"]
            if pb is not None and pb > 0:
                if pb < 1:
                    score += 25
                elif pb < 1.5:
                    score += 15
                elif pb < 2:
                    score += 5
        # =========================
        # 2. 盈利稳定性
        # =========================
        if "净利润增长率" in yearly.columns:
            growth = yearly["净利润增长率"].dropna()
            if len(growth) > 0:
                positive_ratio = (growth > 0).mean()
            if positive_ratio > 0.8:
                score += 15
            elif positive_ratio > 0.6:
                score += 8

        # =========================
        # 3. 财务安全（低负债）
        # =========================
        debt = ind.get("资产负债率")
        if debt is not None and not np.isnan(debt):
            if debt < 0.3:
                score += 20
            elif debt < 0.5:
                score += 10

        # =========================
        # 4. 流动比率安全边际
        # =========================
        detailed = self.proc.calculate_financial_indicators(code, years_list)
        cr = detailed.get("流动比率", np.nan)
        if not np.isnan(cr):
            if cr > 1.5:
                score += 10
            elif cr > 1.0:
                score += 5

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
            "name": self.proc.get_stock_name(code),
            "score": score,
            "pe": val["pe"] if has_val else None,
            "pb": val["pb"] if has_val else None,
            "rating": rating
        }

    def print_score(self, r):
        print(f"\n====== 📊 {r['code']} 格雷厄姆评分 ======")
        print(f"综合总分：{r['score']}/100")
        print(f"PE：{r['pe']}")
        print(f"PB：{r['pb']}")
        print(f"投资评级：{r['rating']}")
        print("=" * 60)


if __name__ == "__main__":
    s = GrahamScorer()
    code = input("请输入股票代码：").strip()
    res = s.score(code)
    if res:
        s.print_score(res)
    else:
        print("评分失败，请检查股票代码或财报数据")
