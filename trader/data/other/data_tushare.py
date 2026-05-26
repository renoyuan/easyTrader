# Tushare Pro 免费A股日线数据下载（需token）
import tushare as ts
import pandas as pd

def get_tushare_daily(symbol: str, start: str, end: str, token: str) -> pd.DataFrame:
    """
    symbol: 6开头沪市, 0/3开头深市, 如 '600519', '000001'
    start/end: 'YYYYMMDD'
    token: tushare.pro token
    """
    ts.set_token(token)
    pro = ts.pro_api()
    if symbol.startswith('6'):
        ts_code = symbol + '.SH'
    else:
        ts_code = symbol + '.SZ'
    df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
    if not df.empty:
        df = df.rename(columns={
            'trade_date': 'Date', 'open': 'Open', 'close': 'Close', 'high': 'High', 'low': 'Low', 'vol': 'Volume',
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
    return df
