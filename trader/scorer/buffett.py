#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 巴菲特完整评分：财务质地+增长趋势(80) + PE估值分位(20) = 100分

import sys
import os
import numpy as np
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trader.processor.feature import StockFeatureProcessor


class BuffettScorer:
    def __init__(self):
        self.proc = StockFeatureProcessor()

    def _trend(self, series, max_p):
        """计算指标趋势得分"""
        d = series.dropna()
        if len(d) < 2:
            return 0
        try:
            x = np.arange(len(d))
            y = d.values
            k = np.polyfit(x, y, 1)[0]
        except:
            return 0
        if k > 0:
            return max_p
        elif abs(k) < 0.002:
            return int(max_p * 0.7)
        return 0

    def get_ak_valuation_5y(self, code: str) -> pd.DataFrame:
        """从akshare stock_value_em 获取近5年 PE(TTM)、PB"""
        try:
            df = ak.stock_value_em(symbol=code)
            if df.empty:
                return pd.DataFrame()

            # 日期筛选近5年
            df["trade_date"] = pd.to_datetime(df["数据日期"])
            five_year_ago = datetime.now() - timedelta(days=5 * 365)
            df = df[df["trade_date"] >= five_year_ago]

            # 重命名并保留关键字段
            df = df.rename(columns={
                "PE(TTM)": "pe_ttm",
                "市净率": "pb"
            })[["trade_date", "pe_ttm", "pb"]]

            # 清洗异常值
            df = df.dropna()
            df = df[(df["pe_ttm"] > 0) & (df["pe_ttm"] < 300)]
            df = df.sort_values("trade_date").reset_index(drop=True)
            return df
        except Exception as e:
            print(f"估值数据获取异常: {e}")
            return pd.DataFrame()

    def calc_valuation_score(self, df: pd.DataFrame) -> tuple[int, str]:
        """PE历史分位打分 0~20分"""
        if df.empty or len(df) < 120:
            return 0, "估值数据不足"

        pe_series = df["pe_ttm"]
        current_pe = pe_series.iloc[-1]
        # 计算当前PE在5年历史分位
        percentile = (pe_series < current_pe).mean()

        if percentile < 0.3:
            return 20, "低估 ✅"
        elif percentile < 0.6:
            return 10, "合理 ⚖️"
        elif percentile < 0.8:
            return 5,  "偏高 ⚠️"
        else:
            return 0,  "高估 ❌"

    def score(self, code, years=5):
        print(f"[buffett] 开始评分: {code}")
        # 1. 通过 StockFeatureProcessor 逐年计算财务指标
        current_year = datetime.now().year
        years_list = list(range(current_year - years, current_year + 1))
        print(f"[buffett] 计算财务指标...")

        yearly = self.proc.calculate_yearly_features(code, years_list)
        if yearly.empty or len(yearly) < 3:
            print(f"[buffett] 财务指标计算失败或数据不足: {code}")
            return None
        print(f"[buffett] 财务指标完成, {len(yearly)} 行")

        # 只对数值列求均值，跳过 year/report_date 以及金额绝对值列
        num_cols = yearly.select_dtypes(include=[np.number]).columns
        skip_cols = {'year', '净利润', '营业收入', '应收账款', '经营活动现金流净额', '存货'}
        ratio_cols = [c for c in num_cols if c not in skip_cols]
        ind = yearly[ratio_cols].mean()

        # 2. 各项趋势得分
        trend = {
            "roe": self._trend(yearly["ROE"], 8),
            "profit": self._trend(yearly["净利润率"], 6),
            "cash": self._trend(yearly["经营现金流/净利润"], 6),
            "debt": self._trend(-yearly["资产负债率"], 4),
            "growth": self._trend(yearly["净利润增长率"], 6),
        }
        trend_total = sum(trend.values())

        # 3. 财务基础分
        base = 0
        if not np.isnan(ind["ROE"]):
            if ind["ROE"] >= 0.15:
                base += 14
            elif ind["ROE"] >= 0.10:
                base += 9
            elif ind["ROE"] >= 0.05:
                base += 4

        if not np.isnan(ind["净利润率"]):
            if ind["净利润率"] >= 0.15:
                base += 10
            elif ind["净利润率"] >= 0.08:
                base += 6
            elif ind["净利润率"] >= 0.03:
                base += 2

        if not np.isnan(ind["资产负债率"]):
            if ind["资产负债率"] < 0.4:
                base += 10
            elif ind["资产负债率"] < 0.6:
                base += 6

        if not np.isnan(ind["经营现金流/净利润"]):
            if ind["经营现金流/净利润"] >= 0.8:
                base += 10
            elif ind["经营现金流/净利润"] >= 0.5:
                base += 6

        if not np.isnan(ind["净利润增长率"]):
            if ind["净利润增长率"] > 0.1:
                base += 10
            elif ind["净利润增长率"] > 0:
                base += 5

        # 质地+趋势总分封顶80
        base_total = min(base + trend_total, 80)

        # 4. 估值打分 0~20
        print(f"[buffett] 获取估值数据...")
        val_df = self.get_ak_valuation_5y(code)
        val_score, val_label = self.calc_valuation_score(val_df)
        print(f"[buffett] 估值完成: {val_score}/20, {val_label}")

        # 最终总分
        total = min(base_total + val_score, 100)

        # 综合评级
        if total >= 80:
            rating = "✅ 卓越标的（长期持有）"
        elif total >= 65:
            rating = "✅ 优质公司"
        elif total >= 50:
            rating = "⚠️ 一般"
        else:
            rating = "❌ 回避"

        # 趋势标签
        t_lb = "上升" if trend_total >= 25 else "平稳" if trend_total >= 18 else "下降"

        return {
            "code": code,
            "name": self.proc.get_stock_name(code),
            "score": total,
            "base": base_total,
            "trend": trend_total,
            "val_score": val_score,
            "val_label": val_label,
            "trend_label": t_lb,
            "rating": rating,
            "indicators": ind,
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
    s = BuffettScorer()
    code = input("请输入股票代码：").strip()
    res = s.score(code)
    if res:
        s.print_score(res)
    else:
        print("评分失败，请检查股票代码或财报数据")