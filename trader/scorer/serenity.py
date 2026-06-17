#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-07-11
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note: 白毛女（Serenity）供应链卡位评分模型——从财务数据反推产业链稀缺性与定价权

"""
PROJECT_NAME: easyTrader
CREATE_TIME: 2026-07-11
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno
note: 白毛女（Serenity）供应链卡位评分模型——从财务数据反推产业链稀缺性与定价权
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime

from trader.processor.feature import StockFeatureProcessor


class SerenityScorer:

    """
    白毛女（Serenity）供应链卡位评分模型
    ======================================

    核心思想（源自 Serenity / @aleabitoreddit 供应链研究方法论）：
    - 不只看公司好不好，先看产业链哪个环节最稀缺
    - 稀缺 = 低供应商数量 + 长认证周期 + 高扩产壁垒 + 客户无法绕过
    - 映射到财务：高毛利率 + 高ROE + 持续高资本开支 + 低资产周转降速
    - 找的不是"好公司"，而是"供应链上别人绕不开的那一环"

    核心评分因子：
        1. 定价权（高毛利率 + 高净利率 + 趋势稳定）30分
        2. 资本壁垒（持续高资本开支 + Capex/折旧比）20分
        3. 稀缺性信号（ROE高低 + 高毛利下的低周转）20分
        4. 扩张质量（营收增长 + 利润增长 + 现金流匹配）20分
        5. 财务健康（低负债 + 健康现金流）10分

    适合：
    - AI 产业链（芯片、封装、设备、材料、散热、光模块）
    - 半导体设备和材料
    - 精密制造/高端零部件
    - 专精特新"卡脖子"环节
    - 赛道型供应链投资
    """

    def __init__(self):
        self.proc = StockFeatureProcessor()

    # =========================
    # 获取估值 + 股息
    # =========================
    def get_valuation(self, code):

        result = {
            "pe": None,
            "pb": None,
            "dividend_yield": None,
            "missing_fields": [],
        }

        print(f"[serenity] 获取股息率...")
        dy = self.proc.calculate_dividend_yield(code)
        if not np.isnan(dy):
            result["dividend_yield"] = dy
        else:
            result["missing_fields"].append("股息率")

        print(f"[serenity] 获取 PE/PB...")
        pe, pb = self.proc.calculate_pe_pb(code)
        if pe is not None:
            result["pe"] = pe
        else:
            result["missing_fields"].append("PE")
        if pb is not None:
            result["pb"] = pb
        else:
            result["missing_fields"].append("PB")

        print(f"[serenity] 数据完成: PE={result['pe']}, PB={result['pb']}, 股息率={result['dividend_yield']}")
        return result

    # =========================
    # 核心评分
    # =========================
    def score(self, code, years=5):

        print(f"[serenity] 开始供应链卡位评分: {code}")

        # ---- 财务指标 ----
        current_year = datetime.now().year
        years_list = list(range(current_year - years, current_year + 1))
        print(f"[serenity] 计算财务指标: {years_list}")

        yearly = self.proc.calculate_yearly_features(code, years_list)
        if yearly.empty or len(yearly) < 2:
            print(f"[serenity] 财务指标数据不足: {code}")
            return None
        print(f"[serenity] 财务指标完成, {len(yearly)} 行")

        # ---- 估值 ----
        print(f"[serenity] 获取估值...")
        val = self.get_valuation(code)
        print(f"[serenity] 估值完成")

        score = 0
        indicators = {}
        warnings = list(val["missing_fields"])

        # ---- 均值指标 ----
        num_cols = yearly.select_dtypes(include=[np.number]).columns
        ind = yearly[num_cols].mean()

        # ==============================
        # 1. 定价权（毛利率+净利率+稳定性）30分
        # ==============================
        gross = ind.get("毛利率") if "毛利率" in ind else None
        net_margin = ind.get("净利率") if "净利率" in yearly.columns else None
        indicators["毛利率(均值)"] = gross
        indicators["净利率(均值)"] = net_margin

        # —— 高毛利率说明有定价权 ——
        if gross is not None and not np.isnan(gross):
            if gross >= 0.60:
                gross_score = 15
                indicators["定价权等级"] = "极高（强护城河）"
            elif gross >= 0.45:
                gross_score = 12
                indicators["定价权等级"] = "高（品牌/技术溢价）"
            elif gross >= 0.30:
                gross_score = 8
                indicators["定价权等级"] = "中上（有一定壁垒）"
            elif gross >= 0.20:
                gross_score = 5
                indicators["定价权等级"] = "中等（竞争较激烈）"
            else:
                gross_score = 2
                indicators["定价权等级"] = "低（商品化/红海）"

            # 毛利率稳定性加分（波动小说明客户粘性强）
            if "毛利率" in yearly.columns:
                gross_std = yearly["毛利率"].dropna().std()
                indicators["毛利率波动率"] = gross_std
                if gross_std < 0.03:
                    gross_score += 5  # 极其稳定
                elif gross_std < 0.06:
                    gross_score += 3
                elif gross_std < 0.10:
                    gross_score += 1
        else:
            gros_score = 0
            warnings.append("毛利率数据缺失")

        # —— 净利率越高，利润质量越好 ——
        if net_margin is not None and not np.isnan(net_margin):
            if net_margin >= 0.25:
                net_score = 10
            elif net_margin >= 0.15:
                net_score = 7
            elif net_margin >= 0.08:
                net_score = 4
            elif net_margin >= 0.03:
                net_score = 2
            else:
                net_score = 0
        else:
            net_score = 0

        pricing_score = gross_score + net_score
        # 定价权总分封顶 30
        score += min(pricing_score, 30)

        # ==============================
        # 2. 资本壁垒（Capex强度）20分
        # ==============================
        # 寻找资本开支相关列
        capex_col = None
        for col in ["购建固定资产、无形资产和其他长期资产支付的现金",
                     "资本支出", "购建固定资产无形资产", "Capex",
                     "投资活动现金流出"]:
            if col in yearly.columns:
                capex_col = col
                break

        if capex_col:
            capex_series = yearly[capex_col].dropna()
            # 判断折旧摊销列
            dep_col = None
            for dcol in ["折旧与摊销", "折旧", "固定资产折旧、油气资产折耗、生产性生物资产折旧"]:
                if dcol in yearly.columns:
                    dep_col = dcol
                    break

            # Capex/营收比 —— 资本密集度
            if "营业收入" in yearly.columns:
                rev_series = yearly["营业收入"]
                valid = rev_series > 0
                if valid.sum() > 0:
                    capex_ratio = (capex_series[valid] / rev_series[valid]).mean()
                    indicators["资本开支/营收"] = capex_ratio
                    if capex_ratio >= 0.20:
                        score += 10
                    elif capex_ratio >= 0.12:
                        score += 7
                    elif capex_ratio >= 0.06:
                        score += 4
                    elif capex_ratio >= 0.03:
                        score += 2

            # Capex/折旧比 —— 是否在积极扩产
            if dep_col:
                dep_series = yearly[dep_col].dropna()
                if len(capex_series) and len(dep_series):
                    # 取最近2年均值
                    capex_latest = capex_series.tail(2).mean()
                    dep_latest = dep_series.tail(2).mean()
                    if dep_latest > 0:
                        capex_dep_ratio = capex_latest / dep_latest
                        indicators["资本开支/折旧"] = capex_dep_ratio
                        if capex_dep_ratio >= 2.5:
                            score += 10
                            indicators["扩产状态"] = "激进扩产"
                        elif capex_dep_ratio >= 1.8:
                            score += 7
                            indicators["扩产状态"] = "积极扩产"
                        elif capex_dep_ratio >= 1.2:
                            score += 4
                            indicators["扩产状态"] = "稳定维护"
                        elif capex_dep_ratio >= 0.8:
                            score += 2
                            indicators["扩产状态"] = "维护不足"
                        else:
                            indicators["扩产状态"] = "资本开支不足"
            else:
                warnings.append("折旧摊销数据缺失")
        else:
            warnings.append("资本开支数据缺失")

        # ==============================
        # 3. 稀缺性信号（高ROE+高毛利下的低周转）20分
        # ==============================
        roe = ind.get("ROE") if "ROE" in ind else None
        indicators["ROE(均值)"] = roe

        if roe is not None and not np.isnan(roe):
            if roe >= 0.20:
                score += 12
            elif roe >= 0.15:
                score += 8
            elif roe >= 0.10:
                score += 5
            elif roe >= 0.05:
                score += 2

        # 资产周转率信号：高毛利+低周转 = 重资产壁垒/专用资产
        turnover = ind.get("总资产周转率") if "总资产周转率" in yearly.columns else None
        indicators["总资产周转率(均值)"] = turnover

        if turnover is not None and not np.isnan(turnover) and gross is not None and not np.isnan(gross):
            # 高毛利+低周转 = 专用资产壁垒（如芯片设备、精密制造）
            if gross >= 0.35 and turnover < 0.6:
                score += 8
                indicators["资产模式"] = "重资产+高毛利（专用壁垒）"
            elif gross >= 0.25 and turnover < 0.4:
                score += 5
                indicators["资产模式"] = "重资产（规模壁垒）"
            elif gross >= 0.40 and turnover >= 0.8:
                score += 3
                indicators["资产模式"] = "轻资产高利润（品牌/技术壁垒）"
            elif gross < 0.20 and turnover >= 1.0:
                indicators["资产模式"] = "薄利多销（商品化红海）"
            else:
                indicators["资产模式"] = "混合模式"

        # ==============================
        # 4. 扩张质量（营收+利润+现金流匹配）20分
        # ==============================
        # —— 营收增长趋势 ——
        if "营业收入" in yearly.columns:
            rev = yearly["营业收入"].dropna()
            if len(rev) >= 3:
                # 最近3年复合增速
                recent_rev_growth = (rev.iloc[-1] / rev.iloc[-3]) ** (1/2) - 1 if rev.iloc[-3] > 0 else 0
                indicators["近3年营收复合增速"] = recent_rev_growth
                if recent_rev_growth >= 0.25:
                    score += 7
                elif recent_rev_growth >= 0.15:
                    score += 5
                elif recent_rev_growth >= 0.08:
                    score += 3
                elif recent_rev_growth >= 0.03:
                    score += 1

        # —— 利润增长与营收是否匹配 ——
        if "净利润" in yearly.columns and "营业收入" in yearly.columns:
            np_series = yearly["净利润"].dropna()
            rev_series = yearly["营业收入"].dropna()
            if len(np_series) >= 3 and len(rev_series) >= 3:
                recent_np_growth = (np_series.iloc[-1] / np_series.iloc[-3]) ** (1/2) - 1 if np_series.iloc[-3] > 0 else 0
                indicators["近3年净利润复合增速"] = recent_np_growth
                if recent_np_growth >= 0.25:
                    score += 5
                elif recent_np_growth >= 0.15:
                    score += 3
                elif recent_np_growth >= 0.08:
                    score += 2

                # 利润增速 vs 营收增速：利润增速 > 营收增速 = 规模效应/利润率扩张（好信号）
                recent_rev_growth_local = (rev_series.iloc[-1] / rev_series.iloc[-3]) ** (1/2) - 1 if rev_series.iloc[-3] > 0 else 0
                if recent_np_growth > recent_rev_growth_local:
                    score += 4
                    indicators["增长质量"] = "利润增速>营收（利润率改善）"
                elif recent_np_growth > 0 and recent_np_growth > recent_rev_growth_local * 0.7:
                    indicators["增长质量"] = "利润与营收同步增长"
                elif recent_np_growth > 0:
                    indicators["增长质量"] = "利润增长低于营收扩张"
                else:
                    indicators["增长质量"] = "利润下滑（需警惕）"

        # —— 经营现金流是否匹配利润 ——
        ocf_col = None
        for col in ["经营现金流", "经营活动现金流净额", "经营现金流/净利润", "经营活动现金流"]:
            if col in yearly.columns:
                ocf_col = col
                break

        if ocf_col and "净利润" in yearly.columns:
            ocf = yearly[ocf_col].dropna()
            np_series = yearly["净利润"].dropna()
            if len(ocf) and len(np_series):
                # 最近3年现金流/利润比
                min_len = min(len(ocf), len(np_series))
                recent_ocf = ocf.tail(min_len)
                recent_np = np_series.tail(min_len)
                with np.errstate(divide='ignore', invalid='ignore'):
                    valid_np = recent_np != 0
                    if valid_np.sum() > 0:
                        ocf_np_ratio = (recent_ocf[valid_np] / recent_np[valid_np]).mean()
                        indicators["经营现金流/净利润"] = ocf_np_ratio
                        if ocf_np_ratio >= 0.8:
                            score += 4
                        elif ocf_np_ratio >= 0.5:
                            score += 2

        # ==============================
        # 5. 财务健康（低负债+现金流质量）10分
        # ==============================
        debt = ind.get("资产负债率")
        indicators["资产负债率(均值)"] = debt

        if debt is not None and not np.isnan(debt):
            if debt < 0.35:
                score += 6
            elif debt < 0.50:
                score += 4
            elif debt < 0.65:
                score += 2
            else:
                warnings.append("负债率偏高")

        # 流动比率（如果有）
        if "流动比率" in yearly.columns:
            cr = ind.get("流动比率")
            indicators["流动比率(均值)"] = cr
            if cr is not None and not np.isnan(cr):
                if cr >= 2.0:
                    score += 4
                elif cr >= 1.5:
                    score += 2
                elif cr < 1.0:
                    warnings.append("流动比率<1，短期偿债风险")
        elif "流动资产" in yearly.columns and "流动负债" in yearly.columns:
            cr_series = yearly["流动资产"] / yearly["流动负债"]
            cr_mean = cr_series.dropna().mean()
            indicators["流动比率(均值)"] = cr_mean
            if cr_mean >= 2.0:
                score += 4
            elif cr_mean >= 1.5:
                score += 2
            elif cr_mean < 1.0:
                warnings.append("流动比率<1，短期偿债风险")
        else:
            # 无流动数据，用负债率补
            if debt is not None and not np.isnan(debt) and debt < 0.40:
                score += 4

        # ==============================
        # 评分汇总
        # ==============================
        score = min(score, 100)
        score = max(score, 0)

        confidence = "HIGH" if len(warnings) <= 1 else ("MEDIUM" if len(warnings) <= 3 else "LOW")

        # 评级
        if score >= 85:
            rating = "🔒 供应链关键卡位（强稀缺+高壁垒）"
        elif score >= 70:
            rating = "🔑 优质卡位（定价权+壁垒明显）"
        elif score >= 55:
            rating = "⚙️ 一般卡位（有一定壁垒或正在改善）"
        elif score >= 40:
            rating = "🔄 竞争性环节（壁垒不足，易被替代）"
        else:
            rating = "⚠️ 弱势环节（商品化/高度竞争/财务风险）"

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
        print(f"\n====== 🔒 {r['code']} 白毛女(Serenity)供应链卡位评分 ======")
        print(f"综合总分：{r['score']}/100")
        print(f"供应链卡位评级：{r['rating']}")
        print(f"评分可信度：{r['confidence']}")
        if r["warnings"]:
            print("⚠️ 数据警告：")
            for w in r["warnings"]:
                print(f"  - {w}")
        print("-" * 60)
        for k, v in r["indicators"].items():
            if v is None or pd.isna(v):
                continue
            if isinstance(v, str):
                print(f"{k:<28} {v}")
            elif "率" in k and "流动比率" not in k:
                print(f"{k:<28} {v:.2%}")
            else:
                print(f"{k:<28} {v:.2f}")
        print("=" * 60)


if __name__ == "__main__":
    s = SerenityScorer()
    code = input("请输入股票代码：").strip()
    res = s.score(code)
    if res:
        s.print_score(res)
    else:
        print("评分失败，请检查股票代码或财报数据")
