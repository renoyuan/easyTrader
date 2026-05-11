import pandas as pd
import numpy as np
import os
import sys
import json

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(cur_dir)

class BuffettScorer:

    def __init__(self, db_file):

        import sqlite3

        self.conn = sqlite3.connect(db_file)

        # SQLite 性能优化
        self.conn.execute("PRAGMA journal_mode=WAL")

        print(f"✅ 已连接数据库: {db_file}")

    # ======================================
    # 读取财务数据
    # ======================================
    def get_financials(self, code, table, years=5):

        sql = f"""
        SELECT year, data
        FROM {table}
        WHERE code=?
        ORDER BY year DESC
        LIMIT ?
        """

        df = pd.read_sql(
            sql,
            self.conn,
            params=(code, years)
        )

        if df.empty:
            return pd.DataFrame()

        # json.loads 比 pd.read_json 稳定很多
        records = []

        for _, row in df.iterrows():

            try:
                records.append(json.loads(row['data']))
            except:
                continue

        df2 = pd.DataFrame(records)

        df2['year'] = df['year'].values

        # 按年份排序（非常重要）
        df2 = df2.sort_values("year").reset_index(drop=True)

        return df2

    # ======================================
    # 字段兼容
    # ======================================
    def get_col(self, df, keys, default=np.nan):

        if isinstance(keys, str):
            keys = [keys]

        for k in keys:

            if k in df.columns:

                try:

                    s = pd.to_numeric(
                        df[k],
                        errors='coerce'
                    )

                    return s

                except:
                    pass

        return pd.Series(
            [default] * len(df),
            index=df.index
        )

    # ======================================
    # 安全除法
    # ======================================
    def safe_div(self, a, b):

        b = b.replace(0, np.nan)

        with np.errstate(divide='ignore', invalid='ignore'):

            result = a / b

        result = result.replace(
            [np.inf, -np.inf],
            np.nan
        )

        return result

    # ======================================
    # CAGR 趋势评分（替代 polyfit）
    # ======================================
    def get_trend_score(self, s, max_score):

        s = s.dropna()

        if len(s) < 2:
            return 0

        start = s.iloc[0]
        end = s.iloc[-1]

        # 避免负数和0
        if start <= 0 or end <= 0:
            return 0

        years = len(s) - 1

        try:
            cagr = (end / start) ** (1 / years) - 1
        except:
            return 0

        if cagr > 0.15:
            return max_score

        elif cagr > 0.05:
            return int(max_score * 0.7)

        elif cagr > 0:
            return int(max_score * 0.4)

        return 0

    # ======================================
    # 主评分
    # ======================================
    def score(self, code, years=5):

        income = self.get_financials(code, 'income', years)

        balance = self.get_financials(code, 'balance', years)

        cashflow = self.get_financials(code, 'cashflow', years)

        if income.empty or balance.empty:

            print("❌ 数据不足")

            return None

        # ========= 字段 =========

        net_profit = self.get_col(
            income,
            ["净利润", "归属于母公司股东的净利润"]
        )

        revenue = self.get_col(
            income,
            ["营业收入", "营业总收入"]
        )

        equity = self.get_col(
            balance,
            ["归属于母公司股东权益合计", "所有者权益合计"]
        )

        total_debt = self.get_col(
            balance,
            ["负债合计"]
        )

        total_asset = self.get_col(
            balance,
            ["资产总计"]
        )

        operating_cf = self.get_col(
            cashflow,
            ["经营活动产生的现金流量净额"]
        )

        operating_profit = self.get_col(
            income,
            ["营业利润"]
        )

        # ======================================
        # 平均净资产（重要）
        # ======================================

        avg_equity = (
            equity + equity.shift(1)
        ) / 2

        # 第一行补自身
        avg_equity.iloc[0] = equity.iloc[0]

        # ======================================
        # 财务指标
        # ======================================

        roe = self.safe_div(
            net_profit,
            avg_equity
        )

        profit_rate = self.safe_div(
            operating_profit,
            revenue
        )

        cash_rate = self.safe_div(
            operating_cf,
            net_profit.abs()
        )

        debt_rate = self.safe_div(
            total_debt,
            total_asset
        )

        # 增长率
        profit_growth = net_profit.pct_change()

        profit_growth = profit_growth.replace(
            [np.inf, -np.inf],
            np.nan
        )

        # 防止极端值污染
        profit_growth = profit_growth.clip(-3, 3)

        # ======================================
        # 均值
        # ======================================

        roe_avg = roe.mean()

        profit_avg = profit_rate.mean()

        cash_avg = cash_rate.mean()

        debt_avg = debt_rate.mean()

        profit_growth_avg = profit_growth.mean()

        # ======================================
        # 趋势分
        # ======================================

        trend = 0

        trend += self.get_trend_score(roe, 6)

        trend += self.get_trend_score(profit_rate, 5)

        trend += self.get_trend_score(cash_rate, 5)

        trend += self.get_trend_score(net_profit, 7)

        trend += self.get_trend_score(-debt_rate + 1, 3)

        trend = min(trend, 30)

        # ======================================
        # 基础分
        # ======================================

        base = 0

        # ROE
        if roe_avg >= 0.15:
            base += 14
        elif roe_avg >= 0.10:
            base += 9
        elif roe_avg >= 0.05:
            base += 4

        # 利润率
        if profit_avg >= 0.15:
            base += 13
        elif profit_avg >= 0.08:
            base += 8
        elif profit_avg >= 0.03:
            base += 4

        # 现金流
        if cash_avg >= 0.8:
            base += 11
        elif cash_avg >= 0.5:
            base += 6

        # 负债
        if debt_avg < 0.5:
            base += 10
        elif debt_avg < 0.7:
            base += 5

        # 增长
        if profit_growth_avg > 0.08:
            base += 9
        elif profit_growth_avg > 0.03:
            base += 4

        base = min(base, 70)

        total = min(base + trend, 100)

        return {

            "股票代码": code,

            "5年平均ROE": round(roe_avg, 3),

            "营业利润率": round(profit_avg, 3),

            "现金含金量": round(cash_avg, 3),

            "资产负债率": round(debt_avg, 3),

            "利润增长率": round(profit_growth_avg, 3),

            "基础分(70)": base,

            "趋势分(30)": trend,

            "总分(100)": total,

            "趋势":
                "上升" if trend >= 25
                else "平稳" if trend >= 18
                else "下降"
        }

# ======================================
# 主程序
# ======================================

if __name__ == "__main__":

    from db_path import get_db_path

    scorer = BuffettScorer(
        db_file=get_db_path()
    )

    code = input("输入股票代码: ").strip()

    res = scorer.score(code)

    if res:

        print("\n" + "=" * 50)

        for k, v in res.items():

            print(f"{k:<15} → {v}")

        print("=" * 50)

        s = res["总分(100)"]

        if s >= 80:
            print("✅ 卓越标的")

        elif s >= 65:
            print("✅ 优质公司")

        elif s >= 50:
            print("⚠️ 一般")

        else:
            print("❌ 回避")