# GUI界面模块 — 纯净版：仅保留 巴菲特评分系统
import tkinter as tk
from tkinter import messagebox, simpledialog
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 仅保留巴菲特评分
from trader.scorer.buffett import BuffettScorer


class EasyTraserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("easyTrader 巴菲特股票评分系统")
        self.root.geometry("750x600")

        # 巴菲特评分器
        self.buffett = BuffettScorer()
        self.symbol = None

        # 构建界面
        self._build_widgets()

    def _build_widgets(self):
        # 按钮区域
        frame = tk.Frame(self.root)
        frame.pack(pady=15)

        tk.Button(frame, text="📥 输入股票代码", command=self.input_code, width=20, height=2)\
            .grid(row=0, column=0, padx=10)

        tk.Button(frame, text="📊 执行巴菲特评分", command=self.run_buffett_score, width=20, height=2)\
            .grid(row=0, column=1, padx=10)

        # 结果展示
        tk.Label(self.root, text="评分结果", font=("微软雅黑", 12)).pack()
        self.text = tk.Text(self.root, font=("Consolas", 11), height=26, width=85)
        self.text.pack(pady=5, fill=tk.BOTH, expand=True)

        # 清空
        tk.Button(self.root, text="清空内容", command=lambda: self.text.delete(1.0, tk.END)).pack(pady=5)

    def input_code(self):
        code = simpledialog.askstring("股票代码", "请输入6位股票代码：\n例如：600699")
        if code and code.isdigit() and len(code) == 6:
            self.symbol = code
            messagebox.showinfo("成功", f"已选择股票：{code}")
        else:
            messagebox.showerror("错误", "请输入6位数字股票代码")

    def run_buffett_score(self):
        if not self.symbol:
            messagebox.showwarning("提示", "请先输入股票代码")
            return

        self.text.insert(tk.END, "\n=============================================\n")
        self.text.insert(tk.END, "           📊 巴菲特价值评分中...\n")
        self.text.insert(tk.END, "=============================================\n")
        self.root.update()

        try:
            res = self.buffett.score(self.symbol)
            if not res:
                self.text.insert(tk.END, "❌ 评分失败：无财报数据\n")
                return

            self.text.insert(tk.END, f"\n股票代码：{res['code']}\n")
            self.text.insert(tk.END, f"质地评分：{res['base']} / 80\n")
            self.text.insert(tk.END, f"估值评分：{res['val_score']} / 20\n")
            self.text.insert(tk.END, f"综合总分：{res['score']} / 100\n")
            self.text.insert(tk.END, f"趋势状态：{res['trend_label']}\n")
            self.text.insert(tk.END, f"估值状态：{res['val_label']}\n")
            self.text.insert(tk.END, f"投资评级：{res['rating']}\n")
            self.text.insert(tk.END, "-----------------------------------------\n")

            for k, v in res["indicators"].items():
                if pd.isna(v):
                    continue
                self.text.insert(tk.END, f"{k:<18} {v:.2%}\n")

            self.text.insert(tk.END, "=========================================\n\n")

        except Exception as e:
            self.text.insert(tk.END, f"❌ 评分异常：{str(e)}\n")
            messagebox.showerror("错误", str(e))


def main():
    root = tk.Tk()
    app = EasyTraserGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()