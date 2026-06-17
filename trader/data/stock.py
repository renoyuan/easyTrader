#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

r"""
#!/usr/bin/env python
-*- coding: utf-8 -*-
PROJECT_NAME: F:\opensource\easyTrader\trader\data
CREATE_TIME: 2026-05-25 
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno 
note:  
"""

import akshare as ak
import pandas as pd
import time
import requests
import json
from sqlalchemy.exc import SQLAlchemyError

# 导入 ORM
from trader.db.orm import SessionLocal, StockBasic, StockKline, init_db, engine

# 尝试导入 tushare
try:
    import tushare as ts
    _HAS_TUSHARE = True
except ImportError:
    _HAS_TUSHARE = False

# 配置
from trader.config import get_tushare_token


class Stock:
    def __init__(self):
        # 初始化数据库会话
        self.db = SessionLocal()

    # ==========================
    # 1. 获取全市场股票基础信息
    # ==========================
    def get_all_stocks(self):
        """获取全A股股票代码、名称、市场归属"""
        df = ak.stock_info_a_code_name()

        def get_market(code):
            if code.startswith(("60", "68")):
                return "SH"
            elif code.startswith(("00", "30")):
                return "SZ"
            elif code.startswith(("8", "9")):
                return "BJ"
            else:
                return "OTHER"

        df["market"] = df["code"].apply(get_market)
        return df.to_dict("records")

    # ==========================
    # 2. 股票基础信息入库（全量覆盖）
    # ==========================
    def save_stock_basic(self, data_list):
        try:
            # 清空旧数据
            self.db.query(StockBasic).delete()
            self.db.commit()

            objects = []
            for item in data_list:
                obj = StockBasic(
                    code=item["code"],
                    name=item["name"],
                    market=item["market"],
                    list_status="L",
                    industry=""
                )
                objects.append(obj)

            self.db.bulk_save_objects(objects)
            self.db.commit()
            print(f"✅ 股票基础信息入库完成：{len(data_list)} 只")
        except Exception as e:
            print("❌ 股票基础信息入库失败：", str(e))
            self.db.rollback()

    # ==========================
    # 3. 下载单只股票日K线（完整字段）
    # ==========================

    def get_daily_kline(self, symbol: str, start: str, end: str, retry=3):
        """
        优先查本地数据库，缺失部分自动拉取并补全入库，最后返回完整K线数据。
        :param symbol: 股票代码
        :param start: 起始日期（如 '20230101'）
        :param end: 结束日期（如 '20231231'）

        判断是否需要拉取的逻辑：
          - 计算请求区间的预估交易日数 ≈ (end-start) * 245/365
          - 如果本地已有数据 >= 预估数 * 0.8，则认为已完整
          - 否则拉取并增量入库
        """
        from datetime import datetime, timedelta
        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)

        # StockKline 统一单表，无需动态创建

        # 1. 查询本地数据库
        with SessionLocal() as session:
            query = session.query(StockKline).filter(StockKline.code == symbol)
            if start:
                query = query.filter(StockKline.date >= start_dt)
            if end:
                query = query.filter(StockKline.date <= end_dt)
            db_rows = query.order_by(StockKline.date.asc()).all()
            db_df = pd.DataFrame([row.__dict__ for row in db_rows])
            if '_sa_instance_state' in db_df.columns:
                db_df.drop('_sa_instance_state', axis=1, inplace=True)

        # 2. 判断是否已完整
        need_fetch = True
        if not db_df.empty:
            total_days = (end_dt - start_dt).days
            expected_trading_days = max(int(total_days * 245 / 365), 1)
            if len(db_df) >= expected_trading_days * 0.8:
                need_fetch = False

        if need_fetch:
            print(f"⚡ 本地数据不完整，自动拉取 {symbol} {start}~{end} ...")

            df = self._fetch_kline_fallback(symbol, start, end, retry)

            if df is not None and not df.empty:
                df['date'] = pd.to_datetime(df['date'])

                # 只插入本地没有的日期（增量）
                if not db_df.empty:
                    db_dates = set(pd.to_datetime(db_df['date']).date)
                    insert_rows = df[~df['date'].dt.date.isin(db_dates)]
                else:
                    insert_rows = df

                if not insert_rows.empty:
                    self.save_kline_to_db(symbol, insert_rows)

                # 重新查库
                with SessionLocal() as session2:
                    query2 = session2.query(StockKline).filter(StockKline.code == symbol)
                    if start:
                        query2 = query2.filter(StockKline.date >= start_dt)
                    if end:
                        query2 = query2.filter(StockKline.date <= end_dt)
                    db_rows2 = query2.order_by(StockKline.date.asc()).all()
                    db_df = pd.DataFrame([row.__dict__ for row in db_rows2])
                    if '_sa_instance_state' in db_df.columns:
                        db_df.drop('_sa_instance_state', axis=1, inplace=True)
            else:
                print(f"❌ {symbol} 所有数据源均获取失败")
        else:
            print(f"✅ {symbol} {start}~{end} 已完整，无需拉取")

        # 返回（排序后）
        if not db_df.empty:
            db_df = db_df.sort_values('date')
        return db_df

    def _fetch_kline_fallback(self, symbol: str, start: str, end: str, retry=3):
        """
        多数据源递补获取日K线：
          1) akshare stock_zh_a_hist（东方财富）
          2) tushare pro.daily（需用户配置 token）
          3) 网易财经 API（money.163.com）
          4) 腾讯财经 API（ifzq.gtimg.cn）
        """
        # ── 方案 A：akshare 东方财富 ──
        for i in range(retry):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=symbol, period='daily',
                    start_date=start, end_date=end, adjust='',
                )
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume',
                        '成交额': 'amount', '振幅': 'amplitude',
                        '涨跌幅': 'pct_chg', '涨跌额': 'change', '换手率': 'turnover_rate',
                    })
                    df['date'] = pd.to_datetime(df['date'])
                    return df
            except Exception as e:
                print(f"⚠️ 东方财富接口失败 ({e})，重试 {i+1}/{retry}")
                time.sleep(2)

        # ── 方案 B：Tushare Pro ──
        if _HAS_TUSHARE:
            token = get_tushare_token()
            if token:
                print(f"⚡ 尝试 Tushare Pro 获取 {symbol} ...")
                try:
                    df = self._fetch_from_tushare(symbol, start, end, token)
                    if df is not None and not df.empty:
                        print(f"✅ Tushare 获取 {symbol} 成功 ({len(df)} 条)")
                        return df
                except Exception as e:
                    print(f"⚠️ Tushare 接口失败: {e}")

        # ── 方案 C：网易财经 API ──
        print(f"⚡ 尝试网易财经 API 获取 {symbol} ...")
        try:
            df = self._fetch_from_163(symbol, start, end)
            if df is not None and not df.empty:
                print(f"✅ 网易财经接口获取 {symbol} 成功 ({len(df)} 条)")
                return df
        except Exception as e:
            print(f"⚠️ 网易财经接口失败: {e}")

        # ── 方案 D：腾讯财经 API ──
        print(f"⚡ 尝试腾讯财经 API 获取 {symbol} ...")
        try:
            df = self._fetch_from_tencent(symbol, start, end)
            if df is not None and not df.empty:
                print(f"✅ 腾讯财经接口获取 {symbol} 成功 ({len(df)} 条)")
                return df
        except Exception as e:
            print(f"⚠️ 腾讯财经接口失败: {e}")

        return None

    def _fetch_from_tushare(self, symbol: str, start: str, end: str, token: str):
        """通过 Tushare Pro 获取日K线数据"""
        import tushare as ts
        pro = ts.pro_api(token)
        # 转换为 tushare 格式：600519.SH
        suffix = 'SH' if symbol.startswith(('60', '68')) else 'SZ'
        ts_code = f"{symbol}.{suffix}"
        df = pro.daily(
            ts_code=ts_code,
            start_date=start,
            end_date=end,
            fields='trade_date,open,close,high,low,vol,amount,pct_chg,change'
        )
        if df is None or df.empty:
            return None
        df = df.rename(columns={
            'trade_date': 'date',
            'vol': 'volume',
            'pct_chg': 'pct_chg',
            'change': 'change',
        })
        df['date'] = pd.to_datetime(df['date'])
        # tushare 不直接返回振幅和换手率
        df['amplitude'] = None
        df['turnover_rate'] = None
        return df.sort_values('date').reset_index(drop=True)

    def _fetch_from_163(self, symbol: str, start: str, end: str):
        """
        通过网易财经（money.163.com）获取历史日 K 线
        URL: https://quotes.money.163.com/service/chddata.html
        参数: code=股票代码(0/1开头+6位代码), start/end=YYYYMMDD
        返回列: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
        """
        # 网易编码规则：0=深交所(00/30开头)，1=上交所(60/68开头)
        prefix = '1' if symbol.startswith(('60', '68')) else '0'
        code_163 = f"{prefix}{symbol}"

        url = "https://quotes.money.163.com/service/chddata.html"
        params = {
            'code': code_163,
            'start': start,
            'end': end,
            'fields': 'TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;TURNOVER;VOTURNOVER;VATURNOVER;TCAP;MCAP',
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://quotes.money.163.com/',
        }
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.encoding = 'gbk'
        lines = resp.text.strip().split('\n')
        if len(lines) < 2:
            return None

        data = []
        for line in lines[1:]:  # 跳过表头
            parts = line.strip().split(',')
            if len(parts) < 11:
                continue
            try:
                date_str = parts[0].replace('-', '')
                if date_str < start or date_str > end:
                    continue
                row = {
                    'date': pd.to_datetime(date_str),
                    'open': float(parts[3]) if parts[3] != 'None' else None,
                    'close': float(parts[1]) if parts[1] != 'None' else None,
                    'high': float(parts[2]) if parts[2] != 'None' else None,
                    'low': float(parts[4]) if parts[4] != 'None' else None,
                    'volume': float(parts[8]) if parts[8] != 'None' else None,
                    'amount': float(parts[9]) if parts[9] != 'None' else None,
                    'pct_chg': float(parts[6]) if parts[6] != 'None' else None,
                    'change': float(parts[5]) if parts[5] != 'None' else None,
                    'turnover_rate': float(parts[7]) if parts[7] != 'None' else None,
                }
                # 振幅 = (最高-最低)/昨收 * 100，从网易数据可推导，但直接设为 None
                row['amplitude'] = None
                data.append(row)
            except (ValueError, IndexError):
                continue
        if not data:
            return None
        df = pd.DataFrame(data)
        df = df.dropna(subset=['close'])
        return df.sort_values('date').reset_index(drop=True)

    def _fetch_from_tencent(self, symbol: str, start: str, end: str):
        """
        通过腾讯财经获取日K线（仅支持最近一段时间的日K）
        接口：http://web.ifzq.gtimg.cn/appstock/app/fqkline/get
        """
        import urllib.parse
        market = 'sh' if symbol.startswith(('60', '68')) else 'sz'
        url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            'param': f"{market}{symbol},day,{start},{end},10,qfq",
        }
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.encoding = 'utf-8'
            raw = resp.json()
            # 腾讯返回格式：{data: {market: {qfqday: [[date,open,close,high,low,volume],...]}}}
            data_key = f"{market}{symbol}"
            day_data = raw.get('data', {}).get(data_key, {}).get('qfqday', [])
            if not day_data:
                day_data = raw.get('data', {}).get(data_key, {}).get('day', [])
            if not day_data:
                return None
            rows = []
            for item in day_data:
                try:
                    date_str = item[0].replace('-', '')
                    row = {
                        'date': pd.to_datetime(date_str),
                        'open': float(item[1]),
                        'close': float(item[2]),
                        'high': float(item[3]),
                        'low': float(item[4]),
                        'volume': float(item[5]),
                    }
                    rows.append(row)
                except (ValueError, IndexError):
                    continue
            if not rows:
                return None
            df = pd.DataFrame(rows)
            return df.sort_values('date').reset_index(drop=True)
        except Exception:
            return None

    # ==========================
    # 4. K线数据增量入库（只插新数据）
    # ==========================
    def save_kline_to_db(self, code: str, df: pd.DataFrame):
        if df.empty:
            print(f"ℹ️ {code} 无K线数据")
            return

                # StockKline 统一单表，无需动态创建

        try:
            # 查询已存在的日期
            exist_dates = {
                d[0] for d in
                self.db.query(StockKline.date).filter(StockKline.code == code).all()
            }

            insert_count = 0
            for _, row in df.iterrows():
                current_date = row["date"]
                if current_date in exist_dates:
                    continue

                obj = StockKline(
                    date=current_date,
                    code=code,
                    open=row["open"],
                    close=row["close"],
                    high=row["high"],
                    low=row["low"],
                    volume=row["volume"],
                    amount=row.get("amount"),
                    amplitude=row.get("amplitude"),
                    pct_chg=row.get("pct_chg"),
                    change=row.get("change"),
                    turnover_rate=row.get("turnover_rate")
                )
                self.db.add(obj)
                insert_count += 1

            self.db.commit()
            print(f"✅ {code} K线入库：新增 {insert_count} 条")

        except SQLAlchemyError as e:
            print(f"❌ {code} K线入库失败：{str(e)}")
            self.db.rollback()

    # ==========================
    # 关闭数据库连接
    # ==========================
    def close(self):
        self.db.close()


# ==========================
# 主程序使用示例
# ==========================
if __name__ == "__main__":
    # init_db()
    stock = Stock()

    # 1. 同步全市场股票基础信息
    # stock_list = stock.get_all_stocks()
    # stock.save_stock_basic(stock_list)

    # 2. 下载并保存单只股票K线
    df = stock.get_daily_kline("600699", "20230101", "20241231")
    print(df)

    stock.close()
