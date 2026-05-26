r"""
#!/usr/bin/env python
-*- coding: utf-8 -*-
PROJECT_NAME: F:\opensource\easyTrader\trader\processor
CREATE_TIME: 2026-05-11 
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno 
note:  财务清洗 + 指标计算 财务清洗和指标计算模块
"""


import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from trader.data.statement import StatementDownload




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

    def calculate_financial_indicators(self, code: str, years: Optional[List[int]] = None) -> Dict[str, float]:
        """
        计算指定股票的主要财务指标（取全部或指定年份，取均值）
        :param code: 股票代码
        :param years: 年份列表（可选）
        :return: 指标字典
        """
        income_df, balance_df, cashflow_df = self.load_financial_data(code, years)
        indicators = {}
        # 1. 获取基础数据
        net_profit = income_df['net_profit'] if 'net_profit' in income_df else pd.Series(dtype=float)
        revenue = income_df['total_revenue'] if 'total_revenue' in income_df else pd.Series(dtype=float)

        # 2. 盈利能力指标
        if not net_profit.empty and not revenue.empty and not revenue.isna().all():
            indicators['净利润率'] = (net_profit / revenue).mean()
        else:
            indicators['净利润率'] = np.nan

        # 3. 增长性指标
        indicators['收入增长率'] = revenue.pct_change(fill_method=None).mean() if not revenue.empty else np.nan
        indicators['净利润增长率'] = net_profit.pct_change(fill_method=None).mean() if not net_profit.empty else np.nan

        # 4. 需要资产负债表的指标
        if not balance_df.empty:
            total_assets = balance_df['total_assets'] if 'total_assets' in balance_df else pd.Series(dtype=float)
            total_debt = balance_df['total_liabilities'] if 'total_liabilities' in balance_df else pd.Series(dtype=float)
            equity = balance_df['total_equity'] if 'total_equity' in balance_df else pd.Series(dtype=float)

            # ROE
            if not equity.empty and not net_profit.empty:
                indicators['ROE'] = (net_profit / equity).mean()
            else:
                indicators['ROE'] = np.nan

            # 资产负债率
            debt_ratio = balance_df['debt_ratio'] if 'debt_ratio' in balance_df else pd.Series(dtype=float)
            if not debt_ratio.empty and not debt_ratio.isna().all():
                raw_ratio = debt_ratio.mean()
                indicators['资产负债率'] = raw_ratio / 100 if raw_ratio > 1 else raw_ratio
            elif not total_assets.empty and not total_debt.empty:
                indicators['资产负债率'] = (total_debt / total_assets).mean()
            else:
                indicators['资产负债率'] = np.nan

            # 流动比率（用货币资金+应收账款+存货/应付账款+预收账款）
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

            # 净资产增长率
            indicators['净资产增长率'] = equity.pct_change(fill_method=None).mean() if not equity.empty else np.nan
        else:
            indicators['ROE'] = np.nan
            indicators['资产负债率'] = np.nan
            indicators['流动比率'] = np.nan
            indicators['净资产增长率'] = np.nan

        # 5. 需要现金流量表的指标
        if not cashflow_df.empty:
            ocf = cashflow_df['operating_cashflow'] if 'operating_cashflow' in cashflow_df else pd.Series(dtype=float)
            if not net_profit.empty:
                indicators['经营现金流/净利润'] = (ocf / net_profit).mean()
            else:
                indicators['经营现金流/净利润'] = np.nan
        else:
            indicators['经营现金流/净利润'] = np.nan

        return indicators

    def calculate_yearly_features(self, code: str, years: Optional[List[int]] = None) -> pd.DataFrame:
        """
        逐年计算特征，返回 DataFrame（每年一行，按年份升序）
        :param code: 股票代码
        :param years: 年份列表（可选）
        :return: DataFrame
        """
        income_df, balance_df, cashflow_df = self.load_financial_data(code, years)
        if income_df.empty:
            return pd.DataFrame()
        # 按年份对齐
        df = income_df[['year', 'report_date']].copy()
        df['net_profit'] = income_df['net_profit'] if 'net_profit' in income_df else np.nan
        df['total_revenue'] = income_df['total_revenue'] if 'total_revenue' in income_df else np.nan
        # 资产负债表
        if not balance_df.empty:
            balance_df = balance_df.set_index(['year', 'report_date'])
            df = df.set_index(['year', 'report_date'])
            for col in ['total_equity', 'total_liabilities', 'total_assets', 'cash', 'accounts_receivable', 'inventory', 'accounts_payable', 'advance_receipts', 'debt_ratio']:
                if col in balance_df:
                    df[col] = balance_df[col]
            df = df.reset_index()
        # 现金流量表
        if not cashflow_df.empty:
            cashflow_df = cashflow_df.set_index(['year', 'report_date'])
            df = df.set_index(['year', 'report_date'])
            if 'operating_cashflow' in cashflow_df:
                df['operating_cashflow'] = cashflow_df['operating_cashflow']
            df = df.reset_index()
        # 特征计算
        df['ROE'] = df['net_profit'] / df['total_equity']
        df['净利润率'] = df['net_profit'] / df['total_revenue']
        df['资产负债率'] = df['total_liabilities'] / df['total_assets']
        df['经营现金流/净利润'] = df['operating_cashflow'] / df['net_profit']
        df['净利润增长率'] = df['net_profit'].pct_change()
        # 可扩展：添加更多特征工程处理
        return df[['year', 'report_date', 'ROE', '净利润率', '资产负债率', '经营现金流/净利润', '净利润增长率']]

    # 可扩展：添加更多特征工程方法，如标准化、打分、因子生成等