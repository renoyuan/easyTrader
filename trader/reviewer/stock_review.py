"""
个股复盘模块
=============
输入指定股票代码，输出个股过去一年/6个月/2个月/一周/昨日的涨跌数据以及关键财报数据。
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import traceback


class StockReviewer:
    """个股复盘"""

    def __init__(self):
        self._kline_cache = {}

    def get_stock_review(self, symbol: str) -> dict:
        """
        获取个股完整复盘数据
        :return: {
            "code": 代码,
            "name": 名称,
            "periods": {
                "昨日": {...},
                "一周": {...},
                "二月": {...},   # 近2个月
                "六月": {...},   # 近6个月
                "一年": {...},
            },
            "financial": {关键财报数据}
        }
        """
        result = {
            "code": symbol,
            "name": "",
            "periods": {},
            "financial": {},
        }

        try:
            # 获取日K线数据
            df = self._fetch_kline(symbol)
            if df is None or df.empty:
                print(f"❌ {symbol} 无K线数据")
                return result

            # 股票名称
            result["name"] = df.iloc[0].get('name', '')

            # 计算各区间涨跌
            today = pd.to_datetime(datetime.now().date())
            periods = {
                "昨日": timedelta(days=1),
                "一周": timedelta(weeks=1),
                "二月": timedelta(days=60),
                "六月": timedelta(days=180),
                "一年": timedelta(days=365),
            }

            df_sorted = df.sort_values('date', ascending=False).reset_index(drop=True)
            latest_close = df_sorted.iloc[0]['close']

            for period_name, delta in periods.items():
                cutoff = today - delta
                period_df = df_sorted[df_sorted['date'] >= cutoff]
                if period_df.empty:
                    # 如果没有足够数据，用全部数据
                    period_df = df_sorted
                if period_df.empty:
                    continue

                first_close = period_df.iloc[-1]['close']
                period_pct = ((latest_close - first_close) / first_close) * 100 if first_close else 0

                period_data = {
                    "起始日期": str(period_df.iloc[-1]['date']),
                    "结束日期": str(period_df.iloc[0]['date']),
                    "起始价": round(first_close, 2),
                    "最新价": round(latest_close, 2),
                    "涨跌幅%": round(period_pct, 2),
                    "最高": round(period_df['high'].max(), 2),
                    "最低": round(period_df['low'].min(), 2),
                    "成交量": int(period_df['volume'].sum()) if 'volume' in period_df.columns else 0,
                }
                result["periods"][period_name] = period_data

            # 昨日单独再取精确值
            yesterday_df = df_sorted[df_sorted['date'] >= (today - timedelta(days=1))]
            if len(yesterday_df) >= 2:
                yest = yesterday_df.iloc[1]
                today_row = yesterday_df.iloc[0]
                if 'pct_chg' in today_row and pd.notna(today_row['pct_chg']):
                    result["periods"]["昨日"]["涨跌幅%"] = round(float(today_row['pct_chg']), 2)

            # 获取关键财报数据
            result["financial"] = self._get_financial_data(symbol)

        except Exception as e:
            print(f"⚠️ 个股复盘异常: {e}")
            traceback.print_exc()

        return result

    def _fetch_kline(self, symbol: str) -> pd.DataFrame:
        """获取日K线（最长一年）"""
        if symbol in self._kline_cache:
            return self._kline_cache[symbol]

        try:
            end = datetime.now().strftime('%Y%m%d')
            start = (datetime.now() - timedelta(days=400)).strftime('%Y%m%d')

            df = ak.stock_zh_a_hist(
                symbol=symbol, period='daily',
                start_date=start, end_date=end, adjust='qfq',
            )
            if df is not None and not df.empty:
                df.rename(columns={
                    '日期': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume',
                    '涨跌幅': 'pct_chg', '股票名称': 'name',
                }, inplace=True)
                df['date'] = pd.to_datetime(df['date'])
                self._kline_cache[symbol] = df
                return df
        except Exception as e:
            print(f"⚠️ 获取K线失败 {symbol}: {e}")

        return None

    def _get_financial_data(self, symbol: str) -> dict:
        """获取关键财报数据"""
        financial = {}

        try:
            # 1. 获取财务指标（ROE、净利润率等）
            try:
                df_fin = ak.stock_financial_abstract(symbol=symbol)
                if df_fin is not None and not df_fin.empty:
                    latest = df_fin.iloc[0]
                    # 尝试获取常见字段
                    for col in df_fin.columns:
                        val = latest[col]
                        if pd.isna(val):
                            continue
                        col_lower = str(col).lower()
                        if 'roe' in col_lower or '净资产收益率' in col_lower:
                            financial['ROE'] = round(float(val), 2) if val else None
                        elif '净利润' in col_lower and '率' in col_lower:
                            financial['净利润率'] = round(float(val), 2) if val else None
                        elif '营收' in col_lower and '率' in col_lower:
                            financial['营收增长率'] = round(float(val), 2) if val else None
            except Exception:
                pass

            # 2. 获取市盈率、市净率
            try:
                today = datetime.now().strftime('%Y%m%d')
                df_real = ak.stock_zh_a_tick_tx_js(code=symbol, trade_date=today)
                # 这里不需要 tick 数据
            except Exception:
                pass

            # 使用实时行情获取 PE/PB
            try:
                df_spot = ak.stock_zh_a_spot_em()
                if df_spot is not None and not df_spot.empty:
                    row = df_spot[df_spot['代码'] == symbol]
                    if not row.empty:
                        r = row.iloc[0]
                        if '市盈率-动态' in df_spot.columns:
                            financial['PE_TTM'] = round(float(r['市盈率-动态']), 2) if pd.notna(r['市盈率-动态']) else None
                        if '市净率' in df_spot.columns:
                            financial['PB'] = round(float(r['市净率']), 2) if pd.notna(r['市净率']) else None
            except Exception:
                pass

        except Exception as e:
            print(f"⚠️ 获取财报数据失败: {e}")

        return financial
