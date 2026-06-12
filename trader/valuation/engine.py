# -*- coding: utf-8 -*-
"""
估值引擎
- 整合所有估值方法（PE/PB/PS/PEG）
- 批量运行指定方法
- 综合估值结果汇总
"""

from typing import List, Optional, Dict
from datetime import datetime
from trader.valuation.relative import RelativeValuation


class ValuationEngine:
    """
    估值引擎调度器
    支持单只股票、批量股票的多种估值方法运行
    """

    def __init__(self):
        self.val = RelativeValuation()

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
