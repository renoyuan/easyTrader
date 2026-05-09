
# GUI界面模块

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import pandas as pd
from .ai_model import StockAIModel
from .data_downloader import download_stock_to_sqlite, load_stock_from_sqlite

class EasyTraserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("easyTraser 股票分析")
        self.model = StockAIModel()
        self.df = None
        self.symbol = None
        self._build_widgets()

    def _build_widgets(self):
        btn_download = tk.Button(self.root, text="下载股票数据到SQLite", command=self.download_data)
        btn_download.pack(pady=5)
        btn_load = tk.Button(self.root, text="从SQLite加载数据", command=self.load_data_sqlite)
        btn_load.pack(pady=5)
        btn_ai = tk.Button(self.root, text="AI分析", command=self.run_ai)
        btn_ai.pack(pady=5)
        self.text = tk.Text(self.root, height=12, width=70)
        self.text.pack(pady=5)

    def download_data(self):
        def show_messagebox_and_print(level, title, msg):
            print(f"[{level}] {title}: {msg}")
            if level == 'info':
                messagebox.showinfo(title, msg)
            elif level == 'error':
                messagebox.showerror(title, msg)

        import datetime
        symbol = simpledialog.askstring("输入股票代码", "如: 600519 或 000001 或 AAPL")
        if not symbol:
            show_messagebox_and_print("error", "输入错误", "请填写股票代码")
            return
        # 自动补全后缀
        if symbol.isdigit() and len(symbol) == 6:
            if symbol.startswith('6'):
                symbol_full = symbol + '.SS'
            else:
                symbol_full = symbol + '.SZ'
        else:
            symbol_full = symbol
        # 日期输入，默认一年
        today = datetime.date.today()
        one_year_ago = today.replace(year=today.year-1)
        date_range = simpledialog.askstring(
            "选择日期区间",
            f"格式: YYYY-MM-DD,YYYY-MM-DD\n默认: {one_year_ago},{today}",
        )
        if date_range and ',' in date_range:
            start, end = [d.strip() for d in date_range.split(',', 1)]
        else:
            start, end = str(one_year_ago), str(today)
        try:
            table_name=download_stock_to_sqlite(symbol_full, start, end)
            # 检查数据是否真的下载成功
            from trader.data_downloader import load_stock_from_sqlite
            df_check = load_stock_from_sqlite(table_name=table_name)
            if df_check is not None and not df_check.empty:
                msg = f"{table_name} {start}~{end} 数据下载并保存到本地数据库成功！"
                self.text.insert(tk.END, msg + "\n")
                print(msg)
            else:
                show_messagebox_and_print("error", "下载失败", f"{symbol_full} 没有获取到有效数据，请检查代码或网络。")
        except Exception as e:
            show_messagebox_and_print("error", "下载失败", str(e))

    def load_data_sqlite(self):
        def show_messagebox_and_print(level, title, msg):
            print(f"[{level}] {title}: {msg}")
            if level == 'info':
                messagebox.showinfo(title, msg)
            elif level == 'error':
                messagebox.showerror(title, msg)
        symbol = simpledialog.askstring("输入股票代码", "如: 600519.SS 或 AAPL")
        if not symbol:
            show_messagebox_and_print("error", "输入错误", "请填写股票代码")
            return
        try:
            self.df = load_stock_from_sqlite(symbol)
            self.symbol = symbol
            msg = f"{symbol} 数据加载成功，{len(self.df)} 条记录"
            self.text.insert(tk.END, msg + "\n")
            print(msg)
        except Exception as e:
            show_messagebox_and_print("error", "加载失败", str(e))

    def run_ai(self):
        def show_messagebox_and_print(level, title, msg):
            print(f"[{level}] {title}: {msg}")
            if level == 'info':
                messagebox.showinfo(title, msg)
            elif level == 'error':
                messagebox.showerror(title, msg)
        if self.df is None:
            show_messagebox_and_print("error", "错误", "请先加载数据")
            return
        try:
            # 兼容yfinance下载的字段名
            feature_cols = [col for col in ["Open", "High", "Low"] if col in self.df.columns]
            target_col = "Close" if "Close" in self.df.columns else None
            if not (feature_cols and target_col):
                raise ValueError("数据缺少必要字段：Open, High, Low, Close")
            self.model.train(self.df, feature_cols, target_col)
            preds = self.model.predict(self.df, feature_cols)
            msg = f"AI预测结果（前5条）：{preds[:5]}"
            self.text.insert(tk.END, msg + "\n")
            print(msg)
        except Exception as e:
            show_messagebox_and_print("error", "分析失败", str(e))

def main():
    root = tk.Tk()
    app = EasyTraserGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
