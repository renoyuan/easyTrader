# -*- coding: utf-8 -*-
"""
估值系统 ORM 模型
申万行业分级、股票-行业关联、估值结果
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, VARCHAR, Text
from datetime import datetime

# 复用主项目的 Base，保持同引擎
from trader.db.orm import Base


# ==========================
# 申万行业分级表
# ==========================
class SwIndustry(Base):
    """
    申万行业分级表（一级/二级/三级）
    数据来源：akshare sw_index_first_info / sw_index_second_info / sw_index_third_info
    """
    __tablename__ = "sw_industry"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    code = Column(VARCHAR(20), nullable=False, unique=True, comment="行业代码，如 801010.SI")
    name = Column(VARCHAR(100), nullable=False, comment="行业名称")
    level = Column(Integer, nullable=False, comment="层级 1-一级 2-二级 3-三级")
    parent_code = Column(VARCHAR(20), nullable=True, comment="上级行业代码，一级为 NULL")
    member_count = Column(Integer, nullable=True, comment="成份个数")

    # 行业估值基准
    pe_static = Column(Float, nullable=True, comment="静态市盈率")
    pe_ttm = Column(Float, nullable=True, comment="TTM滚动市盈率")
    pb = Column(Float, nullable=True, comment="市净率")
    dividend_yield = Column(Float, nullable=True, comment="静态股息率(%)")

    # 合理估值区间
    pe_range_low = Column(Float, nullable=True, comment="合理PE下限")
    pe_range_high = Column(Float, nullable=True, comment="合理PE上限")
    pb_range_low = Column(Float, nullable=True, comment="合理PB下限")
    pb_range_high = Column(Float, nullable=True, comment="合理PB上限")

    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<SwIndustry(level={self.level}, code={self.code}, name={self.name})>"


# ==========================
# 股票-行业关联表（多对多）
# ==========================
class StockIndustry(Base):
    """
    股票与申万行业的多对多关联
    一只股票可属于多个行业（如三级行业同时归属于二级、一级）
    数据来源：akshare sw_index_third_cons
    """
    __tablename__ = "stock_industry"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    code = Column(VARCHAR(20), nullable=False, comment="股票代码")
    name = Column(VARCHAR(50), nullable=True, comment="股票简称")
    industry_code = Column(VARCHAR(20), nullable=False, comment="行业代码")
    industry_name = Column(VARCHAR(100), nullable=True, comment="行业名称")
    level = Column(Integer, nullable=False, comment="所属层级 1/2/3")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<StockIndustry(code={self.code}, industry={self.industry_name})>"


# ==========================
# 估值结果表
# ==========================
class ValuationResult(Base):
    """
    估值结果表
    每次估值计算的结果存储在此
    """
    __tablename__ = "valuation_result"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    code = Column(VARCHAR(20), nullable=False, comment="股票代码")
    trade_date = Column(VARCHAR(10), nullable=False, comment="估值日期")
    method = Column(VARCHAR(20), nullable=False, comment="估值方法: PE/PB/PS/PEG/EVEBITDA/DCF/DDM")

    # 合理股价区间
    fair_price = Column(Float, nullable=True, comment="合理股价")
    price_range_low = Column(Float, nullable=True, comment="合理股价下限")
    price_range_high = Column(Float, nullable=True, comment="合理股价上限")

    # 合理市值区间
    fair_mv = Column(Float, nullable=True, comment="合理市值(亿元)")
    mv_range_low = Column(Float, nullable=True, comment="合理市值下限(亿元)")
    mv_range_high = Column(Float, nullable=True, comment="合理市值上限(亿元)")

    # 当前实际值
    current_price = Column(Float, nullable=True, comment="当前股价")
    current_pe = Column(Float, nullable=True, comment="当前PE(TTM)")
    current_pb = Column(Float, nullable=True, comment="当前PB")

    # 估值偏离度（%）
    deviation = Column(Float, nullable=True, comment="偏离度% (正=高估, 负=低估)")

    # 估值参数（JSON格式存储）
    params_json = Column(Text, nullable=True, comment="估值参数JSON")

    create_time = Column(DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<ValuationResult(code={self.code}, method={self.method}, date={self.trade_date})>"
