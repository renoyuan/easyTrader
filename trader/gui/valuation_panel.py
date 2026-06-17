#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME: easyTrader
# CREATE_TIME: 2026-05-25
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# note:  

"""
估值面板 —— 独立的估值模块 GUI
输入股票代码，运行多种估值方法，展示结果
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from threading import Thread
from typing import Optional
from trader.valuation.engine import ValuationEngine, quick_valuate


COLOR_BG = "#f0f2f5"
COLOR_CARD_BG = "#ffffff"
COLOR_TEXT = "#202124"
COLOR_TEXT_SECONDARY = "#5f6368"
COLOR_PRIMARY = "#1a73e8"
COLOR_SUCCESS = "#34a853"
COLOR_WARNING = "#fbbc04"
COLOR_DANGER = "#ea4335"
FONT_NORMAL = ("微软雅黑", 10)
FONT_MONO = ("Consolas", 10)
FONT_TITLE = ("微软雅黑", 12, "bold")


class ValuationPanel:
    """
    估值面板
    在独立标签页中显示，包含：
    - 股票代码输入
    - 估值方法选择（复选框）
    - 运行按钮
    - 结果展示区
    """

    def __init__(self, notebook: ttk.Notebook,
                 status_callback=None,
                 info_callback=None):
        self.notebook = notebook
        self._status_cb = status_callback
        self._info_cb = info_callback
        self.symbol: Optional[str] = None

        # 构建页面
        self.frame = tk.Frame(notebook, bg=COLOR_CARD_BG)
        notebook.add(self.frame, text="📈 估值分析")

        self._build_widgets()

    # ════════════════════════════════════
    # 界面构建
    # ════════════════════════════════════

    def _build_widgets(self):
        # ── 顶部操作栏（纵向排列，确保不缩放也能看到所有控件） ──
        top_bar = tk.Frame(self.frame, bg=COLOR_CARD_BG)
        top_bar.pack(fill=tk.X, padx=10, pady=(8, 2))

        # 第1行：股票代码输入
        row1 = tk.Frame(top_bar, bg=COLOR_CARD_BG)
        row1.pack(fill=tk.X, pady=2)

        tk.Label(
            row1, text="股票代码：",
            bg=COLOR_CARD_BG, fg=COLOR_TEXT,
            font=FONT_NORMAL
        ).pack(side=tk.LEFT)

        self.code_var = tk.StringVar()
        self.code_entry = tk.Entry(
            row1, textvariable=self.code_var,
            width=10, font=("Consolas", 12, "bold"),
            relief=tk.SOLID, bd=1
        )
        self.code_entry.pack(side=tk.LEFT, padx=(4, 8))
        self.code_entry.bind("<Return>", lambda e: self.run_valuation())

        tk.Button(
            row1, text="输入代码",
            command=self._input_code,
            bg=COLOR_PRIMARY, fg="white",
            font=("微软雅黑", 9, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=8, pady=1,
        ).pack(side=tk.LEFT)

        # 状态标签放在右侧
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(
            row1, textvariable=self.status_var,
            bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
            font=("微软雅黑", 9)
        ).pack(side=tk.RIGHT)

        # 第2行：估值方法选择 + 开始按钮
        row2 = tk.Frame(top_bar, bg=COLOR_CARD_BG)
        row2.pack(fill=tk.X, pady=2)

        tk.Label(
            row2, text="估值方法：",
            bg=COLOR_CARD_BG, fg=COLOR_TEXT,
            font=FONT_NORMAL
        ).pack(side=tk.LEFT)

        self.method_vars = {}
        for m in ["PE", "PB", "PS", "PEG"]:
            var = tk.BooleanVar(value=True)
            self.method_vars[m] = var
            tk.Checkbutton(
                row2, text=m,
                variable=var,
                bg=COLOR_CARD_BG, fg=COLOR_TEXT,
                font=("微软雅黑", 9),
                selectcolor=COLOR_CARD_BG,
            ).pack(side=tk.LEFT, padx=1)

        # 开始估值按钮
        tk.Button(
            row2, text="🚀 开始估值",
            command=self.run_valuation,
            bg=COLOR_SUCCESS, fg="white",
            font=("微软雅黑", 10, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=14, pady=2,
        ).pack(side=tk.LEFT, padx=(10, 0))

        # ── 分隔线 ──
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=10, pady=4
        )

        # ── 结果展示区（左右分栏） ──
        result_frame = tk.Frame(self.frame, bg=COLOR_CARD_BG)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # 左侧：数值结果表格
        left_frame = tk.Frame(result_frame, bg=COLOR_CARD_BG)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            left_frame,
            columns=("方法", "合理股价", "区间下限", "区间上限", "偏离度", "判断"),
            show="headings",
            height=8,
        )
        self.tree.heading("方法", text="方法")
        self.tree.heading("合理股价", text="合理股价")
        self.tree.heading("区间下限", text="区间下限")
        self.tree.heading("区间上限", text="区间上限")
        self.tree.heading("偏离度", text="偏离度%")
        self.tree.heading("判断", text="判断")

        self.tree.column("方法", width=60, anchor=tk.CENTER)
        self.tree.column("合理股价", width=100, anchor=tk.CENTER)
        self.tree.column("区间下限", width=100, anchor=tk.CENTER)
        self.tree.column("区间上限", width=100, anchor=tk.CENTER)
        self.tree.column("偏离度", width=90, anchor=tk.CENTER)
        self.tree.column("判断", width=80, anchor=tk.CENTER)

        vsb = tk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 右侧：详细参数展示
        right_frame = tk.Frame(result_frame, bg=COLOR_CARD_BG, width=280)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(8, 0))
        right_frame.pack_propagate(False)

        tk.Label(
            right_frame, text="估值参数",
            bg=COLOR_CARD_BG, fg=COLOR_TEXT,
            font=FONT_TITLE
        ).pack(anchor=tk.W, pady=(0, 4))

        self.detail_text = tk.Text(
            right_frame, font=FONT_MONO,
            bg="#fafafa", fg=COLOR_TEXT,
            wrap=tk.WORD, relief=tk.FLAT,
            padx=8, pady=8,
            highlightthickness=1,
            highlightcolor="#dadce0",
            height=12,
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True)

        # ── 综合评估区 ──
        summary_frame = tk.Frame(self.frame, bg=COLOR_CARD_BG)
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        ttk.Separator(summary_frame, orient=tk.HORIZONTAL).pack(fill=tk.X)

        self.summary_var = tk.StringVar(value="等待估值...")
        tk.Label(
            summary_frame, textvariable=self.summary_var,
            bg=COLOR_CARD_BG, fg=COLOR_TEXT,
            font=("微软雅黑", 11, "bold"),
            wraplength=700,
        ).pack(pady=(6, 4), anchor=tk.W)

    # ════════════════════════════════════
    # 逻辑
    # ════════════════════════════════════

    def _input_code(self):
        code = simpledialog.askstring(
            "股票代码",
            "请输入 6 位股票代码：\n例如：600519（贵州茅台）",
            parent=self.frame
        )
        if code:
            code = code.strip()
            if code.isdigit() and len(code) == 6:
                self.symbol = code
                self.code_var.set(code)
                self._set_status(f"已选择 {code}")
            else:
                messagebox.showerror("输入错误", "请输入 6 位数字股票代码！")

    def run_valuation(self):
        code = self.code_var.get().strip()
        if not code:
            code = self.symbol
        if not code or not (code.isdigit() and len(code) == 6):
            messagebox.showwarning("提示", "请先输入股票代码")
            return

        self.symbol = code
        methods = [m for m, v in self.method_vars.items() if v.get()]
        if not methods:
            messagebox.showwarning("提示", "请至少选择一个估值方法")
            return

        self._set_status("估值计算中...")
        Thread(target=self._do_valuation, args=(code, methods), daemon=True).start()

    def _do_valuation(self, code: str, methods: list):
        try:
            result = quick_valuate(code, methods)

            # 在主线程更新UI
            self.frame.after(0, self._display_result, code, result)
            self.frame.after(0, self._set_status, "估值完成")
        except Exception as e:
            self.frame.after(0, self._set_status, f"估值失败: {str(e)[:40]}")
            self.frame.after(0, self._info, f"估值异常: {e}")

    def _display_result(self, code: str, result: dict):
        """展示估值结果"""
        # 清空旧数据
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.detail_text.delete(1.0, tk.END)

        summary = result.pop("_summary", None)

        # 各方法结果填入表格
        for method in ["PE", "PB", "PS", "PEG"]:
            r = result.get(method)
            if not r:
                continue
            if "error" in r:
                self.tree.insert("", tk.END, values=(
                    method, "数据不足", "-", "-", "-", "跳过"
                ))
                continue

            dev = r.get("deviation")
            dev_str = f"{dev:+.2f}" if dev is not None else "-"
            if dev is not None:
                if dev < -20:
                    tag = "低估"
                elif dev < -5:
                    tag = "偏低"
                elif dev > 20:
                    tag = "高估"
                elif dev > 5:
                    tag = "偏高"
                else:
                    tag = "合理"
            else:
                tag = "-"

            self.tree.insert("", tk.END, values=(
                method,
                r.get("fair_price", "-"),
                r.get("price_range_low", "-"),
                r.get("price_range_high", "-"),
                dev_str,
                tag,
            ))

            # 详情展示（取第一个有参数的）
            if not self.detail_text.get(1.0, tk.END).strip():
                params = r.get("params_json", "")
                if params:
                    self.detail_text.insert(tk.END, f"📊 {method} 估值参数\n")
                    self.detail_text.insert(tk.END, f"{params}\n\n")

        # 综合评估
        if summary:
            verdict = summary.get("verdict", "-")
            avg_price = summary.get("avg_fair_price", "-")
            price_range = summary.get("price_range")
            avg_dev = summary.get("avg_deviation")

            text = f"💡 综合判断：{verdict}"
            text += f"  |  平均合理股价：{avg_price} 元"
            if price_range:
                text += f"  |  综合区间：({price_range[0]}, {price_range[1]})"
            if avg_dev is not None:
                text += f"  |  平均偏离度：{avg_dev:+.2f}%"
            self.summary_var.set(text)

    def _set_status(self, msg: str, is_ok: bool = True):
        icon = "✅" if is_ok else "⚠️"
        self.status_var.set(f"{icon} {msg}")
        if self._status_cb:
            self._status_cb(msg, is_ok)

    def _info(self, msg: str):
        if self._info_cb:
            self._info_cb(msg)
