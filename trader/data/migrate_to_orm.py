"""
迁移脚本：把旧表中的 data JSON 字段解析为新 ORM 列。
运行方式：
    python migrate_to_orm.py

功能：
1. 自动创建 ORM 表（不存在则创建）
2. 自动从旧表读取 JSON 数据并写入新 ORM 表
3. 自动处理字段映射
"""
import sqlite3
import json
import os
from sqlalchemy import text
from orm import (
    SessionLocal, engine,  # 注意：这里必须引入 engine
    Base,                  # 用来创建表
    Balance, Cashflow, Income, Performance, Dividend
)

# ====================== 数据库路径 ======================
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "db")
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "stock_data.sqlite")

# ====================== 字段映射 ======================
INCOME_MAP = {
    "净利润": "net_profit",
    "净利润同比": "net_profit_yoy",
    "营业总收入": "total_revenue",
    "营业总收入同比": "total_revenue_yoy",
    "营业总支出-营业支出": "total_cost",
    "营业总支出-销售费用": "selling_expense",
    "营业总支出-管理费用": "admin_expense",
    "营业总支出-财务费用": "financial_expense",
    "营业总支出-营业总支出": "total_cost_sum",
    "营业利润": "operating_profit",
    "利润总额": "total_profit",
    "序号": "seq",
    "公告日期": "report_date",
}

BALANCE_MAP = INCOME_MAP.copy()
PERFORMANCE_MAP = {
    "每股收益": "eps",
    "营业总收入-营业总收入": "total_revenue",
    "营业总收入-同比增长": "total_revenue_yoy",
    "营业总收入-季度环比增长": "total_revenue_qoq",
    "净利润-净利润": "net_profit",
    "净利润-同比增长": "net_profit_yoy",
    "净利润-季度环比增长": "net_profit_qoq",
    "每股净资产": "navps",
    "净资产收益率": "roe",
    "每股经营现金流量": "operating_cashflow_ps",
    "销售毛利率": "gross_margin",
    "所处行业": "industry",
    "最新公告日期": "last_announce_date",
    "序号": "seq",
}

CASHFLOW_MAP = {
    "净现金流-净现金流": "net_cashflow",
    "净现金流-同比增长": "net_cashflow_yoy",
    "经营性现金流-现金流量净额": "operating_cashflow",
    "经营性现金流-净现金流占比": "operating_cashflow_ratio",
    "投资性现金流-现金流量净额": "investing_cashflow",
    "投资性现金流-净现金流占比": "investing_cashflow_ratio",
    "融资性现金流-现金流量净额": "financing_cashflow",
    "融资性现金流-净现金流占比": "financing_cashflow_ratio",
    "序号": "seq",
    "公告日期": "report_date",
}

DIVIDEND_MAP = {
    "代码": "code",
    "名称": "name",
    "送转股份-送转总比例": "bonus_total_ratio",
    "送转股份-送转比例": "bonus_ratio",
    "送转股份-转股比例": "transfer_ratio",
    "现金分红-现金分红比例": "cash_dividend_ratio",
    "现金分红-股息率": "dividend_yield",
    "每股收益": "eps",
    "每股净资产": "navps",
    "每股公积金": "capital_reserve_ps",
    "每股未分配利润": "undistributed_profit_ps",
    "净利润同比增长": "net_profit_yoy",
    "总股本": "total_shares",
    "预案公告日": "plan_announce_date",
    "股权登记日": "register_date",
    "除权除息日": "ex_dividend_date",
    "方案进度": "plan_status",
    "最新公告日期": "last_announce_date",
}

# ====================== 工具函数 ======================
def to_number(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except:
        try:
            return int(v)
        except:
            return v

# ====================== 核心：创建所有 ORM 表 ======================
def create_all_tables():
    print("正在创建所有 ORM 表（不存在则创建）...")
    # 关键：SQLAlchemy 自动创建所有表
    Base.metadata.create_all(bind=engine)
    print("表创建完成！")

# ====================== 迁移表数据 ======================
def migrate_table(table_name, orm_cls, mapping):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 检查旧表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not cursor.fetchone():
        print(f"旧表 {table_name} 不存在，跳过迁移")
        conn.close()
        return

    # 读取旧数据
    cursor.execute(f"SELECT code, name, report_date, year, data FROM {table_name}")
    rows = cursor.fetchall()

    session = SessionLocal()
    count = 0

    for code, name, report_date, year, data_text in rows:
        if not data_text:
            continue
        try:
            data = json.loads(data_text)
        except:
            continue

        kwargs = {
            "code": code,
            "name": name,
            "report_date": report_date,
            "year": year
        }

        # 映射字段
        for cn, attr in mapping.items():
            if cn in data:
                kwargs[attr] = to_number(data.get(cn))

        # 合并写入 ORM
        obj = orm_cls(**kwargs)
        session.merge(obj)
        count += 1

    session.commit()
    session.close()
    conn.close()
    print(f"迁移 {table_name} 完成：{count} 行")

# ====================== 主程序 ======================
if __name__ == '__main__':
    print("开始迁移到 ORM 表...")

    # 第一步：自动创建所有表！！！（你之前缺的就是这个）
    create_all_tables()

    # 第二步：迁移数据
    migrate_table('income', Income, INCOME_MAP)
    migrate_table('balance', Balance, BALANCE_MAP)
    migrate_table('performance', Performance, PERFORMANCE_MAP)
    migrate_table('cashflow', Cashflow, CASHFLOW_MAP)
    migrate_table('dividend', Dividend, DIVIDEND_MAP)

    print("🎉 全部迁移完成！")