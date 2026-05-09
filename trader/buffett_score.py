
import sqlite3
import pandas as pd
import numpy as np
from .db_path import get_db_path

class BuffettScorer:
    """
    巴菲特风格的股票打分器。
    主要维度：
    1. 盈利能力（净资产收益率ROE、净利润率）
    2. 负债安全（资产负债率、流动比率）
    3. 现金流（经营现金流/净利润）
    4. 增长性（收入、净利润、净资产增长率）
    5. 行业龙头（可选，需外部数据）
    """
    def __init__(self, db_file=None):
        if db_file is None:
            db_file = get_db_path()
        self.conn = sqlite3.connect(db_file)

    def get_financials(self, code, table, years=5):
        sql = f"""
        SELECT year, data FROM {table}
        WHERE code=?
        ORDER BY year DESC
        LIMIT ?
        """
        df = pd.read_sql(sql, self.conn, params=(code, years))
        if df.empty:
            return pd.DataFrame()
        # data列为json字符串
        records = [pd.read_json(row['data'], typ='series') for _, row in df.iterrows()]
        df2 = pd.DataFrame(records)
        df2['year'] = df['year'].values
        return df2

    def score(self, code, years=5):
        # 1. 盈利能力
        income = self.get_financials(code, 'income', years)
        balance = self.get_financials(code, 'balance', years)
        cashflow = self.get_financials(code, 'cashflow', years)
        if income.empty or balance.empty or cashflow.empty:
            return None
        # ROE
        roe = (income['净利润'] / balance['归属于母公司股东权益合计']).mean()
        # 净利润率
        profit_margin = (income['净利润'] / income['营业总收入']).mean()
        # 2. 负债安全
        debt_ratio = (balance['负债合计'] / balance['资产总计']).mean()
        current_ratio = (balance['流动资产合计'] / balance['流动负债合计']).mean()
        # 3. 现金流
        ocf_ratio = (cashflow['经营活动产生的现金流量净额'] / income['净利润']).mean()
        # 4. 增长性
        revenue_growth = income['营业总收入'].pct_change().mean()
        profit_growth = income['净利润'].pct_change().mean()
        equity_growth = balance['归属于母公司股东权益合计'].pct_change().mean()
        # 5. 综合打分（0-100）
        score = 0
        # 盈利能力
        if roe > 0.15: score += 20
        elif roe > 0.10: score += 15
        elif roe > 0.05: score += 10
        if profit_margin > 0.15: score += 10
        elif profit_margin > 0.10: score += 7
        elif profit_margin > 0.05: score += 4
        # 负债安全
        if debt_ratio < 0.5: score += 10
        elif debt_ratio < 0.7: score += 7
        else: score += 3
        if current_ratio > 2: score += 10
        elif current_ratio > 1.5: score += 7
        elif current_ratio > 1: score += 4
        # 现金流
        if ocf_ratio > 1: score += 10
        elif ocf_ratio > 0.8: score += 7
        elif ocf_ratio > 0.5: score += 4
        # 增长性
        if revenue_growth > 0.1: score += 10
        if profit_growth > 0.1: score += 10
        if equity_growth > 0.1: score += 10
        # 结果
        detail = {
            'ROE': roe,
            '净利润率': profit_margin,
            '资产负债率': debt_ratio,
            '流动比率': current_ratio,
            '经营现金流/净利润': ocf_ratio,
            '收入增长率': revenue_growth,
            '净利润增长率': profit_growth,
            '净资产增长率': equity_growth,
            'score': score
        }
        return detail

if __name__ == "__main__":
    scorer = BuffettScorer()
    code = input("输入股票代码: ")
    result = scorer.score(code)
    if result:
        print("\n巴菲特风格打分:")
        for k, v in result.items():
            print(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")
    else:
        print("数据不足，无法评分。")
