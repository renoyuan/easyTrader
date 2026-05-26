"""
SQLAlchemy ORM模型定义
数据库：股票财务报表 + 基础信息 + K线数据表
"""
import os
from sqlalchemy import create_engine
from sqlalchemy import Column, String, Float, Integer, Text, Date, DateTime, BigInteger, VARCHAR
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

# ==========================
# 数据库连接配置（使用项目内绝对路径以避免工作目录导致的路径问题）
# ==========================
DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'stock_data.sqlite'))
DB_DIR = os.path.dirname(DB_FILE)
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = f"sqlite:///{DB_FILE.replace('\\', '/')}"
# SQLite 在多线程/多session下可能需要关闭同一线程校验
engine = create_engine(DB_PATH, echo=False, future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ==========================
# 股票基础信息表
# ==========================

class StockBasic(Base):
    __tablename__ = "stock_basic"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键ID")
    code = Column(VARCHAR(20), nullable=False, unique=True, comment="股票代码")
    name = Column(VARCHAR(50), nullable=False, comment="股票名称")
    market = Column(VARCHAR(20), nullable=False, comment="市场 SH-上证 SZ-深证 BJ-北证")
    list_status = Column(VARCHAR(10), default="L", comment="上市状态 L-上市")
    industry = Column(VARCHAR(50), default="", comment="所属行业")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间"
    )

    def __repr__(self):
        return f"<StockBasic(code={self.code}, name={self.name})>"

# ==========================
# 利润表
# ==========================
class Income(Base):
    __tablename__ = 'income'
    code = Column(String, primary_key=True, comment="股票代码")
    name = Column(String, comment="股票简称")
    report_date = Column(String, primary_key=True, comment="报告日期")
    year = Column(Integer, nullable=True, comment="年份")
    
    seq                  = Column(Integer, nullable=True, comment="序号")
    net_profit           = Column(Float, nullable=True, comment="净利润")
    net_profit_yoy       = Column(Float, nullable=True, comment="净利润同比")
    total_revenue        = Column(Float, nullable=True, comment="营业总收入")
    total_revenue_yoy    = Column(Float, nullable=True, comment="营业总收入同比")
    total_cost           = Column(Float, nullable=True, comment="营业总支出-营业支出")
    selling_expense      = Column(Float, nullable=True, comment="营业总支出-销售费用")
    admin_expense        = Column(Float, nullable=True, comment="营业总支出-管理费用")
    financial_expense    = Column(Float, nullable=True, comment="营业总支出-财务费用")
    total_cost_sum       = Column(Float, nullable=True, comment="营业总支出-营业总支出")
    operating_profit     = Column(Float, nullable=True, comment="营业利润")
    total_profit         = Column(Float, nullable=True, comment="利润总额")
    


# ==========================
# 现金流量表
# ==========================
class Cashflow(Base):
    __tablename__ = 'cashflow'
    code = Column(String, primary_key=True, comment="股票代码")
    name = Column(String, comment="股票简称")
    report_date = Column(String, primary_key=True, comment="报告日期")
    year = Column(Integer, nullable=True, comment="年份")
    seq = Column(Integer, nullable=True, comment="序号")
    
    net_cashflow = Column(Float, nullable=True, comment="净现金流-净现金流")
    net_cashflow_yoy = Column(Float, nullable=True, comment="净现金流-同比增长")
    
    operating_cashflow = Column(Float, nullable=True, comment="经营性现金流-现金流量净额")
    operating_cashflow_ratio = Column(Float, nullable=True, comment="经营性现金流-净现金流占比")
    
    investing_cashflow = Column(Float, nullable=True, comment="投资性现金流-现金流量净额")
    investing_cashflow_ratio = Column(Float, nullable=True, comment="投资性现金流-净现金流占比")
    
    financing_cashflow = Column(Float, nullable=True, comment="融资性现金流-现金流量净额")
    financing_cashflow_ratio = Column(Float, nullable=True, comment="融资性现金流-净现金流占比")
    

# ==========================
# 资产负债表
# ==========================
class Balance(Base):
    __tablename__ = 'balance'
    code = Column(String, primary_key=True, comment="股票代码")
    name = Column(String, comment="股票简称")
    report_date = Column(String, primary_key=True, comment="公告日期")
    year = Column(Integer, nullable=True, comment="年份")
    seq = Column(Integer, nullable=True, comment="序号")

    # 资产端
    cash = Column(Float, nullable=True, comment="货币资金（元）")
    accounts_receivable = Column(Float, nullable=True, comment="应收账款（元）")
    inventory = Column(Float, nullable=True, comment="存货（元）")
    total_assets = Column(Float, nullable=True, comment="总资产（元）")
    total_assets_yoy = Column(Float, nullable=True, comment="总资产同比（%）")

    # 负债端
    accounts_payable = Column(Float, nullable=True, comment="应付账款（元）")
    total_liabilities = Column(Float, nullable=True, comment="总负债（元）")
    advance_receipts = Column(Float, nullable=True, comment="预收账款（元）")
    total_liabilities_yoy = Column(Float, nullable=True, comment="总负债同比（%）")

    # 其他指标
    debt_ratio = Column(Float, nullable=True, comment="资产负债率（%）")
    total_equity = Column(Float, nullable=True, comment="股东权益合计（元）")



# ==========================
# 业绩报表
# ==========================
class Performance(Base):
    __tablename__ = 'performance'
    code = Column(String, primary_key=True, comment="股票代码")
    name = Column(String, comment="股票简称")
    report_date = Column(String, primary_key=True, comment="报告日期")
    year = Column(Integer, nullable=True, comment="年份")
    seq = Column(Integer, nullable=True, comment="序号")
    eps = Column(Float, nullable=True, comment="每股收益")
    total_revenue = Column(Float, nullable=True, comment="营业总收入")
    total_revenue_yoy = Column(Float, nullable=True, comment="营业总收入同比")
    total_revenue_qoq = Column(Float, nullable=True, comment="营业总收入季度环比")
    net_profit = Column(Float, nullable=True, comment="净利润")
    net_profit_yoy = Column(Float, nullable=True, comment="净利润同比")
    net_profit_qoq = Column(Float, nullable=True, comment="净利润季度环比")
    navps = Column(Float, nullable=True, comment="每股净资产")
    roe = Column(Float, nullable=True, comment="净资产收益率")
    operating_cashflow_ps = Column(Float, nullable=True, comment="每股经营现金流")
    gross_margin = Column(Float, nullable=True, comment="销售毛利率")
    industry = Column(String, nullable=True, comment="所属行业")
    last_announce_date = Column(String, nullable=True, comment="最新公告日期")

# ==========================
# 分红送配表（股息）
# ==========================
class Dividend(Base):
    __tablename__ = 'dividend'
    code = Column(String, primary_key=True, comment="股票代码")
    name = Column(String, comment="股票简称")
    report_date = Column(String, primary_key=True, comment="报告日期")
    year = Column(Integer, nullable=True, comment="年份")
    seq = Column(Integer, nullable=True, comment="序号")
    bonus_total_ratio = Column(Float, nullable=True, comment="送转总比例")
    bonus_ratio = Column(Float, nullable=True, comment="送股比例")
    transfer_ratio = Column(Float, nullable=True, comment="转股比例")
    cash_dividend_ratio = Column(Float, nullable=True, comment="现金分红比例")
    dividend_yield = Column(Float, nullable=True, comment="股息率")
    eps = Column(Float, nullable=True, comment="每股收益")
    navps = Column(Float, nullable=True, comment="每股净资产")
    capital_reserve_ps = Column(Float, nullable=True, comment="每股公积金")
    undistributed_profit_ps = Column(Float, nullable=True, comment="每股未分配利润")
    net_profit_yoy = Column(Float, nullable=True, comment="净利润同比增长")
    total_shares = Column(Integer, nullable=True, comment="总股本")
    plan_announce_date = Column(String, nullable=True, comment="预案公告日")
    register_date = Column(String, nullable=True, comment="股权登记日")
    ex_dividend_date = Column(String, nullable=True, comment="除权除息日")
    plan_status = Column(String, nullable=True, comment="方案进度")
    last_announce_date = Column(String, primary_key=True, comment="最新公告日期")



# ==========================
# 动态创建单股票K线表
# ==========================
def create_stock_table_class(code: str):
    table_name = f"stock_{code}"
    class StockKline(Base):
        __tablename__ = table_name
        __table_args__ = {'extend_existing': True}
        
        date = Column(Date, primary_key=True, comment="交易日期")
        ts_code = Column(String(10), primary_key=True, comment="股票代码")
        open = Column(Float, nullable=True, comment="开盘价")
        close = Column(Float, nullable=True, comment="收盘价")
        high = Column(Float, nullable=True, comment="最高价")
        low = Column(Float, nullable=True, comment="最低价")
        volume = Column(Integer, nullable=True, comment="成交量")
        amount = Column(Float, nullable=True, comment="成交额")
        amplitude = Column(Float, nullable=True, comment="振幅")
        pct_chg = Column(Float, nullable=True, comment="涨跌幅")
        change = Column(Float, nullable=True, comment="涨跌额")
        turnover_rate = Column(Float, nullable=True, comment="换手率")
    return StockKline

# ==========================
# 初始化数据库表
# ==========================
def init_db():
    Base.metadata.create_all(engine)
    
if __name__ == "__main__":
    init_db()
