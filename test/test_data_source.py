# 测试各主流免费数据源
from datetime import datetime, timedelta
import pandas as pd
import requests
proxies = {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890"
    }
print('--- AKShare ---')
try:
    from trader.data_akshare import get_akshare_daily
    df = get_akshare_daily('600519', (datetime.now()-timedelta(days=30)).strftime('%Y%m%d'), datetime.now().strftime('%Y%m%d'))
    print(df.head())
except Exception as e:
    print('AKShare Error:', e)

print('--- Tushare Pro ---')
try:
    from trader.data_tushare import get_tushare_daily
    import os
    token = ''
    env_path ='.env.local'   

    requests.get("https://www.baidu.com", proxies=proxies)
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('TUSHARE_TOKEN='):
                    token = line.strip().split('=',1)[-1]
    df = get_tushare_daily('600519', (datetime.now()-timedelta(days=30)).strftime('%Y%m%d'), datetime.now().strftime('%Y%m%d'), token)
    print(df.head())
except Exception as e:
    print('Tushare Error:', e)

print('--- yfinance ---')
try:
    from trader.data_yfinance import get_yfinance_daily
    df = get_yfinance_daily('600519.SS', (datetime.now()-timedelta(days=30)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'))
    print(df.head())
except Exception as e:
    print('yfinance Error:', e)

print('--- Alpha Vantage ---')
try:
    from trader.data_alphavantage import get_alphavantage_daily
    import os
    av_key = ''
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.local')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('ALPHAVANTAGE_KEY='):
                    av_key = line.strip().split('=',1)[-1]
    df = get_alphavantage_daily('AAPL', av_key)
    print(df.head())
except Exception as e:
    print('AlphaVantage Error:', e)
