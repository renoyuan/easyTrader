
import akshare as ak
import pandas as pd
import sqlite3
import json
import os
import time
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from db_path import get_db_path

DB_FILE = get_db_path()

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

    tables = ["income", "cashflow", "balance", "performance"]

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

        conn = get_conn()

        for table, df in datasets.items():

            print(f"{table}: {len(df)} 条")

            if df.empty:
                print(f"⚠️ {table} 无数据")
                continue

            rows = df_to_rows(df, date, year)

            save_batch(conn, table, rows)

            print(f"✅ {table} 入库完成")

        conn.commit()
        conn.close()

        print(f"🎉 {year} 年全部完成")

    except Exception as e:

        print(f"❌ {year} 失败: {e}")


# ==========================================
# 查看数据库统计
# ==========================================
def check_db():

    conn = get_conn()

    tables = ["income", "cashflow", "balance", "performance"]

    print("\n===== 数据库统计 =====")

    for table in tables:

        cursor = conn.execute(f'''
        SELECT COUNT(*) FROM {table}
        ''')

        count = cursor.fetchone()[0]

        print(f"{table}: {count}")

    conn.close()


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