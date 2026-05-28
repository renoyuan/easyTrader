"""
SQLAlchemy ORM模型定义
数据库：股票财务报表 + 基础信息 + K线数据表
"""
import os,sys
from sqlalchemy import create_engine
from sqlalchemy import Column, String, Float, Integer, Text, Date, DateTime, BigInteger, VARCHAR
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()


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
# ==========================
# 数据库连接配置（支持 pyinstaller 打包后路径）
# ==========================
def _get_db_path():
    """统一数据库路径：打包后找 exe 同级的 db/ 目录"""
    if getattr(sys, 'frozen', False):
        # pyinstaller 打包环境
        base = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_dir = os.path.join(base, 'db')
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, 'stock_data.sqlite')

DB_FILE = _get_db_path()
DB_DIR = os.path.dirname(DB_FILE)
os.makedirs(DB_DIR, exist_ok=True)
DB_backslash = chr(92)
DB_PATH = f"sqlite:///{DB_FILE.replace(DB_backslash, '/')}"
# SQLite 在多线程/多session下可能需要关闭同一线程校验
engine = create_engine(DB_PATH, echo=False, future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

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
# 财务指标表（新浪财经财务分析指标离线缓存）
# ==========================
class FinancialIndicator(Base):
    """新浪财经-财务指标，按(stock_code, report_date)去重"""
    __tablename__ = "financial_indicator"

    code = Column(String(20), primary_key=True, comment="股票代码")
    report_date = Column(String(10), primary_key=True, comment="报告日期（如 2024-12-31）")
    year = Column(Integer, nullable=True, comment="年份")

    # ── 盈利能力 ──
    roe = Column(Float, nullable=True, comment="净资产收益率(%)")
    roa = Column(Float, nullable=True, comment="总资产净利润率(%)")
    gross_margin = Column(Float, nullable=True, comment="销售毛利率(%)")
    net_profit_margin = Column(Float, nullable=True, comment="销售净利率(%)")
    operating_margin = Column(Float, nullable=True, comment="营业利润率(%)")

    # ── 运营效率 ──
    inventory_turnover = Column(Float, nullable=True, comment="存货周转率(次)")
    ar_turnover = Column(Float, nullable=True, comment="应收账款周转率(次)")
    total_asset_turnover = Column(Float, nullable=True, comment="总资产周转率(次)")

    # ── 偿债能力 ──
    current_ratio = Column(Float, nullable=True, comment="流动比率")
    quick_ratio = Column(Float, nullable=True, comment="速动比率")
    debt_ratio_sina = Column(Float, nullable=True, comment="资产负债率(%)")

    # ── 现金流 ──
    ocf_to_profit = Column(Float, nullable=True, comment="经营现金净流量与净利润的比率(%)")
    ocf_to_revenue = Column(Float, nullable=True, comment="经营现金净流量对销售收入比率(%)")

    # ── 增长 ──
    revenue_growth = Column(Float, nullable=True, comment="主营业务收入增长率(%)")
    profit_growth = Column(Float, nullable=True, comment="净利润增长率(%)")
    asset_growth = Column(Float, nullable=True, comment="总资产增长率(%)")

    # ── 每股指标 ──
    eps = Column(Float, nullable=True, comment="摊薄每股收益(元)")
    navps = Column(Float, nullable=True, comment="每股净资产(元)")
    ocfps = Column(Float, nullable=True, comment="每股经营性现金流(元)")

    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


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


# 模块导入时自动建表（关键：无论开发环境还是 exe 都会执行）
init_db()


if __name__ == "__main__":
    print(f"✅ 数据库路径: {DB_FILE}")
    print(f"✅ 数据库大小: {os.path.getsize(DB_FILE) / 1024 / 1024:.1f} MB")
    # 校验所有表是否存在
    from sqlalchemy import inspect
    insp = inspect(engine)
    tables = insp.get_table_names()
    print(f"✅ 已建表: {tables}")
