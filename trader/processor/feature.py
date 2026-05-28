# -*- coding: utf-8 -*-
# PROJECT_NAME:  __init__.py.py
# CREATE_TIME: 2025/5/21 10:58
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# NOTE: 财务清洗 + 指标计算 财务清洗和指标计算模块



import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from trader.data.statement import StatementDownload
from trader.data.orm import SessionLocal, StockBasic


class StockFeatureProcessor:
    """
    股票特征工程处理器
    只依赖数据抽象层（如 StatementDownload），不直接依赖 ORM。
    """

    def __init__(self):
        self.data_service = StatementDownload()

    def load_financial_data(self, code: str, years: Optional[List[int]] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        通过数据抽象层获取指定股票的 income, balance, cashflow 数据
        """
        income_df = self.data_service.get_income_df(code, years)
        balance_df = self.data_service.get_balance_df(code, years)
        cashflow_df = self.data_service.get_cashflow_df(code, years)
        return income_df, balance_df, cashflow_df

    def _merge_balance(self, df: pd.DataFrame, balance_df: pd.DataFrame, keys: List[str]) -> pd.DataFrame:
        """按 (year, report_date) 合并资产负债表字段"""
        if balance_df.empty:
            return df
        merge_cols = [c for c in keys if c in balance_df.columns]
        if not merge_cols:
            return df
        right = balance_df[['year', 'report_date'] + merge_cols].copy()
        # 确保 year 类型一致，避免拼接
        right['year'] = right['year'].astype(int)
        df['year'] = df['year'].astype(int)
        df = df.merge(right, on=['year', 'report_date'], how='left', suffixes=('', '_bal'))
        for col in merge_cols:
            dup = f"{col}_bal"
            if dup in df.columns:
                df[col] = df[dup].fillna(df[col])
                df.drop(columns=[dup], inplace=True)
        return df

    def _merge_cashflow(self, df: pd.DataFrame, cashflow_df: pd.DataFrame) -> pd.DataFrame:
        """按 (year, report_date) 合并现金流量表字段"""
        if cashflow_df.empty:
            return df
        if 'operating_cashflow' not in cashflow_df.columns:
            return df
        right = cashflow_df[['year', 'report_date', 'operating_cashflow']].copy()
        # 确保 year 类型一致
        right['year'] = right['year'].astype(int)
        df['year'] = df['year'].astype(int)
        df = df.merge(right, on=['year', 'report_date'], how='left', suffixes=('', '_cf'))
        if 'operating_cashflow_cf' in df.columns:
            df['operating_cashflow'] = df['operating_cashflow_cf'].fillna(df['operating_cashflow'])
            df.drop(columns=['operating_cashflow_cf'], inplace=True)
        return df

    def calculate_financial_indicators(self, code: str, years: Optional[List[int]] = None) -> Dict[str, float]:
        """
        计算指定股票的主要财务指标（取全部或指定年份，取均值）
        :param code: 股票代码
        :param years: 年份列表（可选）
        :return: 指标字典
        """
        income_df, balance_df, cashflow_df = self.load_financial_data(code, years)
        indicators = {}
        net_profit = income_df['net_profit'] if 'net_profit' in income_df else pd.Series(dtype=float)
        revenue = income_df['total_revenue'] if 'total_revenue' in income_df else pd.Series(dtype=float)

        if not net_profit.empty and not revenue.empty and not revenue.isna().all():
            indicators['净利润率'] = (net_profit / revenue).mean()
        else:
            indicators['净利润率'] = np.nan

        indicators['收入增长率'] = revenue.pct_change(fill_method=None).mean() if not revenue.empty else np.nan
        indicators['净利润增长率'] = net_profit.pct_change(fill_method=None).mean() if not net_profit.empty else np.nan

        if not balance_df.empty:
            total_assets = balance_df['total_assets'] if 'total_assets' in balance_df else pd.Series(dtype=float)
            total_debt = balance_df['total_liabilities'] if 'total_liabilities' in balance_df else pd.Series(dtype=float)
            equity = balance_df['total_equity'] if 'total_equity' in balance_df else pd.Series(dtype=float)

            if not equity.empty and not net_profit.empty:
                indicators['ROE'] = (net_profit / equity).mean()
            else:
                indicators['ROE'] = np.nan

            debt_ratio = balance_df['debt_ratio'] if 'debt_ratio' in balance_df else pd.Series(dtype=float)
            if not debt_ratio.empty and not debt_ratio.isna().all():
                raw_ratio = debt_ratio.mean()
                indicators['资产负债率'] = raw_ratio / 100 if raw_ratio > 1 else raw_ratio
            elif not total_assets.empty and not total_debt.empty:
                indicators['资产负债率'] = (total_debt / total_assets).mean()
            else:
                indicators['资产负债率'] = np.nan

            cash = balance_df['cash'] if 'cash' in balance_df else pd.Series(dtype=float)
            receivable = balance_df['accounts_receivable'] if 'accounts_receivable' in balance_df else pd.Series(dtype=float)
            inventory = balance_df['inventory'] if 'inventory' in balance_df else pd.Series(dtype=float)
            current_assets = cash + receivable + inventory
            payable = balance_df['accounts_payable'] if 'accounts_payable' in balance_df else pd.Series(dtype=float)
            advance = balance_df['advance_receipts'] if 'advance_receipts' in balance_df else pd.Series(dtype=float)
            current_debt = payable + advance
            if not current_debt.empty and not current_assets.empty:
                indicators['流动比率'] = (current_assets / current_debt).mean()
            else:
                indicators['流动比率'] = np.nan

            indicators['净资产增长率'] = equity.pct_change(fill_method=None).mean() if not equity.empty else np.nan
        else:
            indicators['ROE'] = np.nan
            indicators['资产负债率'] = np.nan
            indicators['流动比率'] = np.nan
            indicators['净资产增长率'] = np.nan

        if not cashflow_df.empty:
            ocf = cashflow_df['operating_cashflow'] if 'operating_cashflow' in cashflow_df else pd.Series(dtype=float)
            if not net_profit.empty:
                indicators['经营现金流/净利润'] = (ocf / net_profit).mean()
            else:
                indicators['经营现金流/净利润'] = np.nan
        else:
            indicators['经营现金流/净利润'] = np.nan

        return indicators

    def get_stock_name(self, code: str) -> str:
        """从 stock_basic 表获取股票名称，失败时返回 code"""
        try:
            with SessionLocal() as session:
                row = session.query(StockBasic).filter(StockBasic.code == code).first()
                if row and row.name:
                    return row.name
        except Exception:
            pass
        return code

    def calculate_yearly_features(self, code: str, years: Optional[List[int]] = None) -> pd.DataFrame:
        """
        逐年计算特征，返回 DataFrame（每年一行，按年份升序）
        使用 merge 方式对齐多表，避免 MultiIndex 字符串拼接问题。
        :param code: 股票代码
        :param years: 年份列表（可选）
        :return: DataFrame（含 year, report_date 及各项财务指标）
        """
        income_df, balance_df, cashflow_df = self.load_financial_data(code, years)
        if income_df.empty:
            return pd.DataFrame()

        df = income_df[['year', 'report_date']].copy()
        # 确保 year 为整数类型，防止 merge 时产生字符串拼接
        df['year'] = df['year'].astype(int)
        df['net_profit'] = income_df['net_profit'] if 'net_profit' in income_df else np.nan
        df['total_revenue'] = income_df['total_revenue'] if 'total_revenue' in income_df else np.nan

        balance_keys = ['total_equity', 'total_liabilities', 'total_assets',
                        'cash', 'accounts_receivable', 'inventory',
                        'accounts_payable', 'advance_receipts', 'debt_ratio']
        df = self._merge_balance(df, balance_df, balance_keys)

        df = self._merge_cashflow(df, cashflow_df)

        df = df.copy()
        df['ROE'] = df['net_profit'] / df['total_equity']
        df['净利润率'] = df['net_profit'] / df['total_revenue']
        df['资产负债率'] = df['total_liabilities'] / df['total_assets']
        df['经营现金流/净利润'] = df['operating_cashflow'] / df['net_profit']
        df['净利润增长率'] = df['net_profit'].pct_change()

        # 保留原始金额字段（供 XuBinScorer 等使用）
        df['净利润'] = df['net_profit']
        df['营业收入'] = df['total_revenue']
        df['应收账款'] = df['accounts_receivable']
        df['经营活动现金流净额'] = df['operating_cashflow']
        df['存货'] = df['inventory']

        # 补充毛利率（从 akshare 主营构成接口获取）
        # df['毛利率'] = self._fill_gross_margin(code, df)
        # 改为用新浪财务指标接口补充更多数据
        df = self._fill_sina_financial_indicators(code, df)

        result_cols = ['year', 'report_date', 'ROE', '净利润率', '资产负债率',
                       '经营现金流/净利润', '净利润增长率', '毛利率',
                       '存货周转率', '应收账款周转率',
                       '净利润', '营业收入', '应收账款', '经营活动现金流净额', '存货']
        keep = [c for c in result_cols if c in df.columns]
        result = df[keep].copy()
        # 确保 year 是纯整数类型
        result['year'] = result['year'].astype(int)
        return result.sort_values('year').reset_index(drop=True)

    def _fill_sina_financial_indicators(self, code: str, df: pd.DataFrame) -> pd.DataFrame:
        """
        从 financial_indicator 表补充财务指标（毛利率、存货周转率等）。
        若数据不存在则自动触发下载。
        """
        try:
            ind_df = self.data_service.get_financial_indicator_df(code)
            if ind_df.empty:
                return df

            # 提取需要的列映射（数据库字段 -> yearly 输出列名）
            col_map = {
                "gross_margin": "毛利率",          # 销售毛利率(%)
                "inventory_turnover": "存货周转率",  # 存货周转率(次)
                "ar_turnover": "应收账款周转率",     # 应收账款周转率(次)
                "net_profit_margin": "销售净利率",
                "current_ratio": "流动比率",
                "quick_ratio": "速动比率",
            }

            # 按年聚合（同一年可能有多个报告期）
            agg = ind_df.groupby("year").mean(numeric_only=True).reset_index()
            agg["year"] = agg["year"].astype(int)

            for db_col, out_col in col_map.items():
                if db_col in agg.columns:
                    vals = agg[db_col].dropna()
                    if not vals.empty:
                        # sina 百分比值转为小数（如 40.5 -> 0.405）
                        if db_col in ("gross_margin", "net_profit_margin"):
                            vals = vals / 100.0
                        year_map = agg.set_index("year")[db_col]
                        df[out_col] = df["year"].map(year_map)

            return df
        except Exception as e:
            print(f"  补充财务指标异常: {e}")
            return df

    # 可扩展：添加更多特征工程方法，如标准化、打分、因子生成等

    def calculate_dividend_yield(self, code: str) -> float:
        """
        获取最近一年的股息率（%）
        通过 StatementDownload 的 get_dividend_df 查询数据库
        """
        df = self.data_service.get_dividend_df(code)
        if df.empty or "dividend_yield" not in df.columns:
            return np.nan
        dy = df["dividend_yield"].dropna()
        return float(dy.iloc[0]) if not dy.empty else np.nan

    def calculate_pe_pb(self, code: str) -> Tuple[Optional[float], Optional[float]]:
        """

        实时获取最近 PE(TTM) 和 PB（通过 akshare 估值表）
        """
        try:

            import akshare as ak
            df = ak.stock_value_em(symbol=code)
            if df.empty:
                return None, None



            pe = df["PE(TTM)"].dropna()
            pb = df["市净率"].dropna()
            return (
                float(pe.iloc[-1]) if not pe.empty else None,
                float(pb.iloc[-1]) if not pb.empty else None,
            )
        except Exception:
            return None, None