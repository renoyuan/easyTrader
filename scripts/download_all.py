# -*- coding: utf-8 -*-
"""
一键全量下载脚本
===============
下载全部 A 股财报数据（利润表、现金流量表、资产负债表、业绩报表、分红送配）+ K线数据
"""
import sys
import time
from datetime import datetime

from trader.data.statement import StatementDownload
from trader.data.stock import Stock
from trader.db.orm import SessionLocal, StockBasic


def download_all_financial_reports(years: list = None):
    """下载所有财报数据"""
    if years is None:
        current_year = datetime.now().year
        years = list(range(2012, current_year + 1))

    st = StatementDownload()

    print("=" * 60)
    print(f"开始下载财报数据：{years[0]} ~ {years[-1]}")
    print("=" * 60)

    for year in years:
        st.download_year(year)

    st.check_db()
    print("财报下载完成\n")


def download_kline_for_all_stocks(start: str = "20150101", end: str = None):
    """下载所有股票 K 线数据"""
    if end is None:
        end = datetime.now().strftime("%Y%m%d")

    stock_obj = Stock()

    # 从数据库获取所有股票代码
    with SessionLocal() as session:
        stocks = session.query(StockBasic.code, StockBasic.name).all()

    if not stocks:
        print("⚠️ 股票基础信息表为空，先拉取全市场股票列表...")
        stock_list = stock_obj.get_all_stocks()
        stock_obj.save_stock_basic(stock_list)
        with SessionLocal() as session:
            stocks = session.query(StockBasic.code, StockBasic.name).all()

    total = len(stocks)
    print(f"\n{'=' * 60}")
    print(f"开始下载 {total} 只股票 K 线数据 ({start} ~ {end})")
    print(f"{'=' * 60}")

    success = 0
    fail = 0

    for i, (code, name) in enumerate(stocks, 1):
        try:
            print(f"\n[{i}/{total}] {code} {name}")
            df = stock_obj.get_daily_kline(code, start, end)
            if df is not None and not df.empty:
                success += 1
            else:
                print(f"  ⚠️ {code} 无数据")
                fail += 1
        except Exception as e:
            print(f"  ❌ {code} 错误: {e}")
            fail += 1

        # 每 50 只停顿一下，避免被反爬
        if i % 50 == 0:
            print(f"  --- 已处理 {i}/{total}，成功 {success}，失败 {fail}，休息 2s ---")
            time.sleep(2)

    print(f"\n{'=' * 60}")
    print(f"K线下载完成：共 {total} 只，成功 {success}，失败 {fail}")
    print(f"{'=' * 60}")


def download_stock_basic_info():
    """下载所有股票基础信息（代码、名称、市场归属）"""
    stock_obj = Stock()
    stock_list = stock_obj.get_all_stocks()
    stock_obj.save_stock_basic(stock_list)
    print(f"股票基础信息入库完成：{len(stock_list)} 只\n")


def main():
    """一键全量下载入口"""
    print("=" * 60)
    print(" easyTrader 全量数据下载工具")
    print(f" 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 股票基础信息
    print("\n>>> 1/3 下载股票基础信息...")
    # download_stock_basic_info()

    # 2. 财报数据（2012 ~ 今年）
    print("\n>>> 2/3 下载财报数据...")
    # download_all_financial_reports()

    # 3. K 线数据
    print("\n>>> 3/3 下载 K 线数据...")
    download_kline_for_all_stocks()

    print(f"\n{'=' * 60}")
    print(f"全量下载完成！{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
