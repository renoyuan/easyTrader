# data/db.py - 数据读取模块
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME:  db.py
# CREATE_TIME: 2025/5/23
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# NOTE: 数据读取模块

import sqlite3
import pandas as pd
import json
import os
import sys
from io import StringIO

# 屏蔽所有 pandas 警告
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)


class DBReader:
    """数据库读取器"""
    def __init__(self, db_path=None):
        if db_path is None:
            # 默认数据库路径（与 orm.py 统一）
            if getattr(sys, 'frozen', False):
                base = os.path.dirname(sys.executable)
            else:
                base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.join(base, 'db', 'stock_data.sqlite')
        else:
            self.db_path = db_path
        print(f"数据库路径: {self.db_path}")
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
    def connect(self):
        """建立数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def get_financial_data(self, code, table, years=5):
        """
        获取财务数据
        :param code: 股票代码
        :param table: 表名（income/balance/cashflow）
        :param years: 获取最近几年的数据
        :return: DataFrame
        """
        sql = f"""
        SELECT year, data FROM {table}
        WHERE code=?
        ORDER BY year DESC
        LIMIT ?
        """
        
        with self.connect() as conn:
            df = pd.read_sql(sql, conn, params=(code, years))
        
        if df.empty:
            return pd.DataFrame()
        
        # 【修复】无警告解析 JSON
        records = []
        for _, row in df.iterrows():
            try:
                s = pd.read_json(StringIO(row['data']), typ='series')
                records.append(s)
            except Exception:
                continue
        
        if not records:
            return pd.DataFrame()
        
        df2 = pd.DataFrame(records)
        df2['year'] = df['year'].values[:len(df2)]
        
        return df2
    
    def get_available_stocks(self, table='income'):
        """获取数据库中可用的股票代码列表"""
        with self.connect() as conn:
            df = pd.read_sql(f"SELECT DISTINCT code FROM {table}", conn)
        
        return df['code'].tolist() if not df.empty else []
    
    def get_stock_info(self, code):
        """获取股票基本信息"""
        income = self.get_financial_data(code, 'income', 1)
        if not income.empty and '股票简称' in income.columns:
            return {
                'code': code,
                'name': income['股票简称'].iloc[0] if len(income) > 0 else None
            }
        return {'code': code, 'name': None}
    
        def _valuation_score(self, val_df) -> tuple[int, str]:
            """
            计算PE估值分 0~20
            返回：估值得分, 估值状态标签
            """
            if val_df.empty or len(val_df) < 100:
                return 0, "估值数据不足"
            
            pe_series = val_df["pe_ttm"]
            curr_pe = pe_series.iloc[0]
            
            # 计算当前PE在5年历史分位
            pe_percentile = (pe_series < curr_pe).mean()

            if pe_percentile < 0.3:
                return 20, "低估 ✅"
            elif pe_percentile < 0.6:
                return 10, "合理 ⚖️"
            elif pe_percentile < 0.8:
                return 5, "偏高 ⚠️"
            else:
                return 0, "高估 ❌"
    def get_valuation_data(self, code, years=5):
        """获取近5年 PE-TTM、PB 估值数据"""
        sql = """
        SELECT trade_date, pe_ttm, pb FROM valuation
        WHERE code=?
        ORDER BY trade_date DESC
        LIMIT ?
        """
        with self.connect() as conn:
            df = pd.read_sql(sql, conn, params=(code, years*250))
        
        if df.empty:
            return pd.DataFrame()
        
        # 去空值、清洗
        df = df.dropna(subset=["pe_ttm", "pb"])
        return df
    def get_ak_valuation_5y(self, code)-> pd.DataFrame:
        """
        从 akshare 的 stock_value_em 获取近5年 PE(TTM) / 市净率(PB)
        字段对应：
            数据日期 → trade_date
            PE(TTM) → pe_ttm
            市净率 → pb
        """
        try:
            # 拉取全部历史估值数据
            df = ak.stock_value_em(symbol=code)
            if df.empty:
                return pd.DataFrame()

            # 1. 日期处理
            df["trade_date"] = pd.to_datetime(df["数据日期"])  # 关键：对应你的列名
            five_year_ago = datetime.now() - timedelta(days=5 * 365)
            df = df[df["trade_date"] >= five_year_ago]

            # 2. 重命名、筛选需要的列
            df = df.rename(columns={
                "PE(TTM)": "pe_ttm",
                "市净率": "pb"
            })[["trade_date", "pe_ttm", "pb"]]

            # 3. 清洗
            df = df.dropna()
            df = df[(df["pe_ttm"] > 0) & (df["pe_ttm"] < 300)]  # 剔除异常PE
            df = df.sort_values("trade_date").reset_index(drop=True)

            return df
        except Exception as e:
            print(f"获取估值失败: {e}")
            return pd.DataFrame()