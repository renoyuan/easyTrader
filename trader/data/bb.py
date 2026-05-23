"""
#!/usr/bin/env python
-*- coding: utf-8 -*-
PROJECT_NAME: F:\opensource\easyTrader\trader\data
CREATE_TIME: 2026-05-12 
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno 
note:  股票数据获取与管理模块，支持多数据源下载、加载与本地数据库操作。
"""
import akshare as ak
import pandas as pd
import sqlite3  # 仅用于原有表，dividend表已用ORM
import json
import os
import time
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# ORM相关导入
from orm import (
    Dividend,
    Balance,
    Cashflow,
    Income,
    Performance,
    SessionLocal,
    init_db as orm_init_db,
)

import pathlib
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "db")
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "stock_data.sqlite")

# ==========================================
# 数据库连接
# ==========================================
def get_conn():
    conn = sqlite3.connect(DB_FILE)

    # WAL 模式（非常重要）
    conn.execute("PRAGMA journal_mode=WAL;")

    # 性能优化
    conn.execute("PRAGMA synchronous=NORMAL;")

    return conn


# ==========================================
# 建表
# ==========================================
def init_db():

    conn = get_conn()

    tables = ["income", "cashflow", "balance", "performance"]  # dividend表用ORM建表

    for table in tables:
        conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {table} (
            code TEXT,
            name TEXT,
            report_date TEXT,
            year INTEGER,
            data TEXT,
            PRIMARY KEY(code, report_date)
        )
        ''')
    # ORM建表
    orm_init_db()

    conn.commit()
    conn.close()


# ==========================================
# DataFrame -> 批量 tuples
# ==========================================
def df_to_rows(df, report_date, year):

    rows = []

    for _, row in df.iterrows():

        row = row.fillna("")

        code = str(row.get("股票代码", ""))
        name = str(row.get("股票简称", ""))

        # Series -> dict -> json
        json_data = json.dumps(
            row.to_dict(),
            ensure_ascii=False,
            default=str
        )

        rows.append((
            code,
            name,
            report_date,
            year,
            json_data
        ))

    return rows


# ==========================================
# 批量保存
# ==========================================
def save_batch(conn, table, rows):

    sql = f'''
    INSERT OR REPLACE INTO {table}
    (code, name, report_date, year, data)
    VALUES (?, ?, ?, ?, ?)
    '''

    conn.executemany(sql, rows)


# ==========================================
# 拉取单年
# ==========================================
def fetch_year(year):
    date = f"{year}1231"
    print(f"\n===== 拉取 {year} 年 =====")
    try:
        datasets = {
            "income": ak.stock_lrb_em(date=date),
            "cashflow": ak.stock_xjll_em(date=date),
            "balance": ak.stock_zcfz_em(date=date),
            "performance": ak.stock_yjbb_em(date=date),
        }
        # 股息率数据
        try:
            dividend_df = ak.stock_fhps_em(date=date)
        except Exception as e:
            print(f"⚠️ 股息率数据获取失败: {e}")
            dividend_df = pd.DataFrame()

        # 使用 ORM 插入 income/cashflow/balance/performance
        session = SessionLocal()

        # 字段映射（中文->ORM属性），以 akshare 返回列为准
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

        # helper
        def to_number(v):
            if v is None or v == "":
                return None
            try:
                return float(v)
            except Exception:
                try:
                    return int(v)
                except Exception:
                    return v

        # process each dataset
        mapping_info = {
            "income": (Income, INCOME_MAP),
            "cashflow": (Cashflow, CASHFLOW_MAP),
            "balance": (Balance, BALANCE_MAP),
            "performance": (Performance, PERFORMANCE_MAP),
        }

        for table, df in datasets.items():
            print(f"{table}: {len(df)} 条")
            if df.empty:
                print(f"⚠️ {table} 无数据")
                continue
            orm_cls, cmap = mapping_info.get(table)
            migrated = 0
            for _, row in df.iterrows():
                # base fields
                code = row.get("股票代码") or row.get("代码") or None
                name = row.get("股票简称") or row.get("名称") or None
                # report_date may be provided in DataFrame columns
                report_date = date
                year_val = year
                kwargs = {"code": code, "name": name, "report_date": report_date, "year": year_val}
                for cn, attr in cmap.items():
                    if cn in row.index:
                        kwargs[attr] = to_number(row.get(cn))
                try:
                    obj = orm_cls(**kwargs)
                    session.merge(obj)
                    migrated += 1
                except Exception as e:
                    print(f"⚠️ 插入 {table} 行失败: {e}")
            print(f"✅ {table} ORM 入库完成：{migrated} 条")
        session.commit()
        session.close()

        # 股息率数据入库（ORM方式）
        if not dividend_df.empty:
            session = SessionLocal()
            for _, row in dividend_df.iterrows():
                obj = Dividend(
                    code=row.get("代码", None),
                    name=row.get("名称", None),
                    report_date=date,
                    year=year,
                    bonus_total_ratio=row.get("送转股份-送转总比例", None),
                    bonus_ratio=row.get("送转股份-送转比例", None),
                    transfer_ratio=row.get("送转股份-转股比例", None),
                    cash_dividend_ratio=row.get("现金分红-现金分红比例", None),
                    dividend_yield=row.get("现金分红-股息率", None),
                    eps=row.get("每股收益", None),
                    navps=row.get("每股净资产", None),
                    capital_reserve_ps=row.get("每股公积金", None),
                    undistributed_profit_ps=row.get("每股未分配利润", None),
                    net_profit_yoy=row.get("净利润同比增长", None),
                    total_shares=row.get("总股本", None),
                    plan_announce_date=row.get("预案公告日", None),
                    register_date=row.get("股权登记日", None),
                    ex_dividend_date=row.get("除权除息日", None),
                    plan_status=row.get("方案进度", None),
                    last_announce_date=row.get("最新公告日期", None)
                )
                session.merge(obj)
            session.commit()
            session.close()
            print(f"✅ 股息率数据入库完成（ORM）")
        else:
            print(f"⚠️ 股息率数据为空")

        # 统计经营现金流缺失数量
        cashflow_df = datasets["cashflow"]
        if not cashflow_df.empty:
            # 常见字段名：“经营活动产生的现金流量净额”
            col_candidates = ["经营活动产生的现金流量净额", "经营现金流量净额"]
            col = None
            for c in col_candidates:
                if c in cashflow_df.columns:
                    col = c
                    break
            if col:
                missing_count = cashflow_df[col].isna().sum() + (cashflow_df[col] == "").sum()
                print(f"⚠️ 经营现金流净额缺失数量: {missing_count}")
            else:
                print(f"⚠️ 未找到经营现金流净额字段")
        else:
            print(f"⚠️ 现金流数据为空，无法统计经营现金流缺失")

        conn.commit()
        conn.close()
        print(f"🎉 {year} 年全部完成")
    except Exception as e:
        print(f"❌ {year} 失败: {e}")

# ==========================================
# 查看数据库统计
# ==========================================
def check_db():
    print("\n===== 数据库统计 =====")
    session = SessionLocal()
    try:
        income_count = session.query(Income).count()
        cashflow_count = session.query(Cashflow).count()
        balance_count = session.query(Balance).count()
        performance_count = session.query(Performance).count()
        dividend_count = session.query(Dividend).count()

        print(f"income: {income_count}")
        print(f"cashflow: {cashflow_count}")
        print(f"balance: {balance_count}")
        print(f"performance: {performance_count}")
        print(f"dividend: {dividend_count}")
    finally:
        session.close()


# ==========================================
# 主程序
# ==========================================
if __name__ == "__main__":

    # 首次跑可以删库
    # if os.path.exists(DB_FILE):
    #     os.remove(DB_FILE)

    init_db()

    print("✅ 数据库初始化完成")

    # 拉取年报
    for year in range(2012, 2026):

        fetch_year(year)

        # 防止东方财富限流
        time.sleep(1)

    check_db()

    print("\n🎉 全部完成")