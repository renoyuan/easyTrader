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

注意：为避免 GUI 启动时触发 akshare 等外部依赖的加载，
      子模块采用惰性加载方式，仅在首次访问时导入。
"""

import importlib

_lazy_modules = {}

def __getattr__(name):
    """惰性加载子模块"""
    if name in _lazy_modules:
        return _lazy_modules[name]
    if name in ('data', 'processor', 'scorer'):
        module = importlib.import_module(f'.{name}', __package__)
        _lazy_modules[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["data", "processor", "scorer"]

