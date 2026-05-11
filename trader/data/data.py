#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME:  data.py
# CREATE_TIME: 2025/5/21 11:03
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# NOTE: 股票数据分析核心模块

import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import traceback
from typing import Optional, Dict

# 全局配置
plt.rcParams["font.sans-serif"] = ['Microsoft YaHei']  # 黑体，Windows 系统自带
plt.rcParams["axes.unicode_minus"] = False            # 解决负号显示异常


class StockAnalyzer:
    """
    股票数据分析器
    功能：获取数据、绘制图表、收益分析
    """
    
    def __init__(self, stock_code: str = "000001.SS", 
                 start_time: str = "2025-01-01", 
                 end_time: str = None,
                 proxy: Optional[str] = None):
        """
        初始化分析器
        :param stock_code: 股票代码，如 "000001.SS" (上证指数)
        :param start_time: 开始日期
        :param end_time: 结束日期，默认为当前日期
        :param proxy: 代理地址
        """
        self.stock_code = stock_code
        self.start_time = start_time
        self.end_time = end_time if end_time else pd.Timestamp.now().strftime("%Y-%m-%d")
        self.proxy = proxy
        self.data: Optional[pd.DataFrame] = None
        
        # 配置代理
        if proxy:
            import os
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy
    
    def download_data(self) -> bool:
        """
        下载股票数据
        :return: 是否下载成功
        """
        try:
            self.data = yf.download(
                self.stock_code,
                start=self.start_time,
                end=self.end_time
            )
            
            # 空数据校验
            if self.data.empty:
                raise ValueError("数据下载失败，请检查代码或网络连接")
            
            # 新版列名适配（Close已包含自动调整）
            self.data = self.data[['Open', 'High', 'Low', 'Close', 'Volume']]
            
            # 数据清洗
            self.data = self.data.dropna()
            
            print(f"✅ 成功下载 {self.stock_code} 数据 ({len(self.data)} 条)")
            return True
            
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            traceback.print_exc()
            return False
    
    def calculate_returns(self) -> Optional[pd.DataFrame]:
        """
        计算收益率指标
        :return: 包含收益率的数据
        """
        if self.data is None:
            print("⚠️ 请先下载数据")
            return None
        
        # 收益率计算
        self.data['Daily Return'] = self.data['Close'].pct_change()
        self.data['Cumulative Return'] = (1 + self.data['Daily Return']).cumprod() - 1
        
        return self.data
    
    def get_total_return(self) -> float:
        """
        计算总收益率
        :return: 总收益率
        """
        if self.data is None:
            print("⚠️ 请先下载数据")
            return 0.0
        
        start_price = self.data['Close'].iloc[0]
        end_price = self.data['Close'].iloc[-1]
        return (end_price - start_price) / start_price
    
    def plot_analysis(self, output_path: str = "plot.png") -> bool:
        """
        绘制分析图表
        :param output_path: 输出路径
        :return: 是否成功
        """
        if self.data is None:
            print("⚠️ 请先下载数据")
            return False
        
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
            
            # 价格走势图
            close_prices = self.data['Close'].squeeze().astype(float)
            ax1.plot(self.data.index, close_prices, label='收盘价', color='#1f77b4', linewidth=1.5)
            ax1.fill_between(
                x=self.data.index,
                y1=close_prices,
                y2=0,
                alpha=0.3,
                color='skyblue',
                edgecolor='none'
            )
            ax1.set_ylabel('价格 (CNY)', fontsize=10)
            ax1.legend()
            ax1.grid(True, linestyle='--', alpha=0.7)
            
            # 累计收益率图
            ax2.plot(self.data.index, self.data['Cumulative Return'],
                     label='累计收益', color='#2ca02c', linewidth=1.5)
            ax2.axhline(0, color='black', linestyle='--', linewidth=0.8)
            ax2.set_ylabel('收益率 (%)', fontsize=10)
            ax2.legend()
            ax2.grid(True, linestyle='--', alpha=0.7)
            
            plt.suptitle(f'{self.stock_code} 收益分析 ({self.start_time} 至 {self.end_time})', y=0.95, fontsize=12)
            plt.tight_layout()
            plt.savefig(output_path)
            print(f"✅ 图表已保存到: {output_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ 绘图失败: {e}")
            traceback.print_exc()
            return False
    
    def print_summary(self):
        """
        打印分析摘要
        """
        if self.data is None:
            print("⚠️ 请先下载数据")
            return
        
        total_return = self.get_total_return()
        print(f"\n📊 {self.stock_code} 收益分析报告")
        print("=" * 50)
        print(f"时间范围: {self.start_time} 至 {self.end_time}")
        print(f"总收益率: {total_return:.2%}")
        print(f"数据条数: {len(self.data)}")
        print(f"\n前5个交易日数据:")
        print(self.data.head().to_string())
def gen_trading_day(start_time: str = "2025-05-21", 
                    direction: str = "end", 
                    gap: int = 22) -> str:
    """
    生成指定交易日后推/前推gap个交易日的日期
    :param start_time: 起始日期
    :param direction: "start" 向前推, "end" 向后推
    :param gap: 交易日间隔
    :return: 目标交易日
    """
    max_retry = 100  # 防止无限循环
    holiday_series = []
    
    while max_retry > 0:
        business_day_offset = pd.offsets.BusinessDay(n=1)
        periods = gap
        
        # 生成初始交易日序列
        if direction == "start":
            trading_series = pd.bdate_range(
                start=start_time, 
                periods=periods, 
                freq=business_day_offset
            )
            target_index = -1
        else:
            trading_series = pd.bdate_range(
                end=start_time, 
                periods=periods, 
                freq=business_day_offset
            )
            target_index = 0

        # 检测节假日
        holiday_dates = []
        for i in trading_series:
            day_str = i.strftime("%Y-%m-%d")
            if day_str not in holiday_series and judge_holiday(day_str):
                holiday_series.append(day_str)
                holiday_dates.append(day_str)

        holiday_count = len(holiday_dates)
        
        # 终止条件判断
        if not holiday_count:
            trading_day = trading_series[target_index]
            return trading_day.strftime("%Y-%m-%d")

        # 动态调整gap
        gap += holiday_count
        max_retry -= 1

    raise ValueError("Exceed maximum retry attempts")


def judge_holiday(date_str: str) -> bool:
    """
    判断指定日期是否为节假日
    :param date_str: 日期字符串 "YYYY-MM-DD"
    :return: 是否为节假日
    """
    from chinese_calendar import is_holiday, get_holiday_detail
    from datetime import date, datetime
    
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    if is_holiday(target_date):
        holiday_name, is_off_day = get_holiday_detail(target_date)
        print(f"{target_date} 是节假日：{holiday_name}（{'休息日' if is_off_day else '调休工作日'}）")
        return True
    return False


if __name__ == "__main__":
    # 创建分析器实例
    analyzer = StockAnalyzer(
        stock_code="000001.SS",
        start_time="2025-01-01",
        # proxy="http://127.0.0.1:10809"  # 如需代理请取消注释
    )
    
    # 执行分析流程
    if analyzer.download_data():
        analyzer.calculate_returns()
        analyzer.print_summary()
        analyzer.plot_analysis(output_path="../doc/plot.png")