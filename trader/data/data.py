#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME:  data.py
# CREATE_TIME: 2025/5/21 11:03
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# NOTE:
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import traceback
plt.rcParams["font.sans-serif"] = ['Microsoft YaHei']  # 黑体，Windows 系统自带
plt.rcParams["axes.unicode_minus"] = False    # 解决负号显示异常
# 配置代理（中国大陆用户必需）[1,6](@ref)
proxy_config = "http://127.0.0.1:10809"  # 替换为实际代理地址
stock_code = "000001.SZ"
start_time = "2025-01-01"
end_time = "2025-05-23"

class Data:
    pass
# 获取数据
# 绘制图表 输出图表 每日推送 预测走势接入模型 收益对比 表格模板
def get_data():
    pass
def draw_plot():
    pass
def send_email():
    pass
def predict():
    pass
def gen_table():
    pass
def get_data_analysis():

    # 数据获取（上证指数正确代码为000001.SS）[6,7](@ref)
    try:
        data = yf.download(
            stock_code,  # 上证指数正确代码
            start=start_time,
            end=end_time,


        )
        print("data", data)
        # 空数据校验[2](@ref)
        if data.empty:
            raise ValueError("数据下载失败，请检查代码或网络连接")

        # 新版列名适配（Close已包含自动调整）[1,6](@ref)
        data = data[['Open', 'High', 'Low', 'Close', 'Volume']]

        # 数据清洗
        data = data.dropna()

        # 收益率计算
        data['Daily Return'] = data['Close'].pct_change()
        data['Cumulative Return'] = (1 + data['Daily Return']).cumprod() - 1

        # 总收益率计算
        start_price = data['Close'].iloc[0]
        end_price = data['Close'].iloc[-1]
        total_return = (end_price - start_price) / start_price

        # 输出结果
        print(f"总收益率（2020-01-01至2023-01-01）: {total_return.round(2).astype(str) + "%"}")
        print("\n前5个交易日数据:")
        print(data.head())

        # 可视化增强[2,7](@ref)
        print(plt.style.available)
        plt.style.use('seaborn-v0_8-whitegrid')
        plt.rcParams["font.sans-serif"] = ['Microsoft YaHei']
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # 价格走势图
        ax1.plot(data.index, data['Close'], label='收盘价', color='#1f77b4', linewidth=1.5)
        # 确保数据为一维
        close_prices = data['Close'].squeeze()  # 压缩维度
        close_prices = close_prices.astype(float)  # 强制类型转换

        # 填充区域
        ax1.fill_between(
            x=data.index,
            y1=close_prices,
            y2=0,  # 默认填充到 x 轴
            alpha=0.3,
            color='skyblue',
            edgecolor='none'
        )
        ax1.set_ylabel('价格 (CNY)', fontsize=10)
        ax1.legend()
        ax1.grid(True, linestyle='--', alpha=0.7)

        # 累计收益率图
        ax2.plot(data.index, data['Cumulative Return'],
                 label='累计收益', color='#2ca02c', linewidth=1.5)
        ax2.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax2.set_ylabel('收益率 (%)', fontsize=10)
        ax2.legend()
        ax2.grid(True, linestyle='--', alpha=0.7)

        plt.suptitle('上证指数收益分析 (2020-2023)', y=0.95, fontsize=12)
        plt.tight_layout()
        plt.savefig('plot.png')
        plt.show()

    except Exception as e:
        print(f"发生错误: { traceback.print_exc()}")
        print("建议解决方案:")
        print("1. 检查代理配置有效性\n2. 升级yfinance: pip install yfinance --upgrade\n3. 尝试更换股票代码后缀(.SS/.SZ)")


def gen_trading_day(start_time="2025-05-21", direction="end", gap=22):
    max_retry = 100  # 防止无限循环
    holiday_series = []
    while max_retry > 0:
        business_day_offset = pd.offsets.BusinessDay(n=1)
        periods = gap
        holiday_count = 0

        # 生成初始交易日序列
        if direction == "start":
            trading_series = pd.bdate_range(start=start_time, periods=periods, freq=business_day_offset, proxy="http://127.0.0.1:7890")
            target_index = -1
        else:
            trading_series = pd.bdate_range(end=start_time, periods=periods, freq=business_day_offset, proxy="http://127.0.0.1:7890")
            target_index = 0

        # 检测节假日
        holiday_dates = []
        for i in trading_series:
            # 生成节假日序列
            day_str = i.strftime("%Y-%m-%d")
            if day_str not in holiday_series and judge_holiday(day_str)  :
                holiday_series.append(day_str)
                holiday_dates.append(day_str)

        holiday_count = len(holiday_dates)
        print(holiday_count)
        # 终止条件判断
        if not holiday_count:
            trading_day = trading_series[target_index]
            end_time = trading_day.strftime("%Y-%m-%d")
            return end_time

        # 动态调整gap
        gap += holiday_count
        print("gap",gap)
        max_retry -= 1

    raise ValueError("Exceed maximum retry attempts")

from chinese_calendar import is_holiday, get_holiday_detail
from datetime import date,datetime
def judge_holiday(date):
    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    if is_holiday(target_date):
        holiday_name, is_off_day = get_holiday_detail(target_date)
        print(f"{target_date} 是节假日：{holiday_name}（{'休息日' if is_off_day else '调休工作日'}）")
        return True
# judge_holiday("2025-05-01")
# print(gen_trading_day(start_time = "2025-05-21",direction="end",gap=22))
get_data_analysis()






