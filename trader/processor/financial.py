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
from typing import Dict, Optional


class FinancialProcessor:
    """财务数据处理器"""
    
    def __init__(self):
        # 字段兼容映射（支持多种数据源的字段命名格式）
        self.col_map = {
            '净利润': ['净利润', '归属于母公司股东的净利润', '净利润(元)', '归属于母公司所有者的净利润'],
            '营业总收入': ['营业总收入', '营业收入', '营业收入(元)', '营业总收入(元)'],
            '归属于母公司股东权益合计': ['归属于母公司股东权益合计', '归属于母公司股东的权益合计', 
                                      '所有者权益(或股东权益)合计', '所有者权益合计', '股东权益合计'],
            '负债合计': ['负债合计', '负债总计', '总负债', '负债-总负债'],
            '资产总计': ['资产总计', '资产合计', '总资产', '资产-总资产'],
            '流动资产合计': ['流动资产合计', '流动资产总计', '流动资产', '资产-流动资产'],
            '流动负债合计': ['流动负债合计', '流动负债总计', '流动负债', '负债-流动负债', '负债-应付账款', '负债-预收账款'],
            '经营活动产生的现金流量净额': ['经营活动产生的现金流量净额', '经营活动现金流量净额', 
                                           '经营活动现金流净额', '经营现金流', '经营性现金流-现金流量净额'],
            '股东权益合计': ['股东权益合计', '所有者权益合计'],
            '资产负债率': ['资产负债率', '负债比率'],
            # 分项资产（用于计算流动资产）
            '货币资金': ['货币资金', '资产-货币资金'],
            '应收账款': ['应收账款', '资产-应收账款'],
            '存货': ['存货', '资产-存货'],
            # 分项负债（用于计算流动负债）
            '应付账款': ['应付账款', '负债-应付账款'],
            '预收账款': ['预收账款', '负债-预收账款'],
        }
    
    def _get_col(self, df: pd.DataFrame, keys) -> pd.Series:
        """
        尝试从df中获取第一个存在的字段
        :param df: DataFrame
        :param keys: 字段名列表
        :return: 字段数据
        """
        if isinstance(keys, str):
            keys = [keys]
        
        for k in keys:
            if k in df.columns:
                return df[k]
        
        return pd.Series([np.nan] * len(df))
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗财务数据
        :param df: 原始DataFrame
        :return: 清洗后的DataFrame
        """
        cleaned = df.copy()
        
        # 去除无关字段
        irrelevant_cols = ['序号', '股票代码', '股票简称', '公告日期']
        cleaned = cleaned.drop([c for c in irrelevant_cols if c in cleaned.columns], axis=1)
        
        # 处理负值（某些指标不应为负）
        for col in cleaned.columns:
            if '资产' in col or '权益' in col or '收入' in col:
                cleaned[col] = cleaned[col].apply(lambda x: abs(x) if x < 0 else x)
        
        # 填充缺失值（使用前向填充）
        cleaned = cleaned.fillna(method='ffill')
        
        return cleaned
    
    def calculate_indicators(self, income_df: pd.DataFrame, 
                            balance_df: pd.DataFrame = None,
                            cashflow_df: pd.DataFrame = None) -> Dict[str, float]:
        """
        计算财务指标
        :param income_df: 利润表数据
        :param balance_df: 资产负债表数据（可选）
        :param cashflow_df: 现金流量表数据（可选）
        :return: 指标字典
        """
        indicators = {}
        
        # 1. 获取基础数据
        net_profit = self._get_col(income_df, self.col_map['净利润'])
        revenue = self._get_col(income_df, self.col_map['营业总收入'])
        
        # 2. 盈利能力指标
        if not net_profit.isna().all() and not revenue.isna().all():
            indicators['净利润率'] = (net_profit / revenue).mean()
        else:
            indicators['净利润率'] = np.nan
        
        # 3. 增长性指标
        indicators['收入增长率'] = revenue.pct_change(fill_method=None).mean()
        indicators['净利润增长率'] = net_profit.pct_change(fill_method=None).mean()
        
        # 4. 需要资产负债表的指标
        if balance_df is not None and not balance_df.empty:
            total_assets = self._get_col(balance_df, self.col_map['资产总计'])
            total_debt = self._get_col(balance_df, self.col_map['负债合计'])
            equity = self._get_col(balance_df, self.col_map['归属于母公司股东权益合计'])
            
            # 如果归属于母公司股东权益合计缺失，尝试用股东权益合计
            if equity.isna().all():
                equity = self._get_col(balance_df, self.col_map['股东权益合计'])
            
            # 如果仍缺失，用总资产-总负债计算
            if equity.isna().all():
                if not total_assets.isna().all() and not total_debt.isna().all():
                    equity = total_assets - total_debt
            
            # ROE
            if not equity.isna().all() and not net_profit.isna().all():
                indicators['ROE'] = (net_profit / equity).mean()
            else:
                indicators['ROE'] = np.nan
            
            # 资产负债率（优先使用直接给出的值，否则计算）
            debt_ratio_direct = self._get_col(balance_df, self.col_map['资产负债率'])
            if not debt_ratio_direct.isna().all():
                raw_ratio = debt_ratio_direct.mean()
                # 处理百分比形式的数据（如果值大于1，说明是百分比，需要除以100）
                indicators['资产负债率'] = raw_ratio / 100 if raw_ratio > 1 else raw_ratio
            elif not total_assets.isna().all() and not total_debt.isna().all():
                indicators['资产负债率'] = (total_debt / total_assets).mean()
            else:
                indicators['资产负债率'] = np.nan
            
            # 流动比率（优先使用直接值，否则用分项计算）
            current_assets = self._get_col(balance_df, self.col_map['流动资产合计'])
            current_debt = self._get_col(balance_df, self.col_map['流动负债合计'])
            
            # 如果流动资产合计缺失，尝试用分项计算
            if current_assets.isna().all():
                cash = self._get_col(balance_df, self.col_map['货币资金'])
                receivable = self._get_col(balance_df, self.col_map['应收账款'])
                inventory = self._get_col(balance_df, self.col_map['存货'])
                current_assets = cash + receivable + inventory
            
            # 如果流动负债合计缺失，尝试用分项计算
            if current_debt.isna().all():
                payable = self._get_col(balance_df, self.col_map['应付账款'])
                advance = self._get_col(balance_df, self.col_map['预收账款'])
                current_debt = payable + advance
            
            if not current_debt.isna().all() and not current_assets.isna().all():
                indicators['流动比率'] = (current_assets / current_debt).mean()
            else:
                indicators['流动比率'] = np.nan
            
            # 净资产增长率
            indicators['净资产增长率'] = equity.pct_change(fill_method=None).mean() if not equity.isna().all() else np.nan
        
        else:
            # 缺少资产负债表数据
            indicators['ROE'] = np.nan
            indicators['资产负债率'] = np.nan
            indicators['流动比率'] = np.nan
            indicators['净资产增长率'] = np.nan
        
        # 5. 需要现金流量表的指标
        if cashflow_df is not None and not cashflow_df.empty:
            ocf = self._get_col(cashflow_df, self.col_map['经营活动产生的现金流量净额'])
            if not net_profit.isna().all():
                indicators['经营现金流/净利润'] = (ocf / net_profit).mean()
            else:
                indicators['经营现金流/净利润'] = np.nan
        else:
            indicators['经营现金流/净利润'] = np.nan
        
        return indicators
    
    def calculate_yearly_indicators(self, income, balance, cashflow):
        """逐年计算指标，返回 DataFrame（每年一行）——使用你自带的字段映射，绝对不报错"""
        df = income.copy()

        # 完全使用你自己的 col_map 和 _get_col，100%兼容
        np = self._get_col(income, self.col_map['净利润'])
        rev = self._get_col(income, self.col_map['营业总收入'])
        equity = self._get_col(balance, self.col_map['归属于母公司股东权益合计'])
        debt = self._get_col(balance, self.col_map['负债合计'])
        asset = self._get_col(balance, self.col_map['资产总计'])
        ocf = self._get_col(cashflow, self.col_map['经营活动产生的现金流量净额'])

        # 安全计算
        df["ROE"] = np / equity
        df["净利润率"] = np / rev
        df["资产负债率"] = debt / asset
        df["经营现金流/净利润"] = ocf / np
        df["净利润增长率"] = np.pct_change()

        # 返回
        return df[["ROE", "净利润率", "资产负债率", "经营现金流/净利润", "净利润增长率"]]