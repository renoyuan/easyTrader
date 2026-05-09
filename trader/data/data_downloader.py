

import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime
import os
DB_PATH = "stock_data.sqlite"


def download_stock_to_sqlite(symbol: str, start: str, end: str, db_path=DB_PATH, table_name=None, source='auto', tushare_token=None):
    def try_tushare(symbol, start, end, token=None):
        try:
            import tushare as ts
        except ImportError:
            print("请先安装 tushare: pip install tushare")
            return None
        if token is None:
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.local')
            token = None
            if os.path.exists(env_path):
                with open(env_path, encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('TUSHARE_TOKEN='):
                            token = line.strip().split('=',1)[-1]
            if not token:
                print("tushare_token 不能为空，请到 https://tushare.pro 注册获取，并写入.env.local 文件")
                return None
        ts.set_token(token)
        pro = ts.pro_api()
        if symbol.startswith('6'):
            ts_code = symbol + '.SH'
        else:
            ts_code = symbol + '.SZ'
        try:
            df = pro.daily(ts_code=ts_code, start_date=start.replace('-',''), end_date=end.replace('-',''))
            print(df.head())
            if not df.empty:
                df = df.rename(columns={
                    'trade_date': 'Date', 'open': 'Open', 'close': 'Close', 'high': 'High', 'low': 'Low', 'vol': 'Volume',
                })
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date')
            return df
        except Exception as e:
            print(f"tushare 下载失败: {e}")
            return None

    def try_akshare(symbol, start, end):
        try:
            import akshare as ak
        except ImportError:
            print("请先安装 akshare: pip install akshare")
            return None
        if symbol.isdigit() and symbol.startswith('6'):
            code = f'sh{symbol}'
        else:
            code = f'sz{symbol}'
        try:
            df = ak.stock_zh_a_hist(symbol=code, period='daily', start_date=start.replace('-',''), end_date=end.replace('-',''), adjust='')
            if not df.empty:
                df = df.rename(columns={
                    '日期': 'Date', '开盘': 'Open', '收盘': 'Close', '最高': 'High', '最低': 'Low', '成交量': 'Volume',
                })
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date')
            return df
        except Exception as e:
            print(f"akshare 下载失败: {e}")
            return None
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
    # 主流程：A股优先 tushare（有权限），否则 akshare，非A股用yfinance
    df = None
    is_a_stock = (symbol.isdigit() and len(symbol) == 6) or symbol.endswith('.SS') or symbol.endswith('.SZ')
    # 统一表名处理
    def get_table_name(symbol):
        t = symbol.replace('.', '_')
        return  t

    table = table_name or symbol.replace('.', '_')
    table_sql = "stock_" + get_table_name(symbol)

    if is_a_stock:
        # 先 tushare
        df = try_tushare(symbol[:6], start, end)
        if df is None or df.empty:
            print(f"tushare不可用，尝试akshare……")
            df = try_akshare(symbol[:6], start, end)
    else:
        try:
            df = yf.download(symbol, start=start, end=end)
        except Exception as e:
            print(f"yfinance 下载失败: {e}")
            df = None
    if df is None or df.empty:
        print(f"未获取到 {symbol} 的数据（已尝试所有数据源）")
        return
    df.reset_index(drop=True, inplace=True)
    with sqlite3.connect(db_path) as conn:
        df.to_sql(table_sql, conn, if_exists='replace', index=False)
    print(f"{symbol} 数据已保存到 {db_path} 的 {table_sql} 表")
    return table_sql

def load_stock_from_sqlite(symbol: str="", db_path=DB_PATH, table_name=None):
    """
    从sqlite数据库读取指定股票数据
    表名格式：stock_600699_SS （永远不会SQL语法错误）
    """
    if not table_name:
        
        # 核心：统一前缀 + 替换符号
        if symbol.startswith('6'):
                symbol = symbol + '.SS'
        elif symbol.startswith(('0','3')):
                symbol = symbol + '.SZ'
    
        base_table = symbol.replace(".", "_")  # 600699.SS → 600699_SS
        
        table_name = f"stock_{base_table}"          # 最终表名：stock_600699_SS

    try:
        with sqlite3.connect(db_path) as conn:
            # 检查表是否存在
            check = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
                (table_name,)
            ).fetchone()

            if not check:
                print(f"⚠️ 表不存在：{table_name}")
                return pd.DataFrame()

            # 安全查询
            df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
            return df

    except Exception as e:
        print(f"[error] 读取失败: {str(e)}")
        return pd.DataFrame()


if __name__ == "__main__":
    # 示例：下载贵州茅台近一年数据并存入sqlite
    download_stock_to_sqlite('600519.SS', '2025-05-01', datetime.now().strftime('%Y-%m-%d'))
    df = load_stock_from_sqlite('600519.SS')
    print(df.head())
