# -*- coding: utf-8 -*-
"""
股票数据获取与管理模块，支持多数据源下载、加载与本地数据库操作。
"""
import akshare as ak
import pandas as pd
import time
from datetime import datetime

from trader.db.orm import (
    Dividend, Balance, Cashflow, Income, Performance,
    FinancialIndicator, SessionLocal, init_db as orm_init_db,
)


# ── 字段映射表（类常量） ──
INCOME_MAP = {
    "序号": "seq", "净利润": "net_profit", "净利润同比": "net_profit_yoy",
    "营业总收入": "total_revenue", "营业总收入同比": "total_revenue_yoy",
    "营业总支出-营业支出": "total_cost", "营业总支出-销售费用": "selling_expense",
    "营业总支出-管理费用": "admin_expense", "营业总支出-财务费用": "financial_expense",
    "营业总支出-营业总支出": "total_cost_sum", "营业利润": "operating_profit",
    "利润总额": "total_profit",
}

CASHFLOW_MAP = {
    "序号": "seq", "净现金流-净现金流": "net_cashflow",
    "净现金流-同比增长": "net_cashflow_yoy",
    "经营性现金流-现金流量净额": "operating_cashflow",
    "经营性现金流-净现金流占比": "operating_cashflow_ratio",
    "投资性现金流-现金流量净额": "investing_cashflow",
    "投资性现金流-净现金流占比": "investing_cashflow_ratio",
    "融资性现金流-现金流量净额": "financing_cashflow",
    "融资性现金流-净现金流占比": "financing_cashflow_ratio",
}

BALANCE_MAP = {
    "序号": "seq", "资产-货币资金": "cash", "资产-应收账款": "accounts_receivable",
    "资产-存货": "inventory", "资产-总资产": "total_assets",
    "资产-总资产同比": "total_assets_yoy", "负债-应付账款": "accounts_payable",
    "负债-总负债": "total_liabilities", "负债-预收账款": "advance_receipts",
    "负债-总负债同比": "total_liabilities_yoy", "资产负债率": "debt_ratio",
    "股东权益合计": "total_equity",
}

PERFORMANCE_MAP = {
    "每股收益": "eps", "营业总收入-营业总收入": "total_revenue",
    "营业总收入-同比增长": "total_revenue_yoy",
    "营业总收入-季度环比增长": "total_revenue_qoq",
    "净利润-净利润": "net_profit", "净利润-同比增长": "net_profit_yoy",
    "净利润-季度环比增长": "net_profit_qoq", "每股净资产": "navps",
    "净资产收益率": "roe", "每股经营现金流量": "operating_cashflow_ps",
    "销售毛利率": "gross_margin", "所处行业": "industry",
    "最新公告日期": "last_announce_date", "序号": "seq",
}


class StatementDownload:

    def __init__(self):
        self.session = SessionLocal()

    # ═══════════════════════════════════════
    #  数据查询方法
    # ═══════════════════════════════════════

    def get_performance_df(self, code: str, years=None) -> pd.DataFrame:
        with SessionLocal() as session:
            q = session.query(Performance).filter(Performance.code == code)
            if years:
                q = q.filter(Performance.year.in_(years))
            rows = q.order_by(Performance.year.asc(), Performance.report_date.asc()).all()
            return self._rows_to_df(rows)

    def get_dividend_df(self, code: str, years=None) -> pd.DataFrame:
        with SessionLocal() as session:
            q = session.query(Dividend).filter(Dividend.code == code)
            if years:
                q = q.filter(Dividend.year.in_(years))
            rows = q.order_by(Dividend.year.asc(), Dividend.report_date.asc()).all()
            return self._rows_to_df(rows)

    def get_kline_df(self, code: str, start=None, end=None) -> pd.DataFrame:
        from trader.data.stock import Stock
        return Stock().get_daily_kline(code, start, end)

    def get_income_df(self, code: str, years=None) -> pd.DataFrame:
        with SessionLocal() as session:
            q = session.query(Income).filter(Income.code == code)
            if years:
                q = q.filter(Income.year.in_(years))
            rows = q.order_by(Income.year.asc(), Income.report_date.asc()).all()
            return self._rows_to_df(rows)

    def get_balance_df(self, code: str, years=None) -> pd.DataFrame:
        with SessionLocal() as session:
            q = session.query(Balance).filter(Balance.code == code)
            if years:
                q = q.filter(Balance.year.in_(years))
            rows = q.order_by(Balance.year.asc(), Balance.report_date.asc()).all()
            return self._rows_to_df(rows)

    def get_cashflow_df(self, code: str, years=None) -> pd.DataFrame:
        with SessionLocal() as session:
            q = session.query(Cashflow).filter(Cashflow.code == code)
            if years:
                q = q.filter(Cashflow.year.in_(years))
            rows = q.order_by(Cashflow.year.asc(), Cashflow.report_date.asc()).all()
            return self._rows_to_df(rows)

    def get_financial_indicator_df(self, code: str, years: list = None) -> pd.DataFrame:
        with SessionLocal() as session:
            q = session.query(FinancialIndicator).filter(FinancialIndicator.code == code)
            if years:
                q = q.filter(FinancialIndicator.year.in_(years))
            records = q.order_by(FinancialIndicator.year.asc(), FinancialIndicator.report_date.asc()).all()
        if not records:
            self.download_financial_indicator(code, years)
            with SessionLocal() as session:
                q = session.query(FinancialIndicator).filter(FinancialIndicator.code == code)
                if years:
                    q = q.filter(FinancialIndicator.year.in_(years))
                records = q.order_by(FinancialIndicator.year.asc(), FinancialIndicator.report_date.asc()).all()
        return self._rows_to_df(records)

    # ═══════════════════════════════════════
    #  批量下载方法
    # ═══════════════════════════════════════

    def download_income(self, year: int):
        date = f"{year}1231"
        try:
            df = ak.stock_lrb_em(date=date)
        except Exception as e:
            print(f"fail 利润表 {date}: {e}")
            return
        count = 0
        for _, row in df.iterrows():
            code = str(row.get("股票代码", "")).strip()
            name = row.get("股票简称", "")
            if not code:
                continue
            kwargs = {"code": code, "name": name, "report_date": date, "year": year}
            for cn_col, orm_attr in INCOME_MAP.items():
                kwargs[orm_attr] = self._to_float(row.get(cn_col))
            try:
                self.session.merge(Income(**kwargs))
                count += 1
            except Exception:
                continue
        self.session.commit()
        print(f"OK 利润表 {year}: {count}")

    def download_cashflow(self, year: int):
        date = f"{year}1231"
        print(f"downloading 现金流量表 {year}...")
        try:
            df = ak.stock_xjll_em(date=date)
        except Exception as e:
            print(f"fail 现金流量表 {year}: {e}")
            return
        count = 0
        for _, row in df.iterrows():
            code = str(row.get("股票代码", "")).strip()
            name = row.get("股票简称", "")
            if not code:
                continue
            data = {"code": code, "name": name, "report_date": date, "year": year}
            for cn_field, attr in CASHFLOW_MAP.items():
                data[attr] = self._to_float(row.get(cn_field))
            try:
                self.session.merge(Cashflow(**data))
                count += 1
            except Exception:
                continue
        self.session.commit()
        print(f"OK 现金流量表 {year}: {count}")

    def download_balance(self, year: int):
        date = f"{year}1231"
        print(f"downloading 资产负债表 {year}...")
        try:
            df = ak.stock_zcfz_em(date=date)
        except Exception as e:
            print(f"fail {e}")
            return
        count = 0
        for _, row in df.iterrows():
            code = str(row.get("股票代码", "")).strip()
            name = row.get("股票简称", "")
            if not code:
                continue
            data = {"code": code, "name": name, "report_date": date, "year": year}
            for cn_field, attr in BALANCE_MAP.items():
                data[attr] = self._to_float(row.get(cn_field))
            self.session.merge(Balance(**data))
            count += 1
        self.session.commit()
        print(f"OK 资产负债表 {year}: {count}")

    def download_performance(self, year: int):
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
            for cn, attr in PERFORMANCE_MAP.items():
                if cn in row:
                    kwargs[attr] = self._to_float(row.get(cn))
            try:
                with SessionLocal() as session:
                    session.merge(Performance(**kwargs))
                    session.commit()
                count += 1
            except Exception:
                continue
        print(f"OK 业绩报表 {year}: {count}")

    def download_dividend(self, year: int):
        date = f"{year}1231"
        print(f"downloading 分红送配 {year}...")
        try:
            df = ak.stock_fhps_em(date=date)
        except Exception as e:
            print(f"fail {e}")
            return
        count = 0
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            name = row.get("名称", "")
            if not code:
                continue
            data = {
                "code": code, "name": name, "report_date": date, "year": year,
                "seq": self._to_int(row.get("序号")),
                "bonus_total_ratio": self._to_float(row.get("送转股份-送转总比例")),
                "bonus_ratio": self._to_float(row.get("送转股份-送转比例")),
                "transfer_ratio": self._to_float(row.get("送转股份-转股比例")),
                "cash_dividend_ratio": self._to_float(row.get("现金分红-现金分红比例")),
                "dividend_yield": self._to_float(row.get("现金分红-股息率")),
                "eps": self._to_float(row.get("每股收益")),
                "navps": self._to_float(row.get("每股净资产")),
                "capital_reserve_ps": self._to_float(row.get("每股公积金")),
                "undistributed_profit_ps": self._to_float(row.get("每股未分配利润")),
                "net_profit_yoy": self._to_float(row.get("净利润同比增长")),
                "total_shares": self._to_float(row.get("总股本")),
                "plan_announce_date": self._to_str(row.get("预案公告日")),
                "register_date": self._to_str(row.get("股权登记日")),
                "ex_dividend_date": self._to_str(row.get("除权除息日")),
                "plan_status": self._to_str(row.get("方案进度")),
                "last_announce_date": self._to_str(row.get("最新公告日期")),
            }
            try:
                self.session.merge(Dividend(**data))
                count += 1
            except Exception:
                continue
        self.session.commit()
        print(f"OK 分红送配 {year}: {count}")

    def download_financial_indicator(self, code: str, years: list = None) -> int:
        current_year = datetime.now().year
        if years is None:
            years = list(range(current_year - 5, current_year + 1))
        min_year = min(years) - 1
        max_year = max(years)
        try:
            with SessionLocal() as session:
                existing = session.query(FinancialIndicator.year).filter(
                    FinancialIndicator.code == code,
                    FinancialIndicator.year >= min_year,
                    FinancialIndicator.year <= max_year,
                ).distinct().all()
                existing_years = {r[0] for r in existing}
                need_years = [y for y in years if y not in existing_years]
                if not need_years:
                    return 0
                min_year = min(need_years) - 1
            print(f"  [fin_indicator] downloading {code} ({min_year}~{max_year})...")
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year=str(min_year))
            if df.empty:
                print(f"  [fin_indicator] {code} no data")
                return 0
            df["日期_dt"] = pd.to_datetime(df["日期"])
            df["year"] = df["日期_dt"].dt.year
            df = df[df["year"].between(min_year, max_year)]
            count = 0
            with SessionLocal() as session:
                for _, row in df.iterrows():
                    rdate = row.get("日期")
                    yr = int(row["year"]) if pd.notna(row["year"]) else None
                    if not rdate or not yr:
                        continue
                    data = {
                        "code": code, "report_date": str(rdate)[:10], "year": yr,
                        "roe": self._to_float(row.get("净资产收益率(%)")),
                        "roa": self._to_float(row.get("总资产净利润率(%)")),
                        "gross_margin": self._to_float(row.get("销售毛利率(%)")),
                        "net_profit_margin": self._to_float(row.get("销售净利率(%)")),
                        "operating_margin": self._to_float(row.get("营业利润率(%)")),
                        "inventory_turnover": self._to_float(row.get("存货周转率(次)")),
                        "ar_turnover": self._to_float(row.get("应收账款周转率(次)")),
                        "total_asset_turnover": self._to_float(row.get("总资产周转率(次)")),
                        "current_ratio": self._to_float(row.get("流动比率")),
                        "quick_ratio": self._to_float(row.get("速动比率")),
                        "debt_ratio_sina": self._to_float(row.get("资产负债率(%)")),
                        "ocf_to_profit": self._to_float(row.get("经营现金净流量与净利润的比率(%)")),
                        "ocf_to_revenue": self._to_float(row.get("经营现金净流量对销售收入比率(%)")),
                        "revenue_growth": self._to_float(row.get("主营业务收入增长率(%)")),
                        "profit_growth": self._to_float(row.get("净利润增长率(%)")),
                        "asset_growth": self._to_float(row.get("总资产增长率(%)")),
                        "eps": self._to_float(row.get("摊薄每股收益(元)")),
                        "navps": self._to_float(row.get("每股净资产(元)")),
                        "ocfps": self._to_float(row.get("每股经营性现金流(元)")),
                    }
                    try:
                        session.merge(FinancialIndicator(**data))
                        count += 1
                    except Exception:
                        continue
                session.commit()
            print(f"  [fin_indicator] {code} saved {count}")
            return count
        except Exception as e:
            print(f"  [fin_indicator] {code} error: {e}")
            return 0

    # ═══════════════════════════════════════
    #  一键下载
    # ═══════════════════════════════════════

    def download_year(self, year: int):
        print(f"\n===== downloading {year} =====")
        self.download_income(year)
        self.download_cashflow(year)
        self.download_balance(year)
        self.download_performance(year)
        self.download_dividend(year)

    def check_db(self):
        print("\n===== DB Stats =====")
        with SessionLocal() as session:
            for t in [Income, Cashflow, Balance, Performance, Dividend, FinancialIndicator]:
                print(f"  {t.__tablename__}: {session.query(t).count()}")

    # ═══════════════════════════════════════
    #  静态工具方法（统一处理 NaN，兼容 MySQL）
    # ═══════════════════════════════════════

    @staticmethod
    def _rows_to_df(rows):
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([r.__dict__ for r in rows])
        if '_sa_instance_state' in df.columns:
            df.drop('_sa_instance_state', axis=1, inplace=True)
        return df

    @staticmethod
    def _to_float(v):
        """安全转 float，NaN/None/空 → None，避免 MySQL 报错"""
        if v is None:
            return None
        try:
            val = float(v)
            return None if pd.isna(val) else val
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_int(v):
        """安全转 int"""
        if v is None:
            return None
        try:
            val = int(float(v))
            return None if pd.isna(val) else val
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_str(v):
        """安全转 str，None/NaN/NaT → None"""
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        s = str(v).strip()
        return s if s and s not in ("None", "NaT", "nan", "") else None
