"""
个股复盘模块
=============
输入指定股票代码，输出个股过去一年/6个月/2个月/一周/昨日的涨跌数据以及关键财报数据。
复用 stock.py（本地数据库优先）和 scorer 中的估值得分逻辑。
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

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
                "二月": {...},
                "六月": {...},
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
            # 1. 获取日K线数据（复用 stock.py 的 get_daily_kline）
            df = self._fetch_kline(symbol)
            if df is None or df.empty:
                print(f"❌ {symbol} 无K线数据")
                return result

            # 确保字段统一
            if 'date' not in df.columns:
                return result

            # 股票名称（尝试从K线数据获取）
            result["name"] = self._get_stock_name(symbol)

            # 2. 计算各区间涨跌
            # 统一 date 列为 datetime64[ns]（数据库可能返回 object 类型）
            if df['date'].dtype == 'object':
                df['date'] = pd.to_datetime(df['date'])

            df_sorted = df.sort_values('date', ascending=False).reset_index(drop=True)
            latest_row = df_sorted.iloc[0]

            # 昨日复盘：K线最新一条就是最后一个完整的交易日数据
            result["periods"]["昨日"] = {
                "日期": str(latest_row['date'].date()),
                "开盘": round(float(latest_row['open']), 2),
                "收盘": round(float(latest_row['close']), 2),
                "最高": round(float(latest_row['high']), 2),
                "最低": round(float(latest_row['low']), 2),
                "涨跌幅%": round(float(latest_row.get('pct_chg', 0)), 2) if 'pct_chg' in latest_row and pd.notna(latest_row.get('pct_chg')) else 0,
                "成交量": int(latest_row.get('volume', 0)),
            }

            # 统计截止日期
            result["统计截止"] = str(latest_row['date'].date())

            # 其他区间：按交易日数量切分
            period_trading_days = {
                "近一周": 5,
                "近两月": 40,
                "近六月": 120,
                "近一年": 245,
            }

            for period_name, n_days in period_trading_days.items():
                if len(df_sorted) < n_days:
                    period_df = df_sorted
                else:
                    period_df = df_sorted.iloc[:n_days]

                if period_df.empty:
                    continue

                first_close = float(period_df.iloc[-1]['close'])
                last_close = float(period_df.iloc[0]['close'])
                period_pct = ((last_close - first_close) / first_close) * 100 if first_close else 0

                result["periods"][period_name] = {
                    "起始日期": str(period_df.iloc[-1]['date'].date()),
                    "结束日期": str(period_df.iloc[0]['date'].date()),
                    "起始价": round(first_close, 2),
                    "最新价": round(last_close, 2),
                    "涨跌幅%": round(period_pct, 2),
                    "最高": round(float(period_df['high'].max()), 2),
                    "最低": round(float(period_df['low'].min()), 2),
                    "成交量": int(period_df['volume'].sum()) if 'volume' in period_df.columns else 0,
                }

            # 3. 获取关键财报与估值数据
            result["financial"] = self._get_financial_data(symbol)

        except Exception as e:
            print(f"⚠️ 个股复盘异常: {e}")
            traceback.print_exc()

        return result

    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称"""
        try:
            # 使用同花顺接口获取名称（稳定不依赖东方财富）
            df = ak.stock_rank_lxsz_ths()
            if df is not None and not df.empty:
                row = df[df['股票代码'] == symbol]
                if not row.empty:
                    return str(row.iloc[0]['股票简称'])
        except Exception:
            pass
        return ""

    def _fetch_kline(self, symbol: str) -> pd.DataFrame:
        """
        复用 stock.py 的 Stock.get_daily_kline 优先从本地数据库获取，
        缺失部分自动拉取并入库。
        """
        if symbol in self._kline_cache:
            return self._kline_cache[symbol]

        try:
            from trader.data.stock import Stock
            stock_srv = Stock()
            end = datetime.now().strftime('%Y%m%d')
            start = (datetime.now() - timedelta(days=400)).strftime('%Y%m%d')
            df = stock_srv.get_daily_kline(symbol, start, end)
            stock_srv.close()

            if df is not None and not df.empty:
                # 确保 date 列名一致
                if 'date' not in df.columns:
                    return None
                self._kline_cache[symbol] = df
                return df
        except Exception as e:
            print(f"⚠️ 从本地数据库获取K线失败: {e}")

        # 兜底：直接用 akshare 东方财富接口
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
                    '涨跌幅': 'pct_chg',
                }, inplace=True)
                df['date'] = pd.to_datetime(df['date'])
                self._kline_cache[symbol] = df
                return df
        except Exception as e:
            print(f"⚠️ 东方财富兜底获取K线失败 {symbol}: {e}")

        return None

    def _get_financial_data(self, symbol: str) -> dict:
        """
        获取关键财报与估值数据。
        优先从本地数据库（statement.py），兜底用同花顺接口。
        """
        financial = {}

        # 1. 从本地数据库获取财报指标（复用 statement.py）
        try:
            from trader.data.statement import StatementDownload
            sd = StatementDownload()
            income = sd.get_income_df(symbol, years=[datetime.now().year - 1, datetime.now().year])
            if income is not None and not income.empty:
                np_row = income.iloc[-1]
                for col in ['净利润', '净利润(元)', '归属于母公司股东的净利润']:
                    if col in np_row and pd.notna(np_row[col]):
                        financial['净利润'] = round(float(np_row[col]) / 1e8, 2)  # 亿
                        break
                for col in ['营业总收入', '营业收入', '营业收入(元)']:
                    if col in np_row and pd.notna(np_row[col]):
                        financial['营收'] = round(float(np_row[col]) / 1e8, 2)
                        break
            balance = sd.get_balance_df(symbol, years=[datetime.now().year - 1])
            if balance is not None and not balance.empty:
                bl_row = balance.iloc[-1]
                for col in ['归属于母公司股东权益合计', '所有者权益合计']:
                    if col in bl_row and pd.notna(bl_row[col]):
                        financial['净资产'] = round(float(bl_row[col]) / 1e8, 2)
                        break
            # 计算 ROE
            if '净利润' in financial and '净资产' in financial and financial['净资产']:
                financial['ROE_估算%'] = round(financial['净利润'] / financial['净资产'] * 100, 2)
        except Exception as e:
            print(f"⚠️ 本地财报获取失败: {e}")

        # 2. 获取 PE/PB（用同花顺估值接口，避免东方财富 spot_em）
        try:
            # 通过同花顺创新高/新低不适用，尝试使用 stock_zh_a_tick_tx_js（腾讯接口）
            pass
        except Exception:
            pass

        # 使用东方财富估值（仅此一项，做好异常保护）
        try:
            df_spot = ak.stock_zh_a_spot_em()
            if df_spot is not None and not df_spot.empty:
                row = df_spot[df_spot['代码'] == symbol]
                if not row.empty:
                    r = row.iloc[0]
                    if '市盈率-动态' in df_spot.columns and pd.notna(r.get('市盈率-动态')):
                        financial['PE_TTM'] = round(float(r['市盈率-动态']), 2)
                    if '市净率' in df_spot.columns and pd.notna(r.get('市净率')):
                        financial['PB'] = round(float(r['市净率']), 2)
        except Exception:
            pass

        return financial
