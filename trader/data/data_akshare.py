# AKShare 免费A股日线数据下载
import akshare as ak
import pandas as pd

def get_akshare_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    symbol: 6开头沪市, 0/3开头深市, 如 '600519', '000001'
    start/end: 'YYYYMMDD'
    """
    if symbol.isdigit() and symbol.startswith('6'):
        code = f'sh{symbol}'
    else:
        code = f'sz{symbol}'
    df = ak.stock_zh_a_hist(symbol=code, period='daily', start_date=start, end_date=end, adjust='')
    if not df.empty:
        df = df.rename(columns={
            '日期': 'Date', '开盘': 'Open', '收盘': 'Close', '最高': 'High', '最低': 'Low', '成交量': 'Volume',
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
    return df
