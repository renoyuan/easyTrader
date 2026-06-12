# -*- coding: utf-8 -*-
"""
相对估值法模块
支持：PE（市盈率）、PB（市净率）、PS（市销率）、PEG（市盈率相对盈利增长比率）
输出：合理股价区间、合理市值区间、偏离度
"""

import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
from trader.db.orm import SessionLocal
from trader.db.valuation_models import SwIndustry, ValuationResult


class RelativeValuation:
    """
    相对估值法
    依赖：
    - SwIndustry 表：行业合理PE/PB区间
    - Valuation 表：个股当前PE/PB
    - Income/Balance 表：EPS、BVPS、营收等财务数据
    """

    def __init__(self):
        self.session = SessionLocal()

    def __del__(self):
        self.session.close()

    # ════════════════════════════════════
    # PE估值法
    # ════════════════════════════════════

    def valuate_pe(self, code: str, eps: float = None,
                   industry_pe_low: float = None,
                   industry_pe_high: float = None) -> Dict:
        """
        PE估值法
        合理股价 = EPS * 行业合理PE
        :param code: 股票代码
        :param eps: 每股收益（如不传则从 performance 表获取）
        :param industry_pe_low: 行业PE下限（如不传从 SwIndustry 查）
        :param industry_pe_high: 行业PE上限
        :return: 估值结果字典
        """
        current_price, current_pe = self._get_current_price_pe(code)
        eps = eps or self._get_eps(code)
        pe_low, pe_high = industry_pe_low, industry_pe_high

        if pe_low is None or pe_high is None:
            pe_low, pe_high = self._get_industry_pe_range(code)

        if eps is None or eps <= 0:
            return self._error_result(code, "EPS缺失或为负")

        fair_price_low = round(eps * pe_low, 2)
        fair_price_high = round(eps * pe_high, 2)
        fair_price = round((fair_price_low + fair_price_high) / 2, 2)

        deviation = self._calc_deviation(current_price, fair_price) if current_price else None

        result = self._build_result(
            code=code, method="PE",
            current_price=current_price, current_pe=current_pe,
            fair_price=fair_price,
            price_range_low=fair_price_low,
            price_range_high=fair_price_high,
            deviation=deviation,
            params={"eps": eps, "pe_low": pe_low, "pe_high": pe_high}
        )
        self._save_result(result)
        return result

    # ════════════════════════════════════
    # PB估值法
    # ════════════════════════════════════

    def valuate_pb(self, code: str, bvps: float = None,
                   industry_pb_low: float = None,
                   industry_pb_high: float = None) -> Dict:
        """
        PB估值法
        合理股价 = BVPS * 行业合理PB
        """
        current_price, current_pe = self._get_current_price_pe(code)
        bvps = bvps or self._get_bvps(code)
        pb_low, pb_high = industry_pb_low, industry_pb_high

        if pb_low is None or pb_high is None:
            pb_low, pb_high = self._get_industry_pb_range(code)

        if bvps is None or bvps <= 0:
            return self._error_result(code, "BVPS缺失或为负")

        # 银行/周期股默认PB区间
        if pb_low is None:
            pb_low, pb_high = 0.5, 2.0

        fair_price_low = round(bvps * pb_low, 2)
        fair_price_high = round(bvps * pb_high, 2)
        fair_price = round((fair_price_low + fair_price_high) / 2, 2)

        deviation = self._calc_deviation(current_price, fair_price) if current_price else None

        result = self._build_result(
            code=code, method="PB",
            current_price=current_price, current_pe=current_pe,
            fair_price=fair_price,
            price_range_low=fair_price_low,
            price_range_high=fair_price_high,
            deviation=deviation,
            params={"bvps": bvps, "pb_low": pb_low, "pb_high": pb_high}
        )
        self._save_result(result)
        return result

    # ════════════════════════════════════
    # PS估值法
    # ════════════════════════════════════

    def valuate_ps(self, code: str, total_shares: float = None,
                   revenue: float = None,
                   ps_ratio: float = None) -> Dict:
        """
        PS估值法（市销率）
        合理市值 = 营业收入 * 行业PS
        合理股价 = 合理市值 / 总股本
        PS行业基准默认用 1~5，高毛利行业偏高
        """
        current_price, current_pe = self._get_current_price_pe(code)

        # 获取总股本
        total_shares = total_shares or self._get_total_shares(code)
        if total_shares is None or total_shares <= 0:
            return self._error_result(code, "总股本缺失")

        # 获取营收
        revenue = revenue or self._get_revenue(code)
        if revenue is None or revenue <= 0:
            return self._error_result(code, "营业收入缺失")

        # 行业PS区间（默认1~5）
        if ps_ratio is None:
            ps_low, ps_high = 1.0, 5.0
            # 高毛利行业可以给更高PS
            gross_margin = self._get_gross_margin(code)
            if gross_margin and gross_margin > 0.4:
                ps_low, ps_high = 2.0, 10.0
            elif gross_margin and gross_margin > 0.6:
                ps_low, ps_high = 3.0, 15.0
        else:
            ps_low = ps_ratio * 0.6
            ps_high = ps_ratio * 1.5

        fair_mv_low = revenue * ps_low
        fair_mv_high = revenue * ps_high
        fair_price_low = round(fair_mv_low / total_shares, 2)
        fair_price_high = round(fair_mv_high / total_shares, 2)
        fair_price = round((fair_price_low + fair_price_high) / 2, 2)

        deviation = self._calc_deviation(current_price, fair_price) if current_price else None

        result = self._build_result(
            code=code, method="PS",
            current_price=current_price, current_pe=current_pe,
            fair_price=fair_price,
            price_range_low=fair_price_low,
            price_range_high=fair_price_high,
            deviation=deviation,
            params={
                "revenue": revenue, "total_shares": total_shares,
                "ps_low": ps_low, "ps_high": ps_high,
                "fair_mv_low": round(fair_mv_low, 2),
                "fair_mv_high": round(fair_mv_high, 2),
            }
        )
        self._save_result(result)
        return result

    # ════════════════════════════════════
    # PEG估值法
    # ════════════════════════════════════

    def valuate_peg(self, code: str, eps: float = None,
                    growth_rate: float = None) -> Dict:
        """
        PEG估值法
        合理PE = 盈利增长率 * PEG系数（默认PEG=1）
        合理股价 = EPS * 合理PE
        PEG=1为合理，<1低估，>1高估
        """
        current_price, current_pe = self._get_current_price_pe(code)
        eps = eps or self._get_eps(code)
        growth_rate = growth_rate or self._get_profit_growth(code)

        if eps is None or eps <= 0:
            return self._error_result(code, "EPS缺失或为负")
        if growth_rate is None or growth_rate <= 0:
            return self._error_result(code, "增长率缺失或为负")

        # PEG=1: 合理PE = 增长率(去掉百分号)
        if growth_rate > 1:
            growth_rate = growth_rate / 100.0  # 假设输入是百分比

        fair_pe = growth_rate * 100  # 如增长率15% -> 合理PE=15
        # 限制合理PE范围
        fair_pe = max(min(fair_pe, 60), 5)

        # PEG合理区间：合理PE * 0.7 ~ 合理PE * 1.3
        pe_low = fair_pe * 0.7
        pe_high = fair_pe * 1.3

        fair_price = round(eps * fair_pe, 2)
        fair_price_low = round(eps * pe_low, 2)
        fair_price_high = round(eps * pe_high, 2)

        current_peg = round(current_pe / (growth_rate * 100), 2) if current_pe and growth_rate else None
        deviation = self._calc_deviation(current_price, fair_price) if current_price else None

        result = self._build_result(
            code=code, method="PEG",
            current_price=current_price, current_pe=current_pe,
            fair_price=fair_price,
            price_range_low=fair_price_low,
            price_range_high=fair_price_high,
            deviation=deviation,
            params={
                "eps": eps, "growth_rate": growth_rate,
                "fair_pe": round(fair_pe, 2), "current_peg": current_peg,
            }
        )
        self._save_result(result)
        return result

    # ════════════════════════════════════
    # 数据获取
    # ════════════════════════════════════

    def _get_current_price_pe(self, code: str) -> Tuple[Optional[float], Optional[float]]:
        """获取当前股价和PE，优先从valuation表，回退到akshare实时拉取"""
        from trader.db.orm import Valuation
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            row = self.session.query(Valuation).filter(
                Valuation.code == code,
                Valuation.trade_date == today,
            ).first()
            if not row:
                row = self.session.query(Valuation).filter(
                    Valuation.code == code
                ).order_by(Valuation.trade_date.desc()).first()

            current_pe = float(row.pe) if row and row.pe else None
            current_pb = float(row.pb) if row and row.pb else None
        except Exception:
            current_pe = None
            current_pb = None

        # 从 K线表获取最新收盘价
        current_price = self._get_latest_close(code)

        # 回退：如果K线没有，用 akshare 实时拉
        if current_price is None:
            try:
                import akshare as ak
                df = ak.stock_individual_info_em(symbol=code)
                if not df.empty:
                    current_price = float(df[df["item"] == "最新价"]["value"].iloc[0])
            except Exception:
                pass

        return current_price, current_pe

    def _get_latest_close(self, code: str) -> Optional[float]:
        """从 stock_kline 表获取最近收盘价"""
        from trader.db.orm import StockKline
        try:
            row = self.session.query(StockKline).filter(
                StockKline.code == code,
                StockKline.close.isnot(None),
            ).order_by(StockKline.date.desc()).first()
            return float(row.close) if row else None
        except Exception:
            return None

    def _get_eps(self, code: str) -> Optional[float]:
        """从 performance 表获取最近EPS"""
        from trader.db.orm import Performance
        try:
            row = self.session.query(Performance).filter(
                Performance.code == code,
                Performance.eps.isnot(None),
            ).order_by(Performance.report_date.desc()).first()
            return float(row.eps) if row else None
        except Exception:
            return None

    def _get_bvps(self, code: str) -> Optional[float]:
        """从 performance 表获取每股净资产"""
        from trader.db.orm import Performance
        try:
            row = self.session.query(Performance).filter(
                Performance.code == code,
                Performance.navps.isnot(None),
            ).order_by(Performance.report_date.desc()).first()
            return float(row.navps) if row else None
        except Exception:
            return None

    def _get_total_shares(self, code: str) -> Optional[float]:
        """从 dividend 表获取总股本（股）"""
        from trader.db.orm import Dividend
        try:
            row = self.session.query(Dividend).filter(
                Dividend.code == code,
                Dividend.total_shares.isnot(None),
            ).order_by(Dividend.report_date.desc()).first()
            return float(row.total_shares) if row else None
        except Exception:
            return None

    def _get_revenue(self, code: str) -> Optional[float]:
        """从 income 表获取最近一年营业总收入"""
        from trader.db.orm import Income
        try:
            row = self.session.query(Income).filter(
                Income.code == code,
                Income.total_revenue.isnot(None),
            ).order_by(Income.report_date.desc()).first()
            return float(row.total_revenue) if row else None
        except Exception:
            return None

    def _get_gross_margin(self, code: str) -> Optional[float]:
        """从 financial_indicator 表获取毛利率"""
        from trader.db.orm import FinancialIndicator
        try:
            row = self.session.query(FinancialIndicator).filter(
                FinancialIndicator.code == code,
                FinancialIndicator.gross_margin.isnot(None),
            ).order_by(FinancialIndicator.report_date.desc()).first()
            return float(row.gross_margin) / 100.0 if row else None  # 转为小数
        except Exception:
            return None

    def _get_profit_growth(self, code: str) -> Optional[float]:
        """从 income 表获取净利润增长率（小数，如0.15）"""
        from trader.db.orm import Income
        try:
            rows = self.session.query(Income).filter(
                Income.code == code,
                Income.net_profit_yoy.isnot(None),
            ).order_by(Income.report_date.desc()).limit(2).all()
            if len(rows) >= 2:
                # 用最近两年的净利润算增长率
                p0 = rows[0].net_profit or 0
                p1 = rows[1].net_profit or 0
                if p1 > 0:
                    return (p0 - p1) / abs(p1)
            return None
        except Exception:
            return None

    def _get_industry_pe_range(self, code: str) -> Tuple[float, float]:
        """从 SwIndustry 获取行业PE区间"""
        from trader.db.valuation_models import StockIndustry
        try:
            stock_ind = self.session.query(StockIndustry).filter(
                StockIndustry.code == code
            ).first()
            if stock_ind:
                sw = self.session.query(SwIndustry).filter(
                    SwIndustry.name == stock_ind.industry_name
                ).first()
                if sw and sw.pe_range_low and sw.pe_range_high:
                    return (sw.pe_range_low, sw.pe_range_high)
        except Exception:
            pass
        return (10, 30)  # 默认

    def _get_industry_pb_range(self, code: str) -> Tuple[Optional[float], Optional[float]]:
        """从 SwIndustry 获取行业PB区间"""
        from trader.db.valuation_models import StockIndustry
        try:
            stock_ind = self.session.query(StockIndustry).filter(
                StockIndustry.code == code
            ).first()
            if stock_ind:
                sw = self.session.query(SwIndustry).filter(
                    SwIndustry.name == stock_ind.industry_name
                ).first()
                if sw and sw.pb_range_low and sw.pb_range_high:
                    return (sw.pb_range_low, sw.pb_range_high)
        except Exception:
            pass
        return (None, None)

    # ════════════════════════════════════
    # 结果处理
    # ════════════════════════════════════

    @staticmethod
    def _calc_deviation(current: float, fair: float) -> float:
        """计算偏离度（%），正=高估，负=低估"""
        if fair <= 0:
            return 0
        return round((current - fair) / fair * 100, 2)

    def _build_result(self, code: str, method: str,
                       current_price: float, current_pe: float,
                       fair_price: float,
                       price_range_low: float, price_range_high: float,
                       deviation: float,
                       params: dict) -> Dict:
        """构建结果字典"""
        return {
            "code": code,
            "method": method,
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
            "current_price": current_price,
            "current_pe": current_pe,
            "fair_price": fair_price,
            "price_range_low": price_range_low,
            "price_range_high": price_range_high,
            "deviation": deviation,
            "params_json": str(params),
        }

    def _error_result(self, code: str, reason: str) -> Dict:
        return {
            "code": code,
            "error": reason,
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
        }

    def _save_result(self, result: Dict):
        """保存估值结果到 valuation_result 表"""
        if "error" in result:
            return
        try:
            obj = ValuationResult(
                code=result["code"],
                trade_date=result["trade_date"],
                method=result["method"],
                current_price=result["current_price"],
                current_pe=result["current_pe"],
                fair_price=result["fair_price"],
                price_range_low=result["price_range_low"],
                price_range_high=result["price_range_high"],
                deviation=result["deviation"],
                params_json=result["params_json"],
            )
            self.session.merge(obj)
            self.session.commit()
        except Exception:
            self.session.rollback()


# ════════════════════════════════════
# 快捷入口
# ════════════════════════════════════

def run_relative_valuation(code: str, methods: list = None):
    """
    对单只股票运行相对估值
    :param code: 股票代码
    :param methods: 估值方法列表，默认全跑 ["PE", "PB", "PS", "PEG"]
    """
    val = RelativeValuation()
    methods = methods or ["PE", "PB", "PS", "PEG"]
    results = {}

    for m in methods:
        if m == "PE":
            results[m] = val.valuate_pe(code)
        elif m == "PB":
            results[m] = val.valuate_pb(code)
        elif m == "PS":
            results[m] = val.valuate_ps(code)
        elif m == "PEG":
            results[m] = val.valuate_peg(code)

    return results


if __name__ == "__main__":
    # 测试
    results = run_relative_valuation("600519")
    for method, r in results.items():
        print(f"\n{method}:")
        for k, v in r.items():
            print(f"  {k}: {v}")
