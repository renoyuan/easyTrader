# yfinance 免费美股/港股/部分A股日线数据下载
import yfinance as yf
import pandas as pd

def get_yfinance_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    symbol: 'AAPL', 'MSFT', '600519.SS', '000001.SZ'
    start/end: 'YYYY-MM-DD'
    """
    df = yf.download(symbol, start=start, end=end)
    if not df.empty:
        df.reset_index(inplace=True)
    return df
