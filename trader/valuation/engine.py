#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

"""
估值引擎
- 整合所有估值方法（PE/PB/PS/PEG）
- 批量运行指定方法
- 综合估值结果汇总
- 估值方法说明
- 股票基本信息查询
"""

from typing import List, Optional, Dict
from datetime import datetime
from trader.valuation.relative import RelativeValuation


# 估值方法说明
METHOD_DESCRIPTIONS = {
    "PE": {
        "name": "市盈率估值法 (PE)",
        "desc": "基于行业合理市盈率 × 每股收益(EPS) 估算合理股价。适用于盈利稳定、周期性弱的公司。",
        "formula": "合理股价 = EPS × 行业合理PE",
        "suitable": "盈利稳定的成熟企业，如消费、医药行业",
    },
    "PB": {
        "name": "市净率估值法 (PB)",
        "desc": "基于行业合理市净率 × 每股净资产(BVPS) 估算合理股价。适用于重资产行业。",
        "formula": "合理股价 = BVPS × 行业合理PB",
        "suitable": "银行、保险、地产等重资产行业，或周期股底部",
    },
    "PS": {
        "name": "市销率估值法 (PS)",
        "desc": "基于营业收入 × 行业PS比率 估算合理市值。适用于盈利不稳定但营收稳定的公司。",
        "formula": "合理股价 = (营业收入 × 行业PS) / 总股本",
        "suitable": "成长期、尚未盈利的科技/互联网公司，或零售行业",
    },
    "PEG": {
        "name": "市盈率相对盈利增长比率 (PEG)",
        "desc": "基于盈利增长率调整PE，PEG=1为合理。适用于高成长公司。",
        "formula": "合理PE = 净利润增长率 × 100 (PEG=1时)",
        "suitable": "高速成长期的公司，如科技、新能源",
    },
}


class ValuationEngine:
    """
    估值引擎调度器
    支持单只股票、批量股票的多种估值方法运行
    """

    def __init__(self):
        self.val = RelativeValuation()

    # ════════════════════════════════════
    # 股票基本信息
    # ════════════════════════════════════

    def get_stock_info(self, code: str) -> Dict:
        """
        获取股票基本信息: 名称、行业、当前价、PE、PB、市值、股息率
        """
        info = {"code": code, "name": "", "industry": "", "current_price": None,
                "pe": None, "pb": None, "market_cap": None, "dividend_yield": None}

        # 名称
        try:
            from trader.data.stock import Stock
            s = Stock()
            try:
                stocks = s.get_all_stocks()
                for st in stocks:
                    if st["code"] == code:
                        info["name"] = st.get("name", "")
                        break
            finally:
                s.close()
        except:
            pass

        # 行业
        try:
            from trader.db.valuation_models import StockIndustry
            from trader.db.orm import SessionLocal
            session = SessionLocal()
            try:
                si = session.query(StockIndustry).filter(StockIndustry.code == code).first()
                if si:
                    info["industry"] = si.industry_name
            finally:
                session.close()
        except:
            pass

        # 当前价、PE
        cp, pe = self.val._get_current_price_pe(code)
        info["current_price"] = cp
        info["pe"] = pe

        # PB、股息率（从估值缓存）
        try:
            from trader.db.orm import SessionLocal, Valuation
            session = SessionLocal()
            try:
                v = session.query(Valuation).filter(Valuation.code == code).order_by(Valuation.trade_date.desc()).first()
                if v:
                    info["pb"] = float(v.pb) if v.pb else info["pb"]
                    info["dividend_yield"] = float(v.dividend_yield) if v.dividend_yield else info["dividend_yield"]
            finally:
                session.close()
        except:
            pass

                # 补充：价格、市值、PE、PB
        # 多数据源回退：东方财富API → 新浪实时 → 本地数据计算
        _prefix = "sh" if code.startswith("6") else "sz" if code.startswith(("0", "3")) else "bj"
        _secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
        _ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

        # 1. 新浪实时行情（最稳定，获取价格和名称）
        if not info["current_price"] or not info["name"]:
            try:
                import requests as _req
                url = f"https://hq.sinajs.cn/list={_prefix}{code}"
                resp = _req.get(url, headers={"Referer": "https://finance.sina.com.cn", "User-Agent": _ua}, timeout=3)
                resp.encoding = "gbk"
                text = resp.text.strip()
                if text and text.startswith("var"):
                    parts = text.split('"')
                    if len(parts) >= 2:
                        data = parts[1].split(",")
                        if len(data) >= 4:
                            if not info["name"] and data[0]:
                                info["name"] = data[0]
                            if not info["current_price"] and data[3]:
                                try:
                                    info["current_price"] = float(data[3])
                                except (ValueError, IndexError):
                                    pass
            except Exception:
                pass

        # 2. 东方财富直连API（价格、市值、PE、PB）
        if not info["market_cap"] or not info["pe"] or not info["pb"]:
            try:
                import requests as _req
                url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={_secid}&fields=f43,f58,f116,f162,f167"
                resp = _req.get(url, headers={"Referer": "https://quote.eastmoney.com/", "User-Agent": _ua}, timeout=3)
                if resp.status_code == 200:
                    d = resp.json().get("data")
                    if d:
                        if not info["current_price"] and d.get("f43") is not None:
                            info["current_price"] = float(d["f43"]) / 100.0 if d["f43"] > 1000 else float(d["f43"])
                        if not info["name"] and d.get("f58"):
                            info["name"] = d["f58"]
                        if not info["market_cap"] and d.get("f116") is not None and d["f116"] > 0:
                            info["market_cap"] = float(d["f116"])
                        if not info["pe"] and d.get("f162") is not None and d["f162"] > 0:
                            info["pe"] = float(d["f162"]) / 100.0
                        if not info["pb"] and d.get("f167") is not None and d["f167"] > 0:
                            info["pb"] = float(d["f167"]) / 100.0
            except Exception:
                pass

        # 3. 从本地数据计算 PE 和 PB
        # PE = 当前价 / EPS
        if not info["pe"] and info.get("current_price"):
            try:
                eps = self.val._get_eps(code)
                if eps and eps > 0:
                    info["pe"] = round(info["current_price"] / eps, 2)
            except Exception:
                pass

        # PB = 当前价 / BVPS
        if not info["pb"] and info.get("current_price"):
            try:
                bvps = self.val._get_bvps(code)
                if bvps and bvps > 0:
                    info["pb"] = round(info["current_price"] / bvps, 2)
            except Exception:
                pass

        # 4. 如果没有市值，用股价 × 总股本估算
        if not info["market_cap"] and info.get("current_price"):
            try:
                tot_shares = self.val._get_total_shares(code)
                if tot_shares:
                    info["market_cap"] = info["current_price"] * tot_shares
            except Exception:
                pass

        return info

    def get_method_descriptions(self) -> Dict:
        """获取估值方法说明字典"""
        return dict(METHOD_DESCRIPTIONS)

    # ════════════════════════════════════
    # 单只股票估值
    # ════════════════════════════════════

    def valuate_stock(self, code: str,
                       methods: List[str] = None,
                       save: bool = True) -> Dict:
        """
        对单只股票运行指定估值方法
        :param code: 股票代码
        :param methods: 估值方法列表，默认全跑 ["PE", "PB", "PS", "PEG"]
        :param save: 是否保存结果到数据库
        :return: 各方法结果 + 综合评估
        """
        methods = methods or ["PE", "PB", "PS", "PEG"]
        results = {}

        for m in methods:
            try:
                if m == "PE":
                    r = self.val.valuate_pe(code)
                elif m == "PB":
                    r = self.val.valuate_pb(code)
                elif m == "PS":
                    r = self.val.valuate_ps(code)
                elif m == "PEG":
                    r = self.val.valuate_peg(code)
                else:
                    continue
                results[m] = r
            except Exception as e:
                results[m] = {"code": code, "method": m, "error": str(e)}

        # 综合评估
        summary = self._summarize(code, results)
        results["_summary"] = summary

        return results

    # ════════════════════════════════════
    # 批量估值
    # ════════════════════════════════════

    def valuate_batch(self, codes: List[str],
                       methods: List[str] = None,
                       progress_callback=None) -> Dict[str, Dict]:
        """
        批量估值
        :param codes: 股票代码列表
        :param methods: 估值方法列表
        :param progress_callback: 进度回调函数 func(current, total, code)
        :return: {code: {PE: {...}, PB: {...}, ...}}
        """
        results = {}
        total = len(codes)

        for i, code in enumerate(codes):
            if progress_callback:
                progress_callback(i + 1, total, code)

            results[code] = self.valuate_stock(code, methods)

        return results

    # ════════════════════════════════════
    # 综合评估
    # ════════════════════════════════════

    def _summarize(self, code: str, results: Dict) -> Dict:
        """
        汇总各估值方法的结果，给出综合判断
        """
        fair_prices = []
        deviations = []

        for method, r in results.items():
            if method.startswith("_"):
                continue
            if "error" in r:
                continue
            fp = r.get("fair_price")
            dev = r.get("deviation")
            if fp and fp > 0:
                fair_prices.append(fp)
            if dev is not None:
                deviations.append(dev)

        if not fair_prices:
            return {"verdict": "数据不足", "fair_price": None}

        avg_fair = round(sum(fair_prices) / len(fair_prices), 2)
        avg_dev = round(sum(deviations) / len(deviations), 2) if deviations else None

        # 判断低估/高估
        if avg_dev and avg_dev < -20:
            verdict = "低估"
        elif avg_dev and avg_dev < -5:
            verdict = "偏低"
        elif avg_dev and avg_dev > 20:
            verdict = "高估"
        elif avg_dev and avg_dev > 5:
            verdict = "偏高"
        else:
            verdict = "合理"

        # 最乐观/最悲观
        min_fair = min(fair_prices) if fair_prices else None
        max_fair = max(fair_prices) if fair_prices else None

        return {
            "verdict": verdict,
            "avg_fair_price": avg_fair,
            "price_range": (round(min_fair, 2), round(max_fair, 2)) if min_fair and max_fair else None,
            "avg_deviation": avg_dev,
            "methods_used": len(fair_prices),
        }

    # ════════════════════════════════════
    # 格式化估值结果用于AI分析
    # ════════════════════════════════════

    def format_for_ai(self, code: str, methods: List[str], results: Dict) -> str:
        """将估值结果格式化为适合AI分析的文字"""
        info = self.get_stock_info(code)
        lines = []
        lines.append(f"股票: {code} {info.get('name', '')}")
        lines.append(f"行业: {info.get('industry', '未知')}")
        lines.append(f"当前股价: {info.get('current_price', '未知')} 元")
        lines.append(f"当前PE: {info.get('pe', '未知')}")
        lines.append(f"当前PB: {info.get('pb', '未知')}")
        if info.get('market_cap'):
            lines.append(f"总市值: {info['market_cap']/1e8:.2f} 亿元")
        lines.append("")

        summary = results.get("_summary", {})
        for method in methods:
            r = results.get(method)
            if not r or "error" in r:
                continue
            desc = METHOD_DESCRIPTIONS.get(method, {})
            lines.append(f"【{desc.get('name', method)}】")
            lines.append(f"  合理股价: {r.get('fair_price', '-')} 元")
            lines.append(f"  合理区间: ({r.get('price_range_low', '-')}, {r.get('price_range_high', '-')})")
            dev = r.get("deviation")
            if dev is not None:
                tag = "高估" if dev > 0 else "低估"
                lines.append(f"  偏离度: {dev:+.2f}% ({tag})")
            lines.append("")

        if summary:
            lines.append(f"【综合评估】")
            lines.append(f"  判断: {summary.get('verdict', '-')}")
            lines.append(f"  平均合理股价: {summary.get('avg_fair_price', '-')} 元")
            if summary.get("price_range"):
                lines.append(f"  综合区间: {summary['price_range']}")
            lines.append(f"  平均偏离度: {summary.get('avg_deviation', '-')}%")

        return "\n".join(lines)

    # ════════════════════════════════════
    # 格式化输出
    # ════════════════════════════════════

    @staticmethod
    def format_result(results: Dict) -> str:
        """将估值结果格式化为可读文本"""
        lines = []
        code = None

        summary = results.pop("_summary", None)

        for method, r in results.items():
            if "error" in r:
                lines.append(f"  [{method}] {r['error']}")
                continue
            if not code:
                code = r.get("code", "")
                lines.append(f"股票: {code}")

            lines.append(f"")
            lines.append(f"  ── {method}估值 ──")
            lines.append(f"    合理股价: {r.get('fair_price', '-')} 元")
            lines.append(f"    合理区间: ({r.get('price_range_low', '-')}, {r.get('price_range_high', '-')}) 元")
            dev = r.get("deviation")
            if dev is not None:
                tag = "高估" if dev > 0 else "低估"
                lines.append(f"    偏离度: {dev:+.2f}% ({tag})")

        if summary:
            lines.append(f"")
            lines.append(f"  ── 综合评估 ──")
            lines.append(f"    判断: {summary.get('verdict', '-')}")
            lines.append(f"    平均合理股价: {summary.get('avg_fair_price', '-')} 元")
            if summary.get("price_range"):
                lines.append(f"    综合区间: {summary['price_range']}")
            lines.append(f"    平均偏离度: {summary.get('avg_deviation', '-')}%")

        return "\n".join(lines)


# ════════════════════════════════════
# 快捷入口
# ════════════════════════════════════

def quick_valuate(code: str, methods: List[str] = None) -> Dict:
    """快速估值单只股票"""
    engine = ValuationEngine()
    return engine.valuate_stock(code, methods)


def batch_valuate(codes: List[str], methods: List[str] = None,
                   progress_callback=None) -> Dict[str, Dict]:
    """批量估值"""
    engine = ValuationEngine()
    return engine.valuate_batch(codes, methods, progress_callback)


if __name__ == "__main__":
    # 测试茅台
    result = quick_valuate("600519")
    print(ValuationEngine.format_result(result))
