"""
easyTrader GUI 模块
===================
按功能拆分为多个子模块：
  - main_window.py    主窗口框架
  - scorer_panel.py   评分面板（巴菲特/格雷厄姆/徐翔）
  - settings_panel.py 设置面板（Tushare Token 等）
"""
from .main_window import EasyTraderGUI

__all__ = ["EasyTraderGUI"]
