"""
SQLAlchemy ORM模型定义
"""
from sqlalchemy import create_engine
from sqlalchemy import Column, String, Float, Integer, Text, Date, DateTime, BigInteger, VARCHAR
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

# 股票基础信息表（修复 SQLite 自增主键）
class StockBasic(Base):
    __tablename__ = "stock_basic"

    # ✅ 修复：SQLite 使用 Integer 自增主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    code = Column(VARCHAR(20), nullable=False, unique=True, comment="股票代码")
    name = Column(VARCHAR(50), nullable=False, comment="股票名称")
    market = Column(VARCHAR(20), nullable=False, comment="市场 SH/SZ/BJ")
    list_status = Column(VARCHAR(10), default="L", comment="上市状态")
    industry = Column(VARCHAR(50), default="", comment="所属行业")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间"
    )

    def __repr__(self):
        return f"<StockBasic(code={self.code}, name={self.name})>"

# 资产负债表
class Balance(Base):
    __tablename__ = 'balance'
    code = Column(String, primary_key=True)
    name = Column(String)
    report_date = Column(String, primary_key=True)
    seq = Column(Integer, nullable=True)
    net_profit = Column(Float, nullable=True)
    net_profit_yoy = Column(Float, nullable=True)
    total_revenue = Column(Float, nullable=True)
    total_revenue_yoy = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    selling_expense = Column(Float, nullable=True)
    admin_expense = Column(Float, nullable=True)
    financial_expense = Column(Float, nullable=True)
    total_cost_sum = Column(Float, nullable=True)
    operating_profit = Column(Float, nullable=True)
    total_profit = Column(Float, nullable=True)
    data = Column(Text, nullable=True)

class Cashflow(Base):
    __tablename__ = 'cashflow'
    code = Column(String, primary_key=True)
    name = Column(String)
    report_date = Column(String, primary_key=True)
    year = Column(Integer, nullable=True)
    seq = Column(Integer, nullable=True)
    net_cashflow = Column(Float, nullable=True)
    net_cashflow_yoy = Column(Float, nullable=True)
    operating_cashflow = Column(Float, nullable=True)
    operating_cashflow_ratio = Column(Float, nullable=True)
    investing_cashflow = Column(Float, nullable=True)
    investing_cashflow_ratio = Column(Float, nullable=True)
    financing_cashflow = Column(Float, nullable=True)
    financing_cashflow_ratio = Column(Float, nullable=True)

class Income(Base):
    __tablename__ = 'income'
    code = Column(String, primary_key=True)
    name = Column(String)
    report_date = Column(String, primary_key=True)
    year = Column(Integer, nullable=True)
    seq = Column(Integer, nullable=True)
    net_profit = Column(Float, nullable=True)
    net_profit_yoy = Column(Float, nullable=True)
    total_revenue = Column(Float, nullable=True)
    total_revenue_yoy = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    selling_expense = Column(Float, nullable=True)
    admin_expense = Column(Float, nullable=True)
    financial_expense = Column(Float, nullable=True)
    total_cost_sum = Column(Float, nullable=True)
    operating_profit = Column(Float, nullable=True)
    total_profit = Column(Float, nullable=True)

class Performance(Base):
    __tablename__ = 'performance'
    code = Column(String, primary_key=True)
    name = Column(String)
    report_date = Column(String, primary_key=True)
    year = Column(Integer, nullable=True)
    seq = Column(Integer, nullable=True)
    eps = Column(Float, nullable=True)
    total_revenue = Column(Float, nullable=True)
    total_revenue_yoy = Column(Float, nullable=True)
    total_revenue_qoq = Column(Float, nullable=True)
    net_profit = Column(Float, nullable=True)
    net_profit_yoy = Column(Float, nullable=True)
    net_profit_qoq = Column(Float, nullable=True)
    navps = Column(Float, nullable=True)
    roe = Column(Float, nullable=True)
    operating_cashflow_ps = Column(Float, nullable=True)
    gross_margin = Column(Float, nullable=True)
    industry = Column(String, nullable=True)
    last_announce_date = Column(String, nullable=True)

class Dividend(Base):
    __tablename__ = 'dividend'
    code = Column(String, primary_key=True)
    name = Column(String)
    report_date = Column(String, primary_key=True)
    year = Column(Integer, nullable=True)
    seq = Column(Integer, nullable=True)
    bonus_total_ratio = Column(Float, nullable=True)
    bonus_ratio = Column(Float, nullable=True)
    transfer_ratio = Column(Float, nullable=True)
    cash_dividend_ratio = Column(Float, nullable=True)
    dividend_yield = Column(Float, nullable=True)
    eps = Column(Float, nullable=True)
    navps = Column(Float, nullable=True)
    capital_reserve_ps = Column(Float, nullable=True)
    undistributed_profit_ps = Column(Float, nullable=True)
    net_profit_yoy = Column(Float, nullable=True)
    total_shares = Column(Integer, nullable=True)
    plan_announce_date = Column(String, nullable=True)
    register_date = Column(String, nullable=True)
    ex_dividend_date = Column(String, nullable=True)
    plan_status = Column(String, nullable=True)
    last_announce_date = Column(String, primary_key=True)

# 数据库连接
DB_PATH = 'sqlite:///../../db/stock_data.sqlite'
engine = create_engine(DB_PATH, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def create_stock_table_class(code: str):
    table_name = f"stock_{code}"
    class StockKline(Base):
        __tablename__ = table_name
        __table_args__ = {'extend_existing': True}
        date = Column(Date, primary_key=True)
        ts_code = Column(String(10), primary_key=True)
        open = Column(Float, nullable=True)
        close = Column(Float, nullable=True)
        high = Column(Float, nullable=True)
        low = Column(Float, nullable=True)
        volume = Column(Integer, nullable=True)
        amount = Column(Float, nullable=True)
        amplitude = Column(Float, nullable=True)
        pct_chg = Column(Float, nullable=True)
        change = Column(Float, nullable=True)
        turnover_rate = Column(Float, nullable=True)
    return StockKline

def init_db():
    Base.metadata.create_all(engine)