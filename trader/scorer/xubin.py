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
CREATE_TIME: 2026-05-28
E_MAIL: renoyuan@foxmail.com
AUTHOR: renoyuan
note: xubin 财报排雷模型（财务造假风险筛查 + 财务健康度打分）
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime

from trader.processor.feature import StockFeatureProcessor


class XuBinScorer:

    """
    XuBin 财报排雷模型
    =====================

    核心思想：
    - 专门识别财务造假、虚增收入、白条利润、资金链风险
    - 不预测涨幅，只做“排雷”，排除高危公司
    - 核心评分因子：
        1. 利润含金量（经营现金流/净利润）30分
        2. 收入真实性（应收账款/营收）25分
        3. 毛利率合理性（与行业对比）15分
        4. 存货健康度（周转+减值）15分
        5. 关联交易与负债异常 15分

    适合：
    - 全行业排雷
    - 避开财务造假、暴雷股
    - 价值投资前财务体检
    """

    def __init__(self):
        self.proc = StockFeatureProcessor()

    # =========================
    # 获取基础财务数据
    # =========================
    def get_basic_finance(self, code):
        result = {
            "pe": None,
            "pb": None,
            "missing_fields": [],
        }

        try:
            pe, pb = self.proc.calculate_pe_pb(code)
            result["pe"] = pe if pe and not np.isnan(pe) else None
            result["pb"] = pb if pb and not np.isnan(pb) else None
        except:
            result["missing_fields"].append("PE/PB获取失败")

        return result

    # =========================
    # 核心排雷评分
    # =========================
    def score(self, code, years=5, as_of_date=None):

        print(f"[xubin] 开始排雷评分: {code}")

        ref_date = as_of_date or datetime.now()
        current_year = ref_date.year if hasattr(ref_date, 'year') else ref_date.year
        years_list = list(range(current_year - years, current_year + 1))
        print(f"[xubin] 读取近{years}年财报: as_of={ref_date} years={years_list}")

        yearly = self.proc.calculate_yearly_features(code, years_list)
        if yearly.empty or len(yearly) < 3:
            print(f"[xubin] 财报数据不足: {code}")
            return None
        print(f"[xubin] 财报数据读取完成, {len(yearly)} 期")

        val = self.get_basic_finance(code)
        score = 0
        indicators = {}
        warnings = []
        high_risk = False

        # 年度均值
        num_cols = yearly.select_dtypes(include=[np.number]).columns
        ind = yearly[num_cols].mean()

        # =========================
        # 1. 利润含金量（30分）
        # 经营现金流净额 / 净利润 ≥1 才健康
        # =========================
        ocf = None
        net_profit = None
        cfr = None

        if "经营活动现金流净额" in yearly.columns and "净利润" in yearly.columns:
            with np.errstate(divide='ignore', invalid='ignore'):
                ocf_series = yearly["经营活动现金流净额"]
                np_series = yearly["净利润"]
                valid = (np_series != 0) & np_series.notna()
                if valid.sum() > 0:
                    cfr = (ocf_series[valid] / np_series[valid]).mean()

        indicators["利润含金量(现金流/净利润)"] = cfr

        if cfr is not None and not np.isnan(cfr):
            if cfr >= 1.0:
                score += 30
            elif cfr >= 0.7:
                score += 20
            elif cfr >= 0.4:
                score += 10
            else:
                warnings.append("利润含金量极低，疑似纸面利润")
                high_risk = True
        else:
            warnings.append("利润含金量数据缺失")

        # =========================
        # 2. 收入真实性（25分）
        # 应收账款/营收 越低越好
        # =========================
        ar_ratio = None
        if "应收账款" in yearly.columns and "营业收入" in yearly.columns:
            with np.errstate(divide='ignore', invalid='ignore'):
                ar = yearly["应收账款"]
                rev = yearly["营业收入"]
                valid = rev > 0
                if valid.sum() > 0:
                    ar_ratio = (ar[valid] / rev[valid]).mean()

        indicators["应收账款/营业收入"] = ar_ratio

        if ar_ratio is not None and not np.isnan(ar_ratio):
            if ar_ratio < 0.20:
                score += 25
            elif ar_ratio < 0.35:
                score += 15
            elif ar_ratio < 0.50:
                score += 5
            else:
                warnings.append("应收账款过高，收入疑似虚增")
                high_risk = True
        else:
            warnings.append("应收账款数据缺失")

        # =========================
        # 3. 毛利率合理性（15分）
        # 异常高/低都有风险
        # =========================
        gross = ind.get("毛利率")
        indicators["毛利率"] = gross

        if gross is not None and not np.isnan(gross):
            if 0.15 < gross < 0.60:
                score += 15
            elif gross > 0.70 or gross < 0.05:
                warnings.append("毛利率异常，疑似造假")
                high_risk = True
            else:
                score += 7
        else:
            warnings.append("毛利率数据缺失")

        # =========================
        # 4. 存货健康度（15分）
        # 不积压、不计提减值就是风险
        # =========================
        inventory_turnover = ind.get("存货周转率")
        indicators["存货周转率"] = inventory_turnover

        if inventory_turnover is not None and not np.isnan(inventory_turnover):
            if inventory_turnover >= 2:
                score += 15
            elif inventory_turnover >= 0.5:
                score += 8
            else:
                warnings.append("存货严重积压，未计提减值风险")
        else:
            score += 8  # 无存货行业默认安全

        # =========================
        # 5. 负债与关联交易（15分）
        # 资产负债率过高 → 资金链风险
        # =========================
        debt = ind.get("资产负债率")
        indicators["资产负债率"] = debt

        if debt is not None and not np.isnan(debt):
            if debt < 0.60:
                score += 15
            elif debt < 0.75:
                score += 7
            else:
                warnings.append("负债率过高，偿债压力大")
                high_risk = True
        else:
            warnings.append("资产负债率数据缺失")

        # =========================
        # 最终评分（0~100）
        # =========================
        score = min(score, 100)
        score = max(score, 0)

        if high_risk:
            rating = "🚨 财务高危（禁止买入）"
        elif score >= 85:
            rating = "✅ 财务极健康"
        elif score >= 70:
            rating = "🟢 财务健康"
        elif score >= 55:
            rating = "⚠️ 财务一般"
        else:
            rating = "🔴 财务较差"

        confidence = "HIGH" if len(warnings) < 2 else "LOW"

        return {
            "code": code,
            "name": self.proc.get_stock_name(code),
            "score": score,
            "rating": rating,
            "confidence": confidence,
            "warnings": warnings,
            "high_risk": high_risk,
            "indicators": indicators,
        }

    # =========================
    # 打印结果（完全同格式）
    # =========================
    def print_score(self, r):
        print(f"\n====== 🚨 {r['code']} XUBIN财报排雷评分 ======")
        print(f"财务健康分：{r['score']}/100")
        print(f"风险评级：{r['rating']}")
        print(f"评分可信度：{r['confidence']}")
        if r["warnings"]:
            print("⚠️ 风险警告：")
            for w in r["warnings"]:
                print(f"  - {w}")
        print("-" * 60)
        for k, v in r["indicators"].items():
            if v is None or pd.isna(v):
                continue
            if "率" in k or "毛利率" in k:
                print(f"{k:<28} {v:.2%}")
            elif "含金量" in k:
                print(f"{k:<28} {v:.2f}")
            else:
                print(f"{k:<28} {v:.2f}")
        print("=" * 60)


if __name__ == "__main__":
    s = XuBinScorer()
    code = input("请输入股票代码：").strip()
    res = s.score(code)
    if res:
        s.print_score(res)
    else:
        print("评分失败，请检查股票代码或财报数据")
