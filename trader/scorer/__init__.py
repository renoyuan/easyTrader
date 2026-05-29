r"""
#!/usr/bin/env python
PROJECT_NAME: F:\opensource\easyTrader\trader\scorer
CREATE_TIME: 2026-05-11 
E_MAIL: renoyuan@foxmail.com
AUTHOR: reno 
note:  股票评分
"""

"""
scorer
======
投资策略评分模块，包含巴菲特、格雷厄姆等多种评分体系。
"""

from .buffett import *
from .graham import *
from .xuxiang import *
from .renoyuan import RenoyuanScorer
from .xubin import XuBinScorer
from .market_scanner import MarketScanner, get_stock_list_by_market, get_stock_names_by_codes, format_top_results, MARKET_MAP, SCORER_MAP

__all__ = ["buffett", "graham", "xuxiang", "RenoyuanScorer", "XuBinScorer",
           "MarketScanner", "get_stock_list_by_market", "get_stock_names_by_codes",
           "format_top_results", "MARKET_MAP", "SCORER_MAP"]
