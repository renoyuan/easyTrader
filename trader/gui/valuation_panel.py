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
支持：股票基本信息卡片、估值方法选择与说明、AI评估
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from threading import Thread
from typing import Optional
from trader.valuation.engine import ValuationEngine, quick_valuate, METHOD_DESCRIPTIONS
from trader.ai.client import DeepSeekClient


COLOR_BG = "#f0f2f5"
COLOR_CARD_BG = "#ffffff"
COLOR_TEXT = "#202124"
COLOR_TEXT_SECONDARY = "#5f6368"
COLOR_PRIMARY = "#1a73e8"
COLOR_SUCCESS = "#34a853"
COLOR_WARNING = "#fbbc04"
COLOR_DANGER = "#ea4335"
COLOR_ACCENT = "#e8f0fe"  # 浅蓝背景
FONT_NORMAL = ("微软雅黑", 10)
FONT_MONO = ("Consolas", 10)
FONT_TITLE = ("微软雅黑", 12, "bold")
FONT_SMALL = ("微软雅黑", 9)


class ValuationPanel:
    """
    估值面板
    在独立标签页中显示，包含：
    - 股票基本信息卡片（名称、行业、当前价、PE、PB、市值）
    - 估值方法选择（复选框 + 说明提示）
    - 运行按钮 + AI评估按钮
    - 结果展示区（表格 + 详情 + 综合评估 + AI点评）
    """

    def __init__(self, notebook: ttk.Notebook,
                 status_callback=None,
                 info_callback=None):
        self.notebook = notebook
        self._status_cb = status_callback
        self._info_cb = info_callback
        self.symbol: Optional[str] = None
        self._engine = ValuationEngine()
        self._ai_client = DeepSeekClient()
        self._last_result = None  # 保存最近一次估值结果
        self._last_methods = None  # 保存最近使用的方法列表

        # 构建页面
        self.frame = tk.Frame(notebook, bg=COLOR_CARD_BG)
        notebook.add(self.frame, text="📈 估值分析")

        self._build_widgets()

    # ════════════════════════════════════
    # 界面构建
    # ════════════════════════════════════

    def _build_widgets(self):
        # ── 顶部操作栏 ──
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

        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(
            row1, textvariable=self.status_var,
            bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
            font=("微软雅黑", 9)
        ).pack(side=tk.RIGHT)

        # ── 股票基本信息卡片 ──
        self.info_card = tk.Frame(
            self.frame, bg=COLOR_ACCENT,
            highlightbackground="#dadce0", highlightthickness=1,
            padx=10, pady=6
        )
        self.info_card.pack(fill=tk.X, padx=10, pady=4, ipady=2)

        self.info_labels = {}
        fields = [
            ("名称", "name"), ("行业", "industry"),
            ("当前价", "current_price"), ("PE", "pe"),
            ("PB", "pb"), ("市值(亿)", "market_cap"),
        ]
        for label_text, key in fields:
            f = tk.Frame(self.info_card, bg=COLOR_ACCENT)
            f.pack(side=tk.LEFT, padx=(12, 4))
            tk.Label(f, text=f"{label_text}：", bg=COLOR_ACCENT, fg=COLOR_TEXT_SECONDARY,
                     font=FONT_SMALL).pack(side=tk.LEFT)
            var = tk.StringVar(value="-")
            self.info_labels[key] = var
            tk.Label(f, textvariable=var, bg=COLOR_ACCENT, fg=COLOR_TEXT,
                     font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT)

        # ── 第2行：估值方法选择 ──
        row2 = tk.Frame(top_bar, bg=COLOR_CARD_BG)
        row2.pack(fill=tk.X, pady=2)

        tk.Label(
            row2, text="估值方法：",
            bg=COLOR_CARD_BG, fg=COLOR_TEXT,
            font=FONT_NORMAL
        ).pack(side=tk.LEFT)

        self.method_vars = {}
        self.method_btns = {}
        for m in ["PE", "PB", "PS", "PEG"]:
            var = tk.BooleanVar(value=True)
            self.method_vars[m] = var
            cb = tk.Checkbutton(
                row2, text=m, variable=var,
                bg=COLOR_CARD_BG, fg=COLOR_TEXT,
                font=("微软雅黑", 9),
                selectcolor=COLOR_CARD_BG,
            )
            cb.pack(side=tk.LEFT, padx=1)
            self.method_btns[m] = cb

        # 方法说明按钮
        self._desc_btn = tk.Button(
            row2, text="❓ 方法说明",
            command=self._show_method_descriptions,
            bg=COLOR_PRIMARY, fg="white",
            font=("微软雅黑", 9),
            relief=tk.FLAT, cursor="hand2",
            padx=6, pady=0,
        )
        self._desc_btn.pack(side=tk.LEFT, padx=(8, 0))

        # 开始估值按钮
        tk.Button(
            row2, text="🚀 开始估值",
            command=self.run_valuation,
            bg=COLOR_SUCCESS, fg="white",
            font=("微软雅黑", 10, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=14, pady=2,
        ).pack(side=tk.LEFT, padx=(10, 0))

        # ── 第2.1行：AI评估按钮（估值完成后才启用） ──
        row_ai = tk.Frame(self.frame, bg=COLOR_CARD_BG)
        row_ai.pack(fill=tk.X, padx=10, pady=2)

        self.ai_btn = tk.Button(
            row_ai, text="🤖 AI 评估结果",
            command=self._run_ai_analysis,
            bg="#9c27b0", fg="white",
            font=("微软雅黑", 9, "bold"),
            relief=tk.FLAT, cursor="hand2",
            padx=10, pady=2,
            state=tk.DISABLED,
        )
        self.ai_btn.pack(side=tk.LEFT)

        self.ai_status_var = tk.StringVar(value="")
        tk.Label(
            row_ai, textvariable=self.ai_status_var,
            bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
            font=FONT_SMALL
        ).pack(side=tk.LEFT, padx=(8, 0))

        # ── 分隔线 ──
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=10, pady=4
        )

        # ── 内容区域（表格 + 详情）整体放入一个可滚动的 Canvas ──
        self._content_canvas = tk.Canvas(self.frame, bg=COLOR_CARD_BG, highlightthickness=0)
        self._content_scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self._content_canvas.yview)
        self._content_canvas.configure(yscrollcommand=self._content_scrollbar.set)

        # 内容容器（放在 canvas 中）
        self._content_inner = tk.Frame(self._content_canvas, bg=COLOR_CARD_BG)
        self._content_window = self._content_canvas.create_window((0, 0), window=self._content_inner, anchor=tk.NW)

        self._content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定内容大小变化 → 更新 canvas 滚动区域
        def _on_content_configure(event):
            self._content_canvas.configure(scrollregion=self._content_canvas.bbox("all"))
        self._content_inner.bind("<Configure>", _on_content_configure)

        # 鼠标滚轮：仅当鼠标在 canvas 区域内时滚动
        def _on_mousewheel(event):
            self._content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._content_canvas.bind("<Enter>", lambda e: self._content_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self._content_canvas.bind("<Leave>", lambda e: self._content_canvas.unbind_all("<MouseWheel>"))

        # ─────────────────────────
        # 以下内容全部放入 _content_inner
        # ─────────────────────────

        inner = self._content_inner

        # ── 结果展示区（左右分栏） ──
        result_frame = tk.Frame(inner, bg=COLOR_CARD_BG)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # 左侧：数值结果表格
        left_frame = tk.Frame(result_frame, bg=COLOR_CARD_BG)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 添加方法说明提示区域
        self.method_desc_var = tk.StringVar(value="💡 勾选上方方法后点击「开始估值」")
        tk.Label(
            left_frame, textvariable=self.method_desc_var,
            bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
            font=FONT_SMALL
        ).pack(anchor=tk.W, pady=(0, 2))

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

        # 右侧：详细参数展示（带独立滚动条）
        right_frame = tk.Frame(result_frame, bg=COLOR_CARD_BG, width=280)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(8, 0))
        right_frame.pack_propagate(False)

        tk.Label(
            right_frame, text="估值参数",
            bg=COLOR_CARD_BG, fg=COLOR_TEXT,
            font=FONT_TITLE
        ).pack(anchor=tk.W, pady=(0, 4))

        # 右侧详情：Text + 滚动条
        detail_container = tk.Frame(right_frame, bg=COLOR_CARD_BG)
        detail_container.pack(fill=tk.BOTH, expand=True)

        detail_vsb = tk.Scrollbar(detail_container, orient=tk.VERTICAL)
        self.detail_text = tk.Text(
            detail_container, font=FONT_MONO,
            bg="#fafafa", fg=COLOR_TEXT,
            wrap=tk.WORD, relief=tk.FLAT,
            padx=8, pady=8,
            highlightthickness=1,
            highlightcolor="#dadce0",
            yscrollcommand=detail_vsb.set,
        )
        detail_vsb.configure(command=self.detail_text.yview)
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── AI点评展示区（带独立滚动条，初始隐藏） ──
        self.ai_frame = tk.Frame(inner, bg="#f3e5f5")
        # AI区域内部：label + Text(带滚动条)
        ai_header = tk.Frame(self.ai_frame, bg="#f3e5f5")
        ai_header.pack(fill=tk.X, padx=10, pady=(6, 0))
        tk.Label(
            ai_header, text="🤖 AI 点评",
            bg="#f3e5f5", fg="#4a148c",
            font=("微软雅黑", 10, "bold")
        ).pack(side=tk.LEFT)

        ai_body = tk.Frame(self.ai_frame, bg="#f3e5f5")
        ai_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 6))

        ai_vsb = tk.Scrollbar(ai_body, orient=tk.VERTICAL)
        self.ai_text = tk.Text(
            ai_body, font=("微软雅黑", 10),
            bg="#f3e5f5", fg=COLOR_TEXT,
            wrap=tk.WORD, relief=tk.FLAT,
            padx=6, pady=4,
            highlightthickness=0,
            height=8,
            yscrollcommand=ai_vsb.set,
        )
        ai_vsb.configure(command=self.ai_text.yview)
        self.ai_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ai_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── 综合评估区 ──
        summary_frame = tk.Frame(inner, bg=COLOR_CARD_BG)
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._summary_card = summary_frame

        ttk.Separator(summary_frame, orient=tk.HORIZONTAL).pack(fill=tk.X)

        self.summary_var = tk.StringVar(value="等待估值...")
        tk.Label(
            summary_frame, textvariable=self.summary_var,
            bg=COLOR_CARD_BG, fg=COLOR_TEXT,
            font=("微软雅黑", 11, "bold"),
            wraplength=700,
        ).pack(pady=(6, 4), anchor=tk.W)

        # ── 底部占位（留白） ──
        tk.Frame(inner, bg=COLOR_CARD_BG, height=20).pack(fill=tk.X)

    # ════════════════════════════════════
    # 方法说明弹窗
    # ════════════════════════════════════

    def _show_method_descriptions(self):
        """弹窗展示四种估值方法说明"""
        win = tk.Toplevel(self.frame)
        win.title("估值方法说明")
        win.geometry("560x440")
        win.configure(bg=COLOR_CARD_BG)
        win.transient(self.frame)
        win.grab_set()

        text = tk.Text(win, font=FONT_NORMAL, bg=COLOR_CARD_BG, fg=COLOR_TEXT,
                       wrap=tk.WORD, padx=12, pady=8,
                       highlightthickness=0, relief=tk.FLAT)
        text.pack(fill=tk.BOTH, expand=True)

        for k, desc in METHOD_DESCRIPTIONS.items():
            text.insert(tk.END, f"● {desc['name']}\n\n", "title")
            text.insert(tk.END, f"  原理：{desc['desc']}\n\n")
            text.insert(tk.END, f"  公式：{desc['formula']}\n\n")
            text.insert(tk.END, f"  适用：{desc['suitable']}\n\n")
            text.insert(tk.END, "─" * 50 + "\n\n")

        text.tag_config("title", font=("微软雅黑", 11, "bold"), foreground=COLOR_PRIMARY)
        text.configure(state=tk.DISABLED)

        tk.Button(win, text="关闭", command=win.destroy,
                  bg=COLOR_PRIMARY, fg="white", font=FONT_NORMAL,
                  relief=tk.FLAT, padx=20, pady=2).pack(pady=8)

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
                self._update_stock_info(code)
                self._set_status(f"已选择 {code}")
            else:
                messagebox.showerror("输入错误", "请输入 6 位数字股票代码！")

    def _update_stock_info(self, code: str):
        """异步更新股票基本信息卡片"""
        Thread(target=self._do_update_info, args=(code,), daemon=True).start()

    def _do_update_info(self, code: str):
        try:
            info = self._engine.get_stock_info(code)
            self.frame.after(0, lambda: self._display_stock_info(info))
        except Exception as e:
            pass

    def _display_stock_info(self, info: dict):
        """显示股票基本信息到卡片"""
        self.info_labels["name"].set(info.get("name", "-") or "-")
        self.info_labels["industry"].set(info.get("industry", "-") or "-")
        price = info.get("current_price")
        self.info_labels["current_price"].set(f"{price:.2f}" if price else "-")
        pe = info.get("pe")
        self.info_labels["pe"].set(f"{pe:.2f}" if pe else "-")
        pb = info.get("pb")
        self.info_labels["pb"].set(f"{pb:.2f}" if pb else "-")
        mc = info.get("market_cap")
        self.info_labels["market_cap"].set(f"{mc/1e8:.2f}" if mc else "-")

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

        # 更新股票信息和方法提示
        self._update_stock_info(code)

        desc_text = " | ".join([
            f"{m}: {METHOD_DESCRIPTIONS[m]['desc'][:20]}..."
            for m in methods
        ])
        self.method_desc_var.set(f"📌 已选：{'、'.join(methods)} | {desc_text}")

        self.ai_btn.configure(state=tk.DISABLED)
        self.ai_status_var.set("")
        self.ai_text.delete(1.0, tk.END)
        self.ai_frame.pack_forget()
        # 重置滚动到顶部
        self._content_canvas.yview_moveto(0.0)

        self._set_status("估值计算中...")
        Thread(target=self._do_valuation, args=(code, methods), daemon=True).start()

    def _do_valuation(self, code: str, methods: list):
        try:
            result = self._engine.valuate_stock(code, methods)
            self._last_result = result
            self._last_methods = methods

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
        first_params = None
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
            if first_params is None:
                params = r.get("params_json", "")
                if params:
                    first_params = (method, params)

        if first_params:
            method_name, params = first_params
            self.detail_text.insert(tk.END, f"📊 {method_name} 估值参数\n")
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

        # 启用AI评估按钮
        self.ai_btn.configure(state=tk.NORMAL)
        self.ai_status_var.set("点击「AI 评估结果」获取AI分析")

    def _run_ai_analysis(self):
        """调用DeepSeek AI对估值结果进行点评"""
        if not self._ai_client.is_ready:
            messagebox.showwarning(
                "AI未配置",
                "请先在设置页面配置 DeepSeek API Key"
            )
            return

        if not self._last_result or not self._last_methods or not self.symbol:
            return

        self.ai_btn.configure(state=tk.DISABLED, text="🤖 AI分析中...")
        self.ai_status_var.set("正在调用DeepSeek AI...")
        Thread(target=self._do_ai_analysis, daemon=True).start()

    def _do_ai_analysis(self):
        try:
            code = self.symbol
            methods = self._last_methods
            result = self._last_result

            # 格式化数据用于AI
            ai_input = self._engine.format_for_ai(code, methods, result)

            # 构建AI提示词
            system_intro = """本估值系统基于相对估值法，通过行业对比判断个股是否被高估/低估：
- PE法：行业合理市盈率 × EPS
- PB法：行业合理市净率 × BVPS
- PS法：行业合理市销率 × 每股营收
- PEG法：盈利增长调整PE
- 综合评估取各方法平均值"""

            analysis = self._ai_client.analyze_scorer_result(
                "相对估值法",
                system_intro,
                ai_input
            )

            self.frame.after(0, self._display_ai_analysis, analysis)

        except Exception as e:
            self.frame.after(0, self._ai_btn_reset)
            self.frame.after(0, self._info, f"AI分析异常: {e}")

    def _display_ai_analysis(self, analysis: str):
        """显示AI点评结果"""
        # 将ai_frame插入到summary_frame之前
        self.ai_frame.pack(fill=tk.X, padx=10, pady=(4, 4), before=self._summary_card)
        self.ai_text.delete(1.0, tk.END)
        self.ai_text.insert(tk.END, analysis)
        self.ai_btn.configure(state=tk.NORMAL, text="🤖 AI 评估结果")
        self.ai_status_var.set("✅ AI分析完成")

        # 滚动到 AI 区域
        self._content_canvas.update_idletasks()
        bbox = self._content_canvas.bbox(self._content_window)
        if bbox:
            self._content_canvas.yview_moveto(1.0)

    def _ai_btn_reset(self):
        self.ai_btn.configure(state=tk.NORMAL, text="🤖 AI 评估结果")
        self.ai_status_var.set("⚠️ 分析失败")

    def _set_status(self, msg: str, is_ok: bool = True):
        icon = "✅" if is_ok else "⚠️"
        self.status_var.set(f"{icon} {msg}")
        if self._status_cb:
            self._status_cb(msg, is_ok)

    def _info(self, msg: str):
        if self._info_cb:
            self._info_cb(msg)
