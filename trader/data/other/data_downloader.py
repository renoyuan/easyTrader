#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME:  data_loader.py
# CREATE_TIME: 2025/5/23
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# NOTE: 统一数据加载模块，支持从doc目录加载JSON财务数据

import json
import os
import pandas as pd
from typing import Dict, Optional, Union


class DataLoader:
    """
    统一数据加载器，支持从doc目录加载财务数据JSON文件
    """

    def __init__(self, data_dir: str = None):
        """
        初始化数据加载器
        :param data_dir: 数据目录路径，默认使用项目根目录下的doc文件夹
        """
        if data_dir is None:
            # 默认使用项目根目录下的doc文件夹
            self.data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'doc'
            )
        else:
            self.data_dir = data_dir

        # 确保数据目录存在
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # 数据文件映射
        self.data_files = {
            'performance': 'performance_data.json',
            'balance': 'balance_data.json',
            'cashflow': 'cashflow_data.json',
            'income': 'income_data.json'
        }

    def _get_file_path(self, data_type: str) -> str:
        """
        获取数据文件路径
        :param data_type: 数据类型，可选值: performance, balance, cashflow, income
        :return: 文件路径
        """
        if data_type not in self.data_files:
            raise ValueError(f"不支持的数据类型: {data_type}")
        return os.path.join(self.data_dir, self.data_files[data_type])

    def load_json_data(self, data_type: str) -> Dict:
        """
        加载JSON数据文件
        :param data_type: 数据类型
        :return: JSON数据字典
        """
        file_path = self._get_file_path(data_type)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"数据文件不存在: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_dataframe(self, data_type: str) -> pd.DataFrame:
        """
        加载数据并转换为DataFrame
        :param data_type: 数据类型
        :return: DataFrame
        """
        data = self.load_json_data(data_type)
        # 如果是列表，直接转换；如果是字典，先转为列表
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            return pd.DataFrame([data])
        else:
            raise TypeError(f"不支持的数据格式: {type(data)}")

    def load_all_financial_data(self) -> Dict[str, pd.DataFrame]:
        """
        加载所有财务数据
        :return: 包含所有数据类型的字典
        """
        result = {}
        for data_type in self.data_files.keys():
            try:
                result[data_type] = self.load_dataframe(data_type)
            except FileNotFoundError:
                print(f"警告: 未找到 {data_type} 数据文件")
                result[data_type] = pd.DataFrame()
        return result

    def save_json_data(self, data_type: str, data: Union[Dict, list]):
        """
        保存数据到JSON文件
        :param data_type: 数据类型
        :param data: 要保存的数据
        """
        file_path = self._get_file_path(data_type)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"数据已保存到: {file_path}")

    def get_stock_data(self, stock_code: str) -> Dict[str, Optional[pd.DataFrame]]:
        """
        获取指定股票的所有财务数据
        :param stock_code: 股票代码
        :return: 包含各类型数据的字典
        """
        all_data = self.load_all_financial_data()
        result = {}

        for data_type, df in all_data.items():
            if not df.empty and '股票代码' in df.columns:
                result[data_type] = df[df['股票代码'] == stock_code]
            else:
                result[data_type] = None

        return result


if __name__ == "__main__":
    # 示例用法
    loader = DataLoader()

    # 1. 加载所有财务数据
    print("=== 加载所有财务数据 ===")
    all_data = loader.load_all_financial_data()
    for data_type, df in all_data.items():
        print(f"\n{data_type} 数据:")
        if not df.empty:
            print(df.head())
        else:
            print("  无数据")

    # 2. 获取指定股票数据
    print("\n=== 获取指定股票数据 ===")
    stock_data = loader.get_stock_data("600624")
    for data_type, df in stock_data.items():
        if df is not None and not df.empty:
            print(f"\n{data_type}:")
            print(df)