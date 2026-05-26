"""
easyTrader 启动入口
====================
保持与原有 gui_app.py 相同的调用方式（from trader.gui_app import main），
实际界面逻辑拆入 trader/gui/ 模块。
"""
import sys
import os

# 确保项目根目录在 sys.path 中
_app_root = os.path.dirname(os.path.dirname(__file__))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

import tkinter as tk
from tkinter import messagebox
from trader.gui import EasyTraderGUI


def main() -> None:
    root = tk.Tk()
    try:
        app = EasyTraderGUI(root)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ GUI 初始化异常: {e}\n")
        messagebox.showerror("启动异常", str(e))
        return
    root.mainloop()


if __name__ == "__main__":
    main()