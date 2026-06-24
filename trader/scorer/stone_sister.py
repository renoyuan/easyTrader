#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

#!/usr/bin/env python
"""
石头姐（Catherine Wood / ARK）科技成长评分模型
=================================================
风格：专注颠覆性科技创新，高成长、高研发投入、高毛利率，
      关注未来 5-10 年的赛道。

核心思想：
  - 只适合科技/创新行业公司（AI、半导体、新能源、生物科技、云计算等）
  - 若股票所属行业不是科技/创新赛道，直接返回"非科技股"不评分
  - 评分维度：
    1. 研发投入强度（研发/营收） 25分
    2. 营收增长率（高增长） 20分
    3. 毛利率（技术壁垒） 20分
    4. ROE（成长质量） 15分
    5. 经营现金流（造血能力） 10分
    6. 负债率（轻资产运作） 10分

满分 100 分
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime

# 石头的科技关键词（判断是否科技股）
TECH_INDUSTRY_KEYWORDS = [
    "半导体", "芯片", "集成电路", "电子", "计算机", "软件", "互联网",
    "人工智能", "AI", "云计算", "大数据", "区块链", "物联网", "5G",
    "通信", "信息技术", "软件开发", "信息技术服务", "智能", "机器人",
    "自动化", "高端制造", "生物科技", "生物制品", "生物医药",
    "医疗器械", "医疗", "新材料", "新能源", "光伏", "锂电池",
    "新能源汽车", "车联网", "数字经济", "数字", "数据", "算力",
    "消费电子", "光学", "光电子", "传感器", "无人", "卫星",
    "航天", "航空", "军工电子", "量子",
    "信息", "光纤", "光缆", "光通信", "光模块",
]

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trader.processor.feature import StockFeatureProcessor


class StoneSisterScorer:
    """
    石头姐科技成长评分
    ==================
    风格：ARK 式颠覆性创新投资，重仓科技成长赛道
    """

    def __init__(self):
        self.proc = StockFeatureProcessor()

    # =========================
    # 行业鉴定（是否科技股）
    # =========================
    def _is_tech_stock(self, code: str, name: str = "") -> tuple:
        """
        判断股票是否属于科技/创新行业
        返回: (is_tech: bool, matched_keyword: str)
        """
        if not name:
            name = self.proc.get_stock_name(code) or ""

        # 1. 从股票名称判断
        name_lower = name.lower()
        if any(kw.lower() in name_lower for kw in TECH_INDUSTRY_KEYWORDS):
            return True, f"名称匹配: {name}"

        # 2. 从行业归属判断（查 StockIndustry 表）
        try:
            from trader.db.valuation_models import StockIndustry, SwIndustry
            from trader.db.orm import SessionLocal

            with SessionLocal() as session:
                # 先查申万三级
                inds = session.query(StockIndustry).filter(
                    StockIndustry.code == code,
                    StockIndustry.level == 3
                ).all()

                for ind in inds:
                    iname = ind.industry_name or ""
                    # 三级行业名称匹配
                    if any(kw in iname for kw in TECH_INDUSTRY_KEYWORDS):
                        return True, f"三级行业: {iname}"

                    # 反查一级行业（看是否属于科技大类）
                    sw = session.query(SwIndustry).filter(
                        SwIndustry.code == ind.industry_code
                    ).first()
                    if sw and sw.parent_code:
                        # 查二级
                        parent = session.query(SwIndustry).filter(
                            SwIndustry.code == sw.parent_code
                        ).first()
                        if parent and parent.parent_code:
                            # 查一级
                            grand = session.query(SwIndustry).filter(
                                SwIndustry.code == parent.parent_code
                            ).first()
                            if grand and any(kw in grand.name for kw in TECH_INDUSTRY_KEYWORDS):
                                return True, f"一级行业: {grand.name}"
        except Exception:
            pass

        return False, ""

    # =========================
    # 获取估值数据
    # =========================
    def get_valuation(self, code):
        result = {
            "pe": None,
            "pb": None,
            "pe_ttm": None,
            "missing_fields": [],
        }
        try:
            pe, pb = self.proc.calculate_pe_pb(code)
            result["pe"] = pe if pe and not np.isnan(pe) else None
            result["pb"] = pb if pb and not np.isnan(pb) else None
            result["pe_ttm"] = result["pe"]
        except Exception:
            result["missing_fields"].append("PE/PB获取失败")
        return result

    # =========================
    # 核心评分
    # =========================
    def score(self, code, years=5, as_of_date=None):
        print(f"[stonesister] 开始评分: {code}")

        # 1. 判断是否科技股
        name = self.proc.get_stock_name(code)
        is_tech, match_reason = self._is_tech_stock(code, name)
        if not is_tech:
            print(f"[stonesister] ⚠️ {code} {name} 非科技/创新行业，跳过评分")
            return {
                "code": code,
                "name": name,
                "score": 0,
                "rating": "❌ 非科技股（石头姐不关注）",
                "tech_match": False,
                "match_reason": match_reason,
                "indicators": {},
                "warnings": ["非科技/创新行业"],
            }

        print(f"[stonesister] ✅ 确认科技股: {match_reason}")

        # 2. 获取财务数据
        ref_date = as_of_date or datetime.now()
        current_year = ref_date.year if hasattr(ref_date, 'year') else ref_date.year
        years_list = list(range(current_year - years, current_year + 1))
        print(f"[stonesister] 读取近{years}年财报: as_of={ref_date}...")

        yearly = self.proc.calculate_yearly_features(code, years_list)
        if yearly.empty or len(yearly) < 2:
            print(f"[stonesister] 财报数据不足: {code}")
            return None

        print(f"[stonesister] 财报完成, {len(yearly)} 期")

        # 3. 获取估值
        val = self.get_valuation(code)
        print(f"[stonesister] PE={val.get('pe')}, PB={val.get('pb')}")

        score = 0
        indicators = {}
        warnings = []

        # 年度均值
        num_cols = yearly.select_dtypes(include=[np.number]).columns
        skip_cols = {'year', '净利润', '营业收入', '应收账款', '经营活动现金流净额', '存货'}
        ratio_cols = [c for c in num_cols if c not in skip_cols]
        ind = yearly[ratio_cols].mean()

        # =========================
        # 1. 研发投入强度（25分）
        # 石头姐最看重：革命性技术需要真金白银投入
        # =========================
        rd_ratio = None
        try:
            # 从 financial_indicator 表获取
            from trader.db.orm import SessionLocal
            from trader.db.valuation_models import FinancialIndicator

            with SessionLocal() as session:
                # 从 performance 表获取研发费用
                rows = session.query(
                    FinancialIndicator
                ).filter(
                    FinancialIndicator.code == code,
                    FinancialIndicator.research_expense_ratio.isnot(None),
                ).order_by(
                    FinancialIndicator.report_date.desc()
                ).limit(3).all()

                if rows:
                    rd_ratio = float(np.mean([r.research_expense_ratio for r in rows]))
                    # 转为小数
                    if rd_ratio > 1:
                        rd_ratio = rd_ratio / 100.0
        except Exception:
            pass

        # 若财务指标表没有，尝试从 financial_indicator 的 yoy_ratio 字段估算
        if rd_ratio is None:
            try:
                # 查看是否有研发相关比率
                rd_fields = ["研究与发展费用", "研发投入"]
                df = self.proc.data_service.get_financial_indicator_df(code)
                if not df.empty:
                    for rf in rd_fields:
                        if rf in df.columns:
                            vals = df[rf].dropna()
                            if not vals.empty:
                                rd_ratio = float(vals.iloc[0]) / 100.0
                                break
            except Exception:
                pass

        indicators["研发投入/营收"] = rd_ratio

        if rd_ratio is not None and not np.isnan(rd_ratio):
            # ARK 喜欢研发投入高的公司（>10% 营收）
            if rd_ratio >= 0.20:
                score += 25
                warnings.append("极高研发投入（>20%），颠覆性创新特征")
            elif rd_ratio >= 0.15:
                score += 22
            elif rd_ratio >= 0.10:
                score += 18
            elif rd_ratio >= 0.08:
                score += 12
            elif rd_ratio >= 0.05:
                score += 8
            else:
                score += 3
                warnings.append("研发投入偏低（<5%），科技属性存疑")
        else:
            warnings.append("研发投入数据缺失（部分行业不披露）")
            score += 8  # 中性分

        # =========================
        # 2. 营收增长率（20分）
        # ARK 核心逻辑：未来 5 年 CAGR > 15%
        # =========================
        revenue_growth = ind.get("收入增长率")
        indicators["营收增长率"] = revenue_growth

        if revenue_growth is not None and not np.isnan(revenue_growth):
            if revenue_growth >= 0.30:
                score += 20
            elif revenue_growth >= 0.20:
                score += 16
            elif revenue_growth >= 0.15:
                score += 12
            elif revenue_growth >= 0.10:
                score += 8
            elif revenue_growth >= 0.05:
                score += 4
            else:
                score += 1
                warnings.append("营收增长缓慢，不符合高成长特征")
        else:
            warnings.append("营收增长率缺失")
            score += 4

        # =========================
        # 3. 毛利率（20分）
        # 科技公司高毛利率 = 技术壁垒 + 定价权
        # =========================
        gross_margin = ind.get("毛利率")
        indicators["毛利率"] = gross_margin

        if gross_margin is not None and not np.isnan(gross_margin):
            if gross_margin >= 0.60:
                score += 20
                warnings.append("极高毛利率（>60%），强大技术壁垒")
            elif gross_margin >= 0.45:
                score += 15
            elif gross_margin >= 0.30:
                score += 10
            elif gross_margin >= 0.20:
                score += 6
            else:
                score += 2
                warnings.append("毛利率偏低，可能缺乏技术壁垒")
        else:
            warnings.append("毛利率缺失")
            score += 6

        # =========================
        # 4. ROE（15分）
        # 成长质量：高ROE说明资本运用效率高
        # =========================
        roe = ind.get("ROE")
        indicators["ROE"] = roe

        if roe is not None and not np.isnan(roe):
            if roe >= 0.20:
                score += 15
            elif roe >= 0.15:
                score += 12
            elif roe >= 0.10:
                score += 8
            elif roe >= 0.05:
                score += 4
            else:
                score += 1
        else:
            warnings.append("ROE缺失")
            score += 3

        # =========================
        # 5. 经营现金流（10分）
        # 能自我造血：经营现金流为正且足够支撑运营
        # =========================
        ocf_to_np = ind.get("经营现金流/净利润")
        indicators["经营现金流/净利润"] = ocf_to_np

        if ocf_to_np is not None and not np.isnan(ocf_to_np):
            if ocf_to_np >= 1.0:
                score += 10
            elif ocf_to_np >= 0.5:
                score += 7
            elif ocf_to_np >= 0:
                score += 3
            else:
                warnings.append("经营现金流为负，烧钱模式（需关注融资能力）")
                score += 1
        else:
            warnings.append("经营现金流/净利润缺失")
            score += 3

        # =========================
        # 6. 负债率（10分）
        # 轻资产、低负债 → 灵活，能专注研发
        # =========================
        debt = ind.get("资产负债率")
        indicators["资产负债率"] = debt

        if debt is not None and not np.isnan(debt):
            if debt < 0.30:
                score += 10
            elif debt < 0.45:
                score += 7
            elif debt < 0.60:
                score += 4
            else:
                warnings.append("负债率过高，财务风险大")
                score += 1
        else:
            warnings.append("资产负债率缺失")
            score += 3

        # =========================
        # 最终评分
        # =========================
        score = min(score, 100)
        score = max(score, 0)

        # 评级
        if score >= 85:
            rating = "🔥 ARK级颠覆者（石头姐强烈推荐）"
        elif score >= 70:
            rating = "✅ 优质科技成长（适合长期持有）"
        elif score >= 55:
            rating = "⚠️ 普通科技股（需关注增长动力）"
        elif score >= 40:
            rating = "🔍 边缘科技股（科技属性弱）"
        else:
            rating = "❌ 不符合ARK标准"

        confidence = "HIGH" if len(warnings) < 2 else "LOW"

        return {
            "code": code,
            "name": name,
            "score": score,
            "rating": rating,
            "tech_match": True,
            "match_reason": match_reason,
            "confidence": confidence,
            "warnings": warnings,
            "indicators": indicators,
            "val": val,
        }

    # =========================
    # 打印结果
    # =========================
    def print_score(self, r):
        if r is None:
            print("评分失败")
            return

        print(f"\n==============================================")
        print(f"  🚀 石头姐（ARK）科技成长评分")
        print(f"  {r['code']} {r['name']}")
        print(f"==============================================")

        if not r.get("tech_match"):
            print(f"  ❌ {r['rating']}")
            print(f"  原因: {r.get('match_reason', '未知')}")
            print(f"==============================================\n")
            return

        print(f"  综合得分: {r['score']}/100")
        print(f"  评级: {r['rating']}")
        print(f"  可信度: {r.get('confidence', 'N/A')}")
        print(f"  科技匹配: {r.get('match_reason', '')}")
        print(f"------------------------------------------------")

        if r.get("warnings"):
            print(f"  ⚠️ 提示:")
            for w in r["warnings"]:
                print(f"    - {w}")

        print(f"------------------------------------------------")
        print(f"  关键指标:")
        for k, v in r.get("indicators", {}).items():
            if v is None or pd.isna(v):
                continue
            if isinstance(v, float):
                if abs(v) < 1:
                    print(f"    {k:<20} {v:.2%}")
                else:
                    print(f"    {k:<20} {v:.2f}")
            else:
                print(f"    {k:<20} {v}")
        print(f"==============================================\n")


if __name__ == "__main__":
    s = StoneSisterScorer()
    code = input("请输入科技股代码: ").strip()
    res = s.score(code)
    s.print_score(res)
