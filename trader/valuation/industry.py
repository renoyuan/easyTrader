# -*- coding: utf-8 -*-
"""
申万行业管理模块
- 下载申万三级行业数据入库
- 维护行业合理估值区间
- 股票-行业关联同步
"""

import akshare as ak
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime
from trader.db.orm import SessionLocal
from trader.db.valuation_models import SwIndustry, StockIndustry


class IndustryManager:
    """
    申万行业管理
    1. 下载一/二/三级行业信息入库
    2. 同步股票与行业的关联关系
    3. 查询行业信息及估值基准
    """

    def __init__(self):
        self.session = SessionLocal()

    # ════════════════════════════════════
    # 1. 行业数据下载入库
    # ════════════════════════════════════

    def download_all(self) -> dict:
        """
        下载申万三级全量行业数据并入库
        返回各级数量统计
        """
        result = {}
        result["一级"] = self._download_level(1)
        result["二级"] = self._download_level(2)
        result["三级"] = self._download_level(3)
        return result

    def _download_level(self, level: int) -> int:
        """
        下载指定级别的申万行业数据
        level: 1-一级 2-二级 3-三级
        """
        try:
            if level == 1:
                df = ak.sw_index_first_info()
            elif level == 2:
                df = ak.sw_index_second_info()
            elif level == 3:
                df = ak.sw_index_third_info()
            else:
                return 0

            if df.empty:
                return 0

            count = 0
            for _, row in df.iterrows():
                code = row.get("行业代码", "")
                name = row.get("行业名称", "")
                members = row.get("成份个数")

                # 二级行业有上级行业字段
                parent = row.get("上级行业") if level == 2 else None

                # 估值数据
                pe_static = self._to_float(row.get("静态市盈率"))
                pe_ttm = self._to_float(row.get("TTM(滚动)市盈率"))
                pb = self._to_float(row.get("市净率"))
                dy = self._to_float(row.get("静态股息率"))

                obj = SwIndustry(
                    code=code,
                    name=name,
                    level=level,
                    parent_code=parent,
                    member_count=members,
                    pe_static=pe_static,
                    pe_ttm=pe_ttm,
                    pb=pb,
                    dividend_yield=dy,
                )
                try:
                    self.session.merge(obj)
                    count += 1
                except Exception:
                    continue

            self.session.commit()
            print(f"  ✅ 申万{level}级行业 {count} 条入库")
            return count
        except Exception as e:
            print(f"  ❌ 申万{level}级行业下载失败: {e}")
            self.session.rollback()
            return 0

    # ════════════════════════════════════
    # 2. 股票-行业关联同步
    # ════════════════════════════════════

    def sync_stock_industry(self) -> int:
        """
        从东方财富行业接口同步股票-行业关联
        每个行业通过 stock_board_industry_cons_em 获取成份股
        建立 股票 -> 行业名称 的关联
        """
        # 获取东方财富行业列表
        try:
            boards = ak.stock_board_industry_name_em()
        except Exception as e:
            print(f"  ❌ 获取行业列表失败: {e}")
            return 0

        total = 0
        for _, row in boards.iterrows():
            board_name = row.get("板块名称", "")
            board_code = row.get("板块代码", "")
            if not board_name or not board_code:
                continue
            # 用东方财富的原始名称传参（含 Ⅱ Ⅲ 等字符）
            count = self._sync_em_industry_cons(board_name, board_code)
            total += count

        print(f"  ✅ 股票-行业关联同步完成，共 {total} 条")
        return total

    def _sync_em_industry_cons(self, board_name: str, board_code: str) -> int:
        """同步单个东方财富行业的成份股"""
        try:
            df = ak.stock_board_industry_cons_em(symbol=board_name)
            if df.empty:
                return 0

            count = 0
            for _, row in df.iterrows():
                stock_code = str(row.get("代码", "")).strip()
                stock_name = row.get("名称", "")
                if not stock_code:
                    continue

                self._upsert_stock_industry(
                    code=stock_code,
                    name=stock_name,
                    industry_code=board_code,
                    industry_name=board_name,
                    level=0  # 东方财富行业不分级，统一为0
                )
                count += 1

            self.session.commit()
            return count
        except Exception as e:
            print(f"  ⚠️ 同步 {board_name} 成份股失败: {e}")
            self.session.rollback()
            return 0

    def _upsert_stock_industry(self, code: str, name: str,
                                industry_code: str, industry_name: str, level: int):
        """插入或更新股票-行业关联"""
        existing = self.session.query(StockIndustry).filter(
            StockIndustry.code == code,
            StockIndustry.industry_code == industry_code,
        ).first()
        if existing:
            existing.name = name
            existing.update_time = datetime.now()
        else:
            obj = StockIndustry(
                code=code,
                name=name,
                industry_code=industry_code,
                industry_name=industry_name,
                level=level,
            )
            self.session.add(obj)

    # ════════════════════════════════════
    # 3. 行业估值基准自动计算
    # ════════════════════════════════════

    def calc_industry_pe_range(self) -> int:
        """
        根据申万行业接口的PE数据，结合历史经验系数，估算合理PE区间
        规则：
        - 低PE行业（银行/钢铁等）：区间 = PE_ttm * 0.7 ~ PE_ttm * 1.5
        - 中等PE行业：区间 = PE_ttm * 0.6 ~ PE_ttm * 2.0
        - 高PE行业（科技/医药等）：区间 = PE_ttm * 0.5 ~ PE_ttm * 2.5
        - 同时限制最低不低于5，最高不超过200
        """
        industries = self.session.query(SwIndustry).filter(
            SwIndustry.pe_ttm.isnot(None)
        ).all()

        count = 0
        for ind in industries:
            pe = ind.pe_ttm
            if pe is None or pe <= 0:
                continue

            # 根据PE绝对值设定浮动系数
            if pe < 10:        # 低PE行业（银行/周期）
                low = pe * 0.7
                high = pe * 1.5
            elif pe < 20:      # 中等偏低
                low = pe * 0.6
                high = pe * 2.0
            elif pe < 40:      # 中等偏高
                low = pe * 0.5
                high = pe * 2.5
            else:              # 高PE行业（科技/成长）
                low = pe * 0.4
                high = pe * 3.0

            ind.pe_range_low = round(max(low, 5), 2)
            ind.pe_range_high = round(min(high, 200), 2)
            count += 1

        self.session.commit()
        print(f"  ✅ 更新 {count} 个行业的PE基准区间（基于行业PE推算）")
        return count

    # ════════════════════════════════════
    # 4. 查询接口
    # ════════════════════════════════════

    def get_stock_industries(self, code: str) -> List[Dict]:
        """
        获取股票所属的所有行业（三级体系）
        返回: [{"level": 1, "code": "801010.SI", "name": "农林牧渔"},
               {"level": 2, ...}, {"level": 3, ...}]
        """
        try:
            # 通过三级行业关联反查
            third = self.session.query(StockIndustry).filter(
                StockIndustry.code == code,
                StockIndustry.level == 3
            ).first()
            if not third:
                return []

            industries = []
            # 三级
            ind3 = self.session.query(SwIndustry).filter(
                SwIndustry.code == third.industry_code
            ).first()
            if ind3:
                industries.append({
                    "level": 3, "code": ind3.code,
                    "name": ind3.name,
                    "pe_range": (ind3.pe_range_low, ind3.pe_range_high),
                })
                # 二级
                if ind3.parent_code:
                    ind2 = self.session.query(SwIndustry).filter(
                        SwIndustry.code == ind3.parent_code
                    ).first()
                    if ind2:
                        industries.append({
                            "level": 2, "code": ind2.code,
                            "name": ind2.name,
                            "pe_range": (ind2.pe_range_low, ind2.pe_range_high),
                        })
                        # 一级
                        if ind2.parent_code:
                            ind1 = self.session.query(SwIndustry).filter(
                                SwIndustry.code == ind2.parent_code
                            ).first()
                            if ind1:
                                industries.append({
                                    "level": 1, "code": ind1.code,
                                    "name": ind1.name,
                                    "pe_range": (ind1.pe_range_low, ind1.pe_range_high),
                                })
            return industries
        except Exception:
            return []

    def get_industry_by_code(self, code: str) -> Optional[Dict]:
        """根据行业代码查询"""
        row = self.session.query(SwIndustry).filter(
            SwIndustry.code == code
        ).first()
        if row:
            return {
                "code": row.code,
                "name": row.name,
                "level": row.level,
                "parent_code": row.parent_code,
                "pe_ttm": row.pe_ttm,
                "pe_range": (row.pe_range_low, row.pe_range_high),
                "pb_range": (row.pb_range_low, row.pb_range_high),
            }
        return None

    def close(self):
        self.session.close()

    # ════════════════════════════════════
    # 工具方法
    # ════════════════════════════════════

    @staticmethod
    def _to_float(v):
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


# ════════════════════════════════════
# 快捷入口
# ════════════════════════════════════

def download_sw_industry():
    """一键下载申万三级行业数据"""
    mgr = IndustryManager()
    try:
        print("[Download] 开始下载申万行业数据...")
        result = mgr.download_all()
        print(f"\n📊 入库统计:")
        for k, v in result.items():
            print(f"  {k}: {v} 条")
        return result
    finally:
        mgr.close()


def sync_all_stock_industry():
    """一键同步所有股票行业归属"""
    mgr = IndustryManager()
    try:
        print("📥 开始同步股票行业归属...")
        count = mgr.sync_stock_industry()
        return count
    finally:
        mgr.close()


def calc_industry_pe_ranges():
    """一键计算各行业合理PE区间"""
    mgr = IndustryManager()
    try:
        print("📊 开始计算行业PE基准区间...")
        count = mgr.calc_industry_pe_range()
        return count
    finally:
        mgr.close()


if __name__ == "__main__":
    # 测试
    download_sw_industry()
    sync_all_stock_industry()
