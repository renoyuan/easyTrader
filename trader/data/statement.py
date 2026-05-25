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

class StatementDownload:
    def __init__(self):
        # 不在构造器创建长期 session，改为每次操作用独立 session（更安全）
        self.session = SessionLocal()

        # 字段映射表
        self.INCOME_MAP = {
            "序号": "seq",
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
        }

        self.CASHFLOW_MAP = {
            "序号": "seq",
            "净现金流-净现金流": "net_cashflow",
            "净现金流-同比增长": "net_cashflow_yoy",
            "经营性现金流-现金流量净额": "operating_cashflow",
            "经营性现金流-净现金流占比": "operating_cashflow_ratio",
            "投资性现金流-现金流量净额": "investing_cashflow",
            "投资性现金流-净现金流占比": "investing_cashflow_ratio",
            "融资性现金流-现金流量净额": "financing_cashflow",
            "融资性现金流-净现金流占比": "financing_cashflow_ratio",
        }

        self.BALANCE_MAP = {
            "序号": "seq",
            "资产-货币资金": "cash",
            "资产-应收账款": "accounts_receivable",
            "资产-存货": "inventory",
            "资产-总资产": "total_assets",
            "资产-总资产同比": "total_assets_yoy",
            "负债-应付账款": "accounts_payable",
            "负债-总负债": "total_liabilities",
            "负债-预收账款": "advance_receipts",
            "负债-总负债同比": "total_liabilities_yoy",
            "资产负债率": "debt_ratio",
            "股东权益合计": "total_equity",
        }

        self.PERFORMANCE_MAP = {
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
    
    
    def to_number(self, v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except:
            try:
                return int(v)
            except:
                return v
    
    def clean_value(self, v):
        """清洗数据：处理 NaN、NaT，转为 None"""
        import pandas as pd
        if pd.isna(v) or v is pd.NaT:
            return None
        try:
            if isinstance(v, (float, int)):
                return float(v) if not pd.isna(v) else None
        except:
            pass
        return v if v not in (None, "", "NaT") else None
    
    # ==========================
    # 1. 利润表
    # ==========================
    def download_income(self, year):
        date = f"{year}1231"
        try:
            df = ak.stock_lrb_em(date=date)
        except Exception as e:
            print(f"❌ 利润表下载失败 {date}: {e}")
            return

        count = 0
        for _, row in df.iterrows():
            code = str(row.get("股票代码", "")).strip()
            name = row.get("股票简称", "")
            if not code:
                continue

            kwargs = {
                "code": code,
                "name": name,
                "report_date": date,
                "year": year,
            }

            # 按字段映射自动赋值
            for cn_col, orm_attr in self.INCOME_MAP.items():
                val = row.get(cn_col)
                try:
                    kwargs[orm_attr] = float(val) if val not in (None, "", "None") else None
                except:
                    kwargs[orm_attr] = None

            try:
                self.session.merge(Income(**kwargs))
                count += 1
            except Exception as e:
                continue

        self.session.commit()
        print(f"✅ 利润表 入库: {count} 条")

    # ==========================
    # 2. 现金流量表
    # ==========================
    def download_cashflow(self, year):
        date = f"{year}1231"
        print(f"📥 下载现金流量表 {year}...")

        try:
            df = ak.stock_xjll_em(date=date)
        except Exception as e:
            print(f"❌ 现金流量表下载失败: {e}")
            return

        count = 0
        for _, row in df.iterrows():
            code = str(row.get("股票代码", "")).strip()
            name = row.get("股票简称", "")
            if not code:
                continue

            data = {
                "code": code,
                "name": name,
                "report_date": date,
                "year": year,
            }

            # 按映射自动赋值
            for cn_field, attr in self.CASHFLOW_MAP.items():
                val = row.get(cn_field)
                try:
                    data[attr] = float(val) if val not in (None, "", "None") else None
                except:
                    data[attr] = None

            try:
                self.session.merge(Cashflow(**data))
                count += 1
            except Exception as e:
                continue

        self.session.commit()
        print(f"✅ 现金流量表 入库: {count} 条")


    # ==========================
    # 3. 资产负债表
    # ==========================
    def download_balance(self, year):
        date = f"{year}1231"
        print(f"📥 下载资产负债表 {year}...")

        try:
            df = ak.stock_zcfz_em(date=date)
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return

        count = 0
        for _, row in df.iterrows():
            code = str(row.get("股票代码", "")).strip()
            name = row.get("股票简称", "")
            if not code:
                continue

            data = {
                "code": code,
                "name": name,
                "report_date": date,
                "year": year,
            }

            for cn_field, attr in self.BALANCE_MAP.items():
                data[attr] = self.to_number(row.get(cn_field))

            self.session.merge(Balance(**data))
            count += 1

        self.session.commit()
        print(f"✅ 资产负债表 入库: {count} 条")
    

    # ==========================
    # 4. 业绩报表
    # ==========================
    def download_performance(self, year):
        date = f"{year}1231"
        try:
            df = ak.stock_yjbb_em(date=date)
        except:
            return

        count = 0
        for _, row in df.iterrows():
            code = row.get("股票代码") or row.get("代码")
            name = row.get("股票简称") or row.get("名称")
            kwargs = {"code": code, "name": name, "report_date": date, "year": year}

            for cn, attr in self.PERFORMANCE_MAP.items():
                if cn in row:
                    kwargs[attr] = self.to_number(row.get(cn))

            try:
                with SessionLocal() as session:
                    session.merge(Performance(**kwargs))
                    session.commit()
                count += 1
            except Exception as e:
                print(f"⚠️ performance 插入失败 {code}: {e}")
                continue
        print(f"✅ 业绩报表 入库: {count} 条")


    # ==========================
    # 5. 分红送配
    # ==========================
    def download_dividend(self, year):
        date = f"{year}1231"
        print(f"📥 下载分红送配 {year}...")

        try:
            df = ak.stock_fhps_em(date=date)
        except Exception as e:
            print(f"❌ 分红下载失败: {e}")
            return

        count = 0
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            name = row.get("名称", "")
            if not code:
                continue

            # ✅ 关键：所有日期、空值自动清洗
            data = {
                "code": code,
                "name": name,
                "report_date": date,
                "year": year,
                "seq": self.clean_value(row.get("序号")),
                "bonus_total_ratio": self.clean_value(row.get("送转股份-送转总比例")),
                "bonus_ratio": self.clean_value(row.get("送转股份-送转比例")),
                "transfer_ratio": self.clean_value(row.get("送转股份-转股比例")),
                "cash_dividend_ratio": self.clean_value(row.get("现金分红-现金分红比例")),
                "dividend_yield": self.clean_value(row.get("现金分红-股息率")),
                "eps": self.clean_value(row.get("每股收益")),
                "navps": self.clean_value(row.get("每股净资产")),
                "capital_reserve_ps": self.clean_value(row.get("每股公积金")),
                "undistributed_profit_ps": self.clean_value(row.get("每股未分配利润")),
                "net_profit_yoy": self.clean_value(row.get("净利润同比增长")),
                "total_shares": self.clean_value(row.get("总股本")),
                "plan_announce_date": self.clean_value(row.get("预案公告日")),
                "register_date": self.clean_value(row.get("股权登记日")),      # NaT → None
                "ex_dividend_date": self.clean_value(row.get("除权除息日")),    # NaT → None
                "plan_status": self.clean_value(row.get("方案进度")),
                "last_announce_date": self.clean_value(row.get("最新公告日期")),
            }

            try:
                self.session.merge(Dividend(** data))
                count += 1
            except Exception as e:
                continue

        self.session.commit()
        print(f"✅ 分红送配 入库: {count} 条")
    
    
    # ==========================
    # 下载一整年所有 5 张报表
    # ==========================
    def download_year(self, year):
        print(f"\n===== 下载 {year} 年全部报表 =====")
        self.download_income(year)
        self.download_cashflow(year)
        self.download_balance(year)
        self.download_performance(year)
        self.download_dividend(year)
    
     # ==========================
    # 查看数据库统计
    # ==========================
    def check_db(self):
        print("\n===== 数据库统计 =====")
        with SessionLocal() as session:
            print("income:", session.query(Income).count())
            print("cashflow:", session.query(Cashflow).count())
            print("balance:", session.query(Balance).count())
            print("performance:", session.query(Performance).count())
            print("dividend:", session.query(Dividend).count())


# ==========================
# 主程序调用
# ==========================
if __name__ == "__main__":
    st = StatementDownload()

    # 下载 2012 ~ 2025 年报
    for year in range(2013, 2026):
        st.download_year(year)
        time.sleep(1)

    st.check_db()
    print("\n🎉 全部完成")