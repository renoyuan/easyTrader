
import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime
DB_PATH = "stock_data.sqlite"
# 数据下载与存储模块

import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime

DB_PATH = "stock_data.sqlite"


def download_stock_to_sqlite(symbol: str, start: str, end: str, db_path=DB_PATH, table_name=None, source='auto', tushare_token=None):
    """
    下载指定股票数据并存入sqlite数据库，支持yfinance和tushare
    :param symbol: 股票代码，如 '600519.SS' 或 'AAPL' 或 '600519'
    :param start: 开始日期 'YYYY-MM-DD'
    :param end: 结束日期 'YYYY-MM-DD'
    :param db_path: 数据库路径
    :param table_name: 表名，默认用symbol
    :param source: 'auto'|'yfinance'|'tushare'
    :param tushare_token: tushare token
    """
    df = None
    used_source = source
    # 自动选择数据源
    if source == 'auto':
        if symbol.isdigit() and len(symbol) == 6:
            used_source = 'tushare'
        else:
            used_source = 'yfinance'
    if used_source == 'yfinance':
        try:
            df = yf.download(symbol, start=start, end=end)
        except Exception as e:
            print(f"yfinance 下载失败: {e}")
            df = None
        # 如果yfinance失败且A股，自动尝试tushare
        if (df is None or df.empty) and (symbol.isdigit() and len(symbol) == 6 or symbol.endswith('.SS') or symbol.endswith('.SZ')):
            print(f"yfinance未获取到 {symbol} 的数据，尝试用tushare下载……")
            used_source = 'tushare'
    if used_source == 'tushare' and (df is None or df.empty):
        try:
            import tushare as ts
        except ImportError:
            print("请先安装 tushare: pip install tushare")
            return
        if tushare_token is None:
            print("tushare_token 不能为空，请到 https://tushare.pro 注册获取")
            return
        ts.set_token(tushare_token)
        pro = ts.pro_api()
        # tushare股票代码格式：000001.SZ/600519.SH
        if symbol.endswith('.SS'):
            ts_code = symbol.replace('.SS', '.SH')
        elif symbol.endswith('.SZ'):
            ts_code = symbol.replace('.SZ', '.SZ')
        elif symbol.isdigit() and symbol.startswith('6'):
            ts_code = symbol + '.SH'
        elif symbol.isdigit():
            ts_code = symbol + '.SZ'
        else:
            ts_code = symbol
        df = pro.daily(ts_code=ts_code, start_date=start.replace('-',''), end_date=end.replace('-',''))
        if not df.empty:
            # tushare字段转换为yfinance风格
            df = df.rename(columns={
                'trade_date': 'Date',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'vol': 'Volume',
            })
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
    if df is None or df.empty:
        print(f"未获取到 {symbol} 的数据（已尝试所有数据源）")
        return
    df.reset_index(drop=True, inplace=True)
    table = table_name or symbol.replace('.', '_')
    with sqlite3.connect(db_path) as conn:
        df.to_sql(table, conn, if_exists='replace', index=False)
    print(f"{symbol} 数据已保存到 {db_path} 的 {table} 表 (数据源: {used_source})")

def load_stock_from_sqlite(symbol: str, db_path=DB_PATH, table_name=None):
    """
    从sqlite数据库读取指定股票数据
    :param symbol: 股票代码
    :param db_path: 数据库路径
    :param table_name: 表名
    :return: DataFrame
    """
    table = table_name or symbol.replace('.', '_')
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(f'SELECT * FROM {table}', conn)
    return df

def load_stock_from_sqlite(symbol: str, db_path=DB_PATH, table_name=None):
    """
    从sqlite数据库读取指定股票数据
    :param symbol: 股票代码
    :param db_path: 数据库路径
    :param table_name: 表名
    :return: DataFrame
    """
    table = table_name or symbol.replace('.', '_')
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(f'SELECT * FROM {table}', conn)
    return df

if __name__ == "__main__":
    # 示例：下载贵州茅台近一年数据并存入sqlite
    download_stock_to_sqlite('600519.SS', '2025-05-01', datetime.now().strftime('%Y-%m-%d'))
    df = load_stock_from_sqlite('600519.SS')
    print(df.head())
