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
from sqlalchemy.exc import SQLAlchemyError

# 导入 ORM
import orm
from orm import SessionLocal, StockBasic, init_db, engine, create_stock_table_class


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
        """
        from datetime import datetime, timedelta
        StockKline = create_stock_table_class(symbol)
        StockKline.__table__.create(bind=engine, checkfirst=True)

        # 1. 查询本地数据库
        with SessionLocal() as session:
            query = session.query(StockKline)
            if start:
                query = query.filter(StockKline.date >= pd.to_datetime(start))
            if end:
                query = query.filter(StockKline.date <= pd.to_datetime(end))
            db_rows = query.order_by(StockKline.date.asc()).all()
            db_df = pd.DataFrame([row.__dict__ for row in db_rows])
            if '_sa_instance_state' in db_df.columns:
                db_df.drop('_sa_instance_state', axis=1, inplace=True)

        # 2. 检查缺失日期
        date_range = pd.date_range(start=pd.to_datetime(start), end=pd.to_datetime(end))
        db_dates = set(pd.to_datetime(db_df['date']).dt.date) if not db_df.empty else set()
        missing_dates = [d for d in date_range if d.date() not in db_dates]

        if missing_dates:
            # 拉取缺失区间（合并为最小连续区间）
            miss_start = missing_dates[0].strftime('%Y%m%d')
            miss_end = missing_dates[-1].strftime('%Y%m%d')
            print(f"⚡ 本地缺失区间：{miss_start} ~ {miss_end}，自动拉取...")
            for i in range(retry):
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=symbol,
                        period='daily',
                        start_date=miss_start,
                        end_date=miss_end,
                        adjust='',
                    )
                    if not df.empty:
                        df.rename(columns={
                            '日期': 'date',
                            '开盘': 'open',
                            '收盘': 'close',
                            '最高': 'high',
                            '最低': 'low',
                            '成交量': 'volume',
                            '成交额': 'amount',
                            '振幅': 'amplitude',
                            '涨跌幅': 'pct_chg',
                            '涨跌额': 'change',
                            '换手率': 'turnover_rate'
                        }, inplace=True)
                        df['date'] = pd.to_datetime(df['date'])
                        # 只插入缺失的
                        insert_rows = df[~df['date'].dt.date.isin(db_dates)]
                        if not insert_rows.empty:
                            self.save_kline_to_db(symbol, insert_rows)
                        # 重新查库
                        with SessionLocal() as session2:
                            query2 = session2.query(StockKline)
                            if start:
                                query2 = query2.filter(StockKline.date >= pd.to_datetime(start))
                            if end:
                                query2 = query2.filter(StockKline.date <= pd.to_datetime(end))
                            db_rows2 = query2.order_by(StockKline.date.asc()).all()
                            db_df = pd.DataFrame([row.__dict__ for row in db_rows2])
                            if '_sa_instance_state' in db_df.columns:
                                db_df.drop('_sa_instance_state', axis=1, inplace=True)
                        break
                    else:
                        print(f"❌ {symbol} 拉取K线无数据")
                except Exception as e:
                    print(f"⚠️ {symbol} 下载失败 {e}，重试 {i + 1}/{retry}")
                    time.sleep(2)
        # 返回完整区间
        if not db_df.empty:
            db_df = db_df.sort_values('date')
        return db_df

    # ==========================
    # 4. K线数据增量入库（只插新数据）
    # ==========================
    def save_kline_to_db(self, code: str, df: pd.DataFrame):
        if df.empty:
            print(f"ℹ️ {code} 无K线数据")
            return

        # 动态创建表
        StockKline = create_stock_table_class(code)
        StockKline.__table__.create(bind=engine, checkfirst=True)

        try:
            # 查询已存在的日期
            exist_dates = {
                d[0] for d in
                self.db.query(StockKline.date).filter(StockKline.ts_code == code).all()
            }

            insert_count = 0
            for _, row in df.iterrows():
                current_date = row["date"]
                if current_date in exist_dates:
                    continue

                obj = StockKline(
                    date=current_date,
                    ts_code=code,
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