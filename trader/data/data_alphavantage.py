# Alpha Vantage 免费美股/外汇/加密货币日线数据下载（需API KEY）
import pandas as pd
import requests

def get_alphavantage_daily(symbol: str, api_key: str) -> pd.DataFrame:
    """
    symbol: 'AAPL', 'MSFT' 等美股代码
    api_key: Alpha Vantage 免费API KEY
    """
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={api_key}&datatype=csv'
    df = pd.read_csv(url)
    if not df.empty:
        df = df.rename(columns={
            'timestamp': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume',
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
    return df
