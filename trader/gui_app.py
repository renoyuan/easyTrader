# -*- coding: utf-8 -*-

import sys
import os
# 强制全局中文不乱码
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.environ["PYTHONIOENCODING"] = "utf-8"
"""
easyTrader 启动入口
====================
保持与原有 gui_app.py 相同的调用方式（from trader.gui_app import main），
实际界面逻辑拆入 trader/gui/ 模块。
"""
# 确保项目根目录在 sys.path 中
_app_root = os.path.dirname(os.path.dirname(__file__))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

import tkinter as tk
from tkinter import messagebox
from trader.gui import EasyTraderGUI


def main() -> None:
    # 🔍 调试：打印实际数据库路径
    import sys, os
    print(f"[DEBUG] sys.frozen = {getattr(sys, 'frozen', False)}")
    print(f"[DEBUG] sys.executable = {getattr(sys, 'executable', 'N/A')}")
    print(f"[DEBUG] sys.argv = {sys.argv}")
    try:
        from trader.db.orm import DB_URL, init_db
        print(f"[DEBUG] DB_URL = {DB_URL}")
        # 显示 SQLite 路径
        if "sqlite" in DB_URL:
            import re
            m = re.search(r'sqlite:///(.+)', DB_URL)
            if m:
                db_file = m.group(1)
                print(f"[DEBUG] DB_FILE = {db_file}")
                print(f"[DEBUG] DB exists = {os.path.exists(db_file)}")
                if os.path.exists(db_file):
                    print(f"[DEBUG] DB size = {os.path.getsize(db_file) / 1024 / 1024:.1f} MB")
        # 检查表中数据
        from trader.db.orm import SessionLocal, Income
        with SessionLocal() as sess:
            cnt = sess.query(Income).count()
            print(f"[DEBUG] income 表记录数 = {cnt}")
    except Exception as e:
        print(f"[DEBUG] DB init error: {e}")
        import traceback
        traceback.print_exc()

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