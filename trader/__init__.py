# -*- coding: utf-8 -*-
# PROJECT_NAME:  __init__.py.py
# CREATE_TIME: 2025/5/21 10:58
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# NOTE:

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
trader
=====
主交易与分析模块，包含数据获取、处理、评分等子模块。

子模块：
- data       股票数据获取与管理
- processor  财务等数据处理
- scorer     投资策略评分

常用接口可直接从本模块导入。
"""

from . import data, processor, scorer

__all__ = ["data", "processor", "scorer"]
