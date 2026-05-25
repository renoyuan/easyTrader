"""
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
        
        for i in range(retry):
            try:
                
                code = symbol
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period='daily',
                    start_date=start,
                    end_date=end,
                    adjust='',
                   
                )
                print(df)
                if not df.empty:
                    print(len(df))
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
                return df

            except Exception as e:
                print(f"⚠️ {symbol} 下载失败 {e}，重试 {i + 1}/{retry}")
                time.sleep(2)
        print(f"❌ {symbol} 下载失败，已跳过")
        return pd.DataFrame()

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
    df = stock.get_daily_kline("600699", "20230101", "20231231")
    stock.save_kline_to_db("600699", df)

    stock.close()