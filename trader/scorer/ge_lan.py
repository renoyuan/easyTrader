#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
葛兰医药行业评分模型
=====================
风格：专注医药健康赛道，核心逻辑是"好赛道 + 好公司 + 好价格"。
      先判断是否属于医药/医疗/生物/大健康行业，非医药股直接跳过。

核心思想：
  - 只适合医药健康行业（化学制药、中药、生物制品、医疗器械、医疗服务、医药商业等）
  - 若股票所属行业非医药健康，直接返回"非医药股"不评分
  - 评分维度：
    1. 研发管线（研发投入强度） 25分
    2. 盈利能力（ROE + 净利润率） 20分
    3. 成长性（营收增长） 15分
    4. 现金造血（经营现金流） 15分
    5. 估值安全垫（PE/PB 合理度） 15分
    6. 财务稳健（低负债） 10分

满分 100 分
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime

# 医药行业关键词
MED_KEYWORDS = [
    "医药", "制药", "药", "生物", "医疗", "医院", "健康", "保健",
    "疫苗", "血清", "诊断", "检测", "基因", "细胞", "蛋白",
    "抗体", "免疫", "干细胞", "临床", "CRO", "CMO", "CDMO",
    "创新药", "仿制药", "中药", "化学药", "原料药", "中间体",
    "血制品", "体外诊断", "生化", "核药", "造影",
    "医疗器械", "耗材", "设备", "口腔", "眼科", "骨科",
    "医美", "美容", "护理", "康复", "养老",
    "药店", "医药商业", "批发", "分销", "流通",
    "实验", "实验室", "生命科学", "科研",
]

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from trader.processor.feature import StockFeatureProcessor


class GeLanScorer:
    """
    葛兰医药行业评分
    ===============
    风格：中长期持有优质医药股，左侧布局+右侧确认
    """

    def __init__(self):
        self.proc = StockFeatureProcessor()

    # =========================
    # 行业鉴定
    # =========================
    def _is_med_stock(self, code: str, name: str = "") -> tuple:
        """
        判断是否医药健康股
        返回: (is_med: bool, matched_keyword: str)
        """
        if not name:
            name = self.proc.get_stock_name(code) or ""

        # 1. 名称匹配
        name_lower = name.lower()
        if any(kw.lower() in name_lower for kw in MED_KEYWORDS):
            return True, f"名称匹配: {name}"

        # 2. 行业归属匹配
        try:
            from trader.db.valuation_models import StockIndustry, SwIndustry
            from trader.db.orm import SessionLocal

            with SessionLocal() as session:
                # 优先三级行业
                inds = session.query(StockIndustry).filter(
                    StockIndustry.code == code,
                    StockIndustry.level == 3
                ).all()

                for ind in inds:
                    iname = ind.industry_name or ""
                    if any(kw in iname for kw in MED_KEYWORDS):
                        return True, f"三级行业: {iname}"

                    # 向上查一级
                    sw = session.query(SwIndustry).filter(
                        SwIndustry.code == ind.industry_code
                    ).first()
                    if sw and sw.parent_code:
                        parent = session.query(SwIndustry).filter(
                            SwIndustry.code == sw.parent_code
                        ).first()
                        if parent and parent.parent_code:
                            grand = session.query(SwIndustry).filter(
                                SwIndustry.code == parent.parent_code
                            ).first()
                            if grand:
                                gname = grand.name or ""
                                # 申万一级医药生物 = 代码 801150.SI
                                if "医药" in gname or "医疗" in gname or "生物" in gname:
                                    return True, f"一级行业: {gname}"

                # 如果三级没匹配到，直接查一级
                one_inds = session.query(StockIndustry).filter(
                    StockIndustry.code == code,
                    StockIndustry.level == 1
                ).all()
                for ind in one_inds:
                    iname = ind.industry_name or ""
                    if "医药" in iname or "医疗" in iname or "生物" in iname:
                        return True, f"一级行业: {iname}"

        except Exception:
            pass

        return False, ""

    # =========================
    # 获取估值
    # =========================
    def get_valuation(self, code):
        result = {
            "pe": None,
            "pb": None,
            "missing_fields": [],
        }
        try:
            pe, pb = self.proc.calculate_pe_pb(code)
            result["pe"] = pe if pe and not np.isnan(pe) else None
            result["pb"] = pb if pb and not np.isnan(pb) else None
        except Exception:
            result["missing_fields"].append("PE/PB获取失败")
        return result

    # =========================
    # 核心评分
    # =========================
    def score(self, code, years=5):
        print(f"[gelan] 开始评分: {code}")

        # 1. 判断是否医药股
        name = self.proc.get_stock_name(code)
        is_med, match_reason = self._is_med_stock(code, name)
        if not is_med:
            print(f"[gelan] ⚠️ {code} {name} 非医药健康行业，跳过评分")
            return {
                "code": code,
                "name": name,
                "score": 0,
                "rating": "❌ 非医药股（葛兰不关注）",
                "med_match": False,
                "match_reason": match_reason,
                "indicators": {},
                "warnings": ["非医药/健康行业"],
            }

        print(f"[gelan] ✅ 确认医药股: {match_reason}")

        # 2. 获取财务数据
        current_year = datetime.now().year
        years_list = list(range(current_year - years, current_year + 1))
        print(f"[gelan] 读取近{years}年财报...")

        yearly = self.proc.calculate_yearly_features(code, years_list)
        if yearly.empty or len(yearly) < 2:
            print(f"[gelan] 财报数据不足: {code}")
            return None

        print(f"[gelan] 财报完成, {len(yearly)} 期")

        # 3. 获取估值
        val = self.get_valuation(code)

        score = 0
        indicators = {}
        warnings = []

        # 年度均值
        num_cols = yearly.select_dtypes(include=[np.number]).columns
        skip_cols = {'year', '净利润', '营业收入', '应收账款', '经营活动现金流净额', '存货'}
        ratio_cols = [c for c in num_cols if c not in skip_cols]
        ind = yearly[ratio_cols].mean()

        # =========================
        # 1. 研发管线（25分）
        # 医药行业核心：研发投入决定未来管线
        # =========================
        rd_ratio = None
        try:
            df = self.proc.data_service.get_financial_indicator_df(code)
            if not df.empty:
                for col in ["研究与发展费用", "研发投入", "研发费用"]:
                    if col in df.columns:
                        vals = df[col].dropna()
                        if not vals.empty:
                            rd_ratio = float(vals.iloc[0])
                            if rd_ratio > 1:
                                rd_ratio = rd_ratio / 100.0  # 转为小数
                            break
        except Exception:
            pass

        indicators["研发投入/营收"] = rd_ratio

        if rd_ratio is not None and not np.isnan(rd_ratio):
            # 医药行业高研发投入是标配
            if rd_ratio >= 0.15:
                score += 25
                warnings.append("高研发投入（>15%），创新管线充足")
            elif rd_ratio >= 0.10:
                score += 20
            elif rd_ratio >= 0.08:
                score += 15
            elif rd_ratio >= 0.05:
                score += 10
            elif rd_ratio >= 0.03:
                score += 5
            else:
                score += 2
                warnings.append("研发投入低（<3%），仿制药/中药传统品种特征")
        else:
            warnings.append("研发投入数据缺失")
            # 中药企业可能不单独披露，给中性分
            score += 8

        # =========================
        # 2. 盈利能力（20分）
        # ROE + 净利润率 - 好生意要有好利润
        # =========================
        roe = ind.get("ROE")
        indicators["ROE"] = roe

        if roe is not None and not np.isnan(roe):
            if roe >= 0.20:
                score += 10
            elif roe >= 0.15:
                score += 8
            elif roe >= 0.10:
                score += 5
            elif roe >= 0.05:
                score += 3
            else:
                score += 1
        else:
            warnings.append("ROE缺失")
            score += 2

        net_margin = ind.get("净利润率")
        indicators["净利润率"] = net_margin

        if net_margin is not None and not np.isnan(net_margin):
            # 医药行业合理净利润率 10%~30%
            if net_margin >= 0.20:
                score += 10
            elif net_margin >= 0.15:
                score += 8
            elif net_margin >= 0.10:
                score += 6
            elif net_margin >= 0.05:
                score += 3
            else:
                score += 1
        else:
            warnings.append("净利润率缺失")
            score += 2

        # =========================
        # 3. 成长性（15分）
        # 营收持续增长 → 市占率提升 or 新品放量
        # =========================
        revenue_growth = ind.get("收入增长率")
        indicators["营收增长率"] = revenue_growth

        if revenue_growth is not None and not np.isnan(revenue_growth):
            if revenue_growth >= 0.25:
                score += 15
            elif revenue_growth >= 0.15:
                score += 12
            elif revenue_growth >= 0.10:
                score += 8
            elif revenue_growth >= 0.05:
                score += 5
            elif revenue_growth >= 0:
                score += 2
            else:
                warnings.append("营收负增长，基本面走弱")
                score += 0
        else:
            warnings.append("营收增长率缺失")
            score += 3

        # =========================
        # 4. 现金造血（15分）
        # 优秀的医药公司应有强现金流 = 产品有真实需求
        # =========================
        ocf_to_np = ind.get("经营现金流/净利润")
        indicators["经营现金流/净利润"] = ocf_to_np

        if ocf_to_np is not None and not np.isnan(ocf_to_np):
            if ocf_to_np >= 0.9:
                score += 15
            elif ocf_to_np >= 0.7:
                score += 12
            elif ocf_to_np >= 0.4:
                score += 8
            elif ocf_to_np >= 0:
                score += 4
            else:
                warnings.append("经营现金流为负，现金流风险")
                score += 1
        else:
            warnings.append("经营现金流/净利润缺失")
            score += 4

        # =========================
        # 5. 估值安全垫（15分）
        # 医药股合理 PE 范围宽，创新药 PE 高是常态
        # 结合历史分位判断
        # =========================
        pe = val.get("pe")
        pb = val.get("pb")
        indicators["PE(TTM)"] = pe
        indicators["PB"] = pb

        pe_score = 0
        if pe is not None and pe > 0:
            # 医药行业合理 PE 参照：创新药 30~60，仿制药 15~30，器械 25~50
            if pe < 20:
                pe_score = 8
                warnings.append("PE<20，估值处于历史低位（可能是医药底部）")
            elif pe < 30:
                pe_score = 6
            elif pe < 45:
                pe_score = 4
            elif pe < 60:
                pe_score = 2
            else:
                warnings.append("PE>60，高估值，需业绩持续高增长支撑")
                pe_score = 1
        else:
            pe_score = 3
            warnings.append("PE缺失")

        pb_score = 0
        if pb is not None and pb > 0:
            if pb < 2:
                pb_score = 7
            elif pb < 4:
                pb_score = 5
            elif pb < 6:
                pb_score = 3
            else:
                pb_score = 1
        else:
            pb_score = 3

        score += min(pe_score + pb_score, 15)

        # =========================
        # 6. 财务稳健（10分）
        # 医药公司适当负债可以（研发需要钱），但不能过高
        # =========================
        debt = ind.get("资产负债率")
        indicators["资产负债率"] = debt

        if debt is not None and not np.isnan(debt):
            if debt < 0.25:
                score += 10
            elif debt < 0.40:
                score += 7
            elif debt < 0.55:
                score += 4
            else:
                warnings.append("负债率偏高（>55%），财务杠杆大")
                score += 1
        else:
            warnings.append("资产负债率缺失")
            score += 3

        # =========================
        # 最终评分
        # =========================
        score = min(score, 100)
        score = max(score, 0)

        if score >= 85:
            rating = "🔥 葛兰强烈推荐（优质医药龙头）"
        elif score >= 70:
            rating = "✅ 优质医药标的（中长期持有）"
        elif score >= 55:
            rating = "⚖️ 普通医药股（需等待更好买点）"
        elif score >= 40:
            rating = "⚠️ 偏弱（财务或成长性堪忧）"
        else:
            rating = "❌ 不适合医药投资"

        confidence = "HIGH" if len(warnings) < 2 else "LOW"

        return {
            "code": code,
            "name": name,
            "score": score,
            "rating": rating,
            "med_match": True,
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
        print(f"  💊 葛兰医药行业评分")
        print(f"  {r['code']} {r['name']}")
        print(f"==============================================")

        if not r.get("med_match"):
            print(f"  ❌ {r['rating']}")
            print(f"  原因: {r.get('match_reason', '未知')}")
            print(f"==============================================\n")
            return

        print(f"  综合得分: {r['score']}/100")
        print(f"  评级: {r['rating']}")
        print(f"  可信度: {r.get('confidence', 'N/A')}")
        print(f"  医药归属: {r.get('match_reason', '')}")
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
    s = GeLanScorer()
    code = input("请输入医药股代码: ").strip()
    res = s.score(code)
    s.print_score(res)
